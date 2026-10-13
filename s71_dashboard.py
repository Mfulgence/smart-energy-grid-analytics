"""Sections 7.1, 7.2 and 7.4 - The Raw and Aggregate dashboards (Plotly Dash).

One program serves two dashboards with the same five panels, layout and filters:

    http://localhost:8050/raw         dashboard "Raw"        (reads energy_readings)
    http://localhost:8050/aggregate   dashboard "Aggregate"  (reads the continuous aggregates)

Panels (identical in both)
    1  Hourly regional energy            kWh   heatmap, region x hour
    2  Daily network energy              kWh   bars per CAT day
    3  Energy per seven-day period       kWh   bars per period (from 1, 8, 15, 22 Sept)
    4  Daily energy of the selected meter kWh  bars per CAT day
    5  Completeness by region            %     dot per region

Filters: a range of whole CAT days and a meter ID. The panels reload when the
Refresh button is pressed. No query result is cached anywhere: every refresh
runs all five SQL statements again.

How the timing for 7.4 is measured (see assets/dashboard_timing.js)
    * Per-panel QUERY duration: measured in this program around each SQL
      statement and shipped to the browser inside the figure.
    * Whole-dashboard elapsed time: measured in the browser with
      performance.now(), from the click on Refresh until the last of the five
      panels has finished drawing (Plotly's "afterplot" event).
    * "Run timing test" performs 1 warm-up refresh + 10 measured refreshes and
      shows median / minimum / maximum. Every refresh is appended to
      results/7_4_dashboard_timings.csv.

Run:  python s71_dashboard.py        then open http://localhost:8050
"""

from __future__ import annotations

import csv
import queue
import socket
from datetime import date, datetime

import plotly.graph_objects as go
from dash import Dash, Input, Output, State, dcc, html, no_update
from flask import jsonify, request

import dashboard_queries as dq
from common import CAT, RESULTS_DIR, cat_text, connect, setting

TIMING_FILE = RESULTS_DIR / "7_4_dashboard_timings.csv"
TIMING_COLUMNS = ["session", "mode", "run_type", "run", "start_cat", "end_cat", "dashboard_ms",
                  "p1_query_ms", "p2_query_ms", "p3_query_ms", "p4_query_ms", "p5_query_ms",
                  "first_day", "last_day", "meter_id", "machine", "browser"]

