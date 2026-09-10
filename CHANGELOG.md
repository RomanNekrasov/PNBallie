# Changelog

Alle relevante wijzigingen aan deze uitbreiding worden hier bijgehouden.
Requirements en acceptatiestatus staan in `REQUIREMENTS.md`.

## Unreleased — 2026-09-10

### Observability en gebruiksanalytics

- Spark-acceptatie afgerond op de private preview: 17 opgeslagen browsertestevents,
  alle negen schermen, DNT en privacygrenzen, 12 operationele en 16 gebruikspanelen
  met werkende Grafana-queries. Vijf koude routes uit de productiebuild worden
  voortaan ook in CI gecontroleerd. De publieke app behoudt haar bestaande release.
- De private Spark-preview draait met gedeeld Umami en echte Prometheus-,
  Loki- en Tempo-records. De browserproef bevestigt virtuele statistiektabs,
  toegestane acties, gevoelige-datafiltering en geen verzameling bij DNT.
- De eerste schermmeting wacht op routerguards en redirects. Een bezoek aan
  het inlogscherm telt daardoor geen tijdelijk, ongezien speelveld meer mee.
- Asynchroon opstarten houdt de entrymodule vrij voor lazy routes. Een nieuwe
  Chromium-controle laadt vijf routes vanuit de productiebuild en voorkomt een
  leeg inlogscherm door een circulaire modulewacht; deze controle draait ook in CI.
- Op Spark de volledige API→opgeslagen job→worker→modelservice-trace bewezen
  met vier spans, zes gecorreleerde logs en een synthetisch foutpad vóór GPU-werk.
  De bron wordt gewist en de wachtrij en worker zijn na de proef hersteld.
- Gedeeld Umami bewaart Jans 752 events en 20 sessies. Rapportages zijn per
  website afgeschermd; synthetische previewproeven bevestigen land/regio/stad
  zonder IP-kolommen. Echte private previewbezoeken hebben meestal geen locatie.
- Op verzoek is extra rollbackwerk voor de hobbyanalytics-migratie vervallen;
  de al geverifieerde kopie wordt gebruikt. PNBallie-productiescores blijven apart.
- Optionele OpenTelemetry-traces en OTLP/JSON-logs toegevoegd voor API,
  avatarwachtrij, worker en private modelservice. Prometheus meet requestlatency,
  fouten, wachtrij en job-/provideruitkomsten zonder gebruikers-ID-labels.
- Avatartracecontext overleeft de duurzame wachtrij en workerherstart; interne
  headers gaan niet naar de optionele cloudprovider. Telemetrystoringen blijven
  buiten het kritieke pad van wedstrijden, login en opdrachten.
- Umami meet expliciete SPA-schermen, statistiektabs en toegestane acties.
  Runtimeconfiguratie, Do Not Track, een korte toelichting en een veilige
  same-origin proxy ondersteunen gedeelde self-hosted analytics.
- Gevoelige invoer, ruwe URLs, querystrings, invitecodes, foto's en credentials
  worden niet opgenomen. Alleen vertrouwde proxyinformatie kan geschat land,
  regio en plaats toevoegen; IP-adressen worden niet als eventveld bewaard.
- Configuratie, datagrenzen en productie-overgang vastgelegd in
  `docs/OBSERVABILITY.md` en het Spark Phase 7-runbook.

### Lokale test en Spark — vervolg

- Op expliciet verzoek de oude `atlas-qwen3-embeddings`-container op de Spark
  gestopt en automatische herstart uitgeschakeld; container en modelcache bewaard.
  Beschikbaar geheugen nam toe van circa 11 naar 111 GiB.
- De nieuwe private avatarservice start op Spark-loopbackpoort 8011. CUDA 13.0,
  PyTorch 2.13.0 en een echte BF16-kernel op de GB10 zijn gecontroleerd.
- Lokale frontend/API gestart op `localhost:5173` en `localhost:8000`, met een
  SSH-tunnel naar de modelservice. De service is niet publiek blootgesteld.
- Na de GPU- en geheugenproeven de lokale avatarworker gestart. Frontend,
  backend, tunnel en worker draaien; het servicetoken en de verbinding naar
  Spark zijn gecontroleerd zonder een extra generatie te starten.
