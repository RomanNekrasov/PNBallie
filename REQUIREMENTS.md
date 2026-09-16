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

### Koppelen aan een bestaande speler — vervolg

- [x] Na koppelen verdwijnt het vorige profiel zonder wedstrijdhistorie uit alle spelerslijsten.
- [x] Historie blijft beschermd; een bestaande avatar wordt overgenomen als het doelprofiel nog geen avatar heeft. Lopende aanvragen worden veilig geannuleerd.
- [x] Het al achtergebleven dubbele profiel op productie wordt na backup gericht opgeruimd.

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

### Populariteit van statistieken — vervolg

- [x] De bestaande tabmetingen overzichtelijk rangschikken in Grafana.
- [x] Afzonderlijke statistiekblokken meten zodra ze minstens twee seconden
      voor minimaal de helft zichtbaar zijn; bij hoge blokken de schermhoogte
      als grens gebruiken. Verborgen browsertabs tellen niet mee.
- [x] Per bezoek aan de statistieken ieder blok hoogstens één keer tellen;
      scrollen, tabwissels, filters en spelerkeuze veroorzaken geen dubbeltelling.
- [x] Alleen vaste bloknamen versturen, met behoud van DNT/GPC en de bestaande
      gegevensgrenzen. Geen speler-, groeps- of accountgegevens verzamelen.
- [x] In Grafana een ranglijst per blok tonen, op basis van bezoeken met een
      waarneming. Duidelijk maken dat zichtbaarheid geen bewijs van lezen is.
- [x] Implementatie, definities en verificatie documenteren en publiceren;
      daadwerkelijke browsermetingen en rapportages op de Spark-preview testen.

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
- [x] Vervolgfeedback: slogans en dubbele introducties, kopjes en bijschriften
      opruimen. Nuttige instructies, eenheden en foutmeldingen behouden.
- [x] `Over gebruiksstatistieken` van de inlogpagina verwijderen; de toelichting
      blijft beschikbaar in het instellingenmenu.

### Acceptatieomgeving

- [x] `https://acceptatie.pnballie.nl` publiceren als aparte testomgeving, met
      een eigen database en een beheeraccount voor de democompetitie.
- [x] Acht fictieve spelers en 180 wedstrijden over circa 120 dagen toevoegen,
      met 1v1/2v2, verschillende posities en kleuren, dagdelen en blijvende badges.
- [x] Alleen een lege acceptatiedatabase vullen; herstarts bewaren wijzigingen
      die tijdens het testen zijn gemaakt. Geen productiedata overnemen.
- [x] Acceptatie krijgt eigen Umami-rapportage en staging-telemetrie.
- [x] Inloggen, demo-inhoud, statistiekmetingen en de publieke URL verifiëren.

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
- [x] Een eerdere mislukte aanvraag met lokale datum/tijd en uitklapbare
      foutdetails tonen, zodat een oude storing herkenbaar is als historie.
      Opnieuw uploaden blijft mogelijk wanneer een provider is ingesteld;
      actuele uploadfouten blijven zichtbaar. Geen automatische herhaling.
- [x] Eigenaarstoegang, uploadlimieten, afbeeldingsvalidatie en foutpaden bewaken.
- [x] Model op aanvraag starten op de Spark en na verwerking afschalen.
      De echte modelroute is uitgevoerd. Iedere opdracht draait nu in een apart
      proces om ook achtergebleven CUDA-buffers vrij te geven; deze procesgrens is
      afzonderlijk met een echte GPU-allocatie en geheugenmeting gecontroleerd.
- [x] Keuze voor namespace/servicegrens onderbouwen. Kubernetes-/Flux-resources
      horen conform projectafspraak in `spark-homelab`.
- [x] Tests met gesimuleerde modelantwoorden onderscheiden van een echte
      generatieproef; externe afhankelijkheden eerlijk vastleggen.

