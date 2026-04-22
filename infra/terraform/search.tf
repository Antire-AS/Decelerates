# Web search provider for PDF discovery pipeline.
#
# NO AZURE RESOURCE. The web search provider is Serper.dev (external SaaS).
#
# History:
# - Prior attempt #1: DDG HTML scrape. Broke ~2026-04 when DuckDuckGo started
#   returning HTTP 202 anti-bot pages. Measured 0/20 recall in the harness.
# - Prior attempt #2: Bing Web Search v7 via azurerm_cognitive_account.
#   Turned out Microsoft retired Bing.Search.v7 in 2024 — the kind no longer
#   exists in `az cognitiveservices account list-kinds`. Never provisioned.
# - Current: Serper.dev. Pure HTTP API, no Azure resource to provision.
#   Sign up at https://serper.dev/, get API key, paste into GitHub secret
#   `SERPER_API_KEY`. $5/mo flat for 50K queries; free tier 2,500 one-time
#   credits for local-dev / first-prod-week validation.
#
# This .tf file is kept (rather than deleted) as an anchor for the
# "search provider history" knowledge — future contributors see this
# comment and understand why there's no Terraform for the search layer.
