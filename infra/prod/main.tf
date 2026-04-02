module "stack" {
  source = "../modules/pnballie_stack"

  location          = var.location
  org_prefix        = var.org_prefix
  env_short         = var.env_short
  project           = var.project
  image_tag         = var.image_tag
  vm_size           = var.vm_size
  vm_admin_username = var.vm_admin_username
  vm_ssh_public_key = var.vm_ssh_public_key
  ssh_allowed_cidr  = var.ssh_allowed_cidr
  data_disk_size_gb = var.data_disk_size_gb
  compose_content   = file("${path.module}/../../docker-compose.prod.yml")
  caddyfile_content = file("${path.module}/../Caddyfile")
}
