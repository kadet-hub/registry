// PG-23: highlights read-only output with Prism. The page builds the spans from
// Prism's tokens, so no markup string reaches innerHTML. Loaded after the start.
globalThis.Prism = { manual: true };
await import("./prism/prism-core.min.js");
// Markdown extends markup's grammar, so markup loads first.
for (const name of ["markup", "markdown", "yaml", "json"]) await import(`./prism/prism-${name}.min.js`);

const languages = { yml: "yaml", yaml: "yaml", json: "json", md: "markdown" };

function append(parent, tokens) {
  for (const t of tokens) {
    if (typeof t === "string") {
      parent.append(t);
    } else {
      const span = document.createElement("span");
      span.className = ["token", t.type, ...[].concat(t.alias ?? [])].join(" ");
      append(span, [].concat(t.content));
      parent.append(span);
    }
  }
}

// Writes text into pre, highlighted by the language its file name's extension names.
export function highlight(pre, text, name) {
  const grammar = globalThis.Prism.languages[languages[name.split(".").pop()]];
  if (!grammar) {
    pre.textContent = text;
    return;
  }
  pre.replaceChildren();
  append(pre, globalThis.Prism.tokenize(text, grammar));
}
