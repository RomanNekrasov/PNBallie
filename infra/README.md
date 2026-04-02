# Infrastructure

Terraform assets for PNBallie production (`p`) on Azure.

## Layout

- `modules/pnballie_stack/`: reusable stack module.
- `prod/`: production environment root.

## Deployed resources

- Resource group (`pnb-dlb-p-pnballie-rg`)
- Azure Container Registry (Basic)
- Linux VM (Docker host)
- Managed data disk mounted at `/data` for persistent SQLite storage
- VNet/subnet/public IP/NSG

The VM runs `/opt/pnballie/docker-compose.prod.yml` with images from ACR.
