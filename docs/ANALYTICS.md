# Gebruiksstatistieken voor PNBallie

PNBallie gebruikt de bestaande zelf gehoste Umami-installatie. De app telt
schermen, tabwisselingen en expliciete acties. De statistieken staan los van
de eigen competitie- en wedstrijdstatistieken. Het zijn clientobservaties,
geen financieel of administratief auditlogboek.

## Inschakelen en runtime

Analytics staat standaard uit, ook in Vite en tests. De frontend haalt
`/config.json` op zonder cookies of referrer. Een ontbrekend bestand, foutieve
configuratie, onbereikbaar Umami of een geblokkeerd script verhindert het
gebruik van de app niet. De configuratieaanvraag heeft een deadline van 3 seconden.

De productiecontainer genereert configuratie in zijn schrijfbare `/tmp`; de
rootfilesystem blijft read-only. Een ConfigMap-mount op de statische `config.json`
is niet nodig. De browser krijgt alleen:

```json
{"analytics":{"enabled":true,"websiteId":"03c9b13b-4507-517c-b008-c488152a163b"}}
```

De website-UUID is een publieke collectoridentifier, geen wachtwoord.

| Containerinstelling | Waarde / betekenis |
| --- | --- |
| `ANALYTICS_ENABLED` | `true` of `1` om in te schakelen; standaard uit |
| `ANALYTICS_WEBSITE_ID` | UUID van de betreffende Umami-website |
| `ANALYTICS_UPSTREAM` | Privé `host:port`, hier `umami.analytics.svc.cluster.local:3000` |
| `ANALYTICS_DNS_RESOLVER` | Optionele IPv4-DNS-server; standaard de eerste nameserver uit `/etc/resolv.conf` |
| `ANALYTICS_TRUSTED_PROXY_CIDRS` | Optionele, expliciete IPv4-CIDR's van vertrouwde Cloudflare Tunnel-proxypods, gescheiden door spaties/komma's; standaard leeg |

Productie (`pnballie.nl`) gebruikt `e2a427f6-a458-5afe-9043-feca1e0ed7c8`.
Preview (`pnballie-preview.tail67de92.ts.net`) gebruikt
`03c9b13b-4507-517c-b008-c488152a163b`. Houd deze websites gescheiden.

Nginx resolveert de upstream tijdens aanvragen. Ontbrekende Umami-DNS verhindert
dus niet dat PNBallie start. Collectoraanvragen hebben korte proxytime-outs.
Een normale Vite-start heeft geen analyticsproxy en gebruikt de uitgeschakelde
configuratie in `frontend/public/config.json`. Controleer ingeschakelde analytics
in de frontendcontainer of de previewomgeving.

## Publieke collectorgrens

Alleen deze exacte paden worden naar Umami doorgestuurd:

| Browserpad | Toegestane methode | Privé Umami-pad |
| --- | --- | --- |
| `/analytics/script.js` | GET / HEAD | `/script.js` |
| `/analytics/api/send` | POST, maximaal 16 KiB | `/api/send` |

Andere `/analytics/`-paden krijgen 404. De Umami-interface, rapportage-API,
heartbeat en beheerfuncties worden niet via PNBallie gepubliceerd. De frontend
blokkeert ook `/metrics`, `/metrics/`, interne telemetry- en tracepaden; interne
scrapers moeten de backend rechtstreeks via de private service benaderen.

De proxy neemt browserheaders niet automatisch over. De kleine expliciete
allowlist bevat de standaard User-Agent, Content-Type, Host en de Umami-collectorheaders.
Appcookies, Authorization, Referer en willekeurige forwardingheaders worden
verwijderd. Analyticsrequests staan niet in het nginx-accesslog.

### Geschatte locatie en vertrouwde proxies

Umami kan land/regio/stad grofweg uit een client-IP afleiden. PNBallie vraagt geen
GPS-toestemming en voegt geen client-IP toe aan eventproperties.

Alleen een expliciet vertrouwde Cloudflare Tunnel-proxy mag `CF-Connecting-IP`
aanleveren. Nginx controleert de oorspronkelijke socketpeer via
`$realip_remote_addr`; alleen voor deze CIDR's wordt het geverifieerde adres
doorgegeven als `X-Forwarded-For` / `X-Real-IP`. Alle binnenkomende
`X-Forwarded-*`, `Forwarded`, `True-Client-IP` en `CF-IPCountry` worden niet
overgenomen. Gebruik concrete proxypod-IP's of de minimaal noodzakelijke
vertrouwde subnetten; geen algemeen podnetwerk waar willekeurige pods kunnen
binnenkomen. `/0` en te brede CIDR's worden geweigerd.

Op de private Tailscale-preview blijft de trustlist leeg. Het doorgegeven
clientadres is dan leeg: een onbekende/interne locatie is beter dan een
bezoeker die met eigen headers een locatie kan vervalsen. Als proxypod-IP's
wijzigen, moet de beheerconfiguratie worden bijgewerkt. Analytics wordt niet
gebruikt voor autorisatie.

## Wat wordt gemeten

