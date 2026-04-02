# PNBallie Prod Deployment

## Terraform apply

```bash
export TF_VAR_vm_ssh_public_key="$(cat ~/.ssh/pnballie_prod_vm.pub)"
terraform init
terraform plan -out prod.tfplan
terraform apply prod.tfplan
```

## Build and push images to ACR

```bash
az acr build --registry pnbdlbppnballiecr --image pnballie-backend:latest ../../backend
az acr build --registry pnbdlbppnballiecr --image pnballie-frontend:latest ../../frontend
```

## Deploy latest images on VM

```bash
ssh -i ~/.ssh/pnballie_prod_vm pnballie@pnb-dlb-p-pnballie.westeurope.cloudapp.azure.com 'sudo /opt/pnballie/deploy.sh'
```

## Azure DevOps pipeline

Root pipeline file: `azure-pipelines.yml`

Setup requirements:

- Create/verify service connection: `pnb-dlb-s-datalab-devops-conn`
- Add secure file for PROD SSH key (default name used in pipeline): `pnballie_prod_vm`
- Optional variable overrides in pipeline UI:
  - `VITE_AZURE_CLIENT_ID`
  - `VITE_AZURE_TENANT_ID`
  - `VITE_AZURE_SCOPE`
  - `PROD_VM_IP`
  - `PROD_VM_SSH_PRIVATE_KEY`
  - `prodVmResourceGroup`
  - `prodVmNsgName`
