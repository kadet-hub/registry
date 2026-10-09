// Filter the cards by text and tag; no markup is built from data.
const search = document.getElementById("search");
const cards = [...document.querySelectorAll(".card")];
const buttons = [...document.querySelectorAll("#tags button")];
let tag = null;

function apply() {
  const q = search.value.trim().toLowerCase();
  let shown = 0;
  for (const card of cards) {
    const ok = card.dataset.text.includes(q) && (!tag || card.dataset.tags.split(" ").includes(tag));
    card.hidden = !ok;
    if (ok) shown++;
  }
  document.getElementById("empty").hidden = shown > 0;
}

search.addEventListener("input", apply);
for (const b of buttons) {
  b.addEventListener("click", () => {
    tag = tag === b.dataset.tag ? null : b.dataset.tag;
    for (const other of buttons) other.classList.toggle("active", other.dataset.tag === tag);
    apply();
  });
}
