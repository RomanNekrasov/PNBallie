# Authenticatie, groepen en migratie

Besluit: de goedgekeurde uitbreiding van 9 september 2026 maakt PNBallie bruikbaar
zonder provincieaccount of Entra ID. De bestaande FastAPI/Vue/SQLite-stack blijft
behouden. Argon2 en de bestaande PyJWT/httpx-libraries verzorgen respectievelijk
wachtwoordhashing en OIDC. Een externe identityserver is optioneel.

## Lokale accounts en sessies

Registratie vraagt een naam, e-mailadres en wachtwoord van minstens 12 tekens.
Met `AUTH_REQUIRE_EMAIL_VERIFICATION=true` stuurt registratie een verificatiemail.
Nieuwe en bestaande lokale accounts moeten bevestigen vóór toegang tot groepen.
Dezelfde SMTP-instelling activeert wachtwoordherstel per mail.
Het geeft op zichzelf geen toegang tot een bestaande competitie. Toegang volgt
uitsluitend uit groepsaanmaak, een geldige uitnodiging of expliciet operatorbeheer.

De server bewaart een Argon2-wachtwoordhash en uitsluitend een hash van het
willekeurige sessietoken. De browser krijgt een HttpOnly-cookie, SameSite=Lax,
met een maximale levensduur van 14 dagen. De CSRF-token blijft in het geheugen van
de frontend en wordt na een paginavernieuwing via `/api/auth/me` opgehaald.
Wachtwoord wijzigen trekt alle eerdere sessies in en maakt één nieuwe sessie.

Groepskeuze mag lokaal worden onthouden; iedere aanvraag controleert opnieuw of
de gebruiker lid is. De app wist groepsgegevens direct bij groepswissel of logout
en negeert antwoorden van oudere aanvragen. Onbekende en vreemde groepen geven
dezelfde 404-respons. Login, registratie, uitnodigingen en avataruploads hebben
limieten die ook na een procesherstart gelden.

## E-mailverificatie via SMTP

Stel `AUTH_REQUIRE_EMAIL_VERIFICATION=true`, `SMTP_HOST`, `SMTP_PORT`,
`SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL` en `SMTP_FROM_NAME` in op
alleen de API. Poort 587 vereist STARTTLS; 465 gebruikt directe TLS, steeds met
certificaatcontrole. Brevo is de eerste provider; er is geen providerspecifieke API.
De afzender en het domein moeten bij de mailprovider geverifieerd zijn. Ontbrekende
configuratie verhindert starten als verificatie verplicht is. Standaard staat de
functie uit zodat lokale ontwikkeling zonder maildienst blijft werken.

Registratie maakt een sessie en probeert één mail te sturen. Een mailstoring
verwijdert het account niet: de gebruiker kan inloggen en opnieuw aanvragen.
Er is geen achtergrond-mailqueue; verzending heeft begrensde SMTP-timeouts.
Limieten: eenmaal per minuut en vijfmaal per dag per account, tienmaal per uur
per client-IP, tweehonderdmaal per dag per installatie. Opnieuw aanvragen vervangt
de vorige link. Na een onduidelijke SMTP-timeout kan een mail toch bezorgd worden;
alleen de nieuwste link blijft geldig. Bezorging in de inbox moet apart worden
gecontroleerd: SMTP-acceptatie alleen bewijst dat niet.

De server bewaart uitsluitend een SHA-256-hash van een willekeurig 256-bit-token,
het account/adres, de veilige terugkeerroute en een vervaltijd van 24 uur.
`/verify-email#token=…` houdt het token buiten HTTP-URLs en Referer-headers.
De pagina verwijdert het fragment en bewaart het token alleen in componentgeheugen.
De link opnieuw openen is nodig na verversen. Alleen een expliciete POST met een
sessie van hetzelfde account en geldige CSRF-token kan bevestigen. GET/scanners,
verkeerde accounts, verlopen links en hergebruik bevestigen niets. Verificatie
maakt geen nieuwe sessie en koppelt geen bestaande speler. Een uitnodigingsroute
blijft bij het challenge opgeslagen zodat de gebruiker na bevestiging kan doorgaan.
Mailadressen, SMTP-responses en tokens worden niet naar telemetry gestuurd.

