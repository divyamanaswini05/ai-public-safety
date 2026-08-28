/* SentinelAI — live surveillance grid behaviour */
(function () {
  "use strict";

  var grid = document.getElementById("survGrid");
  if (!grid) return;

  var REFRESH_MS = 15000;
  var tiles = Array.prototype.slice.call(grid.querySelectorAll(".surv-tile"));
  var searchInput = document.getElementById("survSearch");
  var autoRefresh = document.getElementById("survAutoRefresh");
  var refreshBtn = document.getElementById("survRefreshNow");
  var activeFilter = "all";
  var timer = null;

  function statusLabel(status) {
    return status === "online" ? "LIVE" : status.toUpperCase();
  }

  function formatLastSeen(iso) {
    if (!iso) return "Never";
    var d = new Date(iso);
    if (isNaN(d.getTime())) return "Never";
    var mins = Math.max(0, Math.round((Date.now() - d.getTime()) / 60000));
    if (mins < 1) return "just now";
    if (mins < 60) return mins + "m ago";
    var hours = Math.floor(mins / 60);
    if (hours < 24) return hours + "h ago";
    return d.toLocaleDateString() + " " + d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

  function counterId(status) {
    return "count" + (status.charAt(0).toUpperCase() + status.slice(1));
  }

  function updateTile(camera) {
    var tile = grid.querySelector('.surv-tile[data-cam-id="' + camera.id + '"]');
    if (!tile) return;

    var prev = tile.getAttribute("data-status") || "";
    if (prev !== camera.status) {
      var next = counterId(camera.status);
      var prevEl = document.getElementById(counterId(prev));
      var nextEl = document.getElementById(next);
      if (prevEl) prevEl.textContent = Math.max(0, parseInt(prevEl.textContent || "0", 10) - 1);
      if (nextEl) nextEl.textContent = parseInt(nextEl.textContent || "0", 10) + 1;
    }

    tile.setAttribute("data-status", camera.status);
    tile.classList.remove("is-online", "is-offline", "is-disabled");
    tile.classList.add("is-" + camera.status);

    var badge = tile.querySelector("[data-surv-status]");
    if (badge) {
      badge.textContent = statusLabel(camera.status);
      badge.className = "surv-badge surv-status " + camera.status;
    }

    var preview = tile.querySelector(".surv-preview");
    var dot = tile.querySelector(".surv-live-dot");
    if (camera.status === "online") {
      if (!dot && preview) {
        var el = document.createElement("span");
        el.className = "surv-live-dot";
        preview.appendChild(el);
      }
    } else if (dot) {
      dot.remove();
    }

    var score = camera.health == null ? 0 : Math.round(camera.health);
    var fill = tile.querySelector(".health-fill");
    if (fill) {
      fill.style.width = score + "%";
      fill.className = "health-fill " + (score >= 75 ? "health-good" : score >= 40 ? "health-warn" : "health-bad");
    }
    var health = tile.querySelector("[data-surv-health]");
    if (health) health.textContent = score + "%";

    var seen = tile.querySelector("[data-surv-lastseen]");
    if (seen) seen.textContent = "Last seen: " + formatLastSeen(camera.last_seen);
  }

  /* -------------------------------------------- Search + status filtering */
  function applyVisibility() {
    var query = (searchInput ? searchInput.value : "").trim().toLowerCase();
    tiles.forEach(function (tile) {
      var status = tile.getAttribute("data-status");
      var nameEl = tile.querySelector(".surv-name");
      var locEl = tile.querySelector(".surv-location");
      var haystack = ((nameEl ? nameEl.textContent : "") + " " +
                      (locEl ? locEl.textContent : "")).toLowerCase();
      var visible = (activeFilter === "all" || status === activeFilter) &&
                    (!query || haystack.indexOf(query) !== -1);
      tile.style.display = visible ? "" : "none";
    });
  }

  if (searchInput) searchInput.addEventListener("input", applyVisibility);

  grid.querySelectorAll("[data-surv-filter]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      grid.querySelectorAll("[data-surv-filter]").forEach(function (b) {
        b.classList.remove("active");
      });
      btn.classList.add("active");
      activeFilter = btn.getAttribute("data-surv-filter");
      applyVisibility();
    });
  });

  /* ------------------------------------------------------------ Grid size */
  grid.querySelectorAll(".surv-gridsize").forEach(function (btn) {
    btn.addEventListener("click", function () {
      grid.querySelectorAll(".surv-gridsize").forEach(function (b) {
        b.classList.remove("active");
      });
      btn.classList.add("active");
      grid.setAttribute("data-cols", btn.getAttribute("data-cols"));
    });
  });

  /* ---------------------------------------------------------- Fullscreen */
  grid.querySelectorAll("[data-surv-fullscreen]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var wrap = btn.closest(".surv-preview-wrap");
      if (!wrap) return;
      if (document.fullscreenElement) {
        if (document.exitFullscreen) document.exitFullscreen();
      } else if (wrap.requestFullscreen) {
        wrap.requestFullscreen();
      }
    });
  });

  /* -------------------------------------------------------------- Polling */
  function refresh() {
    fetch("/surveillance/status", { headers: { "Accept": "application/json" } })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        (data.cameras || []).forEach(updateTile);
      })
      .catch(function () {});
  }

  function schedule() {
    if (timer) clearTimeout(timer);
    if (autoRefresh && autoRefresh.checked) {
      timer = setTimeout(function () { refresh(); schedule(); }, REFRESH_MS);
    }
  }

  if (autoRefresh) autoRefresh.addEventListener("change", schedule);
  if (refreshBtn) refreshBtn.addEventListener("click", refresh);

  /* ---------------------------------------- Broken feed fallback to signal */
  grid.querySelectorAll("img.live-feed").forEach(function (img) {
    img.addEventListener("error", function () {
      var wrap = img.closest(".surv-preview");
      if (!wrap) return;
      var sig = document.createElement("div");
      sig.className = "no-signal";
      sig.innerHTML = '<i class="fa-solid fa-video-slash"></i><span>No signal</span>';
      wrap.insertBefore(sig, img);
      img.remove();
    });
  });

  applyVisibility();
  schedule();
})();
