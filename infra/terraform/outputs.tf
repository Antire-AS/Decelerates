output "acr_login_server" {
  description = "Azure Container Registry login server (use without .azurecr.io suffix as ACR_NAME secret)"
  value       = azurerm_container_registry.main.login_server
}

output "api_url" {
  description = "FastAPI Container App public URL"
  value       = "https://${azurerm_container_app.api.latest_revision_fqdn}"
}

output "ui_url" {
  description = "Streamlit Container App public URL"
  value       = "https://${azurerm_container_app.ui.latest_revision_fqdn}"
}

output "github_client_id" {
  description = "Azure AD Application Client ID — set as AZURE_CLIENT_ID in GitHub Actions secrets"
  value       = azuread_application.github_oidc.client_id
}

output "tenant_id" {
  description = "Azure AD Tenant ID — set as AZURE_TENANT_ID in GitHub Actions secrets"
  value       = data.azuread_client_config.current.tenant_id
}

output "db_fqdn" {
  description = "PostgreSQL Flexible Server fully-qualified domain name"
  value       = azurerm_postgresql_flexible_server.main.fqdn
}

output "entra_app_client_id" {
  description = "Entra ID app client ID — set as ENTRA_CLIENT_ID in GitHub secrets if needed"
  value       = azuread_application.broker_ui.client_id
}

output "entra_tenant_id" {
  description = "Azure AD Tenant ID"
  value       = data.azuread_client_config.current.tenant_id
}
