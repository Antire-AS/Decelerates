# Entra ID app registration for the Broker UI with User + Manager app roles
resource "azuread_application" "broker_ui" {
  display_name     = "broker-accelerator-${var.env}"
  sign_in_audience = "AzureADMyOrg"

  web {
    redirect_uris = [
      "https://${azurerm_container_app.ui.latest_revision_fqdn}/.auth/login/aad/callback",
    ]
    implicit_grant {
      id_token_issuance_enabled = true
    }
  }

  app_role {
    allowed_member_types = ["User"]
    description          = "Standard bruker — tilgang til alle funksjoner"
    display_name         = "User"
    enabled              = true
    id                   = "00000000-0000-0000-0000-000000000001"
    value                = "User"
  }

  app_role {
    allowed_member_types = ["User"]
    description          = "Manager — tilgang til admin-funksjoner og porteføljehåndtering"
    display_name         = "Manager"
    enabled              = true
    id                   = "00000000-0000-0000-0000-000000000002"
    value                = "Manager"
  }

  required_resource_access {
    resource_app_id = "00000003-0000-0000-c000-000000000000" # Microsoft Graph
    resource_access {
      id   = "e1fe6dd8-ba31-4d61-89e7-88639da4683d" # User.Read
      type = "Scope"
    }
  }
}

resource "azuread_service_principal" "broker_ui" {
  client_id                    = azuread_application.broker_ui.client_id
  app_role_assignment_required = false
}

resource "azuread_application_password" "broker_ui" {
  application_id = azuread_application.broker_ui.id
  display_name   = "container-apps-easy-auth"
  end_date       = "2099-01-01T00:00:00Z"
}

# Easy Auth config for the UI container app via azapi
resource "azapi_resource" "ui_auth" {
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
            openIdIssuer            = "https://sts.windows.net/${data.azuread_client_config.current.tenant_id}/v2.0"
            clientId                = azuread_application.broker_ui.client_id
            clientSecretSettingName = "microsoft-provider-authentication-secret"
          }
          validation = {
            allowedAudiences = ["api://${azuread_application.broker_ui.client_id}"]
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
