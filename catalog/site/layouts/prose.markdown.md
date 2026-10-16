{{- /* CAT-28: a guide as Markdown, at index.md next to it; shortcodes render their Markdown template (CAT-35a). */ -}}
# {{ .Title }}

{{ strings.TrimSpace .RenderShortcodes }}
