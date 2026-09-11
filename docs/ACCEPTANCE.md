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
