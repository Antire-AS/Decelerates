# ── Log Analytics Workspace ────────────────────────────────────────────────────

resource "azurerm_log_analytics_workspace" "main" {
  name                = "law-${var.env}-brokeraccelerator"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = local.tags
}

# ── Application Insights ───────────────────────────────────────────────────────
# Workspace-based (recommended) — telemetry stored in the Log Analytics workspace above.
# The API container reads the connection string from APPLICATIONINSIGHTS_CONNECTION_STRING
# (set in container_apps.tf) to export OTel traces, metrics, and logs.

resource "azurerm_application_insights" "main" {
  name                = "appi-${var.env}-brokeraccelerator"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  workspace_id        = azurerm_log_analytics_workspace.main.id
  application_type    = "web"
  tags                = local.tags
}

# ── Alert action group ─────────────────────────────────────────────────────────
# Set var.alert_email to receive email notifications when alerts fire.

resource "azurerm_monitor_action_group" "main" {
  name                = "ag-${var.env}-brokeraccelerator"
  resource_group_name = azurerm_resource_group.main.name
  short_name          = "broker-ag"
  tags                = local.tags

  dynamic "email_receiver" {
    for_each = var.alert_email != "" ? [1] : []
    content {
      name          = "ops-email"
      email_address = var.alert_email
    }
  }
}

# ── Alert: failed requests > 5 in 5 min (severity 1 — critical) ───────────────

resource "azurerm_monitor_metric_alert" "failed_requests" {
  name                = "alert-${var.env}-failed-requests"
  resource_group_name = azurerm_resource_group.main.name
  scopes              = [azurerm_application_insights.main.id]
  description         = "Failed HTTP requests > 5 in a 5-minute window"
  severity            = 1
  frequency           = "PT1M"
  window_size         = "PT5M"
  tags                = local.tags

  criteria {
    metric_namespace = "microsoft.insights/components"
    metric_name      = "requests/failed"
    aggregation      = "Count"
    operator         = "GreaterThan"
    threshold        = 5
  }

  action {
    action_group_id = azurerm_monitor_action_group.main.id
  }
}

# ── Alert: unhandled exceptions > 10 in 5 min ─────────────────────────────────

resource "azurerm_monitor_metric_alert" "high_exceptions" {
  name                = "alert-${var.env}-high-exceptions"
  resource_group_name = azurerm_resource_group.main.name
  scopes              = [azurerm_application_insights.main.id]
  description         = "Unhandled exceptions > 10 in a 5-minute window"
  severity            = 2
  frequency           = "PT1M"
  window_size         = "PT5M"
  tags                = local.tags

  criteria {
    metric_namespace = "microsoft.insights/components"
    metric_name      = "exceptions/count"
    aggregation      = "Count"
    operator         = "GreaterThan"
    threshold        = 10
  }

  action {
    action_group_id = azurerm_monitor_action_group.main.id
  }
}

# ── Alert: average response time > 5 s over 5 min ─────────────────────────────

resource "azurerm_monitor_metric_alert" "slow_responses" {
  name                = "alert-${var.env}-slow-responses"
  resource_group_name = azurerm_resource_group.main.name
  scopes              = [azurerm_application_insights.main.id]
  description         = "Average server response time > 5000 ms over 5 minutes"
  severity            = 2
  frequency           = "PT1M"
  window_size         = "PT5M"
  tags                = local.tags

  criteria {
    metric_namespace = "microsoft.insights/components"
    metric_name      = "requests/duration"
    aggregation      = "Average"
    operator         = "GreaterThan"
    threshold        = 5000
  }

  action {
    action_group_id = azurerm_monitor_action_group.main.id
  }
}

# ── Alert: API container CPU > 80 % ────────────────────────────────────────────

resource "azurerm_monitor_metric_alert" "api_cpu" {
  name                = "alert-${var.env}-api-high-cpu"
  resource_group_name = azurerm_resource_group.main.name
  scopes              = [azurerm_container_app.api.id]
  description         = "API container average CPU > 80% over 5 minutes"
  severity            = 2
  frequency           = "PT1M"
  window_size         = "PT5M"
  tags                = local.tags

  criteria {
    metric_namespace = "microsoft.app/containerapps"
    metric_name      = "CpuPercentage"
    aggregation      = "Average"
    operator         = "GreaterThan"
    threshold        = 80
  }

  action {
    action_group_id = azurerm_monitor_action_group.main.id
  }
}

# ── Alert: API container memory > 80 % ────────────────────────────────────────

resource "azurerm_monitor_metric_alert" "api_memory" {
  name                = "alert-${var.env}-api-high-memory"
  resource_group_name = azurerm_resource_group.main.name
  scopes              = [azurerm_container_app.api.id]
  description         = "API container average memory > 80% over 5 minutes"
  severity            = 2
  frequency           = "PT1M"
  window_size         = "PT5M"
  tags                = local.tags

  criteria {
    metric_namespace = "microsoft.app/containerapps"
    metric_name      = "MemoryPercentage"
    aggregation      = "Average"
    operator         = "GreaterThan"
    threshold        = 80
  }

  action {
    action_group_id = azurerm_monitor_action_group.main.id
  }
}
