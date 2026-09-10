# Authenticatie, groepen en migratie

Besluit: de goedgekeurde uitbreiding van 9 september 2026 maakt PNBallie bruikbaar
zonder provincieaccount of Entra ID. De bestaande FastAPI/Vue/SQLite-stack blijft
behouden. Argon2 en de bestaande PyJWT/httpx-libraries verzorgen respectievelijk
wachtwoordhashing en OIDC. Een externe identityserver is optioneel.

## Lokale accounts en sessies

Registratie vraagt een naam, e-mailadres en wachtwoord van minstens 12 tekens.
Het e-mailadres is een inlognaam; de app stuurt geen verificatie- of resetmails.
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
