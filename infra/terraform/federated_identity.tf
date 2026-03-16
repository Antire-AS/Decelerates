# GitHub OIDC federated identity — lets GitHub Actions authenticate to Azure
# without storing any secrets in GitHub. The workflow must have
# `permissions: id-token: write` for this to work.

data "azuread_client_config" "current" {}

resource "azuread_application" "github_oidc" {
  display_name = "broker-accelerator-github-${var.env}"
}

resource "azuread_service_principal" "github_oidc" {
  client_id = azuread_application.github_oidc.client_id
}

# Allow deploy.yml (push to main) to authenticate
resource "azuread_application_federated_identity_credential" "github_main" {
  application_id = azuread_application.github_oidc.id
  display_name   = "github-main"
  description    = "GitHub Actions — push to main branch"
  audiences      = ["api://AzureADTokenExchange"]
  issuer         = "https://token.actions.githubusercontent.com"
  subject        = "repo:${var.github_repo}:ref:refs/heads/main"
}

# Allow ci.yml (pull requests) to authenticate (read-only — tests only need this
# if they need to read Azure resources; omit if tests are fully offline)
resource "azuread_application_federated_identity_credential" "github_pr" {
  application_id = azuread_application.github_oidc.id
  display_name   = "github-pull-requests"
  description    = "GitHub Actions — pull request checks"
  audiences      = ["api://AzureADTokenExchange"]
  issuer         = "https://token.actions.githubusercontent.com"
  subject        = "repo:${var.github_repo}:pull_request"
}

# Contributor on the resource group — needed to update Container Apps
resource "azurerm_role_assignment" "github_contributor" {
  scope                = azurerm_resource_group.main.id
  role_definition_name = "Contributor"
  principal_id         = azuread_service_principal.github_oidc.object_id
}