### Vervolg: gedeelde modelservice — 11 september 2026

- [x] Verloren GPU-toegang in de acceptatieruntime herstellen; native CDI en
      echte gecompileerde CUDA-kernels vóór en na een containerupdate controleren.
- [x] Een bezette gedeelde modelservice laten wachten zonder de drie echte
      generatiepogingen te verbruiken; retries begrenzen en bestaande
      annulering, bronretentie en bescherming tegen verlopen claims behouden.
      52 gerichte avatar-/telemetrytests en Ruff slagen.
- [x] De bijgewerkte worker en private service uitrollen en het wachten op
      gedeelde capaciteit op Spark verifiëren. Vier echte bezetantwoorden met
      een tijdelijke SQLite-database in de acceptatieworker laten pogingen op
      nul, geven leases vrij, behouden de bron en begrenzen de wachttijd.
- [x] Een nieuwe volledige generatie en de resulterende transparante PNG
      controleren. De poging van 11 september gaf geen te controleren PNG; de echte
      profielproef van 12 september slaagt met een opgeslagen 640 × 640 RGBA-PNG.

De GPU-storing en de wachtrijverbetering zijn afzonderlijke bevindingen.
De eerdere definitief mislukte opdracht met gewiste bron wordt niet heropend.
De oude afzonderlijke serviceproef leverde geen te controleren PNG op; de
verlopen proefpod is na inspectie verwijderd. De volgende proef gebruikt een
nieuw tijdelijk spelersprofiel en controleert de volledige route tot opslag.
Details staan in [Eigen spelersavatars](docs/AVATAR_SERVICE.md).

### Vervolg: CUDA-geheugenbudget — 12 september 2026

- [x] Vóór het laden van modelgewichten een PyTorch-allocatorbudget instellen
      in het afzonderlijke modelproces, standaard 70% van het voor CUDA zichtbare
      geheugen. Alleen eindige waarden groter dan 0 tot en met 1 zijn geldig;
      ongeldige configuratie of een mislukte instelling stopt vóór model laden.
- [x] Dezelfde modellen, BF16-instellingen, resolutie en aantallen stappen
      behouden. Vastleggen dat dit budget niet alle driverallocaties omvat en
      geen gegarandeerde vrije hostreserve van 30% oplevert.
- [x] Het budget op Spark uitrollen en met de echte Torch-runtime controleren:
      fractie 0,70 bij 119,7 GiB voor CUDA zichtbaar geheugen. De app passeert
      150 backendtests; de volledige beeldproef is afzonderlijk uitgevoerd.
- [x] Een volledige profielupload via acceptatie, duurzame wachtrij en worker
      afronden, met opgeslagen RGBA-PNG en geheugenmetingen. Eerste poging,
      modelaanvraag 1505,6 seconden, 640 × 640 RGBA en 58,51% transparantie.
      Hostgeheugen herstelt naar 112,207 GiB; de proef gebruikt een bestaande
      repository-avatar en beoordeelt geen nieuwe persoonlijke portretfoto.
- [x] De tijdelijke testrecords na verificatie gericht verwijderen en
      ongewijzigde oorspronkelijke groeps-, profiel-, avatar- en wedstrijddata
      bevestigen. Alleen vijf tijdelijke records zijn verwijderd; de voorstaat
      is ongewijzigd en de testsessie is uitgelogd, zonder volledige databaserestore.

