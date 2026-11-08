{{- /* CAT-28: a guide as Markdown, at index.md next to it; shortcodes render their Markdown template (CAT-35a). */ -}}
{{- /* CAT-36f: Hugo writes alias pages as HTML only, so each alias gets an index.md that links the guide. */ -}}
{{- range .Aliases -}}
{{- $stub := printf "# %s\n\nThis page moved to <%s>. Its Markdown variant is at <%sindex.md>.\n" $.Title $.Permalink $.Permalink -}}
{{- with (resources.FromString (strings.TrimPrefix "/" (path.Join . "index.md")) $stub).Publish }}{{ errorf "%s" . }}{{ end -}}
{{- end -}}
# {{ .Title }}

{{ strings.TrimSpace .RenderShortcodes }}