De adapter in `frontend/src/analytics.ts` gebruikt Umami's handmatige `track`
objectcontract en een tweede `before-send`-validatie. Beide grenzen bouwen een
nieuw payload met alleen toegestane gegevens. Automatische pageviews,
history-hooks, DOM-klikevents en automatische performanceverzameling staan uit.
Er wordt geen `identify` aangeroepen en geen eigen gebruikersidentifier gemaakt.

De virtuele schermen zijn `/app/game`, `/app/stats_overview`,
`/app/stats_ranking`, `/app/stats_players`, `/app/stats_matchups`, `/app/profile`,
`/app/groups`, `/app/admin` en `/app/login`. Statistiektabs melden zelfstandig
schermwisselingen; de URL hoeft daarvoor niet te veranderen. Een uitnodiging
wordt alleen als het scherm `groups` gezien. Titels zijn vaste labels.

| Event | Toegestane properties |
| --- | --- |
| `match_saved` | `mode`: `1v1`, `2v2` |
| `match_deleted` | Geen |
| `stats_filters_changed` | `mode`: `all`, `1v1`, `2v2`; `period`: `all`, `30d`, `50` |
| `comparison_selected` | Geen |
| `profile_saved` | Geen |
| `group_created`, `group_joined`, `group_updated` | Geen |
| `player_added`, `player_updated`, `member_updated`, `member_removed` | Geen |
| `invite_created`, `invite_revoked` | Geen |
| `avatar_queued` | `provider`: `local`, `openai` |
| `avatar_outcome` | `provider`; `outcome`: `succeeded`, `failed`, `cancelled` |
| `screen_visible_30s` | Geen; scherm was 30 seconden achtereen zichtbaar |

Succes-events volgen op een geslaagde API-mutatie. Een avataruitkomst wordt
alleen geteld als de geopende app de overgang van actief naar afgerond ziet.
Een eerder afgeronde avatar ophalen telt niet opnieuw als uitkomst. Een gesloten
browser kan geen uitkomst registreren en twee geopende browsers kunnen dezelfde
overgang zien. Gebruik backendgegevens voor exacte aantallen afgeronde jobs.

`screen_visible_30s` betekent zichtbaarheid, geen bewijs dat iemand actief leest.
Er worden geen muiscoördinaten, toetsaanslagen, sessieopnames of heatmaps gemaakt.
De app verstuurt geen werkelijke URLs/querystrings/hashfragmenten/referrers,
uitnodigingscodes, account-/groep-/speler-/job-ID's, namen, e-mailadressen,
foto's, scores of vrije foutmeldingen. Onbekende events, schermen en propertywaarden
worden geweigerd; aanvullende properties worden verwijderd.

Umami gebruikt zijn normale websitegebonden sessieverwerking en browserinformatie;
PNBallie voegt geen stabiele identifier voor andere websites toe. Do Not Track,
Global Privacy Control en Umami's lokale uitschakelvoorkeur worden gerespecteerd.
Het accountmenu en inlogscherm bevatten een korte toelichting wanneer analytics
is geconfigureerd.

## Verificatie

Gedragstests controleren standaard uit, DNT, geweigerde configuratie,
virtuele tabwisselingen, payloadsanitatie, mislukte saves, nieuwe avataruitkomsten,
onzichtbare schermen en falende trackers. Renderertests controleren veilige
runtimeconfiguratie, ongeldige input en de proxygrens.

De daadwerkelijke nginx-container wordt daarnaast geïsoleerd gecontroleerd met:

```bash
python3 scripts/check_analytics_proxy.py
```

De controle bouwt de frontend en gebruikt tijdelijke containers en een eigen
Docker-netwerk. Bestaande stacks blijven draaien. Met `--image <image>` kan een
al gebouwde frontend worden gecontroleerd; CI gebruikt hiervoor de Compose-image.
Op 10 september 2026 slaagden de controles voor non-root/read-only opstarten,
runtimeconfiguratie, exacte proxypaden, methode- en bodylimieten, verwijderde
privéheaders, vertrouwde en onvertrouwde client-IP's, onderdrukte ruwe URLs in
logs en beschikbaarheid bij ontbrekende of uitgeschakelde analytics.

Voor vrijgave in de preview ook werkelijk controleren:

1. Alleen het publieke script en de collector zijn bereikbaar; metrics,
   reporting, heartbeat en onbekende analyticspaden geven 404/403.
2. Met DNT staat er geen collectorverkeer in de browsernetwerktab.
3. Met DNT uit zijn alleen vaste schermen en bovenstaande eventproperties zichtbaar.
4. Zelf ingevulde forwarding-/Cloudflareheaders beïnvloeden de private previewlocatie niet.
5. De Umami-/Grafana-telling hoort bij de previewwebsite, niet bij productie.

Upstreamcontract gecontroleerd tegen Umami v3.3.1:
[trackerbron](https://github.com/umami-software/umami/blob/v3.3.1/src/tracker/index.ts)
en [collectorbuildconfiguratie](https://github.com/umami-software/umami/blob/v3.3.1/rollup.tracker.config.js).
