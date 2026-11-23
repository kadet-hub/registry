// Theme toggle, the counter on pages with a query (CAT-25a), the menu (CAT-9a) and the "Reference" disclosure (CAT-63a), the listing steps (CAT-62a), the harbour figure and the live edit of the start page, copy buttons, the version selector (CAT-34), sharing a post (CAT-36d), the recipe finder (CAT-37i), and the catalog's
// search, tag filter and sort at /generators/ (CAT-8 to CAT-10, CAT-9a, CAT-67b). No markup is built from data.
const root = document.documentElement;
const announce = (text) => { document.getElementById("announce").textContent = text; };

// Theme
const themeButton = document.getElementById("theme");
const dark = () => root.dataset.theme ? root.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
themeButton.hidden = false;
themeButton.setAttribute("aria-pressed", String(dark()));
themeButton.addEventListener("click", () => {
  const next = dark() ? "light" : "dark";
  root.dataset.theme = next;
  themeButton.setAttribute("aria-pressed", String(next === "dark"));
  try { localStorage.setItem("theme", next); } catch (e) { /* not remembered */ }
});

// CAT-9a: on narrow screens the nav opens from the menu button; Escape closes it.
const header = document.querySelector("header.site");
const menuButton = document.getElementById("menu");
const setMenu = (open) => {
  header.dataset.menu = open ? "open" : "closed";
  menuButton.setAttribute("aria-expanded", String(open));
};
menuButton.hidden = false;
setMenu(false);
menuButton.addEventListener("click", () => setMenu(header.dataset.menu === "closed"));
// CAT-63a: the open "Reference" disclosure closes on Escape, before the menu around it, and when focus leaves it.
const reference = header.querySelector(".reference");
header.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  if (reference.open) { reference.open = false; reference.querySelector("summary").focus(); }
  else if (header.dataset.menu === "open") { setMenu(false); menuButton.focus(); }
});
reference.addEventListener("focusout", (e) => { if (!reference.contains(e.relatedTarget)) reference.open = false; });

// CAT-25a: count.js sends location.search with every count, so on a page whose URL can carry a query (no_onload) the view
// is counted here at a moment the URL holds none: the URL is replaced by its path, counted, and the query put back.
// count.js stands after this script and loads async, so it may have run or not by the time the document is parsed.
addEventListener("DOMContentLoaded", () => {
  const counter = document.querySelector("script[data-goatcounter-settings]");
  if (!counter) return;
  const count = () => {
    const query = location.search;
    history.replaceState(history.state, "", location.pathname + location.hash);
    window.goatcounter.count();
    history.replaceState(history.state, "", location.pathname + query + location.hash);
  };
  if (window.goatcounter?.count) count();
  else counter.addEventListener("load", count);
});

// Version permalinks (CAT-17): open the version a #v<version> link points to.
function openVersion() {
  const target = location.hash && document.getElementById(decodeURIComponent(location.hash.slice(1)));
  if (target && target.tagName === "DETAILS") {
    target.open = true;
    target.scrollIntoView();
  }
}
addEventListener("hashchange", openVersion);
openVersion();

// CAT-62a: below 48rem the start page's listing steps are collapsed under their heading.
// It follows the breakpoint when a phone rotates or a window resizes, as the stylesheet does.
const route = document.querySelector(".route");
if (route) {
  const wide = matchMedia("(min-width: 48rem)");
  const follow = () => { route.open = wide.matches; };
  follow();
  wide.addEventListener("change", follow);
}