Vervolg voor portretgelijkenis: de lokale prompt- en compositieproeven van
12 september worden bijgehouden in [Avatarproeven](docs/AVATAR_EXPERIMENTS.md).
Drie Edit-varianten met één nieuwe selfie zijn uitgevoerd en visueel beoordeeld;
de drie transparante eindvarianten en een afzonderlijke Layered-versie zijn
vergeleken. Kandidaat 01 met CPU-uitsnede was onze aanvankelijke keuze; de gebruiker
vindt de varianten nog te getekend en vraagt om meer realisme. De aanvullende
Edit-proef slaagt met een fotografischer gezicht in kandidaat 05, onze voorkeur
onder de gegenereerde varianten. Een handmatige CPU-compositie met echte
selfiepixels is eveneens gereed en als transparante PNG gevalideerd. De
uitsnede van kandidaat 05 met witdrempel 225 is gekozen, met een verminderde
maar nog zichtbare lichte haarrand. Runtime- en opruimcontroles slagen; de
standaardprompt, permanente code en bestaande profielen zijn ongewijzigd.

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
- [x] Beide repositories documenteren en pushen; echte verificatie op de Spark.

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

## Eindstatus implementatie — 10 september 2026

Alle appfuncties zijn geïmplementeerd en via pull requests in `main` gepubliceerd.
De private Spark-preview is live geverifieerd, inclusief vastgelegde SPA-events,
Grafana-dashboards en een doorlopende API→worker→modelservice-trace.
Vinkjes betekenen geen upgrade van de publieke authenticatie/productiedata.
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

Er zijn geen foto's naar een cloudprovider gestuurd. Een echte OIDC-provider is
nog niet geconfigureerd en de productie-upgrade is niet uitgevoerd. De lokale
app gebruikt een aparte testkopie met 6 spelers en 35 wedstrijden. Zie docs/AVATAR_SERVICE.md en
docs/AUTH_AND_GROUPS.md voor configuratie en verificatie.

## Eindstatus vervolg — 11 september 2026

Statistiekpopulariteit, opgeschoonde teksten en de aparte acceptatieomgeving
zijn gepubliceerd via app-PR 13 en homelab-PR 52. App-release
`72ef9f47abdcb7458f843d6ad60fd1bd3eb10505` passeert 118 backendtests, 89
frontendtests, lint/build, container-/privacycontroles en vijf koude routes.
De images zijn privaat en ondersteunen ARM64 en amd64.

WebKit op 393px en Chromium op 1440px controleren zowel de uitgerolde preview
als `acceptatie.pnballie.nl`. Alle zeventien blokken hebben echte Umami-records;
drempels, deduplicatie, tabtoewijzing en navigatie zijn gecontroleerd. DNT en
lokale opt-out sturen geen analyticsverzoeken. Inlog-, profiel-, groeps- en
beheerpagina's bevatten de opgeschoonde teksten en tekstvelden van minimaal
16px, zonder horizontale overflow of JavaScript-fouten.

Acceptatie start met acht fictieve spelers en 180 wedstrijden, inclusief alle
negen filtercombinaties, beide dagdelen en blijvende badges. Een profielwijziging
en ingelogde sessie blijven na backendvervanging behouden; de bootstrap slaat
bestaande data over. Prometheus, Loki en Tempo bevatten echte stagingmetingen.
Alle achttien gebruikspanelen in Grafana werken, waaronder de tab- en
blokranglijsten. De vier rapportagerollen blijven strikt gescheiden en
land/regio/stad zijn beschikbaar zonder opgeslagen IP-adressen. De eerste
populariteitscijfers zijn acceptatietestverkeer, geen organisch gebruik.

Zie [acceptatie en verificatie](docs/ACCEPTANCE.md) en [promotie naar productie](docs/RELEASE_PROMOTION.md).
De competitie op `pnballie.nl` behoudt haar bestaande authenticatie, images
en scores; deze acceptatie voert die afzonderlijke migratie niet uit.

## Avatarvervolg — nieuw sjabloon, 14 september 2026

- [x] Nieuwe richting vastgelegd: herkenbaar maar zichtbaar getekend, tussen
  de grove cartoon en de fotografische uitsnede in.
- [x] Drie opties met dezelfde selfie en het nieuwe `player_template.png`:
  zacht geschilderd, lichte inktcontouren en fijne pixelkunst.
