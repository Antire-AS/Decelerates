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

  # Uncomment to store state in Azure Blob Storage (recommended for teams):
  # backend "azurerm" {
  #   resource_group_name  = "rg-tfstate"
  #   storage_account_name = "stbrokeracc tfstate"
  #   container_name       = "tfstate"
  #   key                  = "broker-accelerator.tfstate"
  # }
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
