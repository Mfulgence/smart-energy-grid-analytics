"""Panel definitions shared by the dashboards (7.1, 7.2) and the checks (7.3).

Both dashboards show the same five panels. The only difference is which SQL
is executed:
    mode "raw"        -> queries named raw_p1 ... raw_p5   (energy_readings)
    mode "aggregate"  -> queries named agg_p1 ... agg_p5   (continuous aggregates)
The SQL text lives in sql/07_dashboard_panels.sql so that the dashboard, the
verification script and the submitted repository all use the same queries.
"""

from __future__ import annotations

import time
from datetime import date, datetime, timedelta

from common import CAT, load_named_queries

MODES = {"raw": "Raw", "aggregate": "Aggregate"}          # url name -> dashboard name
PREFIX = {"raw": "raw", "aggregate": "agg"}               # url name -> query prefix

# Panel id -> (title, which columns identify a row, which column is the measure)
PANELS = {
    "p1": {"title": "Hourly regional energy", "keys": ["bucket", "region"], "value": "energy_kwh", "unit": "kWh"},
    "p2": {"title": "Daily network energy", "keys": ["bucket"], "value": "energy_kwh", "unit": "kWh"},
    "p3": {"title": "Network energy per seven-day period", "keys": ["bucket"], "value": "energy_kwh", "unit": "kWh"},
    "p4": {"title": "Daily energy of the selected meter", "keys": ["bucket", "meter_id"], "value": "energy_kwh", "unit": "kWh"},
    "p5": {"title": "Completeness by region", "keys": ["region"], "value": "completeness_percent", "unit": "%"},
}

DEFAULT_START = date(2026, 9, 22)     # the comparison window required by 7.3 ...
DEFAULT_END = date(2026, 9, 28)       # ... 22 to 28 September, both days included
DEFAULT_METER = 1000000000

QUERIES = load_named_queries("07_dashboard_panels.sql")


def period_bounds(first_day: date, last_day: date) -> tuple[datetime, datetime]:
    """Turn two whole CAT days (both included) into [start, end) timestamps.

    22 Sept .. 28 Sept  ->  22 Sept 00:00 CAT (inclusive) .. 29 Sept 00:00 CAT (exclusive)
    """
    start = datetime(first_day.year, first_day.month, first_day.day, tzinfo=CAT)
    end = datetime(last_day.year, last_day.month, last_day.day, tzinfo=CAT) + timedelta(days=1)
    return start, end


def panel_sql(mode: str, panel: str) -> str:
    return QUERIES[f"{PREFIX[mode]}_{panel}"]


def run_panel(conn, mode: str, panel: str, first_day: date, last_day: date, meter_id: int):
    """Run one panel query. Returns (column names, rows, query milliseconds).

    The time covers statement submission until the last row is fetched, the
    same definition used for the SQL benchmarks in Sections 3 and 4.
    """
    start, end = period_bounds(first_day, last_day)
    params = {"start": start, "end": end, "meter_id": meter_id}
    started = time.perf_counter()
    cur = conn.execute(panel_sql(mode, panel), params)
    rows = cur.fetchall()
    elapsed_ms = (time.perf_counter() - started) * 1000
    return [col.name for col in cur.description], rows, elapsed_ms
