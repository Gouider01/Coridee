// CoRide shared behaviour. Everything here is progressive: pages work without it.
(function () {
  "use strict";
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

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
    menus.forEach(function (m) { if (m.open) { m.open = false; m.querySelector("summary").focus(); } });
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

  // Scroll reveals.
  var reveals = document.querySelectorAll(".reveal");
  if (reveals.length && "IntersectionObserver" in window && !reduceMotion) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) { if (en.isIntersecting) { en.target.classList.add("is-visible"); io.unobserve(en.target); } });
    }, { threshold: 0.15 });
    reveals.forEach(function (el) { io.observe(el); });
  } else {
    reveals.forEach(function (el) { el.classList.add("is-visible"); });
  }

  // Hero: cursor spotlight on the tile lattice.
  var hero = document.querySelector("[data-hero]");
  if (hero && !reduceMotion) {
    hero.addEventListener("pointermove", function (e) {
      var r = hero.getBoundingClientRect();
      hero.style.setProperty("--mx", (e.clientX - r.left) + "px");
      hero.style.setProperty("--my", (e.clientY - r.top) + "px");
    });
  }

  // Hero search: example city pairs typed into the placeholders.
  var from = document.querySelector("[data-type-from]"), to = document.querySelector("[data-type-to]");
  if (from && to && !reduceMotion) {
    var pairs = [["Tunis", "Sousse"], ["Sfax", "Tunis"], ["Bizerte", "Nabeul"], ["Monastir", "Kairouan"]], i = 0;
    var type = function (el, word, done) {
      var k = 0, iv = setInterval(function () {
        el.placeholder = word.slice(0, ++k);
        if (k >= word.length) { clearInterval(iv); if (done) done(); }
      }, 90);
    };
    setInterval(function () {
      if (document.activeElement === from || document.activeElement === to || from.value || to.value) return;
      i = (i + 1) % pairs.length;
      type(from, pairs[i][0], function () { type(to, pairs[i][1]); });
    }, 4200);
  }

  // Fuel-split calculator and seat plan.
  var calc = document.querySelector("[data-calc]");
  if (calc) {
    var km = 140, pax = calc.querySelector("[data-pax]");
    var fmt = function (n) { return (Math.round(n * 100) / 100).toFixed(2).replace(/\.?0+$/, ""); };
    var update = function () {
      var p = +pax.value, cost = km * 7 / 100 * 2.525, each = cost / (p + 1);
      calc.querySelector("[data-pax-out]").textContent = p;
      calc.querySelector("[data-alone]").innerHTML = fmt(cost) + "<em>TND</em>";
      calc.querySelector("[data-each]").innerHTML = fmt(each) + "<em>TND</em>";
      document.querySelectorAll(".plan__seat[data-seat]").forEach(function (s) { s.classList.toggle("is-on", +s.dataset.seat <= p); });
      var filled = document.querySelector("[data-seats-filled]"); if (filled) filled.textContent = p;
      var saving = document.querySelector("[data-saving]");
      if (saving) saving.textContent = p ? "-" + Math.round((1 - each / cost) * 100) + "% each" : "Driving alone";
    };
    pax.addEventListener("input", update);
    calc.querySelectorAll("[data-km]").forEach(function (b) {
      b.addEventListener("click", function () {
        calc.querySelectorAll("[data-km]").forEach(function (x) { x.setAttribute("aria-pressed", "false"); });
        b.setAttribute("aria-pressed", "true");
        km = +b.dataset.km;
        update();
      });
    });
    update();
  }

  // Passenger / driver steps.
  var roles = document.querySelector("[data-roles]"), how = document.querySelector("[data-how]");
  if (roles && how) {
    var steps = {
      p: [["Search a trip", "Choose where you leave from, where you go and when."], ["Book your seat", "The driver accepts, a chat opens and you get a QR ticket."], ["Ride and rate", "Show your ticket at pickup, then rate each other after the trip."]],
      d: [["Register your car", "Add your vehicle and its papers; our team validates them."], ["Publish a trip", "Set the route, the time, the seats and a fair price per seat."], ["Accept and drive", "Accept passengers, scan their QR ticket at pickup, then rate them."]]
    };
    var cards = how.querySelectorAll(".how__step");
    roles.querySelectorAll("button").forEach(function (b) {
      b.addEventListener("click", function () {
        var r = b.dataset.role;
        roles.querySelectorAll("button").forEach(function (x) { x.setAttribute("aria-pressed", "false"); });
        b.setAttribute("aria-pressed", "true");
        roles.classList.toggle("is-driver", r === "d");
        how.classList.toggle("is-driver", r === "d");
        cards.forEach(function (c, idx) {
          c.classList.add("is-swapping");
          setTimeout(function () {
            c.querySelector("strong").textContent = steps[r][idx][0];
            c.querySelector("strong + span").textContent = steps[r][idx][1];
            c.classList.remove("is-swapping");
          }, 200 + idx * 70);
        });
      });
    });
  }

  // Tilt + glare on feature cards.
  if (!reduceMotion) {
    document.querySelectorAll("[data-tilt]").forEach(function (c) {
      c.addEventListener("pointermove", function (e) {
        var r = c.getBoundingClientRect(), x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height;
        c.style.transform = "rotateX(" + ((0.5 - y) * 10) + "deg) rotateY(" + ((x - 0.5) * 12) + "deg) translateY(-4px)";
        c.style.setProperty("--gx", x * 100 + "%");
        c.style.setProperty("--gy", y * 100 + "%");
      });
      c.addEventListener("pointerleave", function () { c.style.transform = ""; });
    });
  }

  // Count-up numbers.
  document.querySelectorAll("[data-count]").forEach(function (el) {
    var target = +el.dataset.count;
    if (reduceMotion || !target) { el.textContent = target; return; }
    var start = null;
    var step = function (ts) {
      if (!start) start = ts;
      var p = Math.min((ts - start) / 900, 1);
      el.textContent = Math.round(target * (1 - Math.pow(1 - p, 3)));
      if (p < 1) requestAnimationFrame(step);
    };
    el.textContent = "0";
    setTimeout(function () { requestAnimationFrame(step); }, 300);
  });

  // Sign-up stepper: fill each step as its required fields get values.
  document.querySelectorAll("[data-stepper]").forEach(function (stepper) {
    var form = stepper.closest("form") || document;
    var bars = stepper.querySelectorAll("[data-step]");
    var update = function () {
      bars.forEach(function (bar) {
        var fs = form.querySelector(bar.dataset.step);
        if (!fs) return;
        var fields = fs.querySelectorAll("input:not([type=hidden]), select");
        var done = 0;
        fields.forEach(function (f) { if ((f.type === "file" ? f.files.length : f.value)) done++; });
        var pct = fields.length ? Math.round(done / fields.length * 100) : 0;
        bar.style.setProperty("--p", pct + "%");
        bar.classList.toggle("is-on", pct > 0);
      });
    };
    form.addEventListener("input", update);
    form.addEventListener("change", update);
    update();
  });
})();
