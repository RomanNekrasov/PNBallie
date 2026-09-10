# PNBallie

PNBallie is een persoonlijke tafelvoetbalapp met FastAPI, Vue, SQLModel en SQLite.
Iedere groep heeft een eigen competitie, spelers, statistieken en beheerders.
Inloggen kan met e-mail/wachtwoord of een optionele standaard OIDC-provider.

De goedgekeurde uitbreiding staat in [REQUIREMENTS.md](REQUIREMENTS.md).
De wijzigingen en verificatie staan in [CHANGELOG.md](CHANGELOG.md).

## Lokaal starten

Vereisten: Python 3.11+, uv, Node.js 22 en npm. Er is geen Entra-appregistratie nodig.

```bash
uv sync --project backend
npm ci --prefix frontend
make dev
```

Open http://localhost:5173, maak een account en start een groep. De backend draait
op http://localhost:8000. Zonder lokale instellingen gebruikt de backend
`sqlite:///./pnballie.db`, de frontend-origin `http://localhost:5173` en lokale
accounts. Alembic wordt voor de backendstart uitgevoerd.

Docker Compose gebruikt een eigen volume en http://localhost:8080:

```bash
cp .env.example .env
make docker-up
```

Het voorbeeldbestand is voor Compose. Bij native ontwikkeling met dat bestand:
wijzig `AUTH_APP_ORIGIN` naar `http://localhost:5173` en exporteer de variabelen
voor `make dev`. De frontend vraagt de inlogopties aan de backend; het vroegere
`config.json` met Azure-instellingen is niet meer nodig.

## Groepen en profielen

Het huisje op het speelveld opent de statistieken. Via het tandwiel in de
paginakop ga je naar je profiel, groepen of groepsbeheer en kun je uitloggen.

- Maak een groep of gebruik een uitnodigingscode/link van de beheerder.
- Wissel tussen competities via **Groepen**.
- In **Beheer** beheer je spelers, profielkoppelingen, ledenrollen en uitnodigingen.
- Een speler kan ook zonder account meedoen. Een beheerder kan later een account
  koppelen. Deactiveren behoudt de uitslagen en badges.
- In **Profiel** wijzig je je spelersnaam en wachtwoord en vraag je een avatar aan.
- Alleen een groepsbeheerder kan uitslagen verwijderen. De groep houdt altijd
  minstens één beheerder.

Alle groepsgebonden API-routes controleren het lidmaatschap met `X-Group-ID`.
Login gebruikt een HttpOnly-cookie; mutaties vereisen ook `X-CSRF-Token`.
Tokens en wachtwoorden worden niet in browseropslag bewaard.

## Bestaande gegevens en productie

Migraties plaatsen bestaande spelers en wedstrijden in **Bestaande competitie**.
Deze groep is aanvankelijk voor niemand toegankelijk. Registreer eerst het
bedoelde beheerdersaccount en geef het daarna als operator toegang:

```bash
cd backend
uv run python -m app.admin claim-legacy --email admin@example.org
```

Controleer het account vooraf buiten de app en voer de opdracht met de juiste
`DATABASE_URL` uit. De beheerder koppelt daarna de historische spelers aan
groepsleden. Er wordt nooit automatisch op basis van een naam of onbevestigd
e-mailadres toegang tot bestaande scores verleend.

Zie [authenticatie, groepen en migratie](docs/AUTH_AND_GROUPS.md) voor configuratie,
OIDC, back-up, verificatie en terugval. Productie vereist
`APP_ENV=production`, een expliciete HTTPS-`AUTH_APP_ORIGIN` en
`AUTH_COOKIE_SECURE=true`.

