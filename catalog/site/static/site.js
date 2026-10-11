// Theme toggle, copy buttons, and the home page's search, tag filter and
// sort (CAT-8 to CAT-10). No markup is built from data.
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
  if (["name", "published", "stars"].includes(params.get("sort"))) sort.value = params.get("sort");

  const tagsOf = (card) => card.dataset.tags.split(" ").filter(Boolean);
  const matches = (card, q, tags) => card.dataset.text.includes(q) && [...tags].every((t) => tagsOf(card).includes(t));
  const keys = {
    name: (a, b) => a.dataset.name.localeCompare(b.dataset.name),
    published: (a, b) => b.dataset.published.localeCompare(a.dataset.published) || keys.name(a, b),
    stars: (a, b) => Number(b.dataset.stars) - Number(a.dataset.stars) || keys.name(a, b),
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
