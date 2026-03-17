#!/usr/bin/env bash
# scripts/bootstrap-tf-backend.sh — one-time setup for Terraform remote state
#
# Run this ONCE before the first `terraform init`.
# Requires: az CLI logged in with an account that has Owner/Contributor on the subscription.
#
# Usage:
#   bash scripts/bootstrap-tf-backend.sh <subscription-id> <github-client-id>
#
# After this script completes, uncomment the backend "azurerm" block in
# infra/terraform/main.tf and run `terraform init` to migrate state.

set -euo pipefail

SUBSCRIPTION_ID="${1:?Usage: $0 <subscription-id> <github-client-id>}"
GITHUB_CLIENT_ID="${2:?Usage: $0 <subscription-id> <github-client-id>}"

RESOURCE_GROUP="rg-prod-brokeraccelerator"
STORAGE_ACCOUNT="stprodbrokeracc"
CONTAINER="tfstate"
LOCATION="norwayeast"

echo "==> Ensuring resource group exists..."
az group create \
  --name "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --output none

echo "==> Creating storage account for Terraform state..."
az storage account create \
  --name "$STORAGE_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --sku Standard_LRS \
  --allow-blob-public-access false \
  --min-tls-version TLS1_2 \
  --output none

echo "==> Creating tfstate container..."
az storage container create \
  --name "$CONTAINER" \
  --account-name "$STORAGE_ACCOUNT" \
  --auth-mode login \
  --output none

echo "==> Granting GitHub OIDC service principal Storage Blob Data Contributor..."
STORAGE_SCOPE="/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}/providers/Microsoft.Storage/storageAccounts/${STORAGE_ACCOUNT}"
az role assignment create \
  --role "Storage Blob Data Contributor" \
  --assignee "$GITHUB_CLIENT_ID" \
  --scope "$STORAGE_SCOPE" \
  --output none

echo ""
echo "Done. Next steps:"
echo "  1. Uncomment the backend \"azurerm\" block in infra/terraform/main.tf"
echo "  2. cd infra/terraform && terraform init   (migrates local state to Azure)"
echo "  3. Add the new GitHub secrets listed in infra/README.md"
