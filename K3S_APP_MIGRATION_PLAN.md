# PNBallie gereedmaken voor k3s

## Voortgang en overdracht

Stand 9 september 2026: de applicatievoorbereiding in dit plan is uitgevoerd.
De `Validate`- en `Publish images`-workflows slagen voor applicatierevisie
`5970d3e14883d73ae88ec06a718706cb1f0f2988`; beide private images ondersteunen
AMD64 en ARM64. Het onderstaande plan blijft het applicatiecontract.

De k3s-deployment en tunnel zijn actief met de definitieve Azure-database.
Schema en volledige inhoud zijn ook na het vervangen van de backendpod
gecontroleerd; een nieuwe versleutelde back-up is geverifieerd. De private
Entra v2-login werkt. De bestaande Azure-backend is na een geslaagde
terugvaltest weer gestopt en blijft als rollbackpad behouden.

De HTTPS-controles voor de frontend, runtimeconfiguratie en healthcheck op
[https://pnballie.nl](https://pnballie.nl) slagen. De gebruiker heeft publiek
aanmelden met Entra en het bekijken van de bestaande spelers en scores
bevestigd. Het opslaan van een score via de publieke URL moet nog worden
bevestigd; Phase 6 blijft in uitvoering. De actuele uitvoering, back-ups en
acceptatie staan in
[Phase 6 van spark-homelab](https://github.com/RomanNekrasov/spark-homelab/blob/main/docs/phase-6-pnballie.md)
en het bijbehorende migratierunbook; toegang tot die private repository is nodig.

## Samenvatting

Maak PNBallie een zelfstandig bouwbare en beveiligde applicatie die twee private
multi-arch GHCR-images publiceert. Deze repository bevat geen Kubernetes-, Flux-,
Tailscale-, Cloudflare- of Spark-configuratie. De bestaande Azure-infrastructuur
blijft als bevroren rollbackpad behouden met een gestopte backend;
GitHub Actions heeft `azure-pipelines.yml` vervangen.

PNBallie is een persoonlijk project. De provinciale huisstijl en bijbehorende
ontwikkelstandaarden zijn daarom niet van toepassing. De huidige Entra-login via
de PNB-tenant blijft voorlopig behouden.

## Implementatiewijzigingen

### Backend en beveiliging

- Voeg Entra JWT-validatie toe met runtimevariabelen `ENTRA_TENANT_ID`,
  `ENTRA_AUDIENCE` en `ENTRA_REQUIRED_SCOPE=user`.
- Gebruik v2-access-tokens (`api.requestedAccessTokenVersion=2`). De audience
  is de API-client-ID-GUID; de frontendscope blijft `api://<API-client-id>/user`.
- Valideer de RS256-handtekening via Entra JWKS, issuer, tenant, audience,
  verloopdatum en scope.
- Bescherm alle `/api/*`-routes. Ontbrekende of ongeldige tokens geven `401`;
  een ontbrekende scope geeft `403`.
- Geef iedere gebruiker uit de ingestelde PNB Entra-tenant toegang. Voeg voor
  deze migratie geen groeps- of accountfilter toe.
- Verwijder wildcard-CORS. Frontend en API gebruiken dezelfde origin.
- Voeg publieke probes toe:
  - `GET /health/live` meldt of het proces leeft;
  - `GET /health/ready` controleert de databaseverbinding en geeft anders `503`.
- Laat ontbrekende productie-authconfiguratie de backend bij het starten met
  een duidelijke fout stoppen.
- Behoud SQLite, SQLModel en het bestaande databaseschema ongewijzigd.

### Frontend en runtimeconfiguratie

- Vervang de ingebakken `VITE_AZURE_*`-waarden door `/config.json`, geladen
  voordat MSAL wordt geïnitialiseerd.
- Gebruik dit configuratiecontract:

  ```json
  {
    "azureClientId": "...",
    "azureTenantId": "...",
    "azureScope": "api://.../user"
  }
  ```

- Voeg een voorbeeldconfiguratie toe. Houd de echte lokale `config.json`
  buiten Git en de Docker-buildcontext.
- Stop de applicatiestart bij ontbrekende of ongeldige configuratie en toon een
  korte, toegankelijke Nederlandstalige foutmelding met `role="alert"`.
- Laat Nginx `/config.json` zonder caching serveren, `/api/*` naar de backend
  sturen en `/healthz` naar backend-readiness routeren.
- Behoud de huidige login-, spelers- en wedstrijdwerking verder ongewijzigd.

### Containers en lokale ontwikkeling

- Maak backend en frontend geschikt voor `linux/amd64` en `linux/arm64`.
- Pin Python-, uv-, Node- en unprivileged-Nginx-images op versie en digest.
- Laat beide runtimecontainers als vaste non-root gebruiker draaien, zonder
  extra capabilities en met ondersteuning voor een read-only root filesystem.
- Laat het backend-image standaard alleen Uvicorn starten. Alembic blijft als
  afzonderlijk commando beschikbaar voor een Compose-migratieservice en later
  een k3s-init-container.
- Laat de frontend op een niet-geprivilegieerde poort, bijvoorbeeld `8080`,
  luisteren.
- Werk de lokale Docker Compose-configuratie bij met:
  - een aparte eenmalige migratieservice;
  - een SQLite-volume dat alleen op `/data` wordt gekoppeld;
  - healthchecks;
  - een gemounte lokale runtimeconfiguratie;
  - read-only containers en alleen de noodzakelijke tijdelijke volumes.
- Laat `docker-compose.prod.yml` en Terraform ongemoeid als gedocumenteerd,
  bevroren Azure-rollbackpad.

### CI en release

- Voeg GitHub Actions toe voor pull requests en `main`.
- Laat pull-requestvalidatie het volgende uitvoeren:
  - Ruff en Pytest;
  - een Alembic-upgrade tegen een tijdelijke SQLite-database;
  - ESLint, Vitest, TypeScript-controle en de Vite-build;
  - een secretscan;
  - containerbuilds en lokale smoketests;
  - ARM64-buildvalidatie via Docker Buildx.
- Publiceer na iedere merge naar `main` deze private multi-arch-images:
  - `ghcr.io/romannekrasov/pnballie-backend:sha-<commit>`;
  - `ghcr.io/romannekrasov/pnballie-frontend:sha-<commit>`.
- Publiceer geen `latest`-tag. Toon beide immutable image-digests in de
  workflowsamenvatting.
- Gebruik alleen `GITHUB_TOKEN` met minimale `packages: write`-rechten en
  controleer dat beide packages privé blijven.
- Verwijder `azure-pipelines.yml`. Verwijder nog geen Azure-resources of
  rollbackdocumentatie.
- Documenteer runtimeconfiguratie, lokale ontwikkeling, controles,
  releaseproces, image-namen en de tijdelijke Azure-rollbackstatus.

## Publieke interfaces

- Nieuwe publieke endpoints: `/health/live`, `/health/ready` en via de frontend
  `/healthz`.
- Nieuw frontendconfiguratiecontract: `/config.json`.
- Nieuwe backend-runtimevariabelen: `ENTRA_TENANT_ID`, `ENTRA_AUDIENCE` en
  `ENTRA_REQUIRED_SCOPE`.
- De payloads van `/api/players`, `/api/matches` en `/api/stats` blijven gelijk,
  maar alle routes vereisen voortaan een geldig bearer-token.
- De containerimages vormen het overdrachtscontract naar `spark-homelab`;
  Kubernetesmanifesten horen niet in deze repository.

## Test- en acceptatieplan

- Test geldige tokens en tokens met een ontbrekende, verlopen of verkeerde
  issuer, tenant, audience, handtekening of scope.
- Bewijs dat ieder `/api/*`-endpoint zonder token wordt geweigerd en de
  health-endpoints zonder token werken.
- Mock Entra discovery en JWKS in tests; CI mag niet van live Entra afhangen.
- Test geldige, ontbrekende en ongeldige `/config.json` en het meesturen van
  bearer-tokens.
- Controleer dat de bestaande backend- en frontendtests blijven slagen.
- Start de Compose-stack vanaf een lege database en bewijs migratie,
  readiness, frontendconfiguratie en API-proxying.
- Start beide images als non-root en met een read-only root filesystem.
- Controleer na publicatie dat ieder manifest zowel `linux/amd64` als
  `linux/arm64` bevat.
- Controleer dat images, logs en repository geen tokens, lokale configuratie of
  databasebestanden bevatten.

## Aannames en grenzen

- De hele ingestelde PNB Entra-tenant mag de app voorlopig gebruiken.
- GHCR-images blijven privé. Het pull-secret wordt in `spark-homelab` beheerd.
- Frontendconfiguratie wordt bij deployment gemount en niet in het image
  ingebakken.
- De Azure-backend blijft gestopt en de oude omgeving blijft als tijdelijk
  rollbackpad beschikbaar. Na nieuwe schrijfacties op k3s moet bij terugval
  eerst de actuele database worden overgedragen.
- Kubernetesopslag, SOPS, Flux, monitoring, back-ups en migratierunbooks vallen
  buiten deze repository en worden in `spark-homelab` uitgewerkt.
- Er worden in deze fase geen functionele of visuele wijzigingen aan de
  PNBallie-interface gedaan, behalve de configuratiefoutmelding.

## Aanbevolen uitvoeringsvolgorde

1. Voeg healthchecks en backend-tokenvalidatie met tests toe.
2. Bouw de frontend om naar runtimeconfiguratie.
3. Harden en test beide containers als non-root en read-only.
4. Werk de lokale Compose-omgeving en documentatie bij.
5. Voeg GitHub Actions voor validatie en private multi-arch-publicatie toe.
6. Publiceer de eerste digest-gepinde release voor gebruik door
   `spark-homelab`.
7. Verwijder de oude Azure-pipeline pas nadat de GitHub-workflows aantoonbaar
   slagen.
