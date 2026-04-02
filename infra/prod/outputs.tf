output "resource_group_name" {
  value = module.stack.resource_group_name
}

output "acr_name" {
  value = module.stack.acr_name
}

output "acr_login_server" {
  value = module.stack.acr_login_server
}

output "key_vault_name" {
  value = module.stack.key_vault_name
}

output "key_vault_uri" {
  value = module.stack.key_vault_uri
}

output "vm_public_ip" {
  value = module.stack.vm_public_ip
}

output "vm_fqdn" {
  value = module.stack.vm_fqdn
}

output "ssh_command" {
  value = module.stack.ssh_command
}

output "site_url" {
  value = module.stack.site_url
}
