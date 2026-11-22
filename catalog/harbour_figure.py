#!/usr/bin/env python3
"""Writes the harbour figure (CAT-66) and the live edit (CAT-68) of the start page from the recorded run.

    python3 catalog/harbour_figure.py [SITE]

SITE defaults to catalog/site. The script reads SITE/assets/harbour/run/ and writes
SITE/layouts/_partials/harbour.html and live-edit.html. Every line of a panel is a line of the recording, chosen
by the line ranges in STATIONS and LIVE. Three things change how a line is shown, and the figure's note names them
(CAT-66o): temporary paths read <tmp> in the recording already, a sha256 digest shows its first and last eight
characters (CAT-64; the whole digest stays in the text and in its title), and a command longer than 100 characters
is folded at its flags with a continuation backslash (CAT-66n).

A line of more than 28 characters carries its words as spans (tk) and its indentation as a class (i<n>), which the
stylesheet uses below 48rem: there a line wraps between these spans with a hanging indent (CAT-9, CAT-9g). A word of
more than 24 characters cannot fit beside anything, so it is given as several spans, cut after a slash, an @, a comma
or a JSON key.
"""
import html
import pathlib
import re
import sys

SITE = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path(__file__).parent / "site"
RUN = SITE / "assets" / "harbour" / "run"
OUT = SITE / "layouts" / "_partials"
README = (RUN / "README.md").read_text()
DATE = re.search(r"Recorded on (\d{4}-\d\d-\d\d)\.", README).group(1)
KAPITAN = re.search(r"Kapitan (\d+\.\d+\.\d+)", README).group(1)
log = (RUN / "session.log").read_text().rstrip("\n").split("\n")
files = {p: (RUN / p).read_text().rstrip("\n").split("\n") for p in (
    "inventory/targets/prod.yml", "inventory/classes/generators.yml", "compiled/prod/manifests/shop/web-cm.yml",
    "compiled/prod/terraform/bucket-uploads.tf.json", "compiled/prod/terraform/providers.tf.json")}

DG = re.compile(r"sha256:([0-9a-f]{8})([0-9a-f]{48})([0-9a-f]{8})")
SWITCH = {"--no-tty", "--no-same-owner", "-r"}   # flags without a value
FOLD = 100                                       # CAT-66n: a longer command is folded at its flags


def shown(text):
    """The text as a panel shows it: every digest at 24 characters."""
    return DG.sub("sha256:" + "x" * 17, text)


def dg(escaped):
    return DG.sub(r'<span class="dg" title="sha256:\1\2\3">sha256:\1<span class="dg-e"></span><span class="dg-m">\2</span>\3</span>', escaped)


def fold_cmd(line):
    """A long command as rows: the command, then one row per flag with its value and one per argument after the flags."""
    if not line.startswith("$ ") or len(shown(line)) <= FOLD:
        return [line]
    toks = line[2:].split(" ")
    rows, i = [], 0
    head = []
    while i < len(toks) and not toks[i].startswith("-") and "://" not in toks[i]:
        head.append(toks[i])
        i += 1
    rows.append("$ " + " ".join(head))
    while i < len(toks):
        row = [toks[i]]
        if toks[i].startswith("-") and toks[i] not in SWITCH and i + 1 < len(toks):
            i += 1
            row.append(toks[i])
        rows.append("    " + " ".join(row))
        i += 1
    assert " ".join(r.strip() for r in rows) == line, line
    return [r + " \\" for r in rows[:-1]] + rows[-1:]


def row(text, cls, mark=None):
    """One line of a panel. mark: (key, value) of the live edit, the value inside the line."""
    def enc(word):
        body = dg(html.escape(word, quote=False))
        if mark and mark[1] in body:
            body = body.replace(mark[1], f'<mark data-le="{mark[0]}">{mark[1]}</mark>')
        return body
    indent = len(text) - len(text.lstrip(" "))
    if len(shown(text)) > 28:
        def word(w):
            pieces = re.findall(r'.+?(?:/+|@|,|":|$)', w) if len(shown(w)) > 24 else [w]
            assert "".join(pieces) == w, w
            return "".join(f'<span class="tk">{enc(piece)}</span>' for piece in pieces)
        body = " " * indent + "".join(part if part.isspace() else word(part) for part in re.split(r"( +)", text.strip(" ")) if part)
    else:
        body = enc(text)
    assert not mark or body.count("<mark") == 1, text
    return f'<span class="{cls} cl{f" i{indent}" if indent else ""}">{body}</span>'


