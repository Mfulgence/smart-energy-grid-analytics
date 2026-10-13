"""Section 1.3 - MQTT subscriber: EMQX -> PostgreSQL (energy_live).

START THIS PROGRAM FIRST, in its own terminal, then start s13_publisher.py in
a second terminal. A subscriber that connects after the messages were published
would never see them (they are not retained).

Flow of one message
    broker --> on_message()  --> queue --> writer loop --> INSERT --> COMMIT
               (count it,                  (batches of
                parse JSON)                 up to 500 rows)

Why a queue?
    on_message() runs on the network thread. If it had to wait for the database
    on every message, the broker would have to buffer messages for us and could
    drop them when its per-client queue fills up. on_message() therefore only
    counts, parses and queues. The main thread does the slower database work.

Counts kept (they feed the four-count table in the report)
    received   every message delivered to this subscriber
    parsed     messages that were valid JSON with the eight expected fields
    inserted   rows committed in energy_live

Run:  python s13_subscriber.py            (waits for 2,000 messages)
      python s13_subscriber.py --expect 500 --keep
"""

from __future__ import annotations

import argparse
import json
import queue
import time

import paho.mqtt.client as mqtt

from common import RESULTS_DIR, cat_text, file_logger, connect, finish_log, load_env, start_log

STEP = "1_3_subscriber"
TOPIC_FILTER = "energy/meters/#"      # '#' matches every meter_id below this prefix
QOS = 1                               # at-least-once delivery
FIELDS = ("meter_id", "event_time", "received_time", "power_kw",
          "voltage_v", "current_a", "frequency_hz", "energy_kwh")

INSERT_SQL = """
INSERT INTO energy_live (meter_id, event_time, received_time, power_kw,
                         voltage_v, current_a, frequency_hz, energy_kwh)
VALUES (%(meter_id)s, %(event_time)s, %(received_time)s, %(power_kw)s,
        %(voltage_v)s, %(current_a)s, %(frequency_hz)s, %(energy_kwh)s)
"""

# A detailed log file helps explain any difference between the four counts.
log = file_logger("subscriber")

pending: queue.Queue = queue.Queue()   # parsed readings waiting for the database
counts = {"received": 0, "parsed": 0, "parse_errors": 0, "redelivered": 0,
          "retained": 0, "inserted": 0, "insert_errors": 0}
state = {"subscribed": False, "last_message": None}


def on_connect(client, userdata, flags, reason_code, properties):
    """Called when the broker accepts the connection: subscribe here so the
    subscription is also restored automatically after a reconnect."""
    if reason_code.is_failure:
        print(f"Connection refused: {reason_code}")
        log.error("connection refused: %s", reason_code)
        return
    print(f"Connected to broker. Subscribing to {TOPIC_FILTER} at QoS {QOS} ...")
    client.subscribe(TOPIC_FILTER, qos=QOS)


def on_subscribe(client, userdata, mid, reason_codes, properties):
    """The broker confirms the subscription and the QoS it granted."""
    state["subscribed"] = True
    print(f"Subscription confirmed (granted: {', '.join(str(code) for code in reason_codes)}).")
    print("Waiting for messages - now start the publisher in another terminal.")
    log.info("subscribed to %s: %s", TOPIC_FILTER, [str(code) for code in reason_codes])


def on_message(client, userdata, message):
    """Called once per delivered message. Keep it fast: count, parse, queue."""
    counts["received"] += 1
    state["last_message"] = time.time()
    if message.dup:            # the broker is re-sending a message it thinks we missed
        counts["redelivered"] += 1
        log.warning("redelivered message (DUP flag) on %s", message.topic)
    if message.retain:         # should never happen: the publisher sets retain=False
        counts["retained"] += 1
        log.warning("retained message on %s", message.topic)
    try:
        reading = json.loads(message.payload)
        missing = [name for name in FIELDS if name not in reading]
        if missing:
            raise ValueError(f"missing fields {missing}")
        # The topic carries the meter ID too. Check both agree.
        if message.topic.rsplit("/", 1)[-1] != str(reading["meter_id"]):
            raise ValueError("meter_id in topic and payload differ")
    except (ValueError, TypeError) as exc:
        counts["parse_errors"] += 1
        log.error("parse error on %s: %s payload=%r", message.topic, exc, message.payload[:200])
        return
    counts["parsed"] += 1
    pending.put({name: reading[name] for name in FIELDS})   # exactly the eight fields


