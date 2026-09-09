# Infrastructure

Retained Terraform assets for the legacy PNBallie production (`p`) deployment
on Azure. New application deployment is managed by Flux in `spark-homelab`.

The final Azure database has been restored and verified on k3s. The Azure
backend is stopped; preserve these resources and their existing images,
configuration and data as the rollback set. Provisioning changes and resource
deletion require a separate decision; see [the legacy deployment notes](prod/README.md).

## Layout

- `modules/pnballie_stack/`: reusable stack module.
- `prod/`: production environment root.

## Deployed resources

- Resource group (`pnb-dlb-p-pnballie-rg`)
- Azure Container Registry (Basic)
- Linux VM (Docker host)
- Managed data disk mounted at `/data` for persistent SQLite storage
- VNet/subnet/public IP/NSG

The VM retains `/opt/pnballie/docker-compose.prod.yml` and its existing ACR
images. Only the backend was stopped; the VM, frontend and Caddy remain intact.
