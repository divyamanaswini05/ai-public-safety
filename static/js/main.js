/* SentinelAI — global front-end behaviour */
(function () {
  "use strict";

  /* --------------------------------------------------------- Page loader */
  function hideLoader() {
    var loader = document.getElementById("pageLoader");
    if (loader) {
      loader.classList.add("loader-hidden");
      setTimeout(function () { if (loader.parentNode) loader.parentNode.removeChild(loader); }, 450);
    }
  }
  if (document.readyState === "complete") {
    hideLoader();
  } else {
    window.addEventListener("load", hideLoader);
  }

  /* ----------------------------------------------------------- Sidebar */
  var sidebar = document.getElementById("appSidebar");
  var overlay = document.getElementById("sidebarOverlay");
  var toggleBtn = document.getElementById("sidebarToggle");

  function isDesktop() {
    return window.matchMedia("(min-width: 992px)").matches;
  }

  function closeSidebar() {
    document.body.classList.remove("sidebar-open");
    if (overlay) overlay.classList.remove("show");
  }

  if (toggleBtn && sidebar) {
    toggleBtn.addEventListener("click", function () {
      if (isDesktop()) {
        document.body.classList.toggle("sidebar-collapsed");
      } else {
        document.body.classList.toggle("sidebar-open");
        if (overlay) overlay.classList.toggle("show");
      }
    });
  }

  if (overlay) overlay.addEventListener("click", closeSidebar);

  /* Highlight the nav item matching the current URL (already handled server-side
     via request.endpoint, this is a defensive fallback for query-string pages). */
  document.querySelectorAll(".sidebar-nav .nav-link[href]").forEach(function (link) {
    if (link.getAttribute("href") === window.location.pathname) {
      link.classList.add("active");
    }
  });

  /* ------------------------------------------------- Flash-message toasts */
  document.querySelectorAll(".flash-toast").forEach(function (el) {
    var toast = new bootstrap.Toast(el, { delay: 5200 });
    toast.show();
  });

  /* ------------------------- Programmatic toast helper for later modules */
  var TOAST_META = {
    success: { icon: "fa-circle-check", color: "#22c55e" },
    danger: { icon: "fa-circle-xmark", color: "#ef4444" },
    warning: { icon: "fa-triangle-exclamation", color: "#f59e0b" },
    info: { icon: "fa-circle-info", color: "#38bdf8" }
  };

  window.notify = function (message, type) {
    var meta = TOAST_META[type] || TOAST_META.info;
    var container = document.getElementById("flashToastContainer");
    if (!container) return;

    var el = document.createElement("div");
    el.className = "toast flash-toast align-items-center border-0";
    el.setAttribute("role", "alert");
    el.setAttribute("aria-live", "assertive");
    el.setAttribute("aria-atomic", "true");
    el.innerHTML =
      '<div class="d-flex align-items-center px-3 py-2">' +
      '<i class="fa-solid ' + meta.icon + ' me-2" style="color:' + meta.color + '"></i>' +
      '<div class="toast-body"></div>' +
      '<button type="button" class="btn-close btn-close-white ms-auto" data-bs-dismiss="toast" aria-label="Close"></button>' +
      "</div>";
    el.querySelector(".toast-body").textContent = message;
    container.appendChild(el);

    var toast = new bootstrap.Toast(el, { delay: 5200 });
    toast.show();
    el.addEventListener("hidden.bs.toast", function () { el.remove(); });
  };
})();