- Afzonderlijke testdatabase gemaakt uit de bestaande lokale database, met
  6 spelers en 35 wedstrijden. Een lokaal testaccount heeft beheerrechten;
  persoonsgegevens en inloggegevens blijven in de genegeerde `.local-test`-map.
- Beide gepinde Qwen-beeldmodellen volledig gedownload. Een echte HTTP-proef met
  de bestaande Roman-avatar leverde een 640 × 640 RGBA-PNG op in 1463,9 seconden
  (24 minuten en 24 seconden). Poppetje, stang, bal en transparantie op lichte en
  donkere achtergrond visueel gecontroleerd. Dit is nog geen portretgelijkenistest
  met een nieuw geüploade gezichtsfoto.
- Schrijfbare private compiler-cache toegevoegd aan de read-only Spark-runtime;
  echte TorchInductor-/Triton-kernelcompilatie gecontroleerd. De timeout voor de
  modelaanvraag verhoogd van 20 naar 60 minuten op basis van de gemeten looptijd.
- Iedere modelopdracht draait in een apart proces om na afloop ook de extra
  CUDA-buffers vrij te geven. Een aanvullende echte GPU-proef hield 1 GiB vast
  tot procesafsluiting; vrij geheugen vóór/na: 111,53/111,54 GiB. Het PNG-protocol,
  procesafsluiting en fouten zijn getest; geen tweede volledige generatie gedaan.
- Lichte alfaruis onder 16/255 wordt verwijderd zonder de kleuren of zachte
  contouren vanaf die grens aan te passen. Het gecontroleerde poppetje heeft
  daarna 58,51% volledig transparante pixels.
- Lokale upload-API via Vite gecontroleerd: sessie/CSRF, profielbinding, upload,
  duurzame wachtrij, status, annulering en bronverwijdering. De proefaanvraag is
  opgeruimd zonder wedstrijdhistorie te wijzigen of een extra GPU-job te starten.
- Op vervolgfeedback de losse navigatiebalk vervangen door een compact
  instellingenmenu in de bestaande paginakoppen. Het huisje blijft naar
  statistieken gaan; profiel, groepen, groepsbeheer en uitloggen zitten achter
  het tandwiel. Het speelveld gebruikt weer de volle schermhoogte.
- Lange avatarjobs tonen een realistische duur, de aanvraagleeftijd en een
  tijdelijke fout bij opnieuw proberen. Badgegegevens blokkeren de profielstatus
  niet meer; vastlopende statusaanvragen verlopen na 30 seconden zodat polling
  herstelt. Annulering legt uit dat er geen nieuwe avatar wordt opgeslagen.
- Na deze wijzigingen: alle 60 frontendtests, ESLint en TypeScript/productiebuild
  geslaagd. Menu, profiel, groepen, beheer, terugnavigatie en uitloggen in de
  browser gecontroleerd, inclusief 390 × 844. Het tijdelijke testaccount en de
  bijbehorende testcompetitie zijn opgeruimd.

### Vastgelegd

- Concrete vervolgstappen voor live OIDC vastgelegd: provider/client, scopes en
  ID-tokenclaims, callback-URLs, backendconfiguratie, de OIDC-uitsluiting in de
  lokale launcher, herstart en verificatie met een echte provider. Accountkoppeling
  en providerlogout zijn expliciet als beperkingen beschreven. OIDC blijft
  ongeconfigureerd; deze aanvulling wijzigt alleen documentatie.
- Goedgekeurde requirements voor groepsbeheer, open authenticatie, tijdcorrecties,
  statistiekfilters, permanente badges, interfaceverbeteringen en AI-avatars.
- Groepen zijn afgeschermde competities met eigen spelers, wedstrijden en beheer.
- Implementatie gestart op `feature/groups-profiles-stats-avatars`.

### Controles

- 94 backendtests geslaagd: authenticatie, OIDC, groepen, concurrente rechten en
  uitnodigingen, migraties, statistieken, avatars en geïsoleerde modelprocessen.
- 60 frontendtests geslaagd: sessies/CSRF, groepswissels, filters, UTC/zomertijd,
  uitnodigingen via login/registratie, uploads, toestemming, annulering,
  instellingenmenu, lange aanvragen en herstel van vastlopende statusaanvragen.
- Ruff, ESLint, TypeScript en Vite-productiebuild geslaagd.
- Alembic-upgrade vanaf lege én oude database, behoud van bestaande relaties,
  schemadriftcontrole en terug-/hermigratie gecontroleerd op tijdelijke databases.
