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

Once these are set, every push to `main` will automatically build and deploy both containers.

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
- **Remote state**: the backend is set to `local` by default. For team use, uncomment the `backend "azurerm"` block in `main.tf` and create the storage account manually before running `terraform init`.
- **SKUs**: `B_Standard_B1ms` for PostgreSQL and `Basic` ACR are sized for development/staging. Upgrade `sku_name` and ACR SKU for production traffic.
