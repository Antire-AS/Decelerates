# Azure Database for PostgreSQL Flexible Server (v16 with pgvector)
resource "azurerm_postgresql_flexible_server" "main" {
  name                   = "psql-${var.env}-brokeraccelerator"
  resource_group_name    = azurerm_resource_group.main.name
  location               = azurerm_resource_group.main.location
  version                = "16"
  administrator_login    = "brokeradmin"
  administrator_password = var.db_admin_password
  storage_mb             = 32768
  sku_name               = "B_Standard_B1ms"
  backup_retention_days  = 7
  geo_redundant_backup   = "Disabled"
  tags                   = local.tags
}

resource "azurerm_postgresql_flexible_server_database" "brokerdb" {
  name      = "brokerdb"
  server_id = azurerm_postgresql_flexible_server.main.id
  charset   = "UTF8"
  collation = "en_US.utf8"
}

# Enable pgvector extension
resource "azurerm_postgresql_flexible_server_configuration" "pgvector" {
  name      = "azure.extensions"
  server_id = azurerm_postgresql_flexible_server.main.id
  value     = "vector"
}

# Allow connections from Azure services (Container Apps use dynamic IPs)
resource "azurerm_postgresql_flexible_server_firewall_rule" "allow_azure_services" {
  name             = "allow-azure-services"
  server_id        = azurerm_postgresql_flexible_server.main.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}

locals {
  db_connection_string = join("", [
    "postgresql://",
    azurerm_postgresql_flexible_server.main.administrator_login,
    ":",
    var.db_admin_password,
    "@",
    azurerm_postgresql_flexible_server.main.fqdn,
    ":5432/",
    azurerm_postgresql_flexible_server_database.brokerdb.name,
    "?sslmode=require",
  ])
}
