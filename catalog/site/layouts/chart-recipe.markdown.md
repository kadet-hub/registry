{{- /* CAT-37b, CAT-37c: a kadet-hub/recipes recipe as Markdown, at index.md next to it. */ -}}
{{- $r := partial "chart-recipe.html" . -}}
# {{ .Title }}

> {{ $r.lead }}

{{ with $r.compose -}}
- Source: Docker Compose file {{ .repo }}@{{ .commit }} ({{ .path }}), {{ .digest }}: {{ .url }}
- Proof level: {{ $r.level }}, deployed on kind and smoke tested by the kadet-hub/recipes CI
{{ else -}}
- Source chart: {{ $r.source }}
- Proof level: {{ $r.level }}, compared with the chart by the kadet-hub/recipes CI
{{ end -}}
- Generators: {{ range $i, $g := $r.generators }}{{ if $i }}, {{ end }}{{ $g.name }} {{ $g.version }} ({{ $g.digest }}){{ end }}
{{ range $r.classes }}- {{ if .option }}Option{{ else }}Class{{ end }} {{ .class }} ({{ .file }}){{ with .components }}: {{ delimit . ", " }}{{ end }}
{{ end }}- Source: {{ $r.folder }}
- Page: {{ .Permalink }}

## Required parameters

{{ $r.required }}

## Include

```yaml
{{ $r.include }}
```

## Fetching it

fetch/targets/recipes.yml at kadet-hub/recipes {{ $r.sha }}:

```yaml
{{ $r.fetch }}
```

```sh
{{ $r.commands }}
```

The first command exits with status 1 because the fetch target compiles nothing. Verifying the generators and raising the pin: {{ $r.guide }}
{{ range $r.sections }}
## {{ .heading }}

{{ .body }}
{{ end -}}
