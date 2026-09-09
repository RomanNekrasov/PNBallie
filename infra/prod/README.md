# Retained Azure deployment

This directory preserves the Terraform configuration for the existing Azure
VM deployment. Its final database has been restored and verified on k3s.
The retained Azure backend passed a restart/rollback rehearsal and is stopped
again. Keep the VM, configuration, existing images and data as the rollback set.

New releases use GitHub Actions and private GHCR images. Kubernetes resources,
score transfer, backups and cutover are managed in `spark-homelab`; follow its
[PNBallie migration runbook](https://github.com/RomanNekrasov/spark-homelab/blob/main/docs/runbooks/pnballie-migration.md)
(private repository). DNS activation alone does not complete the cutover.

## Preserve the rollback set

- Keep the VM, data disk, existing deployed images, `/opt/pnballie`
  configuration and `/data/pnballie` database until explicit cleanup approval.
- Do not rebuild `latest` images into the retained deployment or run its old
  deploy script as part of a normal application release.
- The legacy stack expects the frontend on port 80. Current images use port
  8080, mounted `/config.json`, backend Entra configuration and a separate
  Alembic step. They cannot directly replace the old images in unchanged
  `docker-compose.prod.yml`.
- Before rollback, stop the k3s writer and establish which database is current.
  If k3s has accepted new scores, back up both copies and transfer the verified
  current database before restarting the Azure writer. Preserve file ownership
  and compare schema, counts and content as described in the homelab runbook.

The original provisioning instructions remain available in
[Git history](https://github.com/RomanNekrasov/PNBallie/blob/5970d3e14883d73ae88ec06a718706cb1f0f2988/infra/prod/README.md).
They describe the old environment, including its retired Azure Pipeline;
`azure-pipelines.yml` is no longer present in this repository.

Temporary migration SSH access is scoped and removed by the homelab workflow.
Refer to that runbook before changing SSH access, running Terraform or
starting/stopping a database writer.