De migratie markeert geen bestaande accounts automatisch als geverifieerd.
Een succesvolle OIDC-login legt bewijs vast als de provider `email_verified: true`
levert voor exact het opgeslagen adres. Groeps-/spelers-/score-/avatar-API's
weigeren onbevestigde accounts wanneer verificatie verplicht is. Inloggen,
uitloggen en mailverificatie blijven beschikbaar.

Acceptatie heeft een fictieve demoaccount zonder echte mailbox. Ook die is na
inschakelen geblokkeerd voor groepsgebruik; geef testers een uitnodiging en laat
ze hun eigen e-mailadres bevestigen. De demoaccount krijgt geen bypass. Productie
krijgt deze wijziging pas bij een afzonderlijke promotie, inclusief SMTP-secret.

## Configuratie

| Variabele | Betekenis |
| --- | --- |
| `DATABASE_URL` | Standaard native `sqlite:///./pnballie.db`; containers gebruiken `/data`. |
| `APP_ENV` | `development` lokaal; `production` voor een uitgerolde app. |
| `AUTH_APP_ORIGIN` | Exacte browserorigin, zonder pad. Native standaard `http://localhost:5173`. |
| `AUTH_COOKIE_SECURE` | Lokaal `false`; in productie verplicht `true`. |
| `AUTH_ALLOW_REGISTRATION` | Nieuwe accounts toestaan, standaard `true`. |
| `OIDC_ISSUER` | Optionele HTTPS issuer-URL van bijvoorbeeld Keycloak of Authentik. |
| `OIDC_CLIENT_ID` | Client-ID bij de provider; samen met issuer instellen. |
| `OIDC_CLIENT_SECRET` | Secret voor een confidential OIDC-client, alleen op de backend. |
| `OIDC_NAME` | Naam van de inlogknop; standaard `Single sign-on`. |

De backend weigert in productie te starten zonder expliciete HTTPS-origin en
secure cookies. Lokale Compose is daarom expliciet `development` bij HTTP;
de containers behouden non-root, read-only rootfilesystem en beperkte capabilities.
Native ontwikkeling met het Compose-voorbeeldbestand vereist het aanpassen van de
origin naar poort 5173. De frontend heeft geen eigen identityconfiguratie meer.

In productie moet een vertrouwde reverse proxy de echte client-IP doorgeven.
Stel Uvicorns vertrouwde proxy-IP's nauwkeurig in; vertrouw nooit een publiek
aangeleverde `X-Forwarded-For` zonder proxyvalidatie. Zonder forwarding blijft
authenticatie veilig, maar delen gebruikers achter dezelfde proxy IP-limieten.

## Standaard OIDC

Registreer `${AUTH_APP_ORIGIN}/api/auth/oidc/callback` als redirect-URI bij de provider.
De flow gebruikt authorization code + PKCE S256, eenmalige state, nonce en een
afzonderlijke HttpOnly state-cookie. ID-tokens worden gecontroleerd op handtekening,
issuer, audience, verloopdatum, nonce en authorized party. Ondersteunde algoritmen
zijn RS256/384/512 en ES256/384/512.

Een nieuw OIDC-account vereist een geverifieerd e-mailadres van de provider. De
stabiele identiteit is `(issuer, sub)`. Accounts worden nooit automatisch aan een
bestaand lokaal account gekoppeld via alleen het e-mailadres. Een adresconflict
vraagt om de oorspronkelijke inlogmethode; automatische accountkoppeling is geen
onderdeel van deze release. Een uitnodigingspad blijft na de OIDC-omleiding behouden.

Geautomatiseerde tests simuleren een OIDC-provider en verifiëren positieve en
negatieve paden. De gekozen echte provider moet vóór uitrol met de productieorigin
worden gecontroleerd.

### Nog uit te voeren voor een echte OIDC-provider

Status op 9 september 2026: de code en gesimuleerde tests zijn aanwezig, maar er
is nog geen echte provider aangesloten of live inlogflow geverifieerd. De huidige
lokale app meldt `"oidc": null` via `/api/auth/providers`.

- [ ] Kies of richt een provider in, bijvoorbeeld Keycloak of Authentik. Browser
      en backend moeten de betreffende login-, discovery-, token- en JWKS-URLs
      kunnen bereiken. Gebruik HTTPS; HTTP is alleen toegestaan voor localhost
      tijdens ontwikkeling.
