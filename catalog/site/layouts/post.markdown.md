{{- /* CAT-28: a guide as Markdown, at index.md next to it; shortcodes render their Markdown template (CAT-35a). */ -}}
# {{ .Title }}

{{ strings.TrimSpace .RenderShortcodes }}
{{ range where site.Data.catalog.releases "monday" (.Params.release | default "") }}{{ range .generators }}{{ if .entries }}{{ $g := . }}{{/* CAT-36b */}}
## {{ .name }}
{{ range .entries }}
### {{ $g.name }} {{ .version }}

{{ .text }}
{{ end }}{{ if .cut }}
[Full changelog]({{ .changelog }})
{{ end }}{{ end }}{{ end }}{{ end -}}