def write_batch(conn, batch: list[dict]) -> None:
    """Insert a batch and commit. If the batch fails, retry row by row so one
    bad row cannot take the good ones down with it, and log each failure."""
    try:
        with conn.cursor() as cur:
            cur.executemany(INSERT_SQL, batch)
        conn.commit()
        counts["inserted"] += len(batch)
    except Exception as exc:                       # noqa: BLE001 - logged and retried
        conn.rollback()
        log.error("batch of %d failed (%s) - retrying row by row", len(batch), exc)
        for row in batch:
            try:
                conn.execute(INSERT_SQL, row)
                conn.commit()
                counts["inserted"] += 1
            except Exception as row_exc:           # noqa: BLE001
                conn.rollback()
                counts["insert_errors"] += 1
                log.error("insert failed: %s row=%s", row_exc, row)


def main() -> None:
    parser = argparse.ArgumentParser(description="Subscribe to meter readings and store them in energy_live.")
    parser.add_argument("--expect", type=int, default=2000, help="stop after this many messages (default 2000)")
    parser.add_argument("--idle", type=float, default=20.0,
                        help="also stop when no message arrived for this many seconds")
    parser.add_argument("--keep", action="store_true", help="do not empty energy_live first")
    args = parser.parse_args()

    start_log(STEP)
    env = load_env()

    # ---- Database: the pilot must begin with an empty energy_live table ------
    conn = connect(autocommit=False)
    if not args.keep:
        conn.execute("TRUNCATE energy_live")
        conn.commit()
        print("energy_live emptied (TRUNCATE) so the pilot starts from zero rows.")

    # ---- MQTT ---------------------------------------------------------------
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="energy-subscriber")
    if env["MQTT_USERNAME"]:
        client.username_pw_set(env["MQTT_USERNAME"], env["MQTT_PASSWORD"])
    client.on_connect, client.on_subscribe, client.on_message = on_connect, on_subscribe, on_message
    client.connect(env["MQTT_HOST"], int(env["MQTT_PORT"]), keepalive=60)
    client.loop_start()                           # network traffic on a background thread
    started = cat_text()

    # ---- Writer loop (main thread) -------------------------------------------
    last_print = 0
    try:
        while True:
            batch = []
            try:
                batch.append(pending.get(timeout=0.5))      # wait briefly for work
                while len(batch) < 500:                     # then take what is ready
                    batch.append(pending.get_nowait())
            except queue.Empty:
                pass
            if batch:
                write_batch(conn, batch)
            if counts["received"] - last_print >= 500:
                last_print = counts["received"]
                print(f"  received {counts['received']:,}   committed {counts['inserted']:,}")
            handled = counts["inserted"] + counts["insert_errors"] + counts["parse_errors"]
            if counts["received"] >= args.expect and handled >= counts["received"]:
                break                                       # target reached, all rows stored
            if state["last_message"] and time.time() - state["last_message"] > args.idle and pending.empty():
                print(f"No message for {args.idle:.0f} s - stopping.")
                break
    except KeyboardInterrupt:
        print("Interrupted - stopping.")

    client.loop_stop()
    client.disconnect()

    # ---- Summary --------------------------------------------------------------
    stored = conn.execute("SELECT count(*) FROM energy_live").fetchone()[0]
    conn.close()
    summary = {**counts, "rows_in_energy_live": stored, "started": started, "finished": cat_text()}
    (RESULTS_DIR / "1_3_subscriber_counts.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    log.info("summary: %s", summary)

    print()
    print(f"Messages received by subscriber : {counts['received']:,}")
    print(f"  parsed successfully           : {counts['parsed']:,}")
    print(f"  parse errors                  : {counts['parse_errors']:,}")
    print(f"  redelivered (DUP flag)        : {counts['redelivered']:,}")
    print(f"Rows inserted and committed     : {counts['inserted']:,}")
    print(f"  failed inserts                : {counts['insert_errors']:,}")
    print(f"Rows now in energy_live         : {stored:,}")
    finish_log(STEP)


if __name__ == "__main__":
    main()
