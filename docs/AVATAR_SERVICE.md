# Eigen spelersavatars

## Resultaat van het onderzoek — 9 september 2026

**Qwen kan echte transparante beelden leveren, met het specifieke
Qwen-Image-Layered-model.** Een Qwen-chat-, vision- of embeddingsmodel is geen
beeldgenerator. Qwen-Image-Edit kan een portret en een referentiepoppetje
combineren, maar een PNG-bestand uit die pipeline is op zichzelf geen bewijs
van transparantie. De gewone beeldpipeline heeft een RGB-decoder.

De geïmplementeerde lokale route gebruikt twee opeenvolgende stappen:

1. **Qwen-Image-Edit-2511** maakt het poppetje uit de eigen foto en de bestaande
   stijl/bodyreferentie. Het model ondersteunt meerdere invoerbeelden en verbeterde
   gezichtsconsistentie.
2. **Qwen-Image-Layered** verdeelt dat resultaat in echte RGBA-lagen. De service
   voegt vrijstaande voorgrondlagen samen en laat de achtergrond weg. Dit is een
   aparte modelstap; geen claim dat de gewone Edit-pipeline zelf alpha maakt.

De meegeleverde bodyreferentie is afgeleid van het bestaande Roman-poppetje,
waarbij het hoofd is verwijderd. Er gaat geen tweede spelersportret mee als
referentie. De vaste prompt vraagt hetzelfde groen/witte tafelvoetbalpoppetje,
stang, bal, cartoonstijl en een licht gepixelde afwerking, met het herkenbare
gezicht van de uploadende speler.

### Bronnen en gepinde modellen

Geraadpleegd en daadwerkelijk opgehaald op 9 september 2026:

