terraform {
  backend "azurerm" {
    resource_group_name  = "rg-terraform-state"
    storage_account_name = "tfstateantire"
    container_name       = "tfstate"
    key                  = "broker-accelerator.tfstate"
  }

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  features {}
}

locals {
  environments = toset(["staging", "production"])
}

module "project_bootstrap" {
  for_each = local.environments
  source   = "../../../modules/project-bootstrap"

  project_name       = "broker-accelerator"
  project_name_short = "broker-accel"
  environment        = each.value
  location           = "norwayeast"

  github_org  = "Antire-AS"
  github_repo = "Decelerates"

  shared_acr_name = "crantireshared"
  shared_acr_rg   = "rg-shared-platform"

  owner_user_principal_ids = [
    "8cb91230-644e-49cf-a858-90f6501ddc16", # tharusan
    "39fac1ef-9c17-4d83-804d-97c190b849cd", # patrick
  ]

  enable_pr_deployments = true

  tags = {
    Project = "Broker Accelerator"
    Team    = "Value Center"
  }
}

# ── Outputs ───────────────────────────────────────────────────────────────────

output "resource_group_name" {
  description = "Resource group per environment"
  value       = { for env, mod in module.project_bootstrap : env => mod.resource_group_name }
}

output "key_vault_name" {
  description = "Key Vault name per environment"
  value       = { for env, mod in module.project_bootstrap : env => mod.key_vault_name }
}

output "key_vault_uri" {
  description = "Key Vault URI per environment"
  value       = { for env, mod in module.project_bootstrap : env => mod.key_vault_uri }
}

output "gha_identity_client_id" {
  description = "GitHub Actions managed identity client ID per environment"
  value       = { for env, mod in module.project_bootstrap : env => mod.gha_identity_client_id }
}

output "runtime_identity_id" {
  description = "Runtime managed identity resource ID per environment"
  value       = { for env, mod in module.project_bootstrap : env => mod.runtime_identity_id }
}

output "setup_instructions" {
  description = "GitHub Actions setup instructions per environment"
  value       = { for env, mod in module.project_bootstrap : env => mod.github_actions_setup }
}