- [ ] Maak een OIDC-client voor authorization code met PKCE S256. Een confidential
      client moet `client_secret_basic` ondersteunen: de backend verstuurt het
      clientsecret met HTTP Basic bij het omwisselen van de code. De gevraagde
      scopes zijn `openid email profile`. Zorg dat het ID-token een stabiele
      `sub`, `email` en de boolean `email_verified: true` bevat; `name` is optioneel.
      Alleen claims op het userinfo-endpoint zijn onvoldoende: de app leest het
      ID-token. Gebruik een van de hierboven genoemde ondertekeningsalgoritmen.
- [ ] Registreer de exacte callback voor de gekozen omgeving. Voor de huidige
      lokale app is dat `http://localhost:5173/api/auth/oidc/callback`; voor Compose
      met de standaardorigin `http://localhost:8080/api/auth/oidc/callback`.
      Productie gebruikt `${AUTH_APP_ORIGIN}/api/auth/oidc/callback` met HTTPS.
- [ ] Configureer `OIDC_ISSUER`, `OIDC_CLIENT_ID`, zo nodig `OIDC_CLIENT_SECRET`,
      en optioneel `OIDC_NAME` op de backend. Bewaar het secret buiten Git en de
      frontend. Nieuwe OIDC-accounts vereisen `AUTH_ALLOW_REGISTRATION=true`.
      Providerrollen kennen geen groepsrechten toe; die beheert PNBallie zelf.
- [ ] Pas voor de huidige persoonlijke testomgeving eerst
      `.local-test/run.py` aan: `environment()` verwijdert nu bewust alle
      variabelen met prefix `OIDC_`. Haal alleen die prefix uit de uitsluitlijst,
      zodat expliciet geëxporteerde OIDC-instellingen worden doorgegeven. Behoud
      de overige uitsluitingen en de aparte testdatabase. Een `.env`-bestand
      wordt door deze launcher niet automatisch ingelezen.
- [ ] Herstart de backend met de nieuwe omgeving. Bij deze launcher hergebruikt
      `start` bestaande processen; gebruik `stop` gevolgd door `start` nadat
      eventuele avatarjobs zijn afgerond, omdat dit ook de lokale worker herstart.
      Controleer vervolgens dat `/api/auth/providers` een OIDC-naam/login-URL
      teruggeeft en de bijbehorende knop op de loginpagina verschijnt. Dit bewijst
      alleen dat de configuratie is ingeladen, nog niet dat aanmelden werkt.
- [ ] Verifieer met de echte provider: eerste login met een geverifieerd account,
      opnieuw inloggen als dezelfde gebruiker, terugkeer naar een uitnodiging,
      groepsrechten en uitloggen. Controleer ook dat een bestaand lokaal account
      met hetzelfde e-mailadres niet automatisch wordt gekoppeld. Uitloggen
      beëindigt de PNBallie-sessie; uitloggen bij de identityprovider zelf is
      niet geïmplementeerd.
- [ ] Herhaal de inlogproef vóór productie-uitrol met de echte HTTPS-origin,
      callback, secure cookies en reverse proxy. Noteer provider, configuratie
      zonder secrets en testresultaat in de changelog. Deploymentconfiguratie
      hoort in `spark-homelab`.

## Groepsrechten en spelers

| Actie | Groepslid | Groepsbeheerder |
| --- | --- | --- |
| Spelers, scores en statistieken bekijken | Ja | Ja |
| Wedstrijd invoeren | Ja | Ja |
| Eigen spelersnaam/avatar wijzigen | Ja | Ja |
| Spelers toevoegen, hernoemen, deactiveren of koppelen | Nee | Ja |
| Groepsnaam, uitnodigingen en ledenrollen beheren | Nee | Ja |
| Wedstrijd verwijderen | Nee | Ja |

Spelersnamen zijn uniek binnen een groep. Hetzelfde account kan in meerdere
groepen een eigen spelersprofiel hebben. Een automatische profielkoppeling
gebruikt de account-ID, nooit een voornaam. Koppelen aan een historische speler
kan de automatisch aangemaakte lege speler vervangen; als die al wedstrijden
heeft, weigert de server dit om geschiedenis niet ongemerkt te verplaatsen.
Het vervangen lege profiel wordt verwijderd, ook uit de beheerlijst. Zijn avatar
wordt overgenomen als de historische speler nog geen avatar heeft; een bestaande
doelavatar blijft staan. Oude avataropdrachten blijven als historie beschikbaar,
maar lopende aanvragen worden geannuleerd en bronfoto’s gewist. Een nieuwe
aanvraag kan daarna vanuit het gekoppelde profiel worden gestart.

