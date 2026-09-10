# PNBallie — groepen, profielen, statistieken en avatars

Vastgesteld met Roman op 9 september 2026. Dit bestand beschrijft de goedgekeurde
scope en houdt de acceptatiestatus bij. Wijzigingen en controles staan in
`CHANGELOG.md`.

## 1. Beheer en afgeschermde groepen

- [x] Iedere groep heeft eigen spelers, wedstrijden, statistieken en beheerders.
- [x] Een gebruiker kan een groep maken of via een code/link lid worden.
- [x] Een groepsbeheerder kan spelers toevoegen en beheren.
- [x] Groepsbeheerders kunnen uitnodigingen aanmaken en intrekken.
- [x] Passende beheerfuncties: leden verwijderen, beheerders aanwijzen en spelers
      deactiveren zonder wedstrijdhistorie te verliezen.
- [x] Groepsrechten worden in de API afgedwongen, ook bij rechtstreeks gebruik van
      identifiers van een andere groep.
- [x] Bestaande spelers en wedstrijden blijven behouden in een bestaande groep.

## 2. Open authenticatie

- [x] Verplichte Entra ID-/provincieafhankelijkheid vervangen door een oplossing
      die andere gebruikersgroepen zelf kunnen gebruiken.
- [x] Gangbare inlogopties ondersteunen; e-mail/wachtwoord en standaard OIDC
      beoordelen en de gekozen oplossing documenteren.
- [x] Inloggen, groepskeuze en uitnodigingen vormen één bruikbare gebruikersflow.
- [x] Eigen identiteit is gekoppeld aan het eigen spelersprofiel binnen een groep.
- [x] Migratie van bestaande gegevens en toegang documenteren.

## 3. Tijd

- [x] UTC consequent gebruiken voor opslag/API en ondubbelzinnige API-tijdstippen.
- [x] Frontend toont correcte lokale tijd, inclusief zomer- en wintertijd.
- [x] Datumfilters en activiteit vóór/na 14:00 gebruiken de bedoelde lokale tijd.
- [x] Overbodig zichtbaar label `Europe/Amsterdam` bij statistieken verwijderen.
- [x] Regressiecontroles voor UTC, lokale datums en zomertijd toevoegen.

## 4. Statistieken

- [x] Filter: alle wedstrijden, 1v1 of 2v2.
- [x] Periodefilter: all-time en recente wedstrijden. Implementatiekeuze:
      laatste 30 dagen én laatste 50 wedstrijden, zolang dit eenvoudig blijft.
- [x] Filters werken consistent op de relevante statistieken en lege selecties.
- [x] `Goals per Duel` vervangen door gemiddeld doelverschil, met dezelfde
      definitie als de andere doelverschilstatistieken (voorbeeld gebruiker: 3,6).
- [x] Speelactiviteit toont vóór en na 14:00 met verschillende grafiekkleuren.
- [x] `Kleurverdeling` hernoemen naar `Wins per kleur`.
- [x] Bij de 1v1- en 2v2-verdeling een oranje/blauwe indicator voor de leidende
      kleur tonen, met een duidelijke gelijke-standweergave.

## 5. Profielen en permanente badges

- [x] Achievement `Hoogste Score` verwijderen.
- [x] Permanente badges afleiden uit de volledige wedstrijdhistorie.
- [x] Minimaal een badge voor ooit vijf wedstrijden achtereen winnen.
- [x] Verdiende badges blijven zichtbaar nadat een winreeks is afgelopen en bij
      het kiezen van een andere statistiekperiode.
- [x] Het vlammetje blijft uitsluitend de actuele winreeks tonen.
- [x] Bestaande historie telt mee bij het toekennen van badges.

## 6. Interface

- [x] Score tussen de spelers plaatsen, bij 2v2 tussen beide teams.
- [x] Menuopties krijgen duidelijke hover- en toetsenbordfocusfeedback.
- [x] Nieuwe beheer-, groeps- en profielpagina's passen bij de bestaande app en
      blijven bruikbaar op telefoon en desktop.