def gap(k, why=""):
    return f'<span class="fold">⋯ {k} line{"s" if k != 1 else ""}{why}</span>'


def lines(src, show, last=None, marks=None, why=None):
    """show: 1-based line numbers to print; every gap becomes a fold with its count."""
    out, prev, last = [], 0, last or len(src)
    for i in sorted(show) + [last + 1]:
        if i - prev - 1 > 0:
            out.append(gap(i - prev - 1, (why or {}).get(prev + 1, "")))
        if i <= last:
            for text in fold_cmd(src[i - 1]):
                cls = "ln"
                if src[i - 1].startswith("$ "):
                    cls += " cmd"
                if text.startswith("✓"):
                    cls += " ok"
                out.append(row(text, cls, (marks or {}).get(i)))
        prev = i
    return "".join(out)


def term(title, body, kind="term"):
    return f'<div class="term dark-panel{" file" if kind == "file" else ""}"><p class="term-title">{title}</p><pre><code>{body}</code></pre></div>'


def file(path, show, **kw):
    return term(path, lines(files[path], show, **kw), "file")


def whole(digest):
    """CAT-64a: a whole digest in two halves, which stand on one line where they fit and under each other where not."""
    h = digest.removeprefix("sha256:")
    assert len(h) == 64
    return f'<code class="digest sha"><span>sha256:{h[:32]}</span><span>{h[32:]}</span></code>'


PINS = re.findall(r"source: ghcr\.io/kadet-hub/([a-z-]+):([0-9.]+)@(sha256:[0-9a-f]{64})", "\n".join(files["inventory/classes/generators.yml"]))
assert [p[0] for p in PINS] == ["kubernetes", "terraform-aws"]
recorded = (f'<div class="pins"><p>Recorded on {DATE}, not necessarily the latest version</p><dl>'
            + "".join(f"<div><dt>{name} {version}</dt><dd>{whole(digest)}</dd></div>" for name, version, digest in PINS) + "</dl></div>")

# The lines of session.log each station shows: station 2 the checks of both pins, station 3 both fetches, station 4 the compile.
S2 = [1, 6, 16, 21, 22, 26, 27, 28, 29, 30, 40, 45, 46, 60, 61, 62, 72]
S3 = [50, 51, 54, 55, 59, 82, 83, 86, 87, 91]
S4 = [92, 93, 94, 95, 96]
STEP = (2500, 2800, 3900, 2400, 2400)   # CAT-66a: how long the run stays on each station, in milliseconds: its motion and a rest
STATIONS = [
    (1, "Inventory", "Harbour office", "", "Your project",
     '<p>The target <code>prod</code> takes the classes <code>generators</code> and <code>uploads</code> and sets <code>bucket</code> and <code>region</code> once. The class <code>generators</code> pins two generators from kadet-hub, each by version and digest. The next stations check and fetch these two pins.</p>' + recorded,
     file("inventory/targets/prod.yml", [1, 2, 3, 4]) + file("inventory/classes/generators.yml", [6, 7, 8, 9, 10, 11, 12])),
    (2, "Verify", "Customs gate", "hub", "kadet-hub",
     ('<p>Before anything is fetched, the consumer workflow downloads kadet-hub\'s index, verifies its attestation and reads its serial, 147. It looks up each pin: the index must list the digest under the pinned version, and not as yanked. Then <code>gh attestation verify</code> runs once per digest.</p>'
     '<p>A pass proves that the release workflow of kadet-hub/registry built the artifact with this digest. It does not prove that a generator is harmless in your project, so review the compiled output before you apply it. '
     '<a href="{{ $gh }}/registry/blob/main/docs/consumers.md#what-a-listing-covers">What a listing covers</a> names what the checks look at.</p>'),
     term("Terminal", lines(log, S2, last=81).replace("⋯ 13 lines", "⋯ 3 lines, then 10 lines of the fetch (station 3)"))),
    (3, "Fetch", "Crane", "hub", "kadet-hub",
     ('<p>The workflow pulls each artifact by its digest with <code>oras pull</code> and unpacks it with <code>tar -xf</code> into <code>lib/kubernetes</code> and <code>lib/terraform-aws</code>.</p>'
     f'<p>Kapitan does not fetch here. Kapitan {KAPITAN} verifies nothing itself, neither digests nor attestations, so the compile that follows runs without <code>--fetch</code>.</p>'),
     term("Terminal", lines(log[49:91], [i - 49 for i in S3], why={11: ": the check of the second pin (station 2)"}))),
    (4, "Generators", "Ship Kapitan", "kapitan", "Kapitan",
     '<p><code>kapitan compile</code> renders the inventory and compiles the target. For each <code>kapitan.compile</code> entry with <code>input_type: kadet</code>, Kapitan imports the generator from <code>lib/</code> and calls its <code>main()</code>. Each generator reads its own parameters from the inventory: kubernetes writes YAML to <code>manifests/</code>, terraform-aws JSON to <code>terraform/</code>.</p>',
     term("Terminal", lines(log[91:96], [i - 91 for i in S4])) + file("inventory/classes/generators.yml", [13, 14, 15])),
    (5, "Output", "Two islands", "kapitan", "Kapitan",
     '<p>The files land under <code>compiled/prod/</code>: three Kubernetes manifests in <code>compiled/prod/manifests/shop/</code>, and two Terraform JSON files with the provider lock file in <code>compiled/prod/terraform/</code>. The bucket and the region that the target sets once arrive in both. <a href="#live-edit">Change them below.</a></p>',
     file("compiled/prod/manifests/shop/web-cm.yml", [1, 2, 3, 4, 5]) + file("compiled/prod/terraform/bucket-uploads.tf.json", [11, 12, 13])
     + file("compiled/prod/terraform/providers.tf.json", [2, 3, 4])),
]
assert len(log) == 96, "the station ranges count the lines of session.log"
assert STATIONS[1][6].count("then 10 lines of the fetch") == 1, "station 2: the fold over the fetch"
indents = sorted({int(n) for st in STATIONS for n in re.findall(r' cl i(\d+)"', st[6])})
assert set(indents) <= set(range(1, 13)), indents   # the stylesheet has i1 to i12


