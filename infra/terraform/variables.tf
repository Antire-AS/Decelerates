variable "subscription_id" {
  description = "Azure Subscription ID"
  type        = string
}

variable "location" {
  description = "Azure region"
  type        = string
  default     = "norwayeast"
}

variable "env" {
  description = "Environment name (prod, staging, dev)"
  type        = string
  default     = "prod"
}

variable "github_repo" {
  description = "GitHub repository in owner/repo format"
  type        = string
  # Example: "myorg/Decelerates"
}

variable "api_image_tag" {
  description = "Docker image tag for the API container"
  type        = string
  default     = "latest"
}

variable "ui_image_tag" {
  description = "Docker image tag for the UI container"
  type        = string
  default     = "latest"
}

variable "db_admin_password" {
  description = "PostgreSQL administrator password"
  type        = string
  sensitive   = true
}

variable "anthropic_api_key" {
  description = "Anthropic API key (optional)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "gemini_api_key" {
  description = "Google Gemini API key"
  type        = string
  sensitive   = true
  default     = ""
}

variable "gemini_api_key_2" {
  description = "Google Gemini API key (rotation slot 2)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "gemini_api_key_3" {
  description = "Google Gemini API key (rotation slot 3)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "voyage_api_key" {
  description = "Voyage AI embedding key (optional)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "entra_tenant_id" {
  description = "Azure AD Tenant ID — passed from AZURE_TENANT_ID GitHub secret"
  type        = string
  default     = ""
}

variable "entra_client_id" {
  description = "Entra ID app registration Client ID for Easy Auth (ENTRA_CLIENT_ID secret)"
  type        = string
  default     = ""
}

variable "entra_client_secret" {
  description = "Entra ID app registration Client Secret for Easy Auth (ENTRA_CLIENT_SECRET secret)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "alert_email" {
  description = "Email address for Azure Monitor alert notifications (leave empty to disable email alerts)"
  type        = string
  default     = ""
}
