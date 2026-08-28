/* SentinelAI — dashboard charts (Chart.js) */
(function () {
  "use strict";

  var data = window.SENTINEL_DASHBOARD || {};

  var GRID = "rgba(255,255,255,0.06)";
  var TICK = "#94a0b8";

  Chart.defaults.color = TICK;
  Chart.defaults.borderColor = GRID;
  Chart.defaults.font.family = "'Inter', system-ui, -apple-system, sans-serif";
  Chart.defaults.font.size = 11;

  function lineChart(id, series, color) {
    var el = document.getElementById(id);
    if (!el || !series) return;
    var ctx = el.getContext("2d");
    new Chart(ctx, {
      type: "line",
      data: {
        labels: series.labels,
        datasets: [{
          label: "Events",
          data: series.values,
          borderColor: color,
          backgroundColor: color + "26",
          fill: true,
          tension: 0.4,
          borderWidth: 2,
          pointRadius: 2.5,
          pointBackgroundColor: color,
          pointHoverRadius: 4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { display: false }, ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 8 } },
          y: { beginAtZero: true, ticks: { precision: 0 } }
        }
      }
    });
  }

  function doughnutChart(id, series, colors) {
    var el = document.getElementById(id);
    if (!el || !series) return;
    var ctx = el.getContext("2d");
    new Chart(ctx, {
      type: "doughnut",
      data: {
        labels: series.labels,
        datasets: [{
          data: series.values,
          backgroundColor: colors,
          borderWidth: 2,
          borderColor: "#0a0e1a"
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "62%",
        plugins: {
          legend: {
            position: "bottom",
            labels: { boxWidth: 10, padding: 14, usePointStyle: true, pointStyle: "circle" }
          }
        }
      }
    });
  }

  var SEVERITY_COLORS = ["#22c55e", "#f59e0b", "#f97316", "#ef4444"];
  var TYPE_COLORS = ["#ef4444", "#f59e0b", "#38bdf8", "#a78bfa", "#22c55e", "#f472b6", "#94a0b8"];

  lineChart("incidentTrendChart", data.incident_trend, "#3b82f6");
  lineChart("alertTrendChart", data.alert_trend, "#f59e0b");
  doughnutChart("incidentTypeChart", data.incidents_by_type, TYPE_COLORS);
  doughnutChart("severityChart", data.incidents_by_severity, SEVERITY_COLORS);
  doughnutChart("cameraStatusChart", data.camera_status_split, ["#22c55e", "#ef4444", "#64748b"]);
})();
