// CoRide shared behaviour. Everything here is progressive: pages work without it.
(function () {
  "use strict";

  // Mobile navigation toggle.
  document.querySelectorAll("[data-nav-toggle]").forEach(function (btn) {
    var nav = document.getElementById(btn.getAttribute("aria-controls"));
    if (!nav) return;
    btn.addEventListener("click", function () {
      var open = nav.getAttribute("data-open") === "true";
      nav.setAttribute("data-open", String(!open));
      btn.setAttribute("aria-expanded", String(!open));
    });
  });

  // Close <details> menus on outside click and on Escape.
  var menus = document.querySelectorAll("[data-menu]");
  document.addEventListener("click", function (e) {
    menus.forEach(function (m) { if (m.open && !m.contains(e.target)) m.open = false; });
  });
  document.addEventListener("keydown", function (e) {
    if (e.key !== "Escape") return;
    menus.forEach(function (m) {
      if (m.open) { m.open = false; m.querySelector("summary").focus(); }
    });
  });

  // Dismissible alerts.
  document.querySelectorAll("[data-alert-close]").forEach(function (btn) {
    btn.addEventListener("click", function () { btn.closest("[data-alert]").remove(); });
  });

  // Photo drop zones: preview the chosen image.
  document.querySelectorAll("[data-drop]").forEach(function (drop) {
    var input = drop.querySelector('input[type="file"]');
    if (!input) return;
    input.addEventListener("change", function () {
      var old = drop.querySelector(".drop__preview");
      if (old) old.remove();
      var file = input.files && input.files[0];
      if (!file || !file.type.startsWith("image/")) { drop.removeAttribute("data-filled"); return; }
      var img = document.createElement("img");
      img.className = "drop__preview";
      img.alt = "";
      img.src = URL.createObjectURL(file);
      drop.insertBefore(img, input);
      drop.setAttribute("data-filled", "true");
    });
  });
})();
