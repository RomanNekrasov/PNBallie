# PNBallie

PNBallie bestaat uit een FastAPI-backend, een Vue-frontend en een SQLite-database. De applicatie wordt als twee private multi-architecture images gepubliceerd voor gebruik vanuit k3s. Kubernetes- en homelabconfiguratie horen in `spark-homelab`, niet in deze repository.

## Migratiestatus

Stand 9 september 2026: PNBallie draait op k3s met de definitieve Azure-gegevens in SQLite. Schema en volledige inhoud zijn gecontroleerd, ook na het vervangen van de backendpod. Een nieuwe versleutelde back-up is gecontroleerd; de private Entra-login werkt.

PNBallie is publiek bereikbaar via [https://pnballie.nl](https://pnballie.nl). De HTTPS-controles voor de frontend, `/healthz` en `/config.json` slagen. De gebruiker heeft publiek aanmelden met Entra, het bekijken van bestaande spelers en scores, en het aanmaken en verwijderen van een score bevestigd. De verwijderde score verdween ook uit de statistieken. Daarmee is de migratie (Phase 6) afgerond; een nieuwe versleutelde databaseback-up is gecontroleerd.

De Azure-backend is gestopt en blijft na een geslaagde terugvaltest beschikbaar als rollbackpad. Azure opruimen wordt afzonderlijk beoordeeld; er zijn nog geen resources verwijderd. De acceptatie en uitvoeringsinstructies staan in de [Phase 6-documentatie](https://github.com/RomanNekrasov/spark-homelab/blob/main/docs/phase-6-pnballie.md) en het [migratierunbook](https://github.com/RomanNekrasov/spark-homelab/blob/main/docs/runbooks/pnballie-migration.md) in de private homelabrepository.

## Lokale ontwikkeling

Vereisten: Python 3.11, [uv](https://docs.astral.sh/uv/), Node.js 22, npm en optioneel Docker Compose.

```bash
uv sync --project backend
npm ci --prefix frontend
cp .env.example .env
cp frontend/public/config.example.json frontend/public/config.json
```

Vul lokale Entra-waarden in beide genegeerde bestanden in. Het frontendcontract is:

```json
{
  "azureClientId": "...",
  "azureTenantId": "...",
  "azureScope": "api://.../user"
}
```

Voor native ontwikkeling moet je de backendvariabelen exporteren; `make dev` leest `.env` niet automatisch:

```bash
set -a
. ./.env
set +a
make dev
```

De native frontend draait op `http://localhost:5173`, de backend op `http://localhost:8000`. Docker Compose leest `.env` wel automatisch: start met `make docker-up` en open `http://localhost:8080`. Compose voert Alembic eerst eenmalig uit, bewaart alleen `/data` in het SQLite-volume en start daarna backend en frontend als non-root met read-only rootfilesystems.

## Runtimeconfiguratie en endpoints

De backend gebruikt `ENTRA_TENANT_ID`, `ENTRA_AUDIENCE` en `ENTRA_REQUIRED_SCOPE` (standaard in Compose: `user`). In productie (`APP_ENV=production`) stopt de backend direct als een instelling ontbreekt. Alle `/api/*`-routes vereisen een geldig RS256 Entra-token met de juiste issuer, tenant, audience, vervaldatum en scope.

Stel in de API-appregistratie `api.requestedAccessTokenVersion` in op `2`. `ENTRA_AUDIENCE` moet overeenkomen met de `aud` van het v2-access-token: normaal de client-ID-GUID van de API-applicatie. De frontend vraagt de scope `api://<API-client-id>/user` aan. Registreer iedere gebruikte frontend-origin als **SPA**-redirect-URI; MSAL gebruikt `window.location.origin`. Behoud de bestaande Azure-redirect zolang het rollbackpad beschikbaar blijft.

- `GET /health/live`: backend-livenessprobe zonder authenticatie.
- `GET /health/ready`: backend-database-readinessprobe zonder authenticatie.
- `GET /healthz`: Nginx-frontendproxy naar backend-readiness; deze proxy bestaat niet in de Vite-devserver.
- `GET /config.json`: gemounte frontendconfiguratie met caching uitgeschakeld.

Commit nooit `.env`, `frontend/public/config.json`, tokens of databasebestanden.

## Controles

Voer alle lokale controles uit met `make check`. Dit omvat Ruff, Pytest, ESLint, Vitest, TypeScript en de Vite-productiebuild. GitHub Actions controleert daarnaast een Alembic-upgrade vanaf een lege database, secrets, Compose-smoketests, non-root/read-only gedrag en builds voor `linux/amd64` en `linux/arm64`.

## Release

Elke merge naar `main` publiceert zonder `latest`-alias:

- `ghcr.io/romannekrasov/pnballie-backend:sha-<commit>`
- `ghcr.io/romannekrasov/pnballie-frontend:sha-<commit>`

De workflow gebruikt alleen `GITHUB_TOKEN` met `packages: write`, verifieert beide architecturen en de private packagezichtbaarheid, en toont de immutable digests in de workflowsamenvatting.

Publicatie volgt pas nadat de `Validate`-workflow op `main` slaagt. Een nieuw image wordt niet automatisch uitgerold: de geselecteerde digest wordt afzonderlijk bijgewerkt in `spark-homelab`.

## Tijdelijk Azure-rollbackpad

De Azure-backend is gestopt. De VM, `docker-compose.prod.yml`, Terraform, de bestaande Azure-images, configuratie en gegevens blijven behouden als tijdelijk rollbackpad. Na nieuwe schrijfacties op k3s moet bij terugval eerst de actuele database worden overgedragen; start Azure nooit met een verouderde kopie. De Azure Pipeline is verwijderd. De huidige images passen niet zonder aanpassingen in de oude productiestack: poorten, runtimeconfiguratie en migratiestappen verschillen. Volg het homelabrunbook voor terugval; lees [infra/prod/README.md](infra/prod/README.md) voor de grenzen van de historische Azure-configuratie.