- [x] Vervolgfeedback: de losse navigatiebalk verwijderen. Het huisje op het
      speelveld blijft naar statistieken leiden; profiel, groepen en beheer
      komen in een compact instellingenmenu in de bestaande paginakop.

## 7. Asynchrone AI-avatar

- [x] Foto uploaden vanuit het eigen spelersprofiel.
- [x] Hoofd/gezicht verwerken op hetzelfde type poppetje als de huidige avatars,
      in een consistente cartoon-/pixelstijl.
- [x] Resultaat opslaan als PNG met een daadwerkelijk transparant alfakanaal.
- [x] Onderzoeken welk Qwen-beeldmodel geschikt is; een vision/chatmodel is niet
      automatisch een beeldgenerator.
- [x] Haalbaarheid toetsen aan de Spark en de inrichting in
      `/Users/roman/PycharmProjects/spark-homelab/`.
- [x] Een transparantieproef uitvoeren wanneer de benodigde runtime beschikbaar
      is; direct genereren onderscheiden van een achtergrondverwijderingsstap.
- [x] Bij onvoldoende lokale kwaliteit een GPT-endpoint als configureerbaar
      alternatief ondersteunen.
- [x] Verwerking via een duurzame asynchrone wachtrij en worker/service; de
      frontend blijft bruikbaar en toont status/fouten.
- [x] Eigenaarstoegang, uploadlimieten, afbeeldingsvalidatie en foutpaden bewaken.
- [x] Model op aanvraag starten op de Spark en na verwerking afschalen.
      De echte modelroute is uitgevoerd. Iedere opdracht draait nu in een apart
      proces om ook achtergebleven CUDA-buffers vrij te geven; deze procesgrens is
      afzonderlijk met een echte GPU-allocatie en geheugenmeting gecontroleerd.
- [x] Keuze voor namespace/servicegrens onderbouwen. Kubernetes-/Flux-resources
      horen conform projectafspraak in `spark-homelab`.
- [x] Tests met gesimuleerde modelantwoorden onderscheiden van een echte
      generatieproef; externe afhankelijkheden eerlijk vastleggen.

## 8. Tracing, telemetry, logging en gebruiksanalytics

Vervolgopdracht van 9 september 2026; uitwerking en Spark-acceptatie staan ook in
`spark-homelab/docs/phase-7-shared-observability.md`.

- [x] Grafana uitbreiden met applicatiemetrics, doorlopende traces en gecorreleerde logs.
- [x] API, avatarworker en private modelservice instrumenteren, met behoud van
      de asynchrone tracecontext en zonder gevoelige inhoud te loggen.
- [x] Umami aansluiten op een gedeelde analyticsomgeving met afzonderlijke
      websites en rapportages voor Jan Doorlopen en PNBallie.
- [x] SPA-schermen, statistiektabs en belangrijke interacties expliciet meten,
      ook als de browser-URL niet verandert.
- [x] Geschatte land/regio/stad van bezoekers ondersteunen via vertrouwde
      IP-doorgifte; geen GPS, opgeslagen IP-adressen, replay of formulierinhoud.
- [x] Tracking uitschakelen bij Do Not Track; analytics en telemetry mogen de
      applicatie niet blokkeren bij uitval.
- [x] Verzameling via dezelfde origin, beheer-/rapportage- en observability-
      endpoints alleen privaat; previewdata gescheiden van productiegebruik.
- [x] De geverifieerde analyticskopie activeren en PNBallie-productiehistorie behouden.
      Op 10 september accepteert de gebruiker eventueel verlies van hobbyanalytics;
      extra rollbackwerk voor Jan Doorlopen is daarom geen vereiste.
- [ ] Beide repositories documenteren en pushen; echte verificatie op de Spark.

## Uitvoering en randvoorwaarden

