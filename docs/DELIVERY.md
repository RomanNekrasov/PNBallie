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