# Colours and fonts shared by all panels (same palette as the report charts).
BLUE = "#2a78d6"
BLUE_SCALE = ["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]   # light -> dark = low -> high
TEXT, TEXT_SECONDARY, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"

# ---------------------------------------------------------------------------------
# Database connections. The five panels are requested by the browser at the same
# time, so five connections are opened once at start-up and reused. Opening a
# connection inside each request would add connection time to every measurement.
# ---------------------------------------------------------------------------------
POOL: queue.Queue = queue.Queue()
for _ in range(5):
    POOL.put(connect())

app = Dash(__name__, title="Smart Energy Grid dashboards", suppress_callback_exceptions=True)
server = app.server


# ---------------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------------
def base_layout(title: str, meta: dict) -> dict:
    """Layout shared by every panel. `meta` carries the refresh token and the
    query duration to the browser so the timing script can read them there."""
    return dict(
        title=dict(text=title, x=0.01, xanchor="left", font=dict(size=15, color=TEXT)),
        meta=meta,
        datarevision=meta["token"],          # tells Plotly the data changed -> full redraw every refresh
        margin=dict(l=60, r=20, t=48, b=44), height=320,
        paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
        font=dict(color=TEXT_SECONDARY, size=12),
        xaxis=dict(gridcolor=GRID, linecolor=GRID), yaxis=dict(gridcolor=GRID, linecolor=GRID),
        showlegend=False,
    )


def day_label(bucket: datetime) -> str:
    return bucket.astimezone(CAT).strftime("%d %b")


def build_figure(panel: str, rows: list, meta: dict, meter_id: int) -> go.Figure:
    """Turn the rows of one panel query into its chart."""
    title = dq.PANELS[panel]["title"]
    fig = go.Figure()
    if not rows:
        fig.update_layout(**base_layout(f"{title} - no data in the selected range", meta))
        return fig

    if panel == "p1":       # rows: bucket, region, energy_kwh, reading_count
        # Ten regions are too many to tell apart as ten coloured lines, so the
        # panel is a heatmap: one row per region, one column per hour, darker = more kWh.
        regions = sorted({row[1] for row in rows}, key=lambda name: (len(name), name))
        hours = sorted({row[0] for row in rows})
        lookup = {(row[1], row[0]): row[2] for row in rows}
        fig.add_trace(go.Heatmap(
            x=[hour.astimezone(CAT).replace(tzinfo=None) for hour in hours], y=regions,
            z=[[lookup.get((region, hour)) for hour in hours] for region in regions],
            colorscale=[[i / 4, colour] for i, colour in enumerate(BLUE_SCALE)],
            colorbar=dict(title="kWh", thickness=12),
            hovertemplate="%{y}<br>%{x|%d %b %H:00} CAT<br>%{z:,.1f} kWh<extra></extra>"))
        fig.update_layout(**base_layout(f"{title} (kWh)", meta))
        fig.update_yaxes(autorange="reversed", showgrid=False)
        fig.update_xaxes(title_text="Hour (CAT)", showgrid=False)

    elif panel in ("p2", "p3", "p4"):   # rows: bucket, [meter_id,] energy_kwh, reading_count
        value_index = 2 if panel == "p4" else 1
        if panel == "p3":               # label each bar with the days the period covers
            labels = [f"{day_label(row[0])} - {(row[0].astimezone(CAT).day + 6):02d} Sep" for row in rows]
        else:
            labels = [day_label(row[0]) for row in rows]
        values = [row[value_index] for row in rows]
        fig.add_trace(go.Bar(x=labels, y=values, marker_color=BLUE,
                             width=0.45 if len(values) > 1 else 0.2,      # slim bars, never a wall of colour
                             text=[f"{value:,.1f}" for value in values] if len(values) <= 10 else None,
                             textposition="outside", cliponaxis=False,
                             hovertemplate="%{x}<br>%{y:,.2f} kWh<extra></extra>"))
        extra = f", meter {meter_id}" if panel == "p4" else ""
        fig.update_layout(**base_layout(f"{title}{extra} (kWh)", meta))
        fig.update_yaxes(title_text="Energy (kWh)", rangemode="tozero")
        fig.update_xaxes(type="category", showgrid=False,
                         title_text="Seven-day period" if panel == "p3" else "CAT day")

    else:                               # p5 rows: region, meters, readings, planned, completeness
        # All regions sit near 99 %, so bars from zero would look identical.
        # Dots on a zoomed axis show the differences honestly.
        regions = [row[0] for row in rows]
        values = [row[4] for row in rows]
        fig.add_trace(go.Scatter(x=values, y=regions, mode="markers+text",
                                 marker=dict(color=BLUE, size=11),
                                 text=[f"{value:.3f} %" for value in values], textposition="middle right",
                                 hovertemplate="%{y}<br>%{x:.4f} %<extra></extra>", cliponaxis=False))
        fig.update_layout(**base_layout(f"{title} (%)", meta))
        low, high = min(values), max(values)
        pad = max((high - low) * 0.6, 0.05)
        fig.update_xaxes(title_text="Completeness (%)", range=[low - pad, high + pad * 2.2], ticksuffix=" %")
        fig.update_yaxes(autorange="reversed", showgrid=False)
    return fig


# ---------------------------------------------------------------------------------
# Page layout (the same function builds both dashboards)
# ---------------------------------------------------------------------------------
def dashboard_layout(mode: str) -> html.Div:
    name = dq.MODES[mode]
    source = ("energy_readings (raw hypertable) joined to meters" if mode == "raw"
              else "continuous aggregates agg_region_hourly, agg_region_15min, agg_meter_daily")
    graph = lambda panel: dcc.Graph(id=f"panel-{panel}", config={"displayModeBar": False},
                                    style={"height": "320px"})
    return html.Div(className="page", children=[
        dcc.Store(id="mode", data=mode),
        dcc.Store(id="refresh-token"),            # written in the browser on every Refresh click
        html.Div(className="header", children=[
            html.H1(name, id="dashboard-name"),
            html.Span(f"Smart Energy Grid - measurement queries read {source}", className="subtitle"),
            html.Span([dcc.Link("Raw", href="/raw"), " | ", dcc.Link("Aggregate", href="/aggregate")],
                      className="switch"),
        ]),
        # ---- one filter row above all panels ----
        html.Div(className="filters", children=[
            html.Label(["Whole CAT days ",
                        dcc.DatePickerRange(id="date-range", start_date=dq.DEFAULT_START, end_date=dq.DEFAULT_END,
                                            min_date_allowed=date(2026, 9, 1), max_date_allowed=date(2026, 9, 28),
                                            display_format="YYYY-MM-DD", minimum_nights=0)]),
            # A plain text box keeps the same look in every Dash version; the
            # value is validated on the server (see clean_meter_id).
            html.Label(["Meter ", dcc.Input(id="meter-id", type="text", value=str(dq.DEFAULT_METER),
                                            debounce=True, style={"width": "120px"})]),
            html.Button("Refresh", id="refresh-btn", n_clicks=0),
            html.Button("Run timing test (1 warm-up + 10 measured)", id="benchmark-btn", n_clicks=0),
            html.Span(id="timing-status", className="status"),
        ]),
        html.Div(className="grid", children=[
            html.Div(graph("p1"), className="panel wide"),
            html.Div(graph("p2"), className="panel"),
            html.Div(graph("p3"), className="panel"),
            html.Div(graph("p4"), className="panel"),
            html.Div(graph("p5"), className="panel"),
        ]),
        html.Div(id="timing-table", className="timing"),   # filled by dashboard_timing.js
    ])


def home_layout() -> html.Div:
    return html.Div(className="page", children=[
        html.H1("Smart Energy Grid dashboards"),
        html.P("Two dashboards with the same panels, filters and date range:"),
        html.Ul([html.Li(dcc.Link("Raw - reads energy_readings directly", href="/raw")),
                 html.Li(dcc.Link("Aggregate - reads the continuous aggregates", href="/aggregate"))]),
    ])


app.layout = html.Div([dcc.Location(id="url"), html.Div(id="page-content")])


@app.callback(Output("page-content", "children"), Input("url", "pathname"))
def show_page(pathname: str):
    """Pick the dashboard from the address: /raw or /aggregate."""
    mode = (pathname or "/").strip("/").lower()
    return dashboard_layout(mode) if mode in dq.MODES else home_layout()


# ---------------------------------------------------------------------------------
# Refresh flow
#   click Refresh -> (browser) note the time, create a new token
#                 -> (server)  five callbacks run the five panel queries
#                 -> (browser) Plotly draws; the timing script notes each finish
# ---------------------------------------------------------------------------------
app.clientside_callback(
    "function(n_clicks) { return window.dashTiming.start(n_clicks || 0); }",
    Output("refresh-token", "data"),
    Input("refresh-btn", "n_clicks"),
)


def clean_meter_id(value) -> int:
    """Return a valid meter ID (1000000000 .. 1000003999) or the default one."""
    try:
        meter_id = int(str(value).strip())
    except (TypeError, ValueError):
        return dq.DEFAULT_METER
    return meter_id if 1000000000 <= meter_id <= 1000003999 else dq.DEFAULT_METER


def make_panel_callback(panel: str):
    @app.callback(Output(f"panel-{panel}", "figure"),
                  Input("refresh-token", "data"),
                  State("mode", "data"), State("date-range", "start_date"),
                  State("date-range", "end_date"), State("meter-id", "value"))
    def update(token, mode, start_date, end_date, meter_id, panel=panel):
        if token is None or not start_date or not end_date:
            return no_update
        first_day, last_day = date.fromisoformat(start_date[:10]), date.fromisoformat(end_date[:10])
        meter_id = clean_meter_id(meter_id)
        conn = POOL.get()                       # borrow a connection ...
        try:
            _, rows, query_ms = dq.run_panel(conn, mode, panel, first_day, last_day, meter_id)
        finally:
            POOL.put(conn)                      # ... and always give it back
        # meta travels to the browser inside the figure; the timing script reads it.
        meta = {"token": token["token"], "panel": panel, "mode": mode,
                "query_ms": round(query_ms, 3), "rows": len(rows),
                "first_day": first_day.isoformat(), "last_day": last_day.isoformat(), "meter_id": meter_id}
        return build_figure(panel, rows, meta, meter_id)
    return update


for _panel in dq.PANELS:
    make_panel_callback(_panel)


# ---------------------------------------------------------------------------------
# Timing record: the browser posts one line per completed refresh.
# ---------------------------------------------------------------------------------
@server.post("/api/timing")
def record_timing():
    data = request.get_json(force=True)
    start = datetime.fromtimestamp(data["start_epoch_ms"] / 1000, CAT)
    row = {"session": data["session"], "mode": data["mode"], "run_type": data["run_type"], "run": data["run"],
           "start_cat": cat_text(start), "end_cat": cat_text(), "dashboard_ms": round(data["dashboard_ms"], 1),
           "first_day": data.get("first_day", ""), "last_day": data.get("last_day", ""),
           "meter_id": data.get("meter_id", ""), "machine": setting("MACHINE_ID") or socket.gethostname(),
           "browser": data.get("browser", "")}
    for panel in dq.PANELS:
        row[f"{panel}_query_ms"] = data["panels"][panel]["query_ms"]
    new_file = not TIMING_FILE.exists()
    with open(TIMING_FILE, "a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=TIMING_COLUMNS)
        if new_file:
            writer.writeheader()
        writer.writerow(row)
    return jsonify(ok=True)


if __name__ == "__main__":
    print("Raw dashboard       : http://localhost:8050/raw")
    print("Aggregate dashboard : http://localhost:8050/aggregate")
    print("Query-result caching: none (every refresh re-runs all five queries)")
    # debug=False: no auto-reloader and no dev tools, so nothing extra runs during timing.
    app.run(host="127.0.0.1", port=8050, debug=False)
