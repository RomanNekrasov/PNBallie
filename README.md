# PNBallie

PNBallie bestaat uit een FastAPI-backend, een Vue-frontend en een SQLite-database. De applicatie wordt als twee private multi-architecture images gepubliceerd voor gebruik vanuit k3s. Kubernetes- en homelabconfiguratie horen in `spark-homelab`, niet in deze repository.

## Lokale ontwikkeling

Vereisten: Python 3.11, [uv](https://docs.astral.sh/uv/), Node.js 22, npm en optioneel Docker Compose.

```bash
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

Start zonder containers met `make dev` of start de geharde stack met `make docker-up`. De frontend is dan beschikbaar op `http://localhost:8080`. Compose voert Alembic eerst eenmalig uit, bewaart alleen `/data` in het SQLite-volume en start daarna backend en frontend als non-root met read-only rootfilesystems.

## Runtimeconfiguratie en endpoints

De backend gebruikt `ENTRA_TENANT_ID`, `ENTRA_AUDIENCE` en `ENTRA_REQUIRED_SCOPE` (standaard in Compose: `user`). In productie (`APP_ENV=production`) stopt de backend direct als een instelling ontbreekt. Alle `/api/*`-routes vereisen een geldig RS256 Entra-token met de juiste issuer, tenant, audience, vervaldatum en scope.

- `GET /health/live`: publieke livenessprobe.
- `GET /health/ready`: publieke database-readinessprobe.
- `GET /healthz`: frontendproxy naar backend-readiness.
- `GET /config.json`: gemounte frontendconfiguratie met caching uitgeschakeld.

Commit nooit `.env`, `frontend/public/config.json`, tokens of databasebestanden.

## Controles

Voer alle lokale controles uit met `make check`. Dit omvat Ruff, Pytest, ESLint, Vitest, TypeScript en de Vite-productiebuild. GitHub Actions controleert daarnaast een Alembic-upgrade vanaf een lege database, secrets, Compose-smoketests, non-root/read-only gedrag en builds voor `linux/amd64` en `linux/arm64`.

## Release

Elke merge naar `main` publiceert zonder `latest`-alias:

- `ghcr.io/romannekrasov/pnballie-backend:sha-<commit>`
- `ghcr.io/romannekrasov/pnballie-frontend:sha-<commit>`

De workflow gebruikt alleen `GITHUB_TOKEN` met `packages: write`, verifieert beide architecturen en de private packagezichtbaarheid, en toont de immutable digests in de workflowsamenvatting.

## Tijdelijk Azure-rollbackpad

`docker-compose.prod.yml`, Terraform en de bestaande Azure-resources blijven bevroren beschikbaar als tijdelijk rollbackpad. De Azure Pipeline is verwijderd; wijzigingen of verwijdering van Azure-resources vallen buiten deze migratie.
