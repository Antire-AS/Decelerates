# Bing Web Search v7 — replacement for the DuckDuckGo HTML-scrape fallback
# in api/services/pdf_web.py. DDG started returning HTTP 202 anti-bot pages
# around 2026-04, which made the agentic IR discovery pipeline's search
# layer silently broken. Bing's paid API isn't bot-detected and the F1
# SKU gives 1K queries/month free, comfortably covering our ~100-300
# discovery calls/month.
#
# See docs/superpowers/plans/2026-04-22-pdf-discovery-redesign.md Phase 2.

resource "azurerm_cognitive_account" "bing_search" {
  name                = "cog-${var.env}-bing-search"
  # Bing Search is a global service, not regional — always "global".
  location            = "global"
  resource_group_name = azurerm_resource_group.main.name
  kind                = "Bing.Search.v7"
  sku_name            = "F1"
  tags                = local.tags
}

output "bing_search_key" {
  description = "Primary access key for Bing Web Search. Paste into GitHub secret BING_SEARCH_API_KEY."
  value       = azurerm_cognitive_account.bing_search.primary_access_key
  sensitive   = true
}

output "bing_search_endpoint" {
  description = "Bing Web Search v7 endpoint. Defaults in app config already point here."
  value       = "https://api.bing.microsoft.com/v7.0/search"
}