- [x] Vergelijking en losse transparante PNG's tonen; resultaten en beperkingen
  vastleggen in `docs/AVATAR_EXPERIMENTS.md`.

De drie transparante PNG-opties zijn gereed. Voorkeur: C, fijne pixelkunst.
Qwen tekent het hoofd afzonderlijk; de nieuwe body blijft vóór eindschaling
behouden. De volledige vergelijking en proefgegevens staan in
`docs/AVATAR_EXPERIMENTS.md`.

## Avatar C naar acceptatie — 15 september 2026

- [x] Optie C in de gewone uploadflow integreren: één lokale Qwen Edit-run
  voor een herkenbaar pixelportret, gevolgd door plaatsing op het nieuwe sjabloon.
- [x] De prompt geschikt maken voor verschillende personen, zonder vaste
  haarkleur, krullen, baard of gezichtsuitdrukking op te leggen.
- [x] Asynchrone wachtrij, privacy, GPU-reservering, tracing en procesopruiming behouden.
- [x] Oudere clients ondersteunen; de nieuwe route expliciet laten bevestigen
  zodat een oude service niet ongemerkt de vorige stijl teruggeeft.
- [x] Tests, private imagepublicatie, GitOps-uitrol en een echte geüploade
  selfie op acceptatie verifiëren, inclusief transparante opslag en geheugenherstel.
- [x] De twee gevraagde spelers toevoegen aan de bestaande productiecompetitie,
  na een gecontroleerde backup, met behoud van bestaande spelers en uitslagen.

Acceptatie draait de geselecteerde C-release sinds 15 september. Na het expliciete
stopverzoek voor embeddings slaagt een echte selfie-upload op de eerste poging,
inclusief transparante opslag, geheugenherstel, tracing en bronopruiming.
De oorspronkelijke demo-/productiegegevens zijn behouden; zie `docs/AVATAR_SERVICE.md`.

## iPhone-upload en capaciteit — 15 september 2026

- [x] Foto's uit de iPhone-bibliotheek kiezen, inclusief HEIC/HEIF en ontbrekende MIME-types.
- [x] Foto's tot 20 MB en 50 megapixels begrensd verkleinen; EXIF/GPS verwijderen en oriëntatie behouden.
- [x] Beschikbare servercapaciteit tonen en onbruikbare uploads weigeren vóór opslag/quotaverbruik.
- [x] Bij tijdelijk geheugentekort wachten zonder de drie echte pogingen te verbruiken.
- [x] Tests, documentatie, publicatie en acceptatie-uitrol; live 48-MP-HEIC-upload en bronopruiming gecontroleerd.
- [ ] Fotoselectie op de echte iPhone bevestigen; backend- en componenttests vervangen de toesteltest niet.
- [x] De gebruiker heeft de embeddingsdienst expliciet laten stoppen. Container en modelbestanden blijven behouden; de C-test is geslaagd.

## E-mailverificatie — 16 september 2026

- [x] SMTP via Brevo (standaard SMTP/STARTTLS), secrets alleen server-side/SOPS.
- [x] Nieuwe en bestaande lokale accounts moeten hun e-mailadres bevestigen voordat groepsgegevens toegankelijk zijn.
- [x] Eenmalige willekeurige link, uitsluitend tokenhash opgeslagen, 24 uur geldig; opnieuw versturen met limieten.
- [x] Bevestigen via expliciete POST, geen automatische login of verificatie door mail-scanners; token uit URL-fragment en niet in telemetry.
- [x] Heldere registratie-/verificatiepagina, behoud van uitnodiging, foutafhandeling bij mailstoring.
- [x] OIDC-verificatie expliciet vastleggen; geen automatische koppeling op e-mailadres.
- [x] Migratie, veiligheids-/frontendtests, documentatie, acceptatie-uitrol en echte SMTP-verzending testen.
- [x] Ontvangst en bevestiging via de echte mailbox door de gebruiker bevestigd; serverbewijs en verbruikte link gecontroleerd.

