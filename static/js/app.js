// Mobile menu toggle and confirm prompts.
document.addEventListener("DOMContentLoaded", function () {
  var toggle = document.querySelector("[data-nav-toggle]");
  var nav = document.getElementById("nav");
  if (toggle && nav) {
    toggle.addEventListener("click", function () {
      nav.classList.toggle("open");
    });
  }
  var sidebarToggle = document.querySelector("[data-sidebar-toggle]");
  var sidebar = document.getElementById("qaSidebar");
  if (sidebarToggle && sidebar) {
    sidebarToggle.addEventListener("click", function () {
      var isMobile = window.matchMedia("(max-width: 760px)").matches;
      var open;
      if (isMobile) {
        sidebar.classList.remove("is-collapsed");
        open = sidebar.classList.toggle("is-open");
      } else {
        sidebar.classList.remove("is-open");
        open = !sidebar.classList.toggle("is-collapsed");
      }
      sidebarToggle.setAttribute("aria-expanded", String(open));
    });
  }
  document.querySelectorAll("[data-confirm]").forEach(function (el) {
    el.addEventListener("click", function (event) {
      if (!window.confirm(el.getAttribute("data-confirm"))) {
        event.preventDefault();
      }
    });
  });
});
