"""Section 5.1 - Identify demand patterns.

Produces
    * total network energy per CAT day            (table + bar chart)
    * totals for the four seven-day periods       (table + bar chart)
    * the three highest 15-minute demand intervals (table)
    * average daily load profile, weekday vs weekend (chart, supports the explanation)

kWh versus kW
    energy_kwh is summed over time  -> consumption (how much was used).
    power_kw is summed across meters at one instant -> demand (how hard the
    network was working at that moment). Peaks are about kW, bills about kWh.

Run:  python s51_demand_patterns.py
"""

from __future__ import annotations

import charts
from common import CAT, RESULTS_DIR, connect, finish_log, format_table, load_named_queries, show_query, start_log

STEP = "5_1_demand_patterns"


def main() -> None:
    start_log(STEP)
    queries = load_named_queries("05_analysis.sql")
    conn = connect()

    _, daily = show_query(conn, queries["daily_energy"], title="Total network energy per CAT day (kWh)")
    _, weekly = show_query(conn, queries["weekly_energy"], title="Energy in the four seven-day periods (kWh)")
    _, peaks = show_query(conn, queries["peak_intervals"], title="Three highest 15-minute network demand intervals (kW)")
    _, profile = show_query(conn, queries["load_profile"], title="Average network demand by hour of day (kW)")
    conn.close()

    # ---- Chart 1: energy per day. Weekend days are drawn in a second colour
    #      because the weekly rhythm is the main pattern to explain. -------------
    days = [row[0].astimezone(CAT) for row in daily]
    energy = [row[2] for row in daily]
    weekend = [day.weekday() >= 5 for day in days]
    fig, ax = charts.new_figure(11, 4.5)
    ax.bar([d.strftime("%d\n%a") for d in days], energy, width=0.7,
           color=[charts.SERIES[1] if w else charts.SERIES[0] for w in weekend])
    ax.bar([0], [0], color=charts.SERIES[0], label="Working day")      # legend entries only
    ax.bar([0], [0], color=charts.SERIES[1], label="Weekend")
    ax.set_title("Total network energy per day, September 2026 (CAT days)")
    ax.set_ylabel("Energy (kWh)")
    ax.set_xlabel("Day of September 2026")
    ax.yaxis.set_major_formatter(lambda value, _: f"{value:,.0f}")
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper left", ncols=2)
    ax.set_ylim(0, max(energy) * 1.15)
    charts.save(fig, "5_1_daily_energy")

    # ---- Chart 2: the four seven-day periods -------------------------------------
    labels = [f"{row[0].astimezone(CAT):%d %b} -\n{(row[0].astimezone(CAT)).day + 6:02d} Sep" for row in weekly]
    totals = [row[1] for row in weekly]
    fig, ax = charts.new_figure(7, 4.5)
    bars = ax.bar(labels, totals, width=0.55, color=charts.SERIES[0])
    ax.bar_label(bars, labels=[f"{value:,.0f}" for value in totals], padding=3, color=charts.TEXT)
    ax.set_title("Network energy per seven-day period")
    ax.set_ylabel("Energy (kWh)")
    ax.yaxis.set_major_formatter(lambda value, _: f"{value:,.0f}")
    ax.grid(axis="x", visible=False)
    ax.set_ylim(0, max(totals) * 1.12)
    charts.save(fig, "5_1_weekly_energy")

    # ---- Chart 3: daily load shape (demand in kW, not energy) -----------------------
    fig, ax = charts.new_figure(9, 4.5)
    hours = [row[0] for row in profile]
    ax.plot(hours, [row[1] for row in profile], color=charts.SERIES[0], label="Working days")
    ax.plot(hours, [row[2] for row in profile], color=charts.SERIES[1], label="Weekend")
    ax.set_title("Average network demand by hour of day")
    ax.set_ylabel("Demand (kW)")
    ax.set_xlabel("Hour of day (CAT)")
    ax.set_xticks(range(0, 24, 2))
    ax.yaxis.set_major_formatter(lambda value, _: f"{value:,.0f}")
    ax.set_ylim(0, None)
    ax.legend(loc="upper left")
    charts.save(fig, "5_1_load_profile")

    # ---- Numbers that support the written explanation ------------------------------
    weekday_avg = sum(e for e, w in zip(energy, weekend) if not w) / weekend.count(False)
    weekend_avg = sum(e for e, w in zip(energy, weekend) if w) / weekend.count(True)
    growth = 100 * (totals[-1] - totals[0]) / totals[0]
    facts = [
        ("Total energy, 28 days (kWh)", f"{sum(energy):,.1f}"),
        ("Average working-day energy (kWh)", f"{weekday_avg:,.1f}"),
        ("Average weekend-day energy (kWh)", f"{weekend_avg:,.1f}"),
        ("Weekend vs working day", f"{100 * (weekend_avg - weekday_avg) / weekday_avg:+.1f} %"),
        ("Growth, period 4 vs period 1", f"{growth:+.2f} %"),
        ("Highest demand interval", f"{peaks[0][0].astimezone(CAT):%Y-%m-%d %H:%M} CAT, {peaks[0][2]:,.1f} kW"),
        ("Energy in that 15-minute interval (kWh)", f"{peaks[0][2] * 0.25:,.1f}  (= kW x 0.25 h)"),
    ]
    print("\n--- Key figures for the written explanation ---")
    print(format_table(["Fact", "Value"], facts))

    (RESULTS_DIR / f"{STEP}.md").write_text(
        "# 5.1 Demand patterns\n\n## Energy per CAT day\n\n"
        + format_table(["cat_day", "weekday", "energy_kwh", "readings"], daily, markdown=True)
        + "\n\n## Seven-day periods\n\n" + format_table(["period_start", "energy_kwh", "readings"], weekly, markdown=True)
        + "\n\n## Three highest demand intervals\n\n"
        + format_table(["event_time", "weekday", "network_demand_kw", "meters_reporting"], peaks, markdown=True)
        + "\n\n## Key figures\n\n" + format_table(["Fact", "Value"], facts, markdown=True) + "\n", encoding="utf-8")
    finish_log(STEP)


if __name__ == "__main__":
    main()
