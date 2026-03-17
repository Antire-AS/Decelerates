terraform {
  required_version = ">= 1.7"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.110"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 2.53"
    }
  }

  backend "azurerm" {
    resource_group_name  = "rg-prod-brokeraccelerator"
    storage_account_name = "stprodbrokeracc"
    container_name       = "tfstate"
    blob_name            = "terraform.tfstate"
    use_oidc             = true
  }
}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}

provider "azuread" {}

resource "azurerm_resource_group" "main" {
  name     = "rg-${var.env}-brokeraccelerator"
  location = var.location
  tags     = local.tags
}

locals {
  tags = {
    project     = "broker-accelerator"
    environment = var.env
    managed_by  = "terraform"
  }
}