- Docker Compose opgebouwd en gestart; backend en frontend gezond, non-root en
  read-only. Kleine avatarworker gestart met `--once` in het app-image.
- Smokecheck zowel native als via Nginx geslaagd: registratie, cookie/CSRF,
  groepsaanmaak, uitnodiging, profielkoppeling, score, filters en groepsisolatie.
- Browsercontrole op desktop en 390 × 844: registratie, groepsaanmaak, speler
  toevoegen, score invoeren, gefilterde statistieken, uitslag tussen teams en badge.

### Toegevoegd

- E-mail/wachtwoord met Argon2id, HttpOnly-sessies, CSRF, duurzame rate limits,
  wachtwoordwijziging met sessie-intrekking en optionele standaard OIDC met PKCE.
- Afgeschermde competities met eigen spelers, wedstrijden, statistieken en rollen.
- Groepskeuze en toetreden via intrekbare code/link met vervaldatum en gebruikslimiet.
- Beheerpaneel voor groepsnaam, spelers, accountkoppelingen, deactiveren, leden en
  rollen, met behoud van de laatste beheerder en wedstrijdhistorie.
- Eigen profiel met spelersnaam, wachtwoord, blijvende badges en avatarinstellingen.
- Statistiekfilters voor alles/1v1/2v2 en all-time/30 kalenderdagen/50 wedstrijden.
- Historische badges voor eerste winst, 5 en 10 zeges achtereen en 50 wedstrijden.
- Duurzame avatarjobs met veilige foto-upload, status, annuleren, leaseherstel,
  begrensde retries, eigenaarcontroles en privé-PNG-opslag met alphavalidatie.
- Optionele Spark-service met Qwen Image Edit-2511 en Qwen Image Layered; modellen
  laden achtereenvolgens en worden daarna vrijgegeven. Capaciteitscontrole voorkomt
  starten bij onvoldoende geheugen.
- Optionele GPT-afbeeldingsroute met expliciete profielkeuze en toestemming.
- Migraties `20260909_groups` en `20260909_avatars`; operator-CLI `claim-legacy` voor
  gecontroleerde toegang tot de bestaande competitie.
- Configuratie-/migratiedocumentatie en reproduceerbare groepssmokecheck in CI.

### Gewijzigd en opgelost

- Entra/MSAL en verplichte Azure-frontendconfiguratie vervangen door draagbare auth.
- API-tijdstippen bevatten UTC; de frontend toont lokale tijd. Activiteitsindeling
  en kalenderfilters houden rekening met Amsterdamse zomer- en wintertijd.
- Scores staan tussen beide teams in recente uitslagen en de wedstrijdhistorie.
- Menuopties hebben hover- en toetsenbordfocusfeedback; initialen blijven leesbaar.
- `Goals per duel` vervangen door gemiddeld doelverschil (absolute winstmarge).
- `Kleurverdeling` heet `Wins per kleur`, met leidende-kleurindicator per spelvorm.
- Activiteit vóór en vanaf 14:00 heeft aparte grafiekkleuren; tijdzonelabel verwijderd.
- `Hoogste Score` verwijderd; blijvende badges gebruiken de volledige historie.
- Oude groepsantwoorden worden genegeerd na groepswissels. Een laat pollantwoord
  kan een geannuleerde avatarjob niet meer opnieuw activeren.
- Alleen groepsbeheerders kunnen wedstrijden verwijderen. Deactiveren van spelers
  en intrekken van ledentoegang behouden uitslagen.
- SQLite en de bestaande deployment-/Azure-terugvalafspraken behouden.

### Nog extern te verifiëren

- Gelijkenis bij een nieuw geüploade gezichtsfoto beoordelen; de geslaagde echte
  Qwen-proef gebruikte de bestaande Roman-avatar als bron. De automatische
  modeltests blijven gescheiden van deze echte GPU-proef.
- Een echte OIDC-provider en eventuele echte OpenAI-generatie met ingestelde
  credentials. Die externe koppelingen zijn configureerbaar en lokaal getest.
- Publicatie en uitrol via Flux. De private lokale Spark-runtime, modelcache en
  SSH-verbinding zijn inmiddels beschikbaar; productie-uitrol blijft afzonderlijk.
  Er is niets naar productie uitgerold en er zijn geen productiescores gewijzigd.
