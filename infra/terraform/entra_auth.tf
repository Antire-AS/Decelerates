# Easy Auth config for the UI container app via azapi.
#
# The app registration is created manually in Azure Portal (one-time setup)
# and its Client ID + Secret are stored as GitHub secrets ENTRA_CLIENT_ID /
# ENTRA_CLIENT_SECRET. This avoids requiring Graph API permissions in CI.
#
# One-time setup in Azure Portal:
#   1. App registrations → New → display name "broker-accelerator-prod"
#   2. Add redirect URI: https://<ui-fqdn>/.auth/login/aad/callback
#   3. App roles → Create: User (value="User"), Manager (value="Manager")
#   4. Certificates & secrets → New client secret → copy value
#   5. Add ENTRA_CLIENT_ID + ENTRA_CLIENT_SECRET as GitHub Actions secrets

resource "azapi_resource" "ui_auth" {
  count     = var.entra_client_id != "" ? 1 : 0
  type      = "Microsoft.App/containerApps/authConfigs@2023-05-01"
  name      = "current"
  parent_id = azurerm_container_app.ui.id

  body = jsonencode({
    properties = {
      platform = { enabled = true }
      globalValidation = {
        redirectToProvider          = "azureactivedirectory"
        unauthenticatedClientAction = "RedirectToLoginPage"
      }
      identityProviders = {
        azureActiveDirectory = {
          enabled = true
          registration = {
            openIdIssuer            = "https://sts.windows.net/${var.entra_tenant_id}/v2.0"
            clientId                = var.entra_client_id
            clientSecretSettingName = "microsoft-provider-authentication-secret"
          }
          validation = {
            allowedAudiences = ["api://${var.entra_client_id}"]
          }
        }
      }
      login = {
        tokenStore = { enabled = true }
      }
    }
  })

  depends_on = [azurerm_container_app.ui]
}
