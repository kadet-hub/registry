{{- /* CAT-28: the generator page as Markdown, at index.md next to it. */ -}}
{{- $page := . -}}
{{- range where site.Data.catalog.generators "name" .Params.generator -}}
{{- $g := . -}}
# {{ .name }}

{{ with .latest -}}
> {{ partial "text.html" $g.description }}

- Latest version: {{ .version }}{{ with .published }}, published {{ substr . 0 10 }}{{ end }}
- Built for: {{ with .compatibility }}{{ range $i, $c := . }}{{ if $i }}, {{ end }}{{ $c.software }} {{ $c.version }}{{ end }} (output validated against these schemas){{ else }}not recorded{{ end }}
- Owners: {{ range $i, $o := $g.owners }}{{ if $i }}, {{ end }}{{ with $o.login }}[{{ . }}](https://github.com/{{ . }}){{ else }}{{ $o.id }}{{ end }}{{ end }}
- Tags: {{ with $g.tags }}{{ delimit . ", " }}{{ else }}none{{ end }}
- Page: {{ $page.Permalink }}
{{ $c := partial "commands.html" (dict "name" $g.name "digest" .digest) }}
## Inventory entry

```yaml
{{ $c.entry }}
```

## Verify

```sh
{{ $c.verify }}
```
{{ with $g.readme }}
## README of {{ $g.latest.version }}

Relative links in the README resolve against {{ $g.blob_url }}.

{{ strings.TrimRight "\n" . }}
{{ end -}}
{{ else -}}
No listed version; every version is yanked:

{{ range .versions -}}
- {{ .version }}: {{ partial "text.html" .yanked }}
{{ end }}
Page: {{ $page.Permalink }}
{{ end -}}
{{ end -}}