Uitnodigingen bevatten een willekeurige code van 144 bits. Alleen de hash wordt
opgeslagen; de code wordt bij aanmaak één keer getoond. Ze zijn 1–30 dagen geldig,
optioneel beperkt in aantal nieuwe leden, en intrekbaar. De gebruiksteller is
atomair. Toetreden met dezelfde uitnodiging is voor een bestaand lid idempotent.
Intrekken blokkeert nieuwe toetredingen; bestaande leden beheer je afzonderlijk.

Leden verwijderen trekt toegang in en deactiveert hun speler. Wedstrijden blijven
bewaard. Controles met een schrijfslot voorkomen dat twee gelijktijdige wijzigingen
de laatste beheerder verwijderen. Avatarpublicatie controleert opnieuw of de
eigenaar nog lid is en aan dezelfde actieve speler gekoppeld is.

## Bestaande database migreren

1. Stop writes naar de bedoelde database en maak een consistente SQLite-back-up.
   Gebruik het bestaande homelabrunbook; kopieer geen actieve WAL-database als een
   los bestand zonder back-upmechanisme.
2. Test met een kopie: `DATABASE_URL=sqlite:////pad/kopie.db uv run alembic upgrade head`.
3. Controleer aantallen spelers, wedstrijden en wedstrijdspelers. Hun ID's blijven
   gelijk. Alle bestaande rijen krijgen groep 1: **Bestaande competitie**.
4. Registreer het bedoelde account in de nieuwe app. Controleer de eigenaar buiten
   de app voordat je beheerrechten toekent.
5. Voer als operator uit, vanuit `backend/`:

   ```bash
   DATABASE_URL=sqlite:////pad/pnballie.db uv run python -m app.admin claim-legacy --email admin@example.org
   ```

6. Vernieuw de groepslijst. Koppel in Beheer het account aan de bestaande speler.
   Nodig de andere spelers uit en koppel hun historische profielen waar nodig.
7. Controleer login, ledenrechten, historische statistieken, tijdstippen, nieuwe
   scores en back-up/restore voordat de nieuwe versie publiek wordt gebruikt.

De migratie creëert bewust geen beheerder op basis van een onbevestigd e-mailadres
of oude voornaam. De operatorstap is noodzakelijk omdat de oude applicatie geen
betrouwbare account-naar-spelerkoppeling opsloeg.

## Terugval

Gebruik bij terugval de eerdere images én de bijbehorende databaseback-up.
De nieuwe multi-groepsdata past niet veilig in het oude Entra-schema. Alembic
weigert daarom terug te gaan naar het oude schema zodra nieuwe groepen bestaan.
Een downgrade van de avatarmigratie verwijdert avatars en jobs; maak eerst een
back-up. Bestaande Azure/Terraform-bestanden zijn historische terugvaldocumentatie
en zijn niet geschikt om de nieuwe images ongewijzigd uit te rollen.

## Uitvoering en checks

`make check` controleert applicatiecode. Backendtests dekken onder andere CSRF,
groepsisolatie, profielkoppelingen, ingetrokken toegang, OIDC, gelijktijdige
uitnodigingen en behoud van de laatste beheerder. Migratietests starten met het
oude schema en bewijzen dat bestaande score-ID's en relaties behouden blijven.

De smokecheck maakt alleen synthetische gegevens in een tijdelijke lokale stack:

```bash
docker compose --env-file .env.example -p pnballie-review up --build --wait
python scripts/smoke_groups.py http://localhost:8080
docker compose --env-file .env.example -p pnballie-review down --volumes
```

Voer deze laatste cleanup alleen uit voor de tijdelijke `pnballie-review`-stack.

## Live acceptatie — 16 september 2026

App-PRs 27 en 28 zijn gepubliceerd; de definitieve release is `8ae8f27e`.
206 backendtests en 100 frontendtests, lint/build en containerchecks slagen.
Homelab-PR 67 is via Flux gereconcilieerd als `da67868c`. Alle twaalf
Kustomizations zijn ready. De migratie en een vergelijking met de versleutelde
backup bevestigen behoud van alle oorspronkelijke competitie- en profieldata.
Productie houdt zijn bestaande images.

