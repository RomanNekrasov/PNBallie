# Tracing, logging, metrics en gebruiksanalytics

PNBallie heeft twee aparte datastromen. Grafana toont operationele informatie
uit Prometheus, Loki en Tempo. Umami toont geaggregeerd gebruik van schermen en
acties. Beide zijn optioneel: lokaal staan ze standaard uit en een storing in
de export mag geen wedstrijd, login of avataropdracht blokkeren.

De gewenste Spark-infrastructuur, versies, migratie en verificatie staan in
`spark-homelab/docs/phase-7-shared-observability.md`. Deze repository bevat de
appinstrumentatie; de app publiceert geen eigen Grafana of databasepoort.

## Operationele configuratie

Stel dit in op API en avatarworker, en waar van toepassing op de modelservice:

| Variabele | Betekenis |
| --- | --- |
| `OTEL_ENABLED=true` | Exporteer spans en gestructureerde logs via OTLP HTTP/protobuf. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Private basis-URL; de app voegt `/v1/traces` en `/v1/logs` toe. |
| `OTEL_TRACES_SAMPLER_ARG=0.1` | Fractie van nieuwe traces; vervolgspans volgen de ouder. Preview gebruikt 1.0. |
| `DEPLOYMENT_ENVIRONMENT` | `development`, `test`, `preview`, `staging` of `production`; los van veilige `APP_ENV`-instellingen. |
| `METRICS_ENABLED=true` | Zet Prometheus-metrics aan; standaard geeft `/metrics` 404. |
| `METRICS_PORT=9101` | Metricsserver van de losse worker; alleen intern publiceren. |
| `METRICS_HOST=0.0.0.0` | Bindadres van de workermetricsserver. |

De services heten `pnballie-api`, `pnballie-avatar-worker` en
`pnballie-avatar-inference`. `OTEL_SERVICE_NAME` mag een van deze waarden
overschrijven. Alleen `deployment.environment.name` uit
`OTEL_RESOURCE_ATTRIBUTES` wordt als fallback gelezen; willekeurige resourcevelden
worden niet doorgestuurd.

De API maakt een eigen trace per verzoek. Een browser kan geen tracecontext,
baggage of samplebeslissing injecteren. Avataropdrachten bewaren uitsluitend een
gevalideerde W3C `traceparent` in SQLite. De worker hervat die context na het
claimen, ook na een procesherstart. Alleen de private lokale modelaanroep krijgt
die header. De optionele OpenAI-aanroep krijgt geen interne traceheaders.

Logs bevatten een vast eventtype, service, omgeving, trace-/span-ID en begrensde
velden zoals routetemplate, status, duur, provider en uitkomst. Bibliotheeklogs
en exceptions worden niet letterlijk geëxporteerd. JSON-consolelogs ondersteunen
lokale diagnose; de collector ontvangt daarnaast dezelfde veilige events via
OTLP. Ruwe Uvicorn- en Nginx-accesslogs staan uit om uitnodigingscodes en
querystrings buiten logs te houden.

De belangrijkste metrics zijn:

- `pnballie_http_requests_total` en `pnballie_http_request_duration_seconds`:
  aantallen, statussen en responstijden per routetemplate.
- `pnballie_avatar_queue_jobs` en `pnballie_avatar_oldest_queued_seconds`:
  wachtrij, lopende opdrachten en oudste wachtende opdracht.
- `pnballie_avatar_jobs_total`, `pnballie_avatar_job_duration_seconds` en
  `pnballie_avatar_queue_wait_seconds`: uitkomsten, verwerking en wachttijd.
- `pnballie_avatar_provider_requests_total` en
  `pnballie_avatar_provider_duration_seconds`: lokale/cloudproviderpogingen.

Geen metriclabel bevat een gebruikers-, groeps-, speler- of job-ID. Histogrammen
hebben de gebruikelijke `_bucket`, `_sum` en `_count`-reeksen. Tel queuegauges van
API en worker niet op: ze lezen dezelfde duurzame wachtrij.

Op Spark bewaart Loki zeven dagen logs en Tempo drie dagen traces; Prometheus
behoudt de bestaande dertig dagen. Export gebruikt begrensde wachtrijen en korte
timeouts. Bij een langdurige storing kan telemetry verloren gaan. Dit is geen
auditlog of backup van scores.

## SPA-gebruiksanalytics

De frontend telt expliciete virtuele schermen en toegestane interacties. Dat
werkt ook voor statistiektabs die dezelfde browser-URL gebruiken. Er worden
geen werkelijke paden, querystrings of fragmenten overgenomen. Een uitnodiging
wordt bijvoorbeeld als uitnodigingsscherm geteld zonder de code in het pad.
Filterwijzigingen en acties geven alleen vaste categorieën door, nooit namen,
e-mails, groeps-/speler-ID's, foto-inhoud of ingevoerde tekst.

Nginx genereert bij het starten `/config.json` met alleen de openbare analytics-
instellingen. Stel in op de frontendcontainer:

```dotenv
ANALYTICS_ENABLED=true
ANALYTICS_WEBSITE_ID=<Umami-website-UUID>
ANALYTICS_UPSTREAM=umami.analytics.svc.cluster.local:3000
ANALYTICS_TRUSTED_PROXY_CIDRS=<uitsluitend-de-vertrouwde-ingress-proxies>
```

