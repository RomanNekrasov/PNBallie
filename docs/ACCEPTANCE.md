# Acceptatieomgeving

`https://acceptatie.pnballie.nl` is de aparte testomgeving. De Kubernetes-
configuratie staat in `spark-homelab/cluster/apps/pnballie-acceptance`; de
publieke competitie en private preview houden hun eigen database.

De eerste start maakt een **Democompetitie** met beheerder/speler Sam en
zeven andere fictieve spelers. Er zijn 180 wedstrijden: 72 keer 1v1 en 108
keer 2v2, verspreid over de afgelopen 120 dagen. Oranje/blauw, voor/achter,
de twee dagdelen en winstreeksen komen aan bod. Sam heeft een historische
reeks van vijf zeges, zodat permanente badges ook zonder actieve reeks te
testen zijn. De wedstrijden zijn voorbeelddata, geen gekopieerde echte scores.

De inloggegevens worden apart aan de beheerder verstrekt en staan niet in
de repository. Je kunt wedstrijden toevoegen, spelers wijzigen, uitnodigingen
maken en filters vergelijken. Herstarts bewaren die wijzigingen.

## Initialisatie

De backend start met twee initcontainers: eerst Alembic, daarna:

```sh
python -m app.demo --if-empty
```

De opdracht leest `DEMO_ADMIN_EMAIL` en `DEMO_ADMIN_PASSWORD` uit het
`pnballie-demo` Secret, uitsluitend in de initcontainer. De normale API krijgt
deze bootstrap-inloggegevens niet als configuratie. Het wachtwoord wordt met
dezelfde Argon2-hasher opgeslagen als andere accounts en wordt nooit gelogd.

De initialisatie vereist exact `DEPLOYMENT_ENVIRONMENT=staging` en
`AUTH_APP_ORIGIN=https://acceptatie.pnballie.nl`. Ze vult alleen een lege
appdatabase, in één transactie. Een lege legacygroep uit de migraties mag al
bestaan. Met `--if-empty` slaat een bezette database de initialisatie over;
zonder die optie weigert de opdracht. Er is geen reset- of overschrijfoptie.

## Metingen en verificatie

Acceptatie heeft een eigen Umami-website en Grafana-datasource. Kies
**Acceptance** in het PNBallie-gebruiksdashboard en **pnballie-acceptance /
staging** bij operationele metingen. Zie [ANALYTICS.md](ANALYTICS.md) voor
de definitie van tab- en blokviews. Testverkeer staat los van productie.

Controleer na publicatie de HTTPS-route, inloggen, acht spelers, 180 initiële
wedstrijden, de 1v1-/2v2- en periodefilters, historische badges en de
statistiekranglijsten in Grafana. Nieuwe testwedstrijden verhogen het aantal;
het initiële aantal is geen blijvende healthcheck.

Zie [Van acceptatie naar productie](RELEASE_PROMOTION.md) voor de CI/CD-stappen
en de eenmalige overstap van de huidige productie-authenticatie.

## Verificatie — 11 september 2026

App-release `72ef9f47abdcb7458f843d6ad60fd1bd3eb10505` is uitgerold met
homelab-revisie `2f2b9907cf0169d5093fe37bc3337e79281aec50`. Alle twaalf Flux-
Kustomizations zijn Ready; HTTPS en lokale login werken. De release passeert
118 backendtests, 89 frontendtests, container-/privacycontroles en vijf koude
routes uit de productiebuild.

De eerste database bevat acht fictieve spelers en 180 wedstrijden: 72 keer
1v1, 108 keer 2v2 en 90 wedstrijden in elk dagdeel. Alle negen combinaties van
spelvorm en periode zijn gecontroleerd, inclusief de blijvende vijf-winbadge.
Een tijdelijke profielwijziging en de ingelogde sessie bleven na vervanging van
de backendpod behouden. De initcontainer sloeg de bestaande database over; de
tijdelijke wijziging is daarna hersteld.

Echte API-verzoeken leveren metrics in Prometheus, logs in Loki en een
gecorreleerde trace in Tempo. Interne metrics-, rapportage- en trace-endpoints
zijn via de publieke app niet toegankelijk.

De uitgerolde interface is getest in WebKit op 393px en Chromium op 1440px.
Alle zeventien statistiekblokken leveren echte Umami-records met sessie- en
bezoek-ID's. De controles bevestigen de zichtbaarheidsdrempel, deduplicatie,
tabtoewijzing en het stoppen bij navigatie. DNT en lokale opt-out veroorzaken
geen analyticsverzoeken. De opgeschoonde accountpagina's hebben tekstvelden van
minimaal 16px, zonder horizontale overflow of JavaScript-fouten.

Alle achttien panelen van het PNBallie-gebruiksdashboard zijn met werkelijke
Grafana-queries en de gerenderde grafieken gecontroleerd. De ranglijsten tonen
vier statistiektabs en zeventien blokken, gesorteerd op verschillende bezoeken.
De vier rapportagerollen weigeren toegang tot andere websites, ruwe tabellen en
schrijfopdrachten. Land/regio/stad zijn beschikbaar zonder opgeslagen
IP-adressen of appgebruikers-ID's. De eerste tellingen komen van de
acceptatieproeven; ze zeggen nog niets over normaal gebruik.