- [Qwen-Image-Edit-2511 modelkaart](https://huggingface.co/Qwen/Qwen-Image-Edit-2511):
  twee invoerbeelden, `QwenImageEditPlusPipeline`, BF16 en consistentieverbeteringen.
  Gebruikte revisie: `6f3ccc0b56e431dc6a0c2b2039706d7d26f22cb9`.
- [Qwen-Image-Layered modelkaart](https://huggingface.co/Qwen/Qwen-Image-Layered):
  expliciete RGBA-laagdecompositie met `QwenImageLayeredPipeline`; de aanbevolen
  eerste proefresolutie is 640 pixels. Gebruikte revisie:
  `8f0ca708dfff6ba1dd5f2d85d78f8c108a040bcf`.
- [Layered VAE-configuratie](https://huggingface.co/Qwen/Qwen-Image-Layered/blob/8f0ca708dfff6ba1dd5f2d85d78f8c108a040bcf/vae/config.json):
  `input_channels: 4` sluit aan op de RGBA-ondersteuning uit de modelkaart.
- [Qwen-Image-Edit-2509 modelkaart](https://huggingface.co/Qwen/Qwen-Image-Edit-2509):
  eerdere versie met expliciete ondersteuning voor één tot drie referentiebeelden.
- [Officiële OpenAI-documentatie: afbeeldingen](https://developers.openai.com/api/docs/guides/image-generation):
  Image Edits accepteert meerdere invoerbeelden en ondersteunt
  `background=transparent` met `output_format=png`.

Beide geselecteerde Qwen-modelkaarten vermelden Apache 2.0. Hugging Face meldde
circa 20,43 miljard BF16-parameters per model: alleen deze gewichten nemen al
ongeveer 38 GiB in. Houd daarnaast ruimte voor de tekstencoder, activaties, CUDA
en de bestaande workloads. De hieronder beschreven Spark-proef duurde ruim
24 minuten. Een exacte GPU-geheugenpiek is niet vastgesteld; de beschikbare
host-RAM is gecontroleerd. CPU-offload schept op de Spark geen extra fysiek
geheugen: de GB10 gebruikt gedeeld systeemgeheugen.

### Wat op de huidige Spark is vastgesteld

Een alleen-lezen SSH-controle gaf op 9 september 2026:

- ARM64 (`aarch64`), NVIDIA GB10.
- 119 GiB systeemgeheugen, 108 GiB gebruikt en circa 11 GiB beschikbaar.
- Een bestaande Docker-container `atlas-qwen3-embeddings` met vLLM.
- `nvidia-smi` rapporteert de geheugencapaciteit op deze GB10 als `N/A`.

Deze vrije ruimte was onvoldoende om de beeldmodellen veilig te starten. De
eerste onderzoeksronde heeft daarom geen modellen geladen of workloads gestopt.
Daarna gaf de gebruiker expliciet toestemming om de ongebruikte embeddingsdienst
te stoppen en de avatarroute voor lokale tests te starten. Alleen
`atlas-qwen3-embeddings` is gestopt; de herstartpolicy is `no` en container,
modelcache en een private configuratiebackup blijven behouden. Daarna was
circa 111 GiB beschikbaar.

De twee gepinde beeldmodellen zijn vervolgens succesvol naar een aparte cache
gedownload (circa 108 GiB; 14 minuten en 27 seconden). Een private modelservice
draait op `127.0.0.1:8011` op de Spark, bereikbaar via een SSH-tunnel vanaf de
lokale app. De gebruikte gepinde CUDA-runtime heeft Torch `2.13.0+cu130`,
CUDA 13.0 en ongewijzigde NVIDIA-driver `580.126.09`. Echte BF16-matrix-,
attention- en vision-convolutionkernels en imports van beide Qwen-pipelines
zijn geslaagd. Ook een echte TorchInductor/Triton-compilatie is gecontroleerd
onder dezelfde non-root/read-only containerinstellingen.

De eerste echte beeldproef laadde Edit in 295 seconden en vond daarna een
runtimecacheprobleem. De runtime gebruikt nu een eigen beschrijfbaar volume
voor uitvoerbare GPU-compilerbestanden; het standaard Docker-tmpfs is `noexec`.
De modelgewichten en applicatiecode blijven read-only. Na de mislukte proef
kwam ongeveer 110 GiB weer beschikbaar.

### Geslaagde beeldproef en vrijgeven van geheugen

De echte tweestapsgeneratie gaf op 9 september 2026 HTTP 200 na **1463,9 seconden
(24 minuten en 24 seconden)**. De invoer was het bestaande Roman-avatarbestand
uit deze repository, samen met de headless bodyreferentie. Er is geen nieuwe
portretfoto of cloudendpoint gebruikt. Edit draaide 40 stappen en Layered 50
stappen op resolutie 640; beide modellen moesten eerst circa vijf minuten laden.

Het resultaat is **640 × 640 RGBA-PNG**. Het complete poppetje, de stang, bal,
groen/witte stijl en licht gepixelde gezichtsweergave zijn op een lichte en donkere
achtergrond bekeken. De gebruiker heeft het getoonde resultaat geaccepteerd.
De uitvoer had aanvankelijk bijna onzichtbare achtergrondruis. De compositie
zet nu alpha 1–15 op 0; kleuren en zachte randen vanaf alpha 16 blijven behouden.
Die correctie is ook zonder nieuwe GPU-generatie op de proef-PNG toegepast:
**58,51% van de pixels is exact transparant** en er zijn geen pixels meer met
alpha 1–15. De lokale bestanden staan buiten Git in
`.local-test/qwen-avatar-proef.png`, het oorspronkelijke bestand in
`.local-test/qwen-avatar-proef-raw.png` en de lichte/donkere controle in
`.local-test/qwen-avatar-contrastcontrole.png`.

De volledige generatie liet in het oorspronkelijke langlevende proces circa
20 GiB achter, ondanks het verwijderen van modelobjecten en legen van de
PyTorch-cache. Daarom start de HTTP-service nu **een apart proces per opdracht**.
Dat proces bezit alle CUDA-status en moet volledig afsluiten voordat het
antwoord wordt teruggegeven. Na herstart van de service was weer circa 111 GiB
beschikbaar; het HTTP-proces gebruikte ongeveer 111 MiB.

Het nieuwe subprocessprotocol is daarna op de echte GB10 gecontroleerd met
een kleine GPU-proef: een child hield bewust 1 GiB CUDA-geheugen vast tot
afsluiten, leverde een geldige PNG, eindigde met code 0 en werd opgeruimd.
Beschikbaar hostgeheugen was **111,53 GiB vóór en 111,54 GiB na** de proef.
Ook de compileer- en cachepreflight slaagde opnieuw (5,0 seconden).
Dit is een echte CUDA-isolatieproef, geen tweede volledige Qwen-generatie met
de nieuwe wrapper. Een complete profielupload met een nieuwe portretfoto
via wachtrij en model blijft de volgende gebruiksproef.

De lokale API, frontend, worker en SSH-tunnel zijn gestart. De Spark-service
is healthy en was na verificatie idle. Productie `/healthz` gaf HTTP 200 vanaf
Mac en Spark; de gestopte embeddingscontainer bleef behouden met restart `no`.
Wachtrij, autorisatie, providercontracten, alpha-correctie en subprocessfouten
zijn daarnaast met lokale tests gecontroleerd.

## Architectuur en namespacekeuze

```text
eigen profiel -> API -> avatar_job in SQLite <- avatar-worker
                                               |
                                               +-> private Spark image service
                                               |   apart proces per opdracht:
                                               |   Edit -> Layered -> proces afsluiten
                                               |
                                               +-> OpenAI Image Edits
                                                   alleen na expliciete profielkeuze

worker -> PNG/alpha-validatie -> player_avatar -> groepsbeveiligde afbeelding
```

- De API en lichte queue-worker horen in namespace `pnballie`, met dezelfde
  SQLite-PVC. De bestaande consistente SQLite-backup bevat daardoor ook de
  definitieve avatars en de wachtrij. De API verwerkt zelf geen GPU-generaties.
- De private modelservice hoort in een eigen namespace `pnballie-avatar`, met
  eigen resourcegrenzen, modelcache en intern servicetoken. Die service heeft
  geen toegang tot de wedstrijddatabase en krijgt geen publieke ingress.
- De service blijft als licht proces bereikbaar. Een apart childproces laadt
  modelgewichten op verzoek en ruimt iedere pipeline vóór de volgende op.
  Er staan nooit bewust twee beeldpipelines tegelijk geladen. **Afsluiten van
  het childproces geeft ook achtergebleven CUDA-buffers vrij.** De servicepod
  hoeft daarvoor niet te stoppen en de applicatie heeft geen
  Kubernetes-beheerrechten nodig. De parent wacht op procesafsluiting en
  beëindigt de procesgroep bij een time-out van een uur. Het servicetoken,
  de OpenAI-sleutel en de database-URL worden niet aan de child doorgegeven.
- Kubernetes- en Flux-resources horen in `spark-homelab`, overeenkomstig
  `CLAUDE.md`. De expliciet gevraagde lokale proef gebruikt een aparte private
  Docker-runtime; Dockerfile, Compose-definitie, downloadscript en runbook staan
  in die repository onder `config/pnballie-avatar`, `scripts` en
  `docs/runbooks/pnballie-avatar-local.md`. De productieapp en score-PVC zijn
  daarbij niet gewijzigd. Een toekomstige productie-uitrol via Flux blijft een
  afzonderlijke stap.
- Gebruik één queue-worker en één inferenceproces (`--workers 1`). Claims zijn
  bestand tegen een overlappende workerstart; het serviceproces verwerkt maximaal
  één beeld tegelijk. Meerdere inferenceprocessen zouden elk een eigen lock
  hebben en worden niet ondersteund op de gedeelde GB10.

De app behoudt SQLModel, SQLite en de bestaande `uv`-stack. Een bestaande
databasewachtrij voorkomt een extra Redis/Celery-beheerdienst voor dit kleine
volume. De GPU-dependencies staan in de optionele `avatar-gpu` extra en komen
niet in de gewone backendinstallatie.

## Configuratie

De API en worker gebruiken dezelfde avatarconfiguratie. Sla sleutels en tokens
op als lokale omgevingsvariabelen of versleutelde deploymentsecrets.

| Variabele | Gebruik |
| --- | --- |
| `AVATAR_LOCAL_URL` | Volledige interne URL, bijvoorbeeld `http://avatar-inference.pnballie-avatar.svc.cluster.local:8000/v1/avatar` |
| `AVATAR_SERVICE_TOKEN` | Gedeeld geheim voor worker en private modelservice |
| `AVATAR_REFERENCE_PATH` | Optioneel; standaard `app/assets/avatar-body.png` in het backendpakket |
| `AVATAR_TIMEOUT_SECONDS` | Modelantwoord-time-out; standaard 3600, tussen 30 en 3600 seconden; de gemeten lokale BF16-route duurt langer dan twintig minuten |
| `OPENAI_API_KEY` | Alleen nodig als OpenAI beschikbaar moet zijn |
| `OPENAI_IMAGE_MODEL` | Expliciet te kiezen GPT Image-model; geen stilzwijgende model- of kostenwijziging |
| `AVATAR_MIN_AVAILABLE_GIB` | Geheugenpoort op de Spark; standaard 80 GiB vrij vóór elke modellaadstap |
| `HF_HOME` | Persistente cache voor de exact gepinde modelrevisies |

`/api/avatars/config` zegt of een provider is **geconfigureerd**; het is geen
live GPU-gereedheidscheck. Een bezette of onvoldoende uitgeruste Spark geeft
een tijdelijke fout. De worker probeert een tijdelijke fout maximaal driemaal,
met wachttijden van 30 en 60 seconden. Een latere nieuwe poging blijft een
expliciete actie vanuit het profiel.

Bij de cloudroute vraagt de worker twee invoerbeelden, PNG-uitvoer,
`background=transparent`, 1024 × 1024 en `quality=medium`. Het model staat
expliciet in de configuratie. De officiële documentatie noemt op de datum van
dit onderzoek `gpt-image-2.5-sunburst` voor nauwkeurige bewerkingen; kies een
model dat daadwerkelijk beschikbaar is in het eigen API-project. Er zijn geen
cloudverzoeken of betaalde generatieproeven uitgevoerd. Een OpenAI-time-out
wordt niet automatisch herhaald omdat de eerste poging al verwerkt kan zijn.

## Lokaal starten en GPU-proef

De gewone API volgt de project-README. Start daarnaast de lichte worker:

```sh
cd backend
uv run alembic upgrade head
uv run python -m app.avatar_worker
```

Eén opdracht verwerken en weer afsluiten:

```sh
uv run python -m app.avatar_worker --once
```

De modelservice moet in een gecontroleerde, met de GB10 compatibele ARM64/CUDA
omgeving draaien. Gebruik op de Spark de geteste gepinde Docker-runtime uit het
homelabrunbook; installeer daar geen willekeurig andere Torch-wheel overheen.
De onderstaande generieke ontwikkelroute is alleen voor een apart ingerichte
compatibele CUDA-omgeving. De Spark-cache bevat inmiddels de exacte HF-revisies;
de service gebruikt altijd `local_files_only=True` en downloadt op een upload
geen modellen.

```sh
cd backend
uv sync --extra avatar-gpu
uv run --extra avatar-gpu python -c 'import torch; print(torch.__version__, torch.cuda.is_available())'
uv run --extra avatar-gpu uvicorn app.avatar_service:app --host 0.0.0.0 --port 8000 --workers 1
```

Bind deze service alleen aan het private containernetwerk. Deel het
servicetoken via secrets. De normale container-/netwerkconfiguratie voor deze
GPU-runtime moet in `spark-homelab` worden gepind en gevalideerd vóór uitrol.

Een echte lokale proef, zodra de cache en capaciteit klaar zijn:

```sh
uv run --extra avatar-gpu python -m app.avatar_smoke /pad/naar/eigen-foto.png --output /tmp/pnballie-avatar-proef.png
```

Deze CLI belt geen cloud, weigert een bestaand uitvoerbestand te overschrijven,
en meldt PNG-modus, afmetingen, transparant pixelpercentage en looptijd. Bekijk
het resultaat bovendien op lichte én donkere achtergrond: controleer identiteit,
complete poppetje/stang/bal, stijl en nette randen. Meet de geheugenpiek en controleer
na de proef dat modelgeheugen is vrijgegeven, de productieapp gezond is en de
uitgeschakelde embeddingsdienst gestopt blijft.
De automatische laagselectie kan een modelresultaat afwijzen; een groene
alpha-controle vervangt deze visuele kwaliteitscontrole niet.

## API-contract

Groepsroutes gebruiken de bestaande login-cookie, `X-Group-ID` en bij mutaties
`X-CSRF-Token`.

| Route | Gedrag |
| --- | --- |
| `GET /api/avatars/config` | `local_available`, `openai_available`, `max_upload_bytes` |
| `POST /api/avatars/me/jobs?provider=local` | Ruwe afbeeldingsbytes; `Content-Type: image/png`, `image/jpeg` of `image/webp`; antwoord 202 |
| `POST /api/avatars/me/jobs?provider=openai&cloud_consent=true` | Dezelfde upload, met expliciete toestemming om de foto door OpenAI te laten verwerken |
| `GET /api/avatars/me/latest` | Laatste eigen opdracht in de actieve groep, of `null` |
| `GET /api/avatars/jobs/{id}` | Eigen opdracht en fout-/resultaatstatus |
| `DELETE /api/avatars/jobs/{id}` | Trek een actieve opdracht in en verwijder de opgeslagen bronfoto |
| `GET /api/avatars/players/{id}.png?v={version}` | Avatar zichtbaar voor ingelogde leden van de werkelijke spelersgroep; geen groepsheader vereist voor een `<img>` |

Een opdracht bevat `id`, `player_id`, `provider`, `status`, `attempts`, `error`,
`created_at`, `updated_at` en `avatar_url`. Mogelijke statussen:
`queued`, `processing`, `succeeded`, `failed`, `cancelled`.
Tijdstippen hebben een expliciete UTC-offset.

## Beveiliging, opslag en herstel

- Een upload bindt aan de ingelogde gebruiker én diens actieve spelersprofiel in
  de groep; de client kiest geen andere speler-ID.
- De API decodeert en hercodeert foto's, verwijdert metadata, weigert animaties
  en controleert werkelijk bestandsformaat. Limieten: 8 MiB upload, 16 megapixels,
  maximaal vijf aanvragen per gebruiker per 24 uur, één actieve opdracht per
  speler. De genormaliseerde foto is maximaal 1024 × 1024.
- De quota/indiening zijn onder een SQLite-schrijftransactie beschermd.
- Atomische claims, vernieuwde leases, een maximumaantal pogingen en fencing
  voorkomen dubbele publicatie na crashes. Iedere publicatie controleert opnieuw
  het lidmaatschap, de actieve speler en diens gebruikersbinding.
- Een echte PNG met deels transparante én deels ondoorzichtige pixels is
  verplicht. Een RGB-PNG, volledig ondoorzichtig RGBA of een leeg transparant
  bestand wordt afgewezen. URL-antwoorden van providers worden niet opgehaald.
- Foto's staan alleen in actieve opdrachtregels. Succes, definitieve fout,
  annulering of een verlopen wachtrijopdracht maakt de bronkolom leeg. De worker
  ruimt na 24 uur verlopen uploads op; een gestopte worker kan geen opruiming
  uitvoeren. Een al lopende modelaanvraag kan na annulering nog aflopen, maar
  mag het resultaat niet meer publiceren.
- De database en oudere backups kunnen tot hun normale retentiegrens nog eerdere
  fotodata bevatten. Het leegmaken van een rij is geen belofte van fysieke
  verwijdering uit SQLite-pagina's of backups. Behandel databasebackups daarom
  als persoonsgegevens en behoud de bestaande versleutelde backupafspraken.
- Logs en API-fouten bevatten geen bronfoto's, tokens, modelresponsebodies of
  interne modelcachepaden. Het servicetoken staat nooit in browserantwoorden.
- De cloudoptie valt nooit automatisch in bij een lokale fout. De speler kiest
  OpenAI zelf en bevestigt de verwerking; de worker controleert die toestemming
  nogmaals. De lokale route stuurt foto's uitsluitend naar de ingestelde private
  modelservice.
- Definitieve PNGs en versies staan in `player_avatar`. Afbeeldingen vereisen
  actuele groepsrechten en hebben `Cache-Control: private, no-store`.
- Draai de Alembic-migratie vóór API en worker starten. Downgrade van
  `20260909_avatars` verwijdert de avatar- en opdrachttabellen; maak eerst een
  consistente versleutelde backup. De wedstrijdhistorie blijft in eigen tabellen.

## Verificatiestatus

- [x] Uploadvalidatie, expliciete cloudtoestemming en limieten getest.
- [x] Eigenaar- en groepsautorisatie, inclusief intrekken van lidmaatschap tijdens
  generatie, getest.
- [x] Duurzame opslag, overlappende claims, leaseherstel, verlopen opdrachten en
  behoud van de vorige avatar bij een ongeldig modelantwoord getest.
- [x] Echte PNG/alpha-validatie, compositie van voorgrondlagen en het multipart
  OpenAI-providercontract getest met lokale testafbeeldingen.
- [x] Private servicetoken, capaciteitsweigering en HTTP-contract getest zonder
  GPU of cloud.
- [x] Een echte tweestaps-Qwen-proef op Spark, visueel geaccepteerde RGBA-PNG
  en gemeten looptijd van 24 minuten en 24 seconden.
- [x] Geheugenretentie na die proef opgelost met een apart proces per opdracht;
  echte 1 GiB CUDA-proef bevestigt terugkeer naar circa 111,5 GiB vrij geheugen.
- [x] Achtergrondruis verwijderd en alpha/randbehoud getest; 58,51% exact
  transparante pixels in de bijgewerkte proef-PNG.
- [ ] Een volledige eigen profielupload met nieuwe foto door de live wachtrij
  en de uiteindelijke subprocesswrapper; lokale worker is hiervoor gestart.
- [ ] Een eventuele echte OpenAI-proef met geconfigureerd project/model en
  expliciete profielkeuze.
- [x] Afzonderlijke lokale Spark-runtime gestart met gepinde modellen, geteste
  GPU-kernels, private compiler-cache en loopback-/SSH-netwerk.
- [ ] Eventuele productieimage publiceren en de service via Flux uitrollen.
