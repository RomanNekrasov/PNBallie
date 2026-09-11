# Van acceptatie naar productie

Promoveer dezelfde immutable containerimages die op
`https://acceptatie.pnballie.nl` zijn getest. Productie behoudt zijn eigen
database, accounts, instellingen en analytics. De demodata wordt niet
overgenomen.

## Bestaande CI/CD

1. Maak een applicatie-PR. GitHub Actions controleert backend, frontend,
   containers en secrets.
2. Na merge naar `main` draait **Validate** opnieuw. Een geslaagde run start
   **Publish images**, dat private ARM64/amd64-images publiceert. De workflow-
   samenvatting bevat de backend- en frontend-digest voor die commit.
3. Maak een PR in `spark-homelab` die de images in
   `cluster/apps/pnballie-acceptance/` op die digests vastzet. Gebruik dezelfde
   backend-digest voor de API, migratie, demo-initialisatie en avatarworker.
4. Na de verplichte `validate`-check en merge past Flux de acceptatieomgeving
   aan. Controleer inloggen, score invoeren, statistieken, beheer en metingen.
5. Maak een afzonderlijke promotie-PR die de geteste digests selecteert in
   `cluster/apps/pnballie/`. Neem alleen de benodigde productieconfiguratie mee:
   productie gebruikt `https://pnballie.nl`, zijn bestaande PVC en eigen
   analytics-website. Voeg geen demo-initialisatie of demo-inloggegevens toe.
6. Na checks en merge rolt Flux productie uit. Controleer readiness, inloggen,
   bestaande historie, een scorewijziging en het operationele dashboard.

Testen, imagepublicatie en Flux-reconciliatie zijn geautomatiseerd. Het kiezen
van een release en maken/mergen van de promotie-PR is nu een GitOps-handeling;
er is nog geen aparte **Promote**-knop in GitHub Actions. Alleen een applicatie-
PR mergen verandert de productie-images niet.

Vermeld in elke promotie-PR de applicatiecommit, beide digests, de uitgevoerde
acceptatiechecks en eventuele migraties. De productie-PR gebruikt dezelfde
digests als acceptatie; opnieuw bouwen is niet nodig.

## Eerste promotie van de nieuwe authenticatie

De huidige productieversie gebruikt nog Entra-only authenticatie. De eerste
promotie van deze versie bevat ook de overstap naar lokale accounts/optioneel
OIDC en groepsgebonden data. Alleen images vervangen is daarvoor onvoldoende.

- Maak een verse, gecontroleerde productiebackup en plan de overgang zodat
  tijdens de migratie geen scorewijzigingen verloren gaan.
- Configureer de productie-origin, veilige cookies, de gekozen authenticatie,
  registratiebeleid, avatarworker en productie-telemetrie in `spark-homelab`.
  Bewaar secrets uitsluitend versleuteld met SOPS.
- Laat Alembic de bestaande database migreren; historische spelers en scores
  komen in de legacygroep. Gebruik geen acceptatiedatabase als bron.
- Registreer de bedoelde beheerder en verifieer diens identiteit. Geef dit
  account vervolgens expliciet beheer over de historie met
  `python -m app.admin claim-legacy --email admin@example.org`, uitgevoerd
  tegen de productiedatabase. Koppel historische spelers daarna bewust via
  Groepsbeheer; namen of een gelijk e-mailadres bewijzen geen eigenaarschap.
- Controleer de werkelijke productie-login, groepsrechten, historische scores
  en score-invoer. Een echte OIDC-provider vereist de providerchecks uit de
  authenticatiedocumentatie.

Zie [authenticatie en groepen](AUTH_AND_GROUPS.md) voor configuratie en
migratie, en de [productie-runbook en fasechecklist](https://github.com/RomanNekrasov/spark-homelab/blob/main/docs/phase-6-pnballie.md)
voor de bestaande scorebackup en publieke acceptatie. De acceptatieomgeving
voltooien voert deze productieovergang niet automatisch uit.

## Terugzetten

Een eerdere image-digest terugzetten gaat via een nieuwe GitOps-PR. Dat werkt
alleen als de database nog compatibel is met die versie. Een databasemigratie
wordt niet teruggedraaid door de image te wijzigen; een eventuele restore is
een afzonderlijke handeling en kan nieuwere scorewijzigingen verliezen.