// The harbour figure. With motion allowed, the five stations become tabs over one panel and a station in the drawing selects
// its tab. The run plays once when the drawing has come into view, each station for as long as its own motion takes, and stops
// on Pause, when the pointer moves over a station or when focus enters the tabs (WCAG 2.2.2). Until it starts nothing moves.
// Without JavaScript or with reduced motion the stations stay listed.
const harbour = document.querySelector(".harbour");
if (harbour && !matchMedia("(prefers-reduced-motion: reduce)").matches) {
  const panels = [...harbour.querySelectorAll(".station")];
  const tablist = harbour.querySelector(".station-tabs");
  const tabs = [...tablist.children];
  const marks = [...harbour.querySelectorAll(".scene [data-station]")];
  const play = harbour.querySelector(".scene-play");
  const frame = harbour.querySelector(".scene-frame");
  const whole = harbour.querySelector(".scene-whole");
  let at = 0;
  let timer = null;
  // The selected station runs its motion; what the earlier stations did stays done, and the later ones have not happened.
  // The frame names the station too: the truck's rules and, below 48rem, the drawing's window hang on it.
  const mark = (n) => {
    for (const m of marks) {
      m.classList.toggle("on", Number(m.dataset.station) === n);
      m.classList.toggle("done", Number(m.dataset.station) < n);
    }
    frame.dataset.at = n;
  };
  const show = (n) => {
    at = n;
    panels.forEach((p, i) => p.classList.toggle("on", i + 1 === n));
    tabs.forEach((t, i) => {
      t.setAttribute("aria-selected", String(i + 1 === n));
      t.tabIndex = i + 1 === n ? 0 : -1;
    });
    mark(n);
  };
  // Runs the selected station's motion once more: without its marks for one style pass, the animations start anew.
  const replay = () => { mark(0); void frame.offsetWidth; mark(at); };
  const stop = () => { clearTimeout(timer); timer = null; play.textContent = "Play"; };
  // Each station stays for as long as its own motion takes (data-ms); after the last one the run is over.
  const step = () => {
    timer = setTimeout(() => {
      if (at === panels.length) return stop();
      show(at + 1);
      step();
    }, Number(panels[at - 1].dataset.ms));
  };
  const start = () => {
    harbour.classList.remove("idle");
    if (at === panels.length) show(1);
    else replay(); // the run starts with the motion of the station it stands on
    play.textContent = "Pause";
    step();
  };
  const go = (n) => { harbour.classList.remove("idle"); stop(); show(n); };

  tablist.setAttribute("role", "tablist");
  harbour.querySelector(".stations").setAttribute("role", "presentation");
  tabs.forEach((t, i) => {
    t.setAttribute("role", "tab");
    t.id = `station-tab-${i + 1}`;
    t.setAttribute("aria-controls", panels[i].id);
    panels[i].setAttribute("role", "tabpanel");
    panels[i].setAttribute("aria-labelledby", t.id);
    t.addEventListener("click", () => go(i + 1));
  });
  // Tabs with automatic activation: the arrow keys move the focus, and the focused tab is the selected one.
  tablist.addEventListener("focusin", (e) => { const i = tabs.indexOf(e.target.closest(".station-tab")); if (i >= 0 && (timer || i + 1 !== at)) go(i + 1); });
  tablist.addEventListener("keydown", (e) => {
    const to = { ArrowRight: at % tabs.length, ArrowLeft: (at + tabs.length - 2) % tabs.length, Home: 0, End: tabs.length - 1 }[e.key];
    if (to === undefined) return;
    e.preventDefault();
    tabs[to].focus();
  });
  // A station's parts lie inside each other (the cargo on the ship), so the innermost one under the pointer decides.
  harbour.querySelector(".scene-window").addEventListener("click", (e) => { const m = e.target.closest("[data-station]"); if (m) go(Number(m.dataset.station)); });
  // A pointer that rests where the figure scrolls in does not count; one that moves over a station does.
  harbour.addEventListener("pointermove", (e) => { if (timer && (e.movementX || e.movementY) && e.target.closest("[data-station], .station-tab")) stop(); });
  play.addEventListener("click", () => (timer ? stop() : start()));

  // Below 48rem the frame shows one station's window, and the tabs stand above it, so drawing and text share a view.
  // The button opens the whole drawing and closes it again.
  const narrow = matchMedia("(width < 48rem)");
  const place = () => (narrow.matches ? frame.before(tablist) : frame.after(tablist));
  place();
  narrow.addEventListener("change", place);
  whole.addEventListener("click", () => {
    const open = frame.classList.toggle("whole");
    whole.setAttribute("aria-expanded", String(open));
    whole.textContent = open ? "Show one station" : "Show whole harbour";
    if (!open) frame.scrollIntoView({ block: "nearest" });
  });

  harbour.classList.add("live", "idle");
  play.hidden = false;
  whole.hidden = false;
  show(1);
  // A terminal taller than its panel scrolls inside it: it takes the keyboard, and a button at its faded end names the lines left.
  for (const pre of harbour.querySelectorAll(".term pre")) {
    if (pre.scrollHeight <= pre.clientHeight + 4) continue;
    const term = pre.parentElement;
    const lines = [...pre.querySelectorAll(".ln, .fold")];
    const more = document.createElement("div");
    const button = document.createElement("button");
    more.className = "term-more";
    button.type = "button";
    more.append(button);
    term.append(more);
    pre.tabIndex = 0;
    pre.setAttribute("role", "group");
    pre.setAttribute("aria-label", "Commands and output, scrolls");
    const left = () => {
      const edge = pre.scrollTop + pre.clientHeight;
      const n = lines.filter((l) => l.offsetTop + l.offsetHeight > edge + 2).length;
      term.classList.toggle("at-end", edge >= pre.scrollHeight - 4);
      button.textContent = `${n} more line${n === 1 ? "" : "s"} ↓`;
    };
    button.addEventListener("click", () => pre.scrollBy({ top: pre.clientHeight * 0.8, behavior: "smooth" }));
    pre.addEventListener("scroll", left, { passive: true });
    left();
  }
  // The run starts once almost all of the drawing is in view, or once it fills a viewport that is shorter than itself.
  const seen = new IntersectionObserver((entries) => {
    const e = entries[entries.length - 1];
    if (e.intersectionRatio >= 0.9 || e.intersectionRect.height >= innerHeight * 0.9) { seen.disconnect(); if (harbour.classList.contains("idle")) start(); }
  }, { threshold: [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1] });
  seen.observe(frame.querySelector(".scene-window"));
}

