terraform {
  required_version = ">= 1.5"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }

  backend "azurerm" {
    resource_group_name  = "pnb-dlb-p-tfstate-rg"
    storage_account_name = "pnbdlbptfstate01"
    container_name       = "tfstate"
    key                  = "pnballie-prod.terraform.tfstate"
    use_azuread_auth     = true
  }
}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}
