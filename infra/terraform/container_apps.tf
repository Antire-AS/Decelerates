# User-assigned managed identity — shared by both Container Apps for ACR pulls
resource "azurerm_user_assigned_identity" "container_apps" {
  name                = "id-${var.env}-brokeraccelerator"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  tags                = local.tags
}

# Container Apps Environment — shared networking + logging for both apps
resource "azurerm_container_app_environment" "main" {
  name                = "cae-${var.env}-brokeraccelerator"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.tags
}

# ── API (FastAPI) ─────────────────────────────────────────────────────────────

resource "azurerm_container_app" "api" {
  name                         = "ca-${var.env}-api"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"
  tags                         = local.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.container_apps.id]
  }

  registry {
    server   = azurerm_container_registry.main.login_server
    identity = azurerm_user_assigned_identity.container_apps.id
  }

  template {
    min_replicas = 1
    max_replicas = 3

    container {
      name   = "api"
      image  = "${azurerm_container_registry.main.login_server}/broker-api:${var.api_image_tag}"
      cpu    = 0.5
      memory = "1Gi"

      env {
        name  = "DATABASE_URL"
        value = local.db_connection_string
      }
      env {
        name  = "ANTHROPIC_API_KEY"
        value = var.anthropic_api_key
      }
      env {
        name  = "GEMINI_API_KEY"
        value = var.gemini_api_key
      }
      env {
        name  = "GEMINI_API_KEY_2"
        value = var.gemini_api_key_2
      }
      env {
        name  = "GEMINI_API_KEY_3"
        value = var.gemini_api_key_3
      }
      env {
        name  = "VOYAGE_API_KEY"
        value = var.voyage_api_key
      }
    }
  }

  ingress {
    external_enabled = true
    target_port      = 8000
    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }
}

# ── UI (Streamlit) ────────────────────────────────────────────────────────────

resource "azurerm_container_app" "ui" {
  name                         = "ca-${var.env}-ui"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"
  tags                         = local.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.container_apps.id]
  }

  registry {
    server   = azurerm_container_registry.main.login_server
    identity = azurerm_user_assigned_identity.container_apps.id
  }

  dynamic "secret" {
    for_each = var.entra_client_secret != "" ? [1] : []
    content {
      name  = "microsoft-provider-authentication-secret"
      value = var.entra_client_secret
    }
  }

  template {
    min_replicas = 1
    max_replicas = 2

    container {
      name   = "ui"
      image  = "${azurerm_container_registry.main.login_server}/broker-ui:${var.ui_image_tag}"
      cpu    = 0.25
      memory = "0.5Gi"

      env {
        name  = "API_BASE_URL"
        value = "https://${azurerm_container_app.api.latest_revision_fqdn}"
      }
      env {
        name  = "ENTRA_CLIENT_ID"
        value = var.entra_client_id
      }
      env {
        name  = "ENTRA_TENANT_ID"
        value = var.entra_tenant_id
      }
    }
  }

  ingress {
    external_enabled = true
    target_port      = 8501
    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }
}
