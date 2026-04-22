# Apply the LLM token observability saved searches

## What this is

PR #183 added three `azurerm_log_analytics_saved_search` resources in
`infra/terraform/monitoring.tf` under the `broker-llm` category. They
are committed to the repo but NOT yet materialised in Azure because
`terraform apply` is a local-only manual step (see `infra/` comment:
Terraform is NOT part of CI/CD).

Once applied, the three queries show up in the Azure portal under
**Log Analytics → Saved searches → broker-llm** and can be pinned to
a workbook or run directly.

## Prerequisites

- Terraform installed locally. If not:
  ```bash
  brew tap hashicorp/tap
  brew install hashicorp/tap/terraform
  ```
  (The community `terraform` formula was removed when HashiCorp
  changed the license — use the official tap.)
- Authenticated to Azure: `az login` + `az account set --subscription
  <broker-accelerator-prod-subscription-id>`.
- `SUBSCRIPTION_ID` handy (check `az account show --query id -o tsv`).
- `DB_ADMIN_PASSWORD` — pull from Azure Key Vault or wherever the
  broker team stores it. It's a required Terraform var with no default.

## Steps

### 1. Initialize Terraform (state backend)

```bash
cd infra/terraform
terraform init
```

The backend is Azure Blob Storage at
`rg-prod-brokeraccelerator` / `stprodbrokeracc` / `tfstate`. First-run
`init` downloads the providers and connects to state. It uses `az
login` creds locally (despite `use_oidc = true` in the backend config,
Azure CLI auth is the fallback for local runs — this works in
practice).

### 2. Plan

```bash
terraform plan \
  -var "subscription_id=$(az account show --query id -o tsv)" \
  -var "github_repo=Antire-AS/Decelerates" \
  -var "db_admin_password=<paste-from-keyvault>" \
  -out=/tmp/plan.out
```

**Before applying, review the plan carefully.** You're expecting to
see exactly 3 new resources:

```
+ azurerm_log_analytics_saved_search.llm_tokens_by_model
+ azurerm_log_analytics_saved_search.llm_tokens_trend
+ azurerm_log_analytics_saved_search.llm_call_volume

Plan: 3 to add, 0 to change, 0 to destroy.
```

If the plan shows additional changes (e.g. the monitor alerts being
"modified" or container_apps being touched), **stop** and investigate
drift — do NOT apply. Drift can happen when someone manually edits
resources in the Azure portal that Terraform also manages.

### 3. Apply (if plan was clean)

```bash
terraform apply /tmp/plan.out
```

Takes ~10 seconds. Three saved searches get created.

### 4. Verify in portal

Azure portal → **Log Analytics workspaces** → `law-prod-broker
accelerator` → **Saved searches** (under "General" on the left) →
category `broker-llm` should show three entries.

Click any of them to run the query. The result set is empty until
the next few LLM calls land in App Insights (`customMetrics` table
lags by ~60 s).

### 5. Cleanup (if you ever want to remove them)

```bash
cd infra/terraform
terraform destroy -target=azurerm_log_analytics_saved_search.llm_tokens_by_model
terraform destroy -target=azurerm_log_analytics_saved_search.llm_tokens_trend
terraform destroy -target=azurerm_log_analytics_saved_search.llm_call_volume
```

(You'd only do this if retiring the observability plane — keeping
them is cheap.)

## Troubleshooting

### "Error: Backend initialization required"

You're missing the state backend. Run `terraform init` first.

### "Error: No valid credential sources found"

`az login` hasn't run, or `az account show` returns a different
subscription. Set it explicitly:

```bash
az account set --subscription "Azure subscription 1"  # or whatever the prod sub is named
```

Then re-run `terraform init`.

### Plan shows dozens of changes

Drift. Someone edited live resources outside Terraform. Reconcile
first — either `terraform import` the divergent resources, or hand-
adjust the `.tf` files to match, or revert the live state to what
Terraform expects. Don't apply until the plan only shows the 3 saved
searches.

## Future: move this to CI

Terraform-in-CI was deliberately excluded earlier because infra
changes should be reviewed with the same rigour as a merge. If the
team grows, consider adding a terraform-plan-only GitHub Actions job
(so PRs show the planned diff) + keep apply local. Atlantis or
HashiCorp Cloud are the usual next steps.
