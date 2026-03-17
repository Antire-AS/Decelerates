# Infrastructure

Azure infrastructure for Broker Accelerator, managed with Terraform.

## Architecture

| Component | Azure Service |
|-----------|---------------|
| API (FastAPI) | Azure Container App |
| UI (Streamlit) | Azure Container App |
| Database | Azure PostgreSQL Flexible Server v16 |
| Container images | Azure Container Registry (Basic SKU) |
| Auth | GitHub OIDC federated credential (no stored secrets) |

## Prerequisites

- [Terraform](https://developer.hashicorp.com/terraform/install) ≥ 1.7
- [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli)
- An Azure subscription

## Bootstrap Terraform state backend

Run this **once** before the first `terraform init`. It creates the Azure Storage Account that holds the Terraform state file and grants the GitHub OIDC principal access to it.

```bash
bash scripts/bootstrap-tf-backend.sh <subscription-id> <github-client-id>
```

Get `<github-client-id>` from `terraform output -raw github_client_id` after a local first apply, or from the Azure portal (App Registration → Client ID).

---

## First-time setup

```bash
# 1. Authenticate
az login
az account set --subscription "<your-subscription-id>"

# 2. Enter the Terraform directory
cd infra/terraform

# 3. Create your variable values (never commit this file)
cat > terraform.tfvars <<EOF
subscription_id   = "<your-subscription-id>"
github_repo       = "<owner/repo>"          # e.g. "myorg/Decelerates"
db_admin_password = "<strong-password>"
anthropic_api_key = "<key-or-empty>"
gemini_api_key    = "<key>"
voyage_api_key    = "<key-or-empty>"
EOF

# 4. Initialise and apply
terraform init
terraform plan
terraform apply
```

After `apply` completes, note the outputs:

```
acr_login_server  = "acrprodbrokeraccelerator.azurecr.io"
api_url           = "https://ca-prod-api.<hash>.norwayeast.azurecontainerapps.io"
ui_url            = "https://ca-prod-ui.<hash>.norwayeast.azurecontainerapps.io"
github_client_id  = "<uuid>"
tenant_id         = "<uuid>"
```

## GitHub Actions secrets

Set these in your repository → Settings → Secrets → Actions:

| Secret | Value |
|--------|-------|
| `AZURE_CLIENT_ID` | `terraform output -raw github_client_id` |
| `AZURE_TENANT_ID` | `terraform output -raw tenant_id` |
| `AZURE_SUBSCRIPTION_ID` | Your Azure subscription ID |
| `ACR_NAME` | Registry name only, e.g. `acrprodbrokeraccelerator` (no `.azurecr.io`) |
| `DB_ADMIN_PASSWORD` | PostgreSQL admin password (same as `db_admin_password` in tfvars) |
| `ANTHROPIC_API_KEY` | Claude API key |
| `GEMINI_API_KEY` | Primary Gemini key |
| `GEMINI_API_KEY_2` | Optional — Gemini rotation slot 2 |
| `GEMINI_API_KEY_3` | Optional — Gemini rotation slot 3 |
| `VOYAGE_API_KEY` | Optional — Voyage AI embeddings key |

Once these are set, every push to `main` will build both container images and run `terraform apply` to deploy them — Terraform is the single source of truth for all infrastructure and image versions.

## Day-to-day operations

```bash
# Review changes before applying
terraform plan

# Apply infrastructure changes
terraform apply

# Tear everything down
terraform destroy
```

## Notes

- **pgvector**: enabled via `azure.extensions = vector` server configuration — no manual SQL needed on first run.
- **Firewall**: `0.0.0.0–0.0.0.0` allows all Azure-hosted IPs to reach PostgreSQL. Container Apps use dynamic egress IPs so a tighter rule is not practical without VNet integration.
- **Remote state**: stored in Azure Blob Storage (`stprodbrokeracc/tfstate`). Run `scripts/bootstrap-tf-backend.sh` once before the first `terraform init`. CI uses OIDC to access the state file — no storage account keys are stored in GitHub.
- **SKUs**: `B_Standard_B1ms` for PostgreSQL and `Basic` ACR are sized for development/staging. Upgrade `sku_name` and ACR SKU for production traffic.
