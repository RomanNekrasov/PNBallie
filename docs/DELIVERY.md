# Releases

Een wijziging op main doorloopt **Validate → Release PNBallie → acceptance →
production**. Documentatiewijzigingen zonder applicatie- of pipelinecode bouwen
geen nieuwe images.

De release bouwt backend en frontend één keer voor ARM64 en AMD64. Na publicatie
maakt de pipeline met een SSH deploy key (alleen spark-homelab) een GitOps-branch.
De homelabworkflow valideert de manifests, controleert dat uitsluitend de
verwachte imagepins/schema/release.json wijzigen en mergeert een PR via de normale
branchbescherming. Flux voert de wijziging uit.

Acceptatie is automatisch. Open de **Release PNBallie**-run in GitHub Actions,
test acceptatie en klik **Review deployments → production → Approve and deploy**.
Roman is de ingestelde reviewer. Productie gebruikt exact dezelfde digests als
de actuele acceptatierelease. Een achterhaalde goedkeuring wordt geweigerd.
Er is geen handmatige digestkopie of clusterlogin nodig.

De pipeline controleert de commit van de frontend, API, verse workerheartbeat en
de werkelijke Alembic-revisie via /version.json en /api/version. Elke deployment
linkt zijn GitOps-branch en controles in de job summary. Bij een fout: lees eerst
de rode job; herstel code/config en start een nieuwe release. De productiejob
begint pas na een geslaagde acceptatiedeployment en goedkeuring.

Een nieuwe databaserevisie moet ook door de homelab-back-uphelper ondersteund
worden voordat promotie slaagt. Runtimeconfiguratie, secrets en databases zijn
omgevingsspecifiek en worden niet door een imagepromotie gekopieerd.

Beheer: HOMELAB_DEPLOY_KEY is een Actions-secret; production is een beschermde
GitHub Environment. Bewaar de private sleutel niet in Git. Het homelab-token mag
PR's maken en heeft alleen tijdens de integratiejob contents/pull-requests write.

## Eerste release

Release 1ad73d673f714095138f12083f45e4636bd7dbe5:
https://github.com/RomanNekrasov/PNBallie/actions/runs/35141771557

De automatische acceptatie-PR (spark-homelab #89) is zonder handmatige merge
door de verplichte validate-check gekomen. De productiejob stopte daadwerkelijk
bij de reviewergoedkeuring. Voor deze eerste release gaf Roman vooraf opdracht
om naar productie te gaan; volgende releases wachten op zijn klik in GitHub.

De echte Azure-proef gaf een private transparante 1024×1024-PNG. Een workerwissel
vlak na indienen veroorzaakte een leaseherstel en een tweede poging; deze slaagde.
De testharness verwachtte eerst precies één poging en is daarop nagecontroleerd.
De originele JPEG bleef byte voor byte behouden met rechten 0600, ook na een
backendherstart. De versleutelde Restic-back-up is teruggelezen en gecontroleerd.
Tijdelijke testaccount-, groeps-, job- en avatarrecords zijn opgeruimd.

Productie is via automatische GitOps-PR #90 uitgerold. De volledige releasepipeline
is groen. Een publieke inlog-/configuratieproef bevestigt Azure als enige ingestelde
provider en identieke frontend-, API- en workerrevisies. Bestaande businessdata is
voor en na de tijdelijke productieproef met fingerprints vergeleken en ongewijzigd.