- Bestaande stack behouden: FastAPI, SQLModel, SQLite, Alembic, Vue en TypeScript.
- Dit is volgens `CLAUDE.md` een persoonlijk project. De bestaande spelvormgeving
  blijft leidend; geen omzetting naar een provinciale website.
- De expliciet goedgekeurde open authenticatie vervangt de eerdere Entra-eis in
  de projectdocumentatie.
- De expliciet gevraagde Spark-uitvoering sluit aan op de bestaande k3s-keuze;
  SQLite en de tijdelijke Azure-terugvalset blijven behouden.
- Geen productiegegevens aanpassen tijdens lokale ontwikkeling en verificatie.
- Werk op een featurebranch; documenteer migraties, configuratie en tests.

## Acceptatie

Per onderdeel: passende gedragstests en autorisatiecontroles. Voor de complete
wijziging: Ruff, Pytest, ESLint, Vitest, TypeScript, productiebuild, Alembic-upgrade
en schemadriftcontrole. Nieuwe gebruikersflows ook lokaal in de browser bekijken.
Uitrollen naar productie en een echte GPU-generatieproef zijn afzonderlijke
verificatiestappen en worden niet afgeleid uit alleen geslaagde unittests.

## Eindstatus lokale implementatie — 9 september 2026

Alle appfuncties zijn geïmplementeerd op de featurebranch. Vinkjes geven de
implementatie en lokale verificatie aan; ze betekenen geen productie-uitrol.
Er slagen 100 backendtests en 75 frontendtests. Lint, TypeScript, productiebuild,
Alembic-upgrade en schemadriftcontrole slagen. De Docker-stack start non-root en
read-only; een smokecheck via Nginx bewijst registratie, uitnodigingen,
profielkoppeling, score-invoer, filters en groepsisolatie. De kleine avatarworker
start ook in het app-image. Browsercontroles omvatten registratie, groepsaanmaak,
spelersbeheer, wedstrijd invoeren, filters, uitslagen en profielbadges op desktop
en een viewport van 390 × 844.

Op expliciet vervolgverzoek is de oude Qwen-embeddingscontainer gestopt en de
automatische herstart uitgezet. Daarmee kwam circa 111 GiB vrij. Beide gepinde
Qwen-beeldmodellen zijn gedownload en draaien in een private Spark-service via
een SSH-tunnel. Een echte HTTP-proef met de bestaande Roman-avatar is geslaagd:
640 × 640 RGBA, een compleet poppetje met stang en bal, visueel gecontroleerd op
lichte en donkere achtergrond. De volledige generatie duurde 1463,9 seconden
(24 minuten en 24 seconden). Dit bewijst de lokale beeld- en transparantieroute;
gelijkenis bij een nieuw geüpload portret blijft door de speler te beoordelen.
De uiteindelijke PNG heeft 58,51% volledig transparante pixels. Lichte alfaruis is
verwijderd, met behoud van zachte contouren. Na de eerste volledige proef bleven
extra CUDA-buffers vastgehouden; daarom draait de modelcode nu in een apart proces.
De aanvullende echte CUDA-proef hield 1 GiB vast tot procesafsluiting en herstelde
het beschikbare geheugen van 111,53 naar 111,54 GiB. Voor die procesaanpassing is
geen tweede volledige beeldgeneratie uitgevoerd.

De losse navigatiebalk is vervangen door het instellingenmenu; de route via
huisje, statistieken en menu is opnieuw in de browser gecontroleerd op desktop
en 390 × 844.

Er zijn geen foto's naar een cloudprovider gestuurd. Een echte OIDC-provider en
publieke uitrol zijn nog niet geconfigureerd. De lokale app gebruikt een aparte
testkopie met 6 spelers en 35 wedstrijden. Zie docs/AVATAR_SERVICE.md en
docs/AUTH_AND_GROUPS.md voor configuratie en verificatie.