Productie blijft op zijn bestaande release. De gedeelde fictieve demoaccount heeft
geen echte mailbox en krijgt geen stilzwijgende verificatie-uitzondering.

## Wachtwoord vergeten en inloggen op de tafel — 16 september 2026

- [x] Link ‘Wachtwoord vergeten’ op het inlogscherm en mail via bestaande SMTP-dienst.
- [x] Geen accountlek via antwoord; limieten op aanvragen en bevestigen, willekeurig gehashte link van 30 minuten.
- [x] Eenmalige reset zonder vooraf inloggen; alle oude sessies en herstel-/verificatielinks intrekken. Geen lokaal wachtwoord toevoegen aan OIDC-only accounts.
- [x] Reset via mailbox bewijst e-mailbezit; ook een nog onbevestigd lokaal account kan zo veilig herstellen.
- [x] Formulier voor nieuw wachtwoord met bevestiging; geen automatische reset door link openen of mailscanner.
- [x] Illustratie links verwijderen en één gecentreerde login binnen de herkenbare voetbaltafel plaatsen, met dezelfde veld- en tafelkleuren als scoreregistratie.
- [x] Mobiel/desktop controleren, documenteren en naar acceptatie uitrollen; productie blijft ongewijzigd.

## Wins per kleur — 16 september 2026

- [x] Toon één kleurverdeling voor de spelvorm onder Tandwiel → Statistieken bekijken; standaard alles samen, optioneel alleen 1v1 of 2v2.
- [x] Controleer alle drie keuzes en rol de frontend via acceptatie uit naar productie (app PR 37; homelab PR 77/78; beide omgevingen leveren dezelfde gecontroleerde statistiekbundel).

## Productiepromotie — 16 september 2026

- [x] Promoveer de geteste acceptatie-images en benodigde authenticatie-, mail-, avatar- en observabilityconfiguratie naar pnballie.nl.
- [x] Behoud de productiewedstrijden en spelers; maak en controleer een verse versleutelde backup en migratieproef.
- [x] Neem uitsluitend het al geverifieerde persoonlijke account van de operator over, maak het beheerder en koppel het aan de bestaande speler Roman.
- [x] Verwijder het ongebruikte spelersprofiel Beheerder zonder wedstrijdhistorie te verwijderen; kopieer geen demodata.
- [x] Controleer productie, rechten, data, backups en metingen; documenteer de overgang.

## Tafelrand — 16 september 2026

- [x] Teken de witte doellijnen achter de bruine tafelrand in de gedeelde tafelillustratie.
- [x] Controleer de weergave en rol uit naar acceptatie (PR 34; homelab PR 73; live mobiele login gecontroleerd).

## Rustige statistieken en wedstrijdbeheer — 16 september 2026

- [x] Verwijder periodekeuze en de dubbele duelteller uit de kop; statistieken tonen standaard alle historie.
- [x] Verplaats Alles samen / 1v1 / 2v2 naar het bestaande tandwielmenu, met zichtbare aanduiding bij een actieve beperking.
- [x] Wedstrijdbeheer via het tandwiel, uitsluitend voor beheerders van de actieve groep; blader ook door oudere wedstrijden.
- [x] Wijzig scores, spelers/opstelling en lokaal tijdstip; valideer teams en sla UTC op. Behoud reeds deelnemende inactieve spelers.
- [x] Verwijder met expliciete bevestiging; voorkom overschrijven/verwijderen van inmiddels gewijzigde wedstrijden.
- [x] Pas statistieken, ELO en historisch afgeleide badges toe op de gecorrigeerde geschiedenis.
- [x] Maak het expliciet aangewezen, geverifieerde acceptatieaccount beheerder van Democompetitie; behoud overige rechten en gegevens.
- [x] Documenteer/test/publiceer en controleer op acceptatie; productie blijft op de bestaande release.
