"""Section 1.3 - MQTT publisher: generator -> EMQX.

Start s13_subscriber.py FIRST, wait until it prints "Waiting for messages",
then run this program in a second terminal.

What it does
  1. Imports the unchanged generator and takes ONLY the first 2,000
     dictionaries from iter_readings() (itertools.islice stops the iterator
     early, so the other 10.7 million readings are never produced).
  2. Converts each dictionary to JSON text.
  3. Publishes one message per reading to energy/meters/<meter_id>
     with QoS 1 and retain=False.
  4. Counts how many messages the broker acknowledged (PUBACK).

QoS 1 in one sentence
    The broker must answer every PUBLISH with a PUBACK. Until that arrives the
    client keeps the message and re-sends it, so a message is delivered at
    least once. "Acknowledged by the broker" = number of PUBACKs received.

The pilot replays historical readings as fast as the pipeline allows. It does
not wait 15 minutes between records.

Run:  python s13_publisher.py             (2,000 readings)
      python s13_publisher.py --count 500
"""

from __future__ import annotations

import argparse
import itertools
import json
import time

import paho.mqtt.client as mqtt

import smart_meter_simulator as sim            # the supplied, unchanged generator

from common import RESULTS_DIR, cat_text, file_logger, finish_log, load_env, start_log

STEP = "1_3_publisher"
TOPIC_TEMPLATE = "energy/meters/{meter_id}"
QOS = 1

log = file_logger("publisher")

sent_ids: set[int] = set()        # message IDs handed to the client library
acked_ids: set[int] = set()       # message IDs the broker has acknowledged
connected = {"ok": False}


def on_connect(client, userdata, flags, reason_code, properties):
    connected["ok"] = not reason_code.is_failure
    log.info("connect result: %s", reason_code)


def on_publish(client, userdata, mid, reason_code, properties):
    """For QoS 1 this fires when the PUBACK for message `mid` arrives."""
    if reason_code.is_failure:
        log.error("broker rejected message id %s: %s", mid, reason_code)
        return
    acked_ids.add(mid)


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish the first N generator readings to EMQX.")
    parser.add_argument("--count", type=int, default=2000, help="readings to publish (default 2000)")
    args = parser.parse_args()

    start_log(STEP)
    env = load_env()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="energy-publisher")
    if env["MQTT_USERNAME"]:
        client.username_pw_set(env["MQTT_USERNAME"], env["MQTT_PASSWORD"])
    client.on_connect, client.on_publish = on_connect, on_publish
    # At most 20 messages may be waiting for their PUBACK at any moment. This
    # paces the publisher to the speed of the broker instead of flooding it.
    client.max_inflight_messages_set(20)
    client.connect(env["MQTT_HOST"], int(env["MQTT_PORT"]), keepalive=60)
    client.loop_start()
    while not connected["ok"]:                    # wait for the CONNACK
        time.sleep(0.05)
    print(f"Connected to broker at {env['MQTT_HOST']}:{env['MQTT_PORT']}")

    started_text, started = cat_text(), time.perf_counter()
    taken = 0
    # islice() pulls exactly --count dictionaries from the generator and stops.
    for reading in itertools.islice(sim.iter_readings(), args.count):
        taken += 1                                # count dictionaries taken from the generator
        topic = TOPIC_TEMPLATE.format(meter_id=reading["meter_id"])
        payload = json.dumps(reading)             # dictionary -> JSON text
        info = client.publish(topic, payload, qos=QOS, retain=False)
        sent_ids.add(info.mid)
        # Back-pressure: never let more than 200 messages wait for their PUBACK.
        # Without this the loop could outrun the network and the broker.
        while len(sent_ids) - len(acked_ids) > 200:
            time.sleep(0.001)
        if taken % 500 == 0:
            print(f"  taken {taken:,}   acknowledged {len(acked_ids):,}")

    # Wait (up to 30 s) until every message has been acknowledged.
    deadline = time.time() + 30
    while len(acked_ids) < len(sent_ids) and time.time() < deadline:
        time.sleep(0.05)
    elapsed = time.perf_counter() - started
    client.loop_stop()
    client.disconnect()

    unacked = sorted(sent_ids - acked_ids)
    if unacked:
        log.error("%d messages were never acknowledged: ids %s", len(unacked), unacked[:50])
    summary = {"taken_from_generator": taken, "acknowledged_by_broker": len(acked_ids),
               "unacknowledged": len(unacked), "seconds": round(elapsed, 3),
               "started": started_text, "finished": cat_text()}
    (RESULTS_DIR / "1_3_publisher_counts.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    log.info("summary: %s", summary)

    print()
    print(f"Dictionaries taken from generator : {taken:,}")
    print(f"Messages acknowledged by broker   : {len(acked_ids):,}")
    print(f"Messages not acknowledged         : {len(unacked):,}")
    print(f"Elapsed                           : {elapsed:.2f} s")
    finish_log(STEP)


if __name__ == "__main__":
    main()
