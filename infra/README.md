# Infrastructure

## Ownership split

| What | Who manages it | When |
|------|---------------|------|
| Container App images (api, ui) | `deploy.yml` via `az containerapp create/update` | Every push to `main` / `staging` |
| Container App Environment (CAE) | Manual / one-time CLI | First-time setup only |
| ACR (`crantireshared`) | Manually provisioned | One-time |
| PostgreSQL (`psql-broker-accelerator`) | Manually provisioned | One-time |
| Managed identity | Manually provisioned | One-time |
| OIDC federation (GitHub → Azure) | `infra/terraform/` | Run locally when auth config changes |
| Entra ID app registration (Easy Auth) | `infra/terraform/` | Run locally when auth config changes |

**Terraform is NOT run in CI/CD.** It is used locally to manage auth/identity resources that rarely change.
The `deploy.yml` workflow is the single source of truth for application deployments.

> **Why this split?** The live Azure resources were provisioned with specific names (`ca-api`, `crantireshared`,
> `rg-broker-accelerator-prod`) that pre-date the Terraform config. Bringing them under Terraform state
> requires `terraform import` for each resource — tracked as future work.
> Until then, keeping Terraform out of CI prevents silent failures.

---

## First-time environment setup (new environment)

```bash
# 1. Create resource group
az group create --name rg-broker-accelerator-prod --location norwayeast

# 2. Create Container Registry
az acr create --name crantireshared --resource-group rg-broker-accelerator-prod --sku Basic

# 3. Create Container App Environment
az containerapp env create \
  --name cae-broker-accelerator-prod \
  --resource-group rg-broker-accelerator-prod \
  --location norwayeast

# 4. Create managed identity for ACR pull
az identity create \
  --name id-runtime-broker-accelerator-prod \
  --resource-group rg-broker-accelerator-prod

# 5. Assign AcrPull to managed identity
az role assignment create \
  --role AcrPull \
  --assignee <managed-identity-principal-id> \
  --scope $(az acr show --name crantireshared --query id -o tsv)

# 6. Bootstrap Terraform backend (for OIDC + Entra auth resources)
bash scripts/bootstrap-tf-backend.sh <subscription-id> <github-client-id>

# 7. Apply Terraform (OIDC federation + Entra auth only)
cd infra/terraform
terraform init && terraform apply
```

After these steps, push to `main` — `deploy.yml` will build and deploy the application.

---

## Adding a new environment variable to running Container Apps

Azure Container Apps preserves env vars across `az containerapp update --image` revisions.
To add or change a variable without redeploying from scratch:

```bash
az containerapp update \
  --name ca-api \
  --resource-group rg-broker-accelerator-prod \
  --set-env-vars "NEW_VAR=value"
```

Also add the variable to the `--env-vars` block in the `Deploy API` step of `deploy.yml`
so it is set correctly on first-time container app creation.

---

## Terraform (OIDC + Entra auth)

Terraform manages only the OIDC federation and Entra ID app registration. Run locally when
these resources need to change.

```bash
cd infra/terraform
az login
terraform init
terraform plan
terraform apply
```

### Notes

- **State backend**: Azure Blob Storage (`stprodbrokeracc/tfstate`). Run
  `scripts/bootstrap-tf-backend.sh` once before the first `terraform init`.
- **pgvector**: enabled via `azure.extensions = vector` server configuration.
- **Firewall**: `0.0.0.0–0.0.0.0` allows all Azure-hosted IPs to reach PostgreSQL. Tighter
  rules require VNet integration.
