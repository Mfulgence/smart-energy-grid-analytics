"""Section 5.2 - Compare regions and customer types.

For each group (region, then customer type) over all 28 days:
    energy total          sum(energy_kwh) of the group's readings
    meter count           REGISTERED meters of the group (from the meters table)
    energy per meter      total / registered meters   <- the normalised value

Why normalise?
    A group can have a large total simply because it has many meters.
    Dividing by the meter count shows whether a typical meter in that group
    really uses more. Differences that survive normalisation are real
    differences in behaviour, not in group size.

Run:  python s52_groups.py
"""

from __future__ import annotations

import charts
from common import RESULTS_DIR, connect, finish_log, format_table, load_named_queries, show_query, start_log

STEP = "5_2_groups"


def bar_chart(names, values, title, ylabel, filename):
    """One-series bar chart: all bars share one colour (the bars are the same
    measure, the label under each bar already says which group it is)."""
    fig, ax = charts.new_figure(9, 4.2)
    bars = ax.bar(names, values, width=0.6, color=charts.SERIES[0])
    ax.bar_label(bars, labels=[f"{value:,.0f}" for value in values], padding=3, color=charts.TEXT)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.yaxis.set_major_formatter(lambda value, _: f"{value:,.0f}")
    ax.grid(axis="x", visible=False)
    ax.set_ylim(0, max(values) * 1.12)
    charts.save(fig, filename)


def main() -> None:
    start_log(STEP)
    queries = load_named_queries("05_analysis.sql")
    conn = connect()
    headers_r, regions = show_query(conn, queries["by_region"], title="Energy by region (28 days)")
    headers_c, types = show_query(conn, queries["by_customer_type"], title="Energy by customer type (28 days)")
    headers_m, mix = show_query(conn, queries["region_customer_mix"], title="Customer mix of each region (explains what remains)")
    conn.close()

    # Spread before and after normalisation.
    def spread(values):
        return 100 * (max(values) - min(values)) / min(values)

    region_totals = [row[2] for row in regions]
    region_per_meter = [row[3] for row in regions]
    type_totals = [row[2] for row in types]
    type_per_meter = [row[3] for row in types]
    facts = [
        ("Regions: highest vs lowest TOTAL", f"{spread(region_totals):.1f} % apart"),
        ("Regions: highest vs lowest PER METER", f"{spread(region_per_meter):.1f} % apart"),
        ("Customer types: highest vs lowest TOTAL", f"{max(type_totals) / min(type_totals):.2f} x"),
        ("Customer types: highest vs lowest PER METER", f"{max(type_per_meter) / min(type_per_meter):.2f} x"),
    ]
    print("\n--- Do the differences survive normalisation? ---")
    print(format_table(["Comparison", "Result"], facts))
    print("Every region has the same number of registered meters, so dividing by the meter")
    print("count cannot change the regional ranking: what remains is the customer mix.")

    bar_chart([row[0].replace("Region ", "R") for row in regions], region_per_meter,
              "Energy per registered meter by region (28 days)", "Energy per meter (kWh)", "5_2_region_per_meter")
    bar_chart([row[0] for row in types], type_per_meter,
              "Energy per registered meter by customer type (28 days)", "Energy per meter (kWh)", "5_2_type_per_meter")

    (RESULTS_DIR / f"{STEP}.md").write_text(
        "# 5.2 Regions and customer types\n\n" + format_table(headers_r, regions, markdown=True) + "\n\n"
        + format_table(headers_c, types, markdown=True) + "\n\n" + format_table(headers_m, mix, markdown=True)
        + "\n\n" + format_table(["Comparison", "Result"], facts, markdown=True) + "\n", encoding="utf-8")
    finish_log(STEP)


if __name__ == "__main__":
    main()