De SMTP-verbinding is met TLS/authenticatie getest vanaf de Mac en de Spark.
Daarna accepteert Brevo exact één verificatiemail voor het afzonderlijk
geautoriseerde testaccount. De publieke API blokkeert dat onbevestigde account
voor groepsgebruik. De browser toont de nieuwe verificatiepagina. Eén veilige
`auth.email.delivery`-logregel meldt succes; SMTP-key, wachtwoord en adres zijn
afwezig in de API-logs. De gebruiker bevestigt ontvangst en succesvolle
bevestiging in de echte mailbox. De server bevestigt `email_verified=true`,
`verification_required=false`, één groepslidmaatschap en verwijdering van de
gebruikte challenge. De afzonderlijke helpersessie is uitgelogd; het account en
de eigen browsersessie van de gebruiker blijven beschikbaar.

Een bestaande testbrowser had een oudere SPA-entry in zijn cache. Een verse
URL laadde de nieuwe verificatiepagina correct; bij een oude pagina kan een
harde refresh nodig zijn. Dit is in de hierna beschreven herstelrelease verholpen door de SPA-entry bij
herladen opnieuw te laten valideren.


## Wachtwoord vergeten

Als `AUTH_REQUIRE_EMAIL_VERIFICATION=true` is en SMTP is ingesteld, verschijnt
**Wachtwoord vergeten?** bij het inloggen. De bestaande Brevo-configuratie op
acceptatie volstaat; er is geen tweede maildienst of extra secret nodig.

1. Open `/forgot-password` en vul het accountadres in. De reactie is hetzelfde
   voor bekende, onbekende en OIDC-only adressen, ook bij bezorgproblemen.
2. Open de mail binnen 30 minuten. `/reset-password#token=…` haalt het token
   direct uit de adresbalk en bewaart het alleen in het geheugen van die pagina.
   Alleen de link openen of scannen wijzigt niets.
3. Vul tweemaal een nieuw wachtwoord in (minimaal 12 tekens). Na opslaan zijn
   alle eerdere sessies en herstel-/verificatielinks voor dat account ongeldig.
   Log opnieuw in. De groepslidmaatschappen en scores blijven behouden.

De database bevat alleen een hash van de willekeurige 256-bit herstelcode.
Een volgende aanvraag vervangt de vorige code. Verlopen codes en codes voor een
gewijzigd adres/wachtwoord worden geweigerd; een schrijfslot voorkomt dubbel
gebruik. Een reset bewijst mailboxbezit, vervangt het oude wachtwoord en trekt
alle oude sessies in; daarmee kan ook een nog onbevestigd lokaal account veilig
worden bevestigd. Een account met alleen OIDC krijgt zo geen lokaal wachtwoord.
Gebruik daarvoor het herstelproces van de identity provider.

Limieten: 10 aanvragen per IP per uur, één mail per adres per minuut, vijf per
dag, en samen met verificatiemails maximaal 200 per dag. Bevestigen is beperkt
tot 20 pogingen per IP per kwartier. SMTP-verzending gebeurt na de neutrale
HTTP-reactie; SMTP-fouten worden uitsluitend als veilige uitkomst gelogd.
Dit is geen duurzame mailqueue: bij een processtop of bezorgfout vraagt de
gebruiker later opnieuw een link aan. Mailadres, code en wachtwoord gaan niet
naar analytics of logging. Resetpagina's worden niet als gebruiksevent verstuurd.

Migratie `20260916_reset` voegt alleen de tabel `password_reset` toe. Maak vóór
uitrol een consistente backup en controleer behoud op een kopie. De nieuwe
inlog-/herstelpagina's hergebruiken de tafel van de scoreregistratie. Nginx laat
de SPA-entry hervalideren (`Cache-Control: no-cache`) bij een volgend bezoek,
zodat nieuw gepubliceerde routes niet langdurig achter een oude entry blijven.
Een al geopende pagina krijgt pas na vernieuwen de nieuwe versie.

