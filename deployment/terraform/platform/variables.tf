variable "project_id" {
  type        = string
  description = "Sandbox project ID."
}

variable "region" {
  type        = string
  default     = "us-central1"
  description = "Region for Model Armor (regional only, never \"global\")."
}

variable "env" {
  type    = string
  default = "sandbox"
}

variable "cost_center" {
  type        = string
  description = "Billing label on every resource."
}

variable "bq_dataset" {
  type    = string
  default = "media_analytics"
}

variable "bq_location" {
  type        = string
  default     = "us-central1"
  description = "BigQuery location; keep it equal to REGION in platform.env."
}

variable "model_armor_template_id" {
  type    = string
  default = "mc-agent-io"
}

variable "business_units" {
  type        = list(string)
  default     = ["news", "entertainment"]
  description = "One Apigee key secret per business unit (design D9)."
}

variable "agent_principals" {
  type        = list(string)
  default     = []
  description = <<-EOT
    IAM members that run the agent, e.g.
    "serviceAccount:app-sa@PROJECT.iam.gserviceaccount.com" (Cloud Run) or the
    agent identity principal printed by `agents-cli deploy --agent-identity`.
    Empty on the first apply; add them after the first deploy and re-apply.
  EOT
}
