{{- /* CAT-25: the privacy page's analytics paragraph, depending on params.goatcounter. */ -}}
{{- with site.Params.goatcounter -}}
## Visitor counting

Each page view is counted with [GoatCounter](https://www.goatcounter.com), which kadet-hub runs itself at `{{ strings.TrimSuffix "/" . }}` on a server rented from netcup GmbH, Germany. A script served from kadet-hub.org (`count.js`) sends the page's path and title, the referring page and your screen width there; the server also receives your IP address and browser's user agent with the request. It derives an approximate location from the IP address and stores neither the IP address, the full user agent nor any tracker ID. The script sets no cookies. It reads the key `skipgc` from your browser's `localStorage`, which is only set when someone opts out of being counted on this site. The legal basis is the legitimate interest in knowing which pages are used (Art. 6(1)(f) GDPR).
{{- else -}}
The site runs no analytics or tracking.
{{- end -}}
