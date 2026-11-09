// Shotwise · review UI behaviours (no build step, no framework).

// Copy-to-clipboard for [data-copy] buttons (keeps the original contract).
document.addEventListener("click", (e) => {
  const b = e.target.closest("[data-copy]");
  if (!b) return;
  const el = document.getElementById(b.dataset.copy);
  if (!el) return;
  navigator.clipboard.writeText(el.innerText).then(() => {
    const t = b.innerHTML;
    b.innerHTML = "Copied";
    b.classList.add("primary");
    setTimeout(() => { b.innerHTML = t; b.classList.remove("primary"); }, 1200);
  });
});

// Auto-dismiss the flash toast.
const f = document.getElementById("flash");
if (f) setTimeout(() => { f.style.transition = "opacity .3s"; f.style.opacity = "0"; setTimeout(() => f.remove(), 320); }, 4000);

// Keyframe art fallbacks: approved.png -> cand_1.png -> empty-art placeholder.
// Exposed globally because <img onerror> may fire before this deferred script runs;
// base.html defines a tiny inline shim that queues those early errors.
window.swFallback = function (img) {
  const fr = img.closest(".frame");
  const next = img.dataset.alt;
  if (next) { img.dataset.alt = ""; img.src = next; if (fr) fr.classList.add("is-fallback"); return; } // a non-approved frame: hide any 'locked' claim
  if (fr) fr.classList.add("is-empty");
};
if (window.__swErr && window.__swErr.length) { window.__swErr.forEach((img) => window.swFallback(img)); window.__swErr = []; }

// Candidate cards: clicking the artwork focuses its Approve button (quick review flow).
document.addEventListener("click", (e) => {
  const fr = e.target.closest(".media-item .frame");
  if (!fr) return;
  const btn = fr.closest(".media-item").querySelector("button");
  if (btn) btn.focus();
});

// Reject bar: a note is required; focus the field instead of posting an empty one.
document.querySelectorAll(".reject-bar form").forEach((form) => {
  form.addEventListener("submit", (ev) => {
    const note = form.querySelector("input[name=note]");
    if (note && !note.value.trim()) { ev.preventDefault(); note.focus(); note.placeholder = "A note is required"; }
  });
});

// Disable a submit button once its form is posted, so a double click cannot approve twice.
document.addEventListener("submit", (e) => {
  if (e.defaultPrevented) return;
  const btn = e.target.querySelector("button[type=submit], button:not([type])");
  if (btn) { btn.disabled = true; btn.style.opacity = ".6"; }
});

// Shot list layout toggle (thumbnail cards / dense table), remembered per browser.
const views = document.querySelector(".shotviews");
if (views) {
  const KEY = "sw.shotview";
  const apply = (v) => {
    views.dataset.view = v;
    document.querySelectorAll(".seg-btn[data-view]").forEach((b) => b.setAttribute("aria-pressed", b.dataset.view === v ? "true" : "false"));
  };
  let saved = null;
  try { saved = localStorage.getItem(KEY); } catch (_) { /* private mode */ }
  const forced = views.dataset.forced === "1"; // ?view=table|cards deep link wins over the remembered choice
  apply(!forced && (saved === "table" || saved === "cards") ? saved : views.dataset.default || "cards");
  document.querySelectorAll(".seg-btn[data-view]").forEach((b) => b.addEventListener("click", () => {
    apply(b.dataset.view);
    try { localStorage.setItem(KEY, b.dataset.view); } catch (_) { /* ignore */ }
  }));
}

// Scroll-spy: highlight the stage in view in the sticky shot bar.
const jumps = document.querySelectorAll(".jump a[href^='#']");
if (jumps.length && "IntersectionObserver" in window) {
  const map = new Map();
  jumps.forEach((a) => { const t = document.querySelector(a.getAttribute("href")); if (t) map.set(t, a); });
  const visible = new Set();
  const io = new IntersectionObserver((entries) => {
    entries.forEach((en) => { if (en.isIntersecting) visible.add(en.target); else visible.delete(en.target); });
    // exactly one tab is active: the intersecting section closest to the top of the viewport
    let best = null, bestY = Infinity;
    visible.forEach((t) => { const y = Math.abs(t.getBoundingClientRect().top); if (y < bestY) { bestY = y; best = t; } });
    map.forEach((a, t) => a.classList.toggle("on", t === best));
  }, { rootMargin: "-35% 0px -55% 0px" });
  map.forEach((_, t) => io.observe(t));
  jumps.forEach((a) => a.addEventListener("click", () => { jumps.forEach((x) => x.classList.remove("on")); a.classList.add("on"); }));
}

// Timestamps: the template prints '07 Oct · 18:43'; when the date is today or yesterday, say so instead.
// The full ISO string stays in the title attribute either way.
document.querySelectorAll("time.when[data-ts]").forEach((el) => {
  const d = new Date(el.dataset.ts);
  if (isNaN(d)) return;
  const now = new Date();
  const day = (x) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const diff = Math.round((day(now) - day(d)) / 86400000);
  const hm = String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0");
  if (diff === 0) el.textContent = "today " + hm;
  else if (diff === 1) el.textContent = "yesterday " + hm;
});

// Horizontal scrollers: show an arrow while there is more to the right, hide it at the end.
document.querySelectorAll(".scroller").forEach((wrap) => {
  const el = wrap.firstElementChild;
  if (!el) return;
  const update = () => {
    const can = el.scrollWidth > el.clientWidth + 2;
    wrap.classList.toggle("can-scroll", can);
    wrap.classList.toggle("at-end", !can || el.scrollLeft + el.clientWidth >= el.scrollWidth - 2);
  };
  el.addEventListener("scroll", update, { passive: true });
  window.addEventListener("resize", update);
  update();
  setTimeout(update, 300); // after web fonts settle
});