App-PR 30 is gepubliceerd als `044e1de5`; alle CI-checks slagen (217 backendtests,
104 frontendtests, zeven koude routes en containerchecks). De migratieproef op
de versleutelde acceptatiebackup `60184514` behoudt alle oorspronkelijke rijen.
De echte browsercontrole op desktop en 320/393px bevestigt de tafelindeling,
16px-invoervelden en het verwijderen van de resetcode uit de adresbalk.
Homelab-PR 69 is gereconcilieerd als `53e8a6a1`. Alle twaalf Flux-resources zijn
ready en API, frontend en worker gebruiken de gepubliceerde images. De live
vergelijking behoudt alle oorspronkelijke account-/competitierijen; schema,
integriteit en foreign keys slagen. De publieke herstelroutes leveren de juiste
cacheheaders, een neutrale aanvraagreactie en afwijzing van ongeldige codes en
vreemde origins. De browser bevestigt de inlogtafel en mobiele herstelpagina's.
Prometheus, Loki, Tempo en de privacycontrole slagen; productie houdt zijn images.
De controles versturen geen nieuwe echte mail en wijzigen geen bestaand wachtwoord.
De gebruiker kan het mailboxtraject zelf testen via **Wachtwoord vergeten?**.


## Wedstrijden beheren

Een groepsbeheerder opent **tandwiel → Wedstrijden beheren**. De lijst toont
50 uitslagen per pagina, ook oudere wedstrijden. Wijzig scores, spelers,
posities en datum/tijd. Het formulier toont lokale tijd en verstuurt UTC;
een ongewijzigd tijdstip behoudt het exacte oorspronkelijke moment, ook tijdens
een terugkerend wintertijd-uur. Nieuwe tijdstippen zonder tijdzone weigert de API.
De validatie voor 1v1/2v2, unieke deelnemers en een winnaar met tien goals blijft
gelden. Een reeds deelnemende inactieve speler mag behouden blijven.

Verwijderen vraagt eerst expliciete bevestiging met teams, score en tijdstip.
Het verwijdert de uitslag en deelnemerskoppelingen definitief; herstel kan via
backup. De webclient stuurt bij wijzigingen en verwijderen de oorspronkelijke
wedstrijd mee. De server vergelijkt die onder een schrijfslot en weigert een
inmiddels gewijzigde uitslag met 409. Herlaad dan de lijst. De oudere DELETE-API
blijft compatibel zonder snapshot; groepsbeheer en CSRF blijven altijd verplicht.
Groepsgrenzen worden ook server-side gecontroleerd.

Statistieken, ELO en historisch afgeleide badges worden bij de volgende aanvraag
uit de gecorrigeerde geschiedenis berekend. Clubstatistieken toont alle historie;
spelvorm staat onder **tandwiel → Statistieken bekijken → Spelvorm**. Een actieve
1v1/2v2-filter wordt kort vermeld; de periodekeuze en dubbele duelteller zijn weg.


De uitbreiding is gepubliceerd als apprelease `6fc85d0b` en via homelab-PR 71
uitgerold naar acceptatie (`618c35d7`). Alle twaalf Flux-resources zijn ready.
221 backendtests en 108 frontendtests slagen. De browsercontrole gebruikte een
private lokale databasekopie voor menu, mobiele/desktopindeling en scorecorrectie.
Op Spark voert de echte ARM64-release dezelfde API-routes uit tegen een aparte
in-memorydatabase: aanmaken, wijzigen, UTC, statistieken, stale-write-conflicten,
CSRF en verwijderen slagen zonder de echte database te beschrijven.
Publieke routes en de nieuwe assets zijn bereikbaar; anonieme API-toegang blijft
geweigerd. Vergelijking met backup `38036556` bewaart alle oorspronkelijke
account-, competitie-, wedstrijd- en avatarrecords. Alleen het expliciet
gevraagde lidmaatschap in Democompetitie is naar beheerder gewijzigd. Productie
houdt zijn bestaande images. Vernieuw de pagina om groepsrechten opnieuw te laden.


### Wie heeft een wedstrijd ingevoerd?

Nieuwe wedstrijden bewaren `recorded_by_user_id` en `recorded_by_name` uit het
geverifieerde account dat de score indient. Die persoon hoeft niet mee te spelen.
De naam wordt vastgelegd op het moment van invoeren en blijft behouden bij
scorecorrecties, profielkoppelingen en latere naamswijzigingen. Een eventueel
verwijderd account laat de naam staan en maakt de accountreferentie leeg.
Alleen groepsbeheerders ontvangen deze gegevens in de wedstrijden-API; in
wedstrijdbeheer staat **Ingevoerd door**. Voor oudere wedstrijden blijven beide
velden leeg en staat **Onbekend**. Er wordt geen invoerder geraden uit spelers,
logs of de datum.
