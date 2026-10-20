// Theme toggle, copy buttons, the version selector (CAT-34), sharing a post (CAT-36d), and the home page's
// search, tag filter and sort (CAT-8 to CAT-10). No markup is built from data.
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

// Home page
const search = document.getElementById("search");
if (search) {
  const list = document.querySelector(".cards");
  const cards = [...list.children];
  const buttons = [...document.querySelectorAll("#tags button[data-tag]")];
  const clear = document.getElementById("clear");
  const sort = document.getElementById("sort");
  const result = document.getElementById("result");
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