// The live edit: the two values go into the marked places of the excerpts as text. Nothing is read from the URL, stored or sent.
const liveEdit = document.querySelector(".live-edit");
if (liveEdit) {
  const bucket = liveEdit.querySelector("#le-bucket");
  const region = liveEdit.querySelector("#le-region");
  const put = (key, value) => { for (const m of liveEdit.querySelectorAll(`mark[data-le="${key}"]`)) m.textContent = value; };
  // CAT-68d: the field's pattern, compiled as the browser compiles it, so a value fits exactly when the field is valid.
  const pattern = new RegExp(`^(?:${bucket.pattern})$`, "v");
  const fits = (v) => pattern.test(v);
  const regions = [...region.options].map((o) => o.value);
  for (const line of liveEdit.querySelectorAll(".le-static")) line.hidden = true;
  liveEdit.querySelector(".le-fields").hidden = false;
  bucket.addEventListener("input", () => {
    const ok = fits(bucket.value);
    bucket.setAttribute("aria-invalid", String(!ok));
    if (ok) put("bucket", bucket.value);
  });
  region.addEventListener("change", () => { if (regions.includes(region.value)) put("region", region.value); });
}

// CAT-19: the table of contents is collapsed on narrow screens and marks the section in view.
const toc = document.querySelector(".toc details");
if (toc) {
  if (!matchMedia("(min-width: 78rem)").matches) toc.open = false;
  const links = new Map([...toc.querySelectorAll("a")].map((a) => [a.hash.slice(1), a]));
  const seen = new Set();
  const mark = () => {
    const current = [...links.keys()].find((id) => seen.has(id));
    if (!current) return; // between headings: keep the last mark
    for (const [id, a] of links) {
      if (id === current) a.setAttribute("aria-current", "true");
      else a.removeAttribute("aria-current");
    }
  };
  const observer = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (e.isIntersecting) seen.add(e.target.id);
      else seen.delete(e.target.id);
    }
    mark();
  }, { rootMargin: "0px 0px -60% 0px" });
  for (const id of links.keys()) {
    const el = document.getElementById(id);
    if (el) observer.observe(el);
  }
}

// Code keeps its lines. A block wider than its box scrolls sideways: it takes the keyboard, and a shade stands at its
// right edge while more follows there.
const wide = new ResizeObserver((entries) => { for (const e of entries) markWide(e.target); });
function markWide(pre) {
  const over = pre.scrollWidth > pre.clientWidth + 1;
  pre.classList.toggle("scroll-x", over);
  pre.classList.toggle("more-x", over && pre.scrollWidth - pre.clientWidth - pre.scrollLeft > 1);
  if (over && !pre.hasAttribute("tabindex")) pre.tabIndex = 0;
}
for (const pre of document.querySelectorAll("pre")) {
  wide.observe(pre);
  pre.addEventListener("scroll", () => markWide(pre), { passive: true });
}

// Copy buttons
for (const button of document.querySelectorAll("button.copy")) {
  if (!navigator.clipboard) continue;
  button.hidden = false;
  button.addEventListener("click", async () => {
    const text = document.getElementById(button.dataset.copy).textContent;
    try {
      await navigator.clipboard.writeText(text);
      button.classList.add("done");
      announce("Copied " + button.getAttribute("aria-label").replace(/^Copy /, ""));
      setTimeout(() => button.classList.remove("done"), 1500);
    } catch (e) {
      announce("Copy failed; select the text instead");
    }
  });
}

