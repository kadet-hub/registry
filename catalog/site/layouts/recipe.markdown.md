{{- /* CAT-37b: a recipe as Markdown, at index.md next to it. */ -}}
{{- $r := partial "recipe.html" . -}}
# {{ .Title }}

> {{ $r.lead }}

- Replaces the Bitnami charts: {{ delimit .Params.replaces ", " }}
- Generators: {{ delimit $r.generators ", " }}
- Operators: {{ with .Params.operators }}{{ delimit . ", " }}{{ else }}none{{ end }}
- Checked: deployed to a new kind cluster; fails unless {{ .Params.check }} ({{ $r.test }})
- Source: {{ $r.folder }}
- Page: {{ .Permalink }}

## inventory/classes/recipes/{{ $r.name }}.yml

```yaml
{{ strings.TrimSpace $r.class }}
```
{{ range $r.libs }}
## {{ .path }}

```yaml
{{ strings.TrimSpace .text }}
```
{{ end }}
## Generator pins (inventory/classes/generators.yml)

```yaml
{{ strings.TrimSpace $r.pins }}
```
