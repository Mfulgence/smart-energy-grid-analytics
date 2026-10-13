"""Section 5.4 - Investigate abnormal consumption.

THE RULE (stated before looking at any label)
    1. For every meter, every 15-minute time-of-day slot and each day type
       (working day or weekend), the TYPICAL power is the median of that
       meter's readings in that slot and day type over the 28 days.
    2. ratio = actual power_kw / typical power_kw.
    3. A reading is flagged as
           demand_spike  when ratio >= 2.0   (at least double the typical value)
           unusual_drop  when ratio <= 0.5   (at most half the typical value)
       Each flag identifies one meter_id and one event_time.

WHY THIS RULE AND THESE THRESHOLDS
    * A meter is compared only with ITSELF at the same time of day and day
      type. A factory at 13:00 on a Tuesday is not compared with a house at
      03:00 on a Sunday, so the normal daily and weekly rhythm is not flagged.
    * The median is robust: a few abnormal hours cannot shift the "typical"
      value, so anomalies do not hide themselves.
    * The thresholds are set from the measured spread of normal readings. The
      program prints the percentiles of the ratio BEFORE any flag is made. On
      the common dataset the central 99.98% of readings sit between about
      0.76 and 1.29 times their typical value, so 0.5 and 2.0 are far outside
      normal variation and should produce very few false alarms. They are
      also easy to explain to operations staff: "twice or half the usual".

EVALUATION (labels are used ONLY here, after the flags exist)
    * detected event  = an injected interval with at least one flag for its
                        meter at or after start_time and before end_time
    * false flag      = a flagged reading outside every injected interval of
                        its meter
    * false flag %    = 100 x false flags / observed readings outside injected
                        intervals
    * meters affected = 100 x meters with at least one false flag / 4,000

Run:  python s54_anomalies.py
"""

from __future__ import annotations

from datetime import datetime, timedelta

import matplotlib.dates as mdates

import smart_meter_simulator as sim

import charts
from common import CAT, RESULTS_DIR, connect, finish_log, format_table, load_named_queries, show_query, start_log

STEP = "5_4_anomalies"
HIGH_THRESHOLD = 2.0     # flag when power is at least 2.0 x typical
LOW_THRESHOLD = 0.5      # flag when power is at most 0.5 x typical


def plot_example(conn, event: dict, flags: set, filename: str) -> None:
    """Plot one meter's power around an event: readings, typical level, flags."""
    start = datetime.fromisoformat(event["start_time"])
    end = datetime.fromisoformat(event["end_time"])
    rows = conn.execute("""
        SELECT r.event_time, r.power_kw, p.typical_kw
        FROM energy_readings r
        JOIN expected_profile p
          ON p.meter_id = r.meter_id
         AND p.slot     = (r.event_time AT TIME ZONE 'Africa/Kigali')::time
         AND p.weekend  = (extract(isodow FROM r.event_time AT TIME ZONE 'Africa/Kigali') >= 6)
        WHERE r.meter_id = %s AND r.event_time >= %s AND r.event_time < %s
        ORDER BY r.event_time""",
        (event["meter_id"], start - timedelta(hours=9), end + timedelta(hours=9))).fetchall()
    times = [row[0].astimezone(CAT).replace(tzinfo=None) for row in rows]
    fig, ax = charts.new_figure(10, 4.2)
    ax.plot(times, [row[2] for row in rows], color=charts.MUTED, label="Typical power (median for this slot)")
    ax.plot(times, [row[1] for row in rows], color=charts.SERIES[0], label="Measured power")
    flagged = [(t, row[1]) for t, row in zip(times, rows) if (event["meter_id"], row[0]) in flags]
    if flagged:
        ax.scatter(*zip(*flagged), color=charts.HIGHLIGHT, s=45, zorder=3,
                   edgecolor=charts.SURFACE, linewidth=1, label="Flagged by the rule")
    ax.axvspan(start.astimezone(CAT).replace(tzinfo=None), end.astimezone(CAT).replace(tzinfo=None),
               color=charts.GRID, alpha=0.6, label="Injected interval (label)")
    ax.set_title(f"Meter {event['meter_id']}: {event['event_type'].replace('_', ' ')} on {start:%d %B %Y}")
    ax.set_ylabel("Power (kW)")
    ax.set_xlabel("Time (CAT)")
    ax.set_ylim(0, None)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b\n%H:%M"))
    # Legend below the plot so it can never cover the readings.
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.28), ncols=4, fontsize=9)
    charts.save(fig, filename)


