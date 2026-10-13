/* Section 7.4 - Browser-side timing for the Raw and Aggregate dashboards.

   Dash loads every file in the assets/ folder automatically.

   What is measured, and how
     dashboard_ms    From the moment Refresh is requested until the LAST of the
                     five panels has finished drawing. Measured here in the
                     browser with performance.now().
     pN_query_ms     Duration of each panel's SQL query, measured on the server
                     and delivered inside the figure (layout.meta.query_ms).

   How "finished drawing" is detected
     Every refresh gets a number (the token). The server stamps that token
     into each figure it returns. Plotly fires the event "plotly_afterplot"
     when a chart has finished drawing. When all five charts have reported
     an afterplot carrying the CURRENT token, the refresh is complete.

   The timing test button runs 1 warm-up refresh followed by 10 measured
   refreshes, shows median / minimum / maximum, and sends every refresh to
   the server, which appends it to results/7_4_dashboard_timings.csv.
*/
(function () {
  "use strict";

  var PANELS = ["p1", "p2", "p3", "p4", "p5"];
  var MEASURED_RUNS = 10;

  var startedAt = {};        // token -> performance.now() when Refresh was requested
  var startedWall = {};      // token -> wall-clock time (ms since 1970) of the request
  var finished = {};         // token -> { p1: {rendered, query_ms, rows}, ... }
  var reported = {};         // token -> true once the refresh was recorded
  var waiting = null;        // resolve function of the refresh the timing test waits for
  var runInfo = { session: "", run_type: "manual", run: 0 };

  /* Called by the Dash clientside callback when Refresh is clicked.
     Returns the token object that triggers the five server callbacks. */
  function start(clicks) {
    var token = Date.now() * 1000 + (clicks % 1000);     // unique for every refresh
    startedAt[token] = performance.now();
    startedWall[token] = Date.now();
    finished[token] = {};
    return { token: token, clicks: clicks };
  }

  /* Read the token and query time that the server stored in the figure. */
  function record(graphDiv, panel) {
    var meta = graphDiv.layout && graphDiv.layout.meta;
    if (!meta || meta.token === undefined || !(meta.token in startedAt)) { return; }
    var token = meta.token;
    if (finished[token][panel]) { return; }               // already noted for this refresh
    finished[token][panel] = { rendered: performance.now(), query_ms: meta.query_ms, rows: meta.rows };
    finished[token].filters = { first_day: meta.first_day, last_day: meta.last_day, meter_id: meta.meter_id };
    var allDone = PANELS.every(function (p) { return finished[token][p]; });
    if (allDone && !reported[token]) {
      reported[token] = true;
      complete(token, meta.mode);
    }
  }

  /* All five panels are drawn: compute the elapsed time, show it, save it. */
  function complete(token, mode) {
    var lastRender = Math.max.apply(null, PANELS.map(function (p) { return finished[token][p].rendered; }));
    var result = {
      session: runInfo.session || "manual", mode: mode, run_type: runInfo.run_type, run: runInfo.run,
      start_epoch_ms: startedWall[token], dashboard_ms: lastRender - startedAt[token], panels: {},
      first_day: finished[token].filters.first_day, last_day: finished[token].filters.last_day,
      meter_id: finished[token].filters.meter_id, browser: navigator.userAgent
    };
    PANELS.forEach(function (p) { result.panels[p] = { query_ms: finished[token][p].query_ms }; });

    var status = document.getElementById("timing-status");
    if (status) {
      status.textContent = "Last refresh (" + runInfo.run_type + "): " + result.dashboard_ms.toFixed(0) +
        " ms until all 5 panels rendered | query ms: " +
        PANELS.map(function (p) { return p + " " + result.panels[p].query_ms.toFixed(1); }).join(", ");
    }
    fetch("/api/timing", { method: "POST", headers: { "Content-Type": "application/json" },
                           body: JSON.stringify(result) });
    if (waiting) { var resolve = waiting; waiting = null; resolve(result); }
  }

  /* Attach the afterplot listener to each chart as soon as Plotly has created
     it. Charts appear after the page loads, so we keep looking for new ones. */
  function attachListeners() {
    PANELS.forEach(function (panel) {
      var graphDiv = document.querySelector("#panel-" + panel + " .js-plotly-plot");
      if (graphDiv && graphDiv.on && !graphDiv.__timingAttached) {
        graphDiv.__timingAttached = true;
        graphDiv.on("plotly_afterplot", function () { record(graphDiv, panel); });
        record(graphDiv, panel);       // the very first draw may already be finished
      }
    });
  }
  setInterval(attachListeners, 25);

  /* ---- Timing test: 1 warm-up + 10 measured refreshes ------------------------ */
  function refreshOnce() {
    return new Promise(function (resolve) {
      waiting = resolve;
      document.getElementById("refresh-btn").click();
    });
  }

  function pause(ms) { return new Promise(function (resolve) { setTimeout(resolve, ms); }); }

  function summarise(values) {
    var sorted = values.slice().sort(function (a, b) { return a - b; });
    var middle = Math.floor(sorted.length / 2);
    var median = sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
    return { median: median, min: sorted[0], max: sorted[sorted.length - 1] };
  }

  async function runTimingTest() {
    var button = document.getElementById("benchmark-btn");
    var table = document.getElementById("timing-table");
    var mode = document.getElementById("dashboard-name").textContent;
    button.disabled = true;
    runInfo.session = mode.toLowerCase() + "-" + new Date().toISOString();
    var results = [];
    for (var run = 0; run <= MEASURED_RUNS; run++) {
      runInfo.run_type = run === 0 ? "warm-up" : "measured";
      runInfo.run = run;
      table.textContent = "Timing test running: " + (run === 0 ? "warm-up" : "measured refresh " + run + " of " + MEASURED_RUNS) + " ...";
      var result = await refreshOnce();
      if (run > 0) { results.push(result); }
      await pause(250);                       // let the browser settle before the next refresh
    }
    runInfo = { session: "", run_type: "manual", run: 0 };
    button.disabled = false;

    var rows = PANELS.map(function (p, i) {
      var s = summarise(results.map(function (r) { return r.panels[p].query_ms; }));
      return ["Panel " + (i + 1) + " query", s];
    });
    rows.push(["Whole dashboard (refresh request until all 5 panels rendered)",
               summarise(results.map(function (r) { return r.dashboard_ms; }))]);
    var html = "<h2>" + mode + " dashboard timing: " + MEASURED_RUNS + " measured refreshes after 1 warm-up</h2>" +
      "<p>Finished " + new Date().toString() + " | tool: performance.now() in the browser (dashboard), " +
      "time.perf_counter() on the server (queries) | no result caching</p>" +
      "<table><tr><th>Measurement</th><th>Median ms</th><th>Minimum ms</th><th>Maximum ms</th></tr>";
    rows.forEach(function (row) {
      html += "<tr><td>" + row[0] + "</td><td>" + row[1].median.toFixed(1) + "</td><td>" +
        row[1].min.toFixed(1) + "</td><td>" + row[1].max.toFixed(1) + "</td></tr>";
    });
    table.innerHTML = html + "</table>";
  }

  document.addEventListener("click", function (event) {
    if (event.target && event.target.id === "benchmark-btn") { runTimingTest(); }
  });

  window.dashTiming = { start: start };
})();
