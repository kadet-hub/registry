{{- /* CAT-25: the privacy page's analytics paragraph, depending on params.goatcounter. */ -}}
{{- with site.Params.goatcounter -}}
## Visitor counting

Each page view is counted with [GoatCounter](https://www.goatcounter.com), a service run by Martin Tournoij, Ireland. A script served from kadet-hub.org (`count.js`) sends the page's path and title, the referring page and your screen width to `{{ . }}.goatcounter.com`; GoatCounter also receives your IP address and browser's user agent with the request. The script sets no cookies. It reads the key `skipgc` from your browser's `localStorage`, which is only set when someone opts out of being counted on this site. According to [GoatCounter's privacy policy](https://www.goatcounter.com/help/privacy), it derives an approximate location from the IP address, does not store IP addresses, the full user agent or any tracker ID, and keeps the data on servers of Hetzner Online GmbH in Finland and Germany. The legal basis is the legitimate interest in knowing which pages are used (Art. 6(1)(f) GDPR).
{{- else -}}
The site runs no analytics or tracking.
{{- end -}}