De publieke app op https://pnballie.nl draait op k3s met de definitief uit Azure
overgedragen SQLite-gegevens. Publieke Entra-login en het bekijken van bestaande
scores zijn bevestigd; de actuele acceptatiestatus staat in
`spark-homelab/docs/phase-6-pnballie.md`. De portable authenticatie, groepen en
analytics uit deze release draaien op de aparte
[private Spark-preview](https://pnballie-preview.tail67de92.ts.net).
Je kunt daar een eigen account en testcompetitie maken.
Imagepublicatie en de private preview staan los van de publieke upgrade.
Kubernetes-/Flux-configuratie hoort in
`spark-homelab`; de historische Azure/Terraform-bestanden blijven als terugvalset.
De Azure-backend is gestopt en de Azure Pipeline is verwijderd. Start een oude
backend nooit met verouderde scores: draag bij terugval eerst de actuele database
over volgens het homelabrunbook. De huidige images passen niet rechtstreeks in
de oude Azure-stack; zie [de historische configuratie](infra/prod/README.md).

## Statistieken

Filter op alles, 1v1 of 2v2, en op all-time, de laatste 30 kalenderdagen of de
laatste 50 wedstrijden van het gekozen type. ELO wordt voor de selectie opnieuw
vanaf 1000 berekend. Blijvende badges en actuele winreeksen gebruiken de volledige
groepshistorie.

Het gemiddelde doelverschil in het overzicht is de gemiddelde winstmarge
`abs(oranje - blauw)`; op spelersniveau blijft doelverschil gesigneerd. De
activiteitsgrafiek gebruikt Amsterdamse kalenderdagen en de grens 14:00. API-tijden
zijn UTC met tijdzone; de browser toont het lokale tijdstip van de kijker.

## AI-avatars

Foto-upload en jobstatus werken via een duurzame SQLite-wachtrij. De kleine worker
draait los van de webserver; de GPU-service draait op de Spark. Alleen de
GPU-service heeft de optionele modeldependencies nodig. Start de worker met:

```bash
make avatar-worker
# of, bij Docker Compose:
docker compose --profile avatars up --build -d
```

Stel voor de lokale route `AVATAR_LOCAL_URL` en `AVATAR_SERVICE_TOKEN` in op
backend én worker. De optionele cloudroute gebruikt `OPENAI_API_KEY` en
`OPENAI_IMAGE_MODEL`; iedere aanvraag vereist toestemming in het profiel.
De volledige Qwen-proef op de Spark duurde ongeveer 24 minuten; de worker wacht
standaard maximaal 60 minuten op het model. De profielpagina mag tussendoor dicht.

[Avatarservice en Spark-onderzoek](docs/AVATAR_SERVICE.md) beschrijft Qwen Image Edit,
echte transparantie via Qwen Image Layered, lifecycle, runtime-inrichting en de
grenzen van de uitgevoerde tests. Een geslaagde wachtrijtest is geen bewijs van
beeldkwaliteit op de GPU.

## Telemetry en analytics

Optionele OpenTelemetry-traces, veilige JSON/OTLP-logs en Prometheus-metrics
voeden de bestaande private Grafana. Umami meet expliciete SPA-schermen en
acties, met Do Not Track en zonder uitnodigingscodes of persoonsgegevens in
events. Zie [configuratie en datagrenzen](docs/OBSERVABILITY.md).

## Controles en release

`make check` voert Ruff, Pytest, ESLint, Vitest, TypeScript en de productiebuild uit.
CI controleert ook Alembic-upgrade en schemadrift, groepsflows via de Nginx-proxy,
non-root/read-only containers en images voor amd64 en arm64.

Endpoints: `/health/live`, `/health/ready` en de Nginx-proxy `/healthz`.
De API-documentatie staat op `/docs` bij de backend.

Merges naar main publiceren na geslaagde CI private immutable images
`ghcr.io/romannekrasov/pnballie-backend:sha-<commit>` en
`ghcr.io/romannekrasov/pnballie-frontend:sha-<commit>`. Uitrol gebeurt afzonderlijk
via de geselecteerde digests in `spark-homelab`.

Commit nooit lokale configuratie, tokens, foto's, databasebestanden of secrets.
