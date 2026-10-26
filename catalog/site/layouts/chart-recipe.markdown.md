{{- /* CAT-37b, CAT-37c, CAT-38: a kadet-hub/recipes recipe as Markdown, at index.md next to it. */ -}}
{{- $r := partial "chart-recipe.html" . -}}
# {{ .Title }}

> {{ $r.lead }}

{{ with $r.latest -}}
- Latest version: {{ .version }}{{ with .published }}, published {{ substr . 0 10 }}{{ end }}
{{ end -}}
{{ with $r.compose -}}
- Source: Docker Compose file {{ .repo }}@{{ .commit }} ({{ .path }}), {{ .digest }}: {{ .url }}
- Proof level: {{ $r.level }}, deployed on kind and smoke tested by the kadet-hub/recipes CI
{{ else with $r.image -}}
- Source: container image {{ . }}, recipe designed in kadet-hub
- Proof level: {{ $r.level }}, deployed on kind and smoke tested by the kadet-hub/recipes CI
{{ else with $r.manifest -}}
- Source: release manifest {{ .repo }}@{{ .tag }} ({{ .file }}), {{ .digest }}: {{ .url }}
- Proof level: {{ $r.level }}, compared with the manifest by the kadet-hub/recipes CI
{{ else -}}
- Source chart: {{ $r.source }}
- Proof level: {{ $r.level }}, compared with the chart by the kadet-hub/recipes CI
{{ end -}}
{{ with $r.latest -}}
- {{ with $r.renders }}renders passed in the release run of {{ substr .at 0 10 }} with {{ .tool }}: {{ .run }}{{ else }}No renders result in the release run's record{{ end }}
- Output capabilities: {{ with .output_capabilities }}{{ delimit . ", " }}{{ else }}none{{ end }}
{{ end -}}
{{ with $r.requires }}- Prerequisites, installed once per cluster before the recipe: {{ delimit . ", " }}
{{ end -}}
- Generators: {{ range $i, $g := $r.generators }}{{ if $i }}, {{ end }}{{ $g.name }} {{ $g.version }} ({{ $g.digest }}){{ end }}
{{ range $r.classes }}- {{ if .option }}Option{{ else }}Class{{ end }} {{ .class }} ({{ .file }}){{ with .components }}: {{ delimit . ", " }}{{ end }}
{{ end }}- Source: {{ $r.folder }}
- Page: {{ .Permalink }}
{{ with $r.replaces }}
## Replaces

{{ . }}
{{ end }}
## Required parameters

{{ $r.required }}

## Include

```yaml
{{ $r.include }}
```

## Fetching it

{{ with $r.latest -}}
{{ with $r.blocked -}}
{{ range . }}Version {{ $r.latest.version }} pins the generator {{ .name }} {{ .version }}, which is yanked: {{ partial "text.html" .yanked }}
{{ end }}
The consumer workflow rejects a yanked generator, so this page shows no fetch inventory for the version.
{{ else -}}
fetch/targets/recipes.yml for {{ $r.name }} {{ .version }}:

```yaml
{{ $r.fetch }}
```

```sh
{{ $r.commands }}
```

The first command exits with status 1 because the fetch target compiles nothing. Verifying the attestation of each recipe the fetch inventory pins:

```sh
{{ $r.verify }}
```

The attested index must also list each digest under its recipe with the pinned version, and not as yanked: https://github.com/{{ site.Data.catalog.owner }}/registry/blob/main/docs/consumers.md#verifying-by-hand
{{ with $r.policy }}
The policy .kapitan-sandbox.yaml must accept the output capabilities of the recipe's test target for the target's output path:

```yaml
{{ . }}
```
{{ end -}}
{{ end -}}
{{ else -}}
fetch/targets/recipes.yml at kadet-hub/recipes {{ $r.sha }}:

```yaml
{{ $r.fetch }}
```

```sh
{{ $r.commands }}
```

The first command exits with status 1 because the fetch target compiles nothing. Verifying the generators and raising the pin: {{ $r.guide }}
{{ end -}}
{{ range $r.sections }}
## {{ .heading }}

{{ .body }}
{{ end -}}
{{ with $r.record }}
## Versions

{{ range .versions }}- {{ .version }}{{ with .published }}, {{ substr . 0 10 }}{{ end }}: {{ .digest }}{{ with .yanked }}; yanked: {{ partial "text.html" . }}{{ end }}
{{- range .generators }}{{ if .yanked }}; pins the generator {{ .name }} {{ .version }}, which is yanked: {{ partial "text.html" .yanked }}{{ end }}{{ end }}
{{ end -}}
{{ end -}}