def main():
    tabs = "".join(f'<button type="button" class="station-tab" data-go="{i}"><span class="station-n">{i}</span><span><b>{name}</b><small>{place}</small></span></button>'
                   for i, name, place, *_ in STATIONS)
    items = "".join(
        f'\n    <li class="station" id="station-{i}" data-n="{i}" data-ms="{STEP[i - 1]}">\n      {{{{ partial "harbour-crop.html" {i} }}}}\n'
        f'      <div class="station-text"><h3><span class="station-n">{i}</span>{name} <small>{place}</small></h3>'
        f'<span class="who {cls}">{who}</span><div class="station-copy">{text}</div></div>\n      <div class="station-out">{out}</div>\n    </li>'
        for i, name, place, cls, who, text, out in STATIONS)
    harbour = f'''{{{{/* Written by catalog/harbour_figure.py from the recorded run in assets/harbour/run/ (CAT-66). Without JavaScript or with reduced motion the five stations stand in order; site.js turns them into tabs. The drawings and the phone's windows come from catalog/harbour_scene.py. */}}}}
{{{{ $gh := printf "https://github.com/%s" site.Data.catalog.owner }}}}
<section class="harbour wrap" aria-labelledby="harbour-title">
  <h2 id="harbour-title" class="visually-hidden">One compile in five stations</h2>
  <div class="scene-frame">
    <div class="scene-window">
      {{{{ partial "harbour-wide.html" . }}}}
      {{{{ partial "harbour-narrow.html" . }}}}
    </div>
    <div class="scene-bar"><button type="button" class="button scene-whole" aria-expanded="false" hidden>Show whole harbour</button><button type="button" class="button scene-play" hidden>Play</button></div>
  </div>
  <div class="station-tabs" aria-label="Stations of the compile">{tabs}</div>
  <ol class="stations">{items}
  </ol>
  <p class="note station-note">The <a href="{{{{ $gh }}}}/examples/tree/main/helm-vs-terraform">helm-vs-terraform</a> example of kadet-hub/examples, recorded on {DATE} with Kapitan {KAPITAN}. Commands, output and file lines are copied from that run, with temporary paths shortened to <code>&lt;tmp&gt;</code>; ⋯ marks lines left out. In the panels a digest is shortened to its first and last eight characters, and a long command is folded at its flags. Each whole digest stands in station 1. On a narrow screen a long line continues indented on the next one.</p>
</section>
'''
    (OUT / "harbour.html").write_text(harbour)

    bucket, region = "example-shop-uploads-prod", "eu-central-1"
    target = files["inventory/targets/prod.yml"]
    assert target[2] == f"  bucket: {bucket}" and target[3] == f"  region: {region}"
    # CAT-68d: 3 to 63 characters, a letter first, lowercase letters, digits and hyphens, no hyphen last, no YAML 1.1 keyword.
    pattern = r"(?!(?:y|n|yes|no|on|off|true|false|null)$)[a-z][a-z0-9\-]{1,61}[a-z0-9]"

    def cube(fam):
        return (f'<svg viewBox="0 -3 80 86" aria-hidden="true"><path class="h-{fam}-t" d="M0 20 40-3 80 20 40 43Z"/>'
                f'<path class="h-{fam}-l" d="M0 20 40 43v40L0 60Z"/><path class="h-{fam}-r" d="M40 43 80 20v40L40 83Z"/></svg>')
    web, uploads, providers = (f"compiled/prod/{p}" for p in ("manifests/shop/web-cm.yml", "terraform/bucket-uploads.tf.json", "terraform/providers.tf.json"))
    live = f'''{{{{/* Written by catalog/harbour_figure.py (CAT-68). site.js puts the two values into excerpts of the recorded run's files, as text. Without JavaScript the run's values stand as text and the fields stay hidden. */}}}}
<section class="live-edit band" id="live-edit" aria-labelledby="live-edit-title">
<div class="wrap">
  <div>
    <h2 id="live-edit-title">Change the target, watch both islands</h2>
    <p class="lead">The target sets <code>bucket</code> and <code>region</code> once. Both generators read them, so the same values arrive in a ConfigMap and in Terraform JSON.</p>
  </div>
  <div class="le-grid">
    <div class="le-target dark-panel">
      <p class="term-title">inventory/targets/prod.yml</p>
      <pre><code>{row(target[0], "ln")}{row(target[1], "ln")}{row(target[2], "ln le-static")}{row(target[3], "ln le-static")}</code></pre>
      <div class="le-fields" hidden>
        <label class="le-row" for="le-bucket"><span>bucket:</span><input id="le-bucket" type="text" value="{bucket}" minlength="3" maxlength="63" pattern="{pattern}" autocapitalize="none" autocorrect="off" autocomplete="off" spellcheck="false" aria-describedby="le-hint"></label>
        <p class="le-hint" id="le-hint">3 to 63 characters: a letter first, then lowercase letters, digits and hyphens, no hyphen last, and no YAML keyword such as <code>true</code> or <code>null</code>. The excerpts keep the last value that fits.</p>
        <label class="le-row" for="le-region"><span>region:</span><select id="le-region"><option>eu-central-1</option><option>eu-west-1</option><option>us-east-1</option></select></label>
      </div>
      <p class="le-foot">The class <code>generators</code> pins both generators by version and digest, as station 1 lists them. kadet-hub's consumer workflow verifies both before it fetches them.</p>
    </div>
    <div class="le-outs">
      <div class="le-out">
        <h3>{cube("kub")}Kubernetes manifests</h3>
        <p class="path">{web}</p>
        <pre><code>{lines(files[web], [1, 2, 3, 4, 5], marks={3: ("bucket", bucket), 4: ("region", region)})}</code></pre>
      </div>
      <div class="le-out">
        <h3>{cube("teal")}Terraform JSON</h3>
        <p class="path">{uploads}</p>
        <pre><code>{lines(files[uploads], [11, 12, 13], marks={13: ("bucket", bucket)})}</code></pre>
        <p class="path">{providers}</p>
        <pre><code>{lines(files[providers], [2, 3, 4], marks={4: ("region", region)})}</code></pre>
      </div>
    </div>
  </div>
  <p class="note">Nothing is compiled on this page. Your browser only substitutes the two values into excerpts of what Kapitan {KAPITAN} rendered for the helm-vs-terraform example. For a real compile of an inventory, open the <a href="{{{{ "/playground/" | relURL }}}}">Playground</a>.</p>
</div>
</section>
'''
    (OUT / "live-edit.html").write_text(live)


if __name__ == "__main__":
    main()