// CAT-34: "I run <software> <version>" over the versions table; rows are shown or hidden, the result is text.
const match = document.querySelector(".match-form");
if (match) {
  const { software, version } = match.elements;
  const result = document.querySelector(".match-result");
  const rows = [...document.querySelectorAll(".built tbody tr")];
  const trim = (v) => v.trim().replace(/^v(?=[0-9])/, "");
  const numbers = (v) => (/^[0-9]+(\.[0-9]+)*$/.test(trim(v)) ? trim(v).split(".").map(Number) : null);
  const compare = (a, b) => {
    for (let i = 0; i < Math.max(a.length, b.length); i++) if ((a[i] || 0) !== (b[i] || 0)) return (a[i] || 0) - (b[i] || 0);
    return 0;
  };
  const builtFor = (row) => [...row.querySelectorAll("[data-software]")].filter((e) => e.dataset.software === software.value).map((e) => e.dataset.version);
  const names = (shown) => {
    const n = shown.map((r) => r.querySelector("th").textContent);
    return n.length > 1 ? n.slice(0, -1).join(", ") + " and " + n[n.length - 1] : n[0];
  };

  function apply() {
    version.setAttribute("list", software.selectedOptions[0].dataset.list);
    const typed = version.value.trim();
    const run = `${software.value} ${typed}`;
    const exact = rows.filter((r) => builtFor(r).some((v) => trim(v) === trim(typed)));
    let shown = exact;
    let text = `Built for ${run}: ${names(exact)}.`;
    if (!typed) {
      shown = rows;
      text = "";
    } else if (!exact.length) {
      const own = numbers(typed);
      const newer = own && [...new Set(rows.flatMap(builtFor))].filter((v) => numbers(v) && compare(numbers(v), own) > 0)
        .sort((a, b) => compare(numbers(a), numbers(b)))[0];
      text = `No listed version is built for ${run}. `;
      if (newer) {
        shown = rows.filter((r) => builtFor(r).includes(newer));
        text += `Shown instead: the versions built for the nearest newer ${software.value} version, ${newer} (${names(shown)}). They were not checked against ${run}.`;
      } else {
        text += own ? `None is built for a newer ${software.value} version either.` : "Only versions of digits and dots, such as 1.21.2, are compared to find a newer one.";
      }
    }
    for (const r of rows) r.hidden = !shown.includes(r);
    result.textContent = text;
    result.classList.toggle("warning", typed !== "" && !exact.length);
  }

  match.hidden = false;
  match.addEventListener("submit", (e) => e.preventDefault());
  software.addEventListener("change", apply);
  version.addEventListener("input", apply);
  apply();
}

// CAT-36d: on a post, sharing on Mastodon through the visitor's server, and the browser's share menu.
const share = document.querySelector(".share");
if (share) {
  const { title, url } = share.dataset;
  const native = share.querySelector(".share-native");
  if (navigator.share) {
    native.hidden = false;
    native.addEventListener("click", () => navigator.share({ title, url }).catch(() => { /* closed: the links remain */ }));
  }
  const mastodon = share.querySelector(".share-mastodon");
  const server = mastodon.elements.server;
  try { server.value = localStorage.getItem("mastodon") || ""; } catch (e) { /* storage blocked: ask each time */ }
  mastodon.hidden = false;
  mastodon.addEventListener("submit", (e) => {
    e.preventDefault();
    const host = server.value.trim();
    try { localStorage.setItem("mastodon", host); } catch (e) { /* not remembered */ }
    window.open(`https://${host}/share?text=${encodeURIComponent(`${title} ${url}`)}`, "_blank", "noopener,noreferrer");
  });
}

