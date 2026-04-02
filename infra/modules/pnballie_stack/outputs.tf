output "resource_group_name" {
  value = azurerm_resource_group.main.name
}

output "acr_name" {
  value = azurerm_container_registry.main.name
}

output "acr_login_server" {
  value = azurerm_container_registry.main.login_server
}

output "key_vault_name" {
  value = azurerm_key_vault.main.name
}

output "key_vault_uri" {
  value = azurerm_key_vault.main.vault_uri
}

output "vm_public_ip" {
  value = azurerm_public_ip.vm.ip_address
}

output "vm_fqdn" {
  value = azurerm_public_ip.vm.fqdn
}

output "ssh_command" {
  value = "ssh ${var.vm_admin_username}@${azurerm_public_ip.vm.fqdn}"
}

output "site_url" {
  value = "https://${azurerm_public_ip.vm.fqdn}"
}