def main() -> None:
    start_log(STEP)
    queries = load_named_queries("05_analysis.sql")
    conn = connect()

    print(f"RULE: flag a reading when power_kw >= {HIGH_THRESHOLD} x typical or <= {LOW_THRESHOLD} x typical,")
    print("      where typical = median power of the same meter, same 15-minute slot, same day type.\n")

    # ---- Detection: no labels are used anywhere in this block ----------------------
    show_query(conn, queries["build_expected_profile"], title="Step 1: typical power per meter, slot and day type")
    conn.execute(queries["index_expected_profile"])
    conn.execute("ANALYZE expected_profile")
    show_query(conn, queries["ratio_distribution"], title="Step 2: spread of actual/typical for ALL readings")
    conn.execute(queries["drop_flags"])
    show_query(conn, queries["build_flags"].format(high=HIGH_THRESHOLD, low=LOW_THRESHOLD),
               title="Step 3: apply the rule and store the flags in anomaly_flags")
    show_query(conn, queries["flag_summary"], title="Flags by type")
    show_query(conn, queries["flag_sample"], title="Sample flagged readings (meter_id + event_time)")
    show_query(conn, queries["flag_runs"], title="Flags grouped per meter", max_rows=60)

    flag_rows = conn.execute("SELECT meter_id, event_time FROM anomaly_flags").fetchall()
    flags = {(meter_id, event_time) for meter_id, event_time in flag_rows}

    # ---- Evaluation: now, and only now, load the injected event labels --------------
    events = sim.anomaly_events()
    print(f"\nanomaly_events() returned {len(events)} injected events (used for evaluation only).")
    parsed = [(e, datetime.fromisoformat(e["start_time"]), datetime.fromisoformat(e["end_time"])) for e in events]

    # An event is detected if at least one flag has its meter and start <= time < end.
    evaluation, detected_count = [], 0
    for event, start, end in parsed:
        hits = sum(1 for meter_id, when in flags if meter_id == event["meter_id"] and start <= when < end)
        detected_count += hits > 0
        evaluation.append((event["meter_id"], event["event_type"], start, end, hits,
                           "DETECTED" if hits else "MISSED"))
    print("\n--- Comparison with the 40 injected events ---")
    print(format_table(["meter_id", "event_type", "start_time", "end_time", "flags inside", "result"], evaluation))

    # A false flag lies outside EVERY injected interval of its own meter.
    intervals: dict[int, list] = {}
    for event, start, end in parsed:
        intervals.setdefault(event["meter_id"], []).append((start, end))
    false_flags = [(meter_id, when) for meter_id, when in flags
                   if not any(start <= when < end for start, end in intervals.get(meter_id, []))]
    meters_with_false_flags = len({meter_id for meter_id, _ in false_flags})

    # Denominator: observed readings outside injected intervals.
    conn.execute("CREATE TEMP TABLE injected_events (meter_id BIGINT, start_time TIMESTAMPTZ, end_time TIMESTAMPTZ)")
    with conn.cursor() as cur:
        cur.executemany("INSERT INTO injected_events VALUES (%s, %s, %s)",
                        [(event["meter_id"], start, end) for event, start, end in parsed])
    _, rows = show_query(conn, queries["readings_inside_events"], title="Observed readings inside injected intervals")
    inside = rows[0][0]
    total = conn.execute("SELECT count(*) FROM energy_readings").fetchone()[0]
    outside = total - inside

    results = [
        ("Injected events", len(events)),
        ("Detected events", f"{detected_count} of {len(events)}"),
        ("Missed events", f"{len(events) - detected_count} of {len(events)}"),
        ("Flagged readings in total", f"{len(flags):,}"),
        ("Flags inside injected intervals (true flags)", f"{len(flags) - len(false_flags):,}"),
        ("False flags (outside every injected interval)", f"{len(false_flags):,}"),
        ("Observed readings outside injected intervals", f"{outside:,}"),
        ("False flags as % of those readings", f"{100 * len(false_flags) / outside:.6f} %"),
        ("Meters with at least one false flag", f"{meters_with_false_flags:,}"),
        ("Percentage of meters affected by false flags", f"{100 * meters_with_false_flags / 4000:.3f} %"),
    ]
    print("\n--- Evaluation result ---")
    print(format_table(["Measure", "Value"], results))
    if false_flags:
        print("\nFirst false flags:")
        print(format_table(["meter_id", "event_time"], sorted(false_flags)[:20]))

    # ---- One spike and one drop as pictures ----------------------------------------
    for kind in ("demand_spike", "unusual_drop"):
        example = next(event for event in events if event["event_type"] == kind)
        plot_example(conn, example, flags, f"5_4_example_{kind}")
    conn.close()

    (RESULTS_DIR / f"{STEP}.md").write_text(
        f"# 5.4 Anomaly detection\n\nRule: ratio >= {HIGH_THRESHOLD} or <= {LOW_THRESHOLD}, where ratio = power_kw / "
        "median power of the same meter, 15-minute slot and day type.\n\n"
        + format_table(["Measure", "Value"], results, markdown=True) + "\n\n"
        + format_table(["meter_id", "event_type", "start_time", "end_time", "flags inside", "result"],
                       evaluation, markdown=True) + "\n", encoding="utf-8")
    finish_log(STEP)


if __name__ == "__main__":
    main()