// CAT-37i: /recipes/ shows the entries that contain every typed word; entries are hidden, the count is text.
const recipeSearch = document.getElementById("recipe-search");
if (recipeSearch) {
  const entries = [...document.querySelectorAll(".guide-list > li")];
  const texts = entries.map((li) => li.textContent.replace(/\s+/g, " ").toLowerCase());
  const result = document.getElementById("recipe-result");
  // A word from a digit, or v and a digit, is a version and an @ starts a digest: a recipe pins one chart version, the reader runs another.
  const words = (q) => q.toLowerCase().replace(/@\S*/g, " ").split(/[\s/:]+/).filter((w) => w && !/^v?[0-9]/.test(w));

  function apply() {
    const q = recipeSearch.value.trim();
    const typed = words(q);
    let shown = 0;
    entries.forEach((li, i) => {
      li.hidden = !typed.every((w) => texts[i].includes(w));
      if (!li.hidden) shown++;
    });
    result.textContent = q ? `${shown} of ${entries.length} recipes matching “${q}”` : "";
    document.getElementById("recipe-empty").hidden = shown > 0;
    history.replaceState(null, "", q ? "?q=" + encodeURIComponent(q) : location.pathname);
  }

  recipeSearch.value = new URLSearchParams(location.search).get("q") || "";
  recipeSearch.closest(".recipe-find").hidden = false;
  recipeSearch.addEventListener("input", apply);
  document.getElementById("recipe-reset").addEventListener("click", () => { recipeSearch.value = ""; apply(); recipeSearch.focus(); });
  apply();
}

// The catalog at /generators/; the start page's search sends ?q= here (CAT-67b).
const search = document.getElementById("search");
if (search) {
  const list = document.querySelector(".cards");
  const cards = [...list.children];
  const buttons = [...document.querySelectorAll("#tags button[data-tag]")];
  const clear = document.getElementById("clear");
  const sort = document.getElementById("sort");
  const result = document.getElementById("result");
  const filters = document.querySelector(".filters");
  const tagToggle = document.getElementById("tag-toggle");
  const setTags = (open) => {
    filters.dataset.tags = open ? "open" : "closed";
    tagToggle.setAttribute("aria-expanded", String(open));
  };
  tagToggle.hidden = false;
  setTags(false);
  tagToggle.addEventListener("click", () => setTags(filters.dataset.tags === "closed"));
  const params = new URLSearchParams(location.search);
  const known = new Set(buttons.map((b) => b.dataset.tag));
  let selected = new Set((params.get("tags") || "").split(",").filter((t) => known.has(t)));
  search.value = params.get("q") || "";
  if (["name", "published", "popularity"].includes(params.get("sort"))) sort.value = params.get("sort");

  const tagsOf = (card) => card.dataset.tags.split(" ").filter(Boolean);
  const matches = (card, q, tags) => card.dataset.text.includes(q) && [...tags].every((t) => tagsOf(card).includes(t));
  const keys = {
    name: (a, b) => a.dataset.name.localeCompare(b.dataset.name),
    published: (a, b) => b.dataset.published.localeCompare(a.dataset.published) || keys.name(a, b),
    popularity: (a, b) => Number(b.dataset.popularity) - Number(a.dataset.popularity) || keys.name(a, b),
  };

  function apply() {
    const q = search.value.trim().toLowerCase();
    let shown = 0;
    for (const card of cards) {
      card.hidden = !matches(card, q, selected);
      if (!card.hidden) shown++;
    }
    for (const b of buttons) {
      const on = selected.has(b.dataset.tag);
      const next = new Set(selected); next.add(b.dataset.tag);
      const count = cards.filter((c) => matches(c, q, next)).length;
      b.setAttribute("aria-pressed", String(on));
      b.disabled = !on && count === 0;
    }
    clear.hidden = selected.size === 0;
    tagToggle.querySelector(".count").textContent = selected.size ? `(${selected.size})` : "";
    const tagText = [...selected].join(" and ");
    result.textContent = `${shown} generator${shown === 1 ? "" : "s"}${tagText ? " tagged " + tagText : ""}${q ? ` matching “${q}”` : ""}`;
    document.getElementById("empty").hidden = shown > 0;
    list.append(...[...cards].sort(keys[sort.value]));

    const p = new URLSearchParams();
    if (selected.size) p.set("tags", [...selected].join(","));
    if (q) p.set("q", search.value.trim());
    if (sort.value !== "name") p.set("sort", sort.value);
    const s = p.toString().replaceAll("%2C", ",");
    history.replaceState(null, "", s ? "?" + s : location.pathname);
  }

  search.addEventListener("input", apply);
  sort.addEventListener("change", apply);
  for (const b of buttons) {
    b.addEventListener("click", () => {
      selected.has(b.dataset.tag) ? selected.delete(b.dataset.tag) : selected.add(b.dataset.tag);
      apply();
    });
  }
  const reset = () => { selected = new Set(); search.value = ""; apply(); search.focus(); };
  clear.addEventListener("click", reset);
  document.getElementById("reset").addEventListener("click", reset);
  apply();
}