Alleen `/analytics/script.js` en `/analytics/api/send` worden op dezelfde origin
doorgegeven. De browser krijgt geen toegang tot de Umami-beheerinterface of de
reportingdatabase. DNS wordt opnieuw opgelost zodat een Umami-herstart of
namespacewissel geen appherstart vereist. Een ongeldige of ontbrekende
configuratie schakelt analytics uit. Do Not Track schakelt verzameling uit.

Doorgestuurde IP-, Cookie-, Authorization- en Referer-headers worden verwijderd.
Alleen een geconfigureerde vertrouwde proxy mag via `CF-Connecting-IP` de
bezoekerlocatie aanleveren. Een directe bezoeker kan dit niet met een zelf
gekozen header vervalsen. Zonder vertrouwde publieke ingress is locatie onbekend;
een private Tailscale-preview bewijst daarom geen echte publieke geolocatie.

Umami verrijkt een vertrouwd IP met geschat land, regio en plaats. Het IP zelf
wordt niet in de eventdatabase bewaard. Dit is geen GPS-positie; VPNs, mobiele
providers en geodatabases kunnen een andere plaats opleveren. PNBallie gebruikt
geen replay, heatmaps, cross-site browser-ID of gebruikersprofielen in analytics.
De notice in de interface legt de meting uit. Umami bewaart maximaal twaalf
maanden en rapportages blijven per website gescheiden.

## Verificatie en productie-overgang

`make check` controleert onder andere echte lokale OTLP-protobufexport,
API→job→worker→modelcontext, gevoelige invoer, exportstoringen, SPA-events en
analyticsconfiguratie. Containerchecks controleren de veilige Nginx-proxy.
Spark-acceptatie moet daarnaast echte records in Prometheus, Loki, Tempo en
Umami aantonen; een geslaagde unit test is geen bewijs van een live dashboard.

De preview gebruikt een eigen SQLite-volume en Umami-website. De publieke
PNBallie-release blijft apart gepind totdat de operator de auth-/groepsmigratie
kiest. Voor die overgang zijn een verse scorebackup, geverifieerd beheerdersaccount,
`claim-legacy`, productie-website-ID en de juiste vertrouwde ingress nodig.
Zie ook [authenticatie en groepen](AUTH_AND_GROUPS.md).

Grafana blijft privé op `https://grafana.tail67de92.ts.net`:
`/d/pnballie-operations` voor applicatiegedrag en `/d/pnballie-analytics` voor gebruik.
Open een JSON-logrecord om naar de bijbehorende trace te gaan.

## Spark-verificatie — 10 september 2026

De private preview draait op
<https://pnballie-preview.tail67de92.ts.net>, met een eigen SQLite-volume en
Umami-website. De publieke app behoudt haar bestaande images en scores.
De gedeelde Umami-interface staat op <https://analytics.tail67de92.ts.net>.

De echte API-proef vindt requestmetrics in Prometheus, gestructureerde logs in
Loki en de trace met hetzelfde ID in Tempo. API, worker en modelservice hebben
gezonde Prometheus-scrapes. De private modelservice is ook afzonderlijk getest
met HTTP-foutpaden vóór modelgeneratie: tracecontext en native logcorrelatie
komen aan, terwijl querystrings en het testtoken buiten de telemetry blijven.

Een aanvullende synthetische opdracht doorloopt de echte duurzame wachtrij en
de normale worker. Alleen de bronbytes van die testopdracht worden vóór verwerking
ongeldig gemaakt. De modelservice weigert ze vóór GPU-generatie. Tempo bevat vier
spans met de juiste ouderrelaties; Loki bevat zes bijbehorende events van alle
drie services. De opdracht eindigt na één poging, wist haar bron en laat de
wachtrij leeg achter. Workerreplica's en Flux-reconciliatie zijn hersteld.

Browsercontroles op desktop en mobiel bevestigen de negen virtuele schermen,
statistiektabs zonder URL-wijziging, filters en profielacties. Umami accepteert
de toegestane payloads; uitnodigingscodes, querystrings, fragmenten en appcookies
ontbreken. Een nieuwe mobiele context met DNT verstuurt geen tracker- of
collectoraanvragen. De lokale database is bijgewerkt naar
`20260910_telemetry`; frontend, API, avatarworker en Spark-tunnel draaien weer.

Jan behoudt 752 events en 20 sessies. Een test via Jans echte collectproxy is
alleen zichtbaar in de previewrapportage; beide andere websiterapportages blijven
leeg voor dat testevent. Expliciet synthetische locatieproeven leveren land,
regio en stad op via Umami's lokale geodatabase. Ze zijn geen echte bezoekers.
De private preview geeft geen publiek bezoekers-IP door; geolocatie voor echte
publieke PNBallie-bezoekers vereist de gedocumenteerde productie-ingressconfiguratie.

De exacte infrastructuurrevisies, aanvullende dashboard-/migratieproeven en
definitieve acceptatie staan in het Phase 7-document in `spark-homelab`.
De laatste browserproef bevestigt 17 daadwerkelijk opgeslagen events en alle
negen schermpaden in Grafana SQL. De 12 operationele en 16 gebruikspanelen
renderen en voeren hun queries succesvol uit. Bij browserautomatisering is een
normale browser-User-Agent nodig: Umami negeert bots bewust en HTTP 200 betekent
dan niet dat een event is opgeslagen. De gebruikssamenvattingen zijn per dag;
gebruik kalenderdagbereiken voor die panelen.
OIDC vereist nog de eerder beschreven echte providerconfiguratie; dat staat
los van deze werkende telemetry- en analyticsaansluiting.
