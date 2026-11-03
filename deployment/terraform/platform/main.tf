# Platform resources the agent needs, outside the agent deployment itself:
# the governed BigQuery dataset, the Model Armor template, Apigee key secrets
# (empty: versions are added by hand), and least-privilege grants for the
# agent identities. Design domains: data access, guardrails, gateway keys.
#
# This module never enables APIs and never grants project-wide admin roles.
# APIs are enabled in the console (runbook Phase 1); review `terraform plan`
# before every apply.

terraform {
  required_version = ">= 1.6"
  required_providers {
    google = { source = "hashicorp/google", version = ">= 6.40, < 8.0" }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  labels = {
    env         = var.env
    owner       = "platform-team"
    cost-center = var.cost_center
    app         = "agent-platform"
  }
  # Roles each agent identity needs on the project (narrow, not editor).
  agent_project_roles = [
    "roles/aiplatform.user",   # models, Sessions, Memory Bank, Example Store, sandbox
    "roles/bigquery.jobUser",  # run read-only queries
    "roles/mcp.toolUser",      # call the BigQuery remote MCP server
    "roles/modelarmor.user",   # screen prompts and responses
    "roles/logging.logWriter", # logs
    "roles/cloudtrace.agent",  # traces
    "roles/monitoring.metricWriter",
    "roles/serviceusage.serviceUsageConsumer",
  ]
  agent_role_pairs = {
    for pair in setproduct(var.agent_principals, local.agent_project_roles) :
    "${pair[0]}|${pair[1]}" => { member = pair[0], role = pair[1] }
  }
}

resource "google_bigquery_dataset" "media" {
  dataset_id  = var.bq_dataset
  location    = var.bq_location
  description = "Synthetic media data for the agent platform sandbox (fictional titles)"
  labels      = merge(local.labels, { bu = "platform" })
}

resource "google_bigquery_dataset_iam_member" "agent_reader" {
  for_each   = toset(var.agent_principals)
  dataset_id = google_bigquery_dataset.media.dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = each.value
}

resource "google_project_iam_member" "agent" {
  for_each = local.agent_role_pairs
  project  = var.project_id
  role     = each.value.role
  member   = each.value.member
}

resource "google_secret_manager_secret" "apigee_key" {
  for_each  = toset(var.business_units)
  secret_id = "mc-apigee-key-${each.value}"
  labels    = merge(local.labels, { bu = each.value })
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_iam_member" "agent_key_reader" {
  for_each = {
    for pair in setproduct(var.business_units, var.agent_principals) :
    "${pair[0]}|${pair[1]}" => { bu = pair[0], member = pair[1] }
  }
  secret_id = google_secret_manager_secret.apigee_key[each.value.bu].id
  role      = "roles/secretmanager.secretAccessor"
  member    = each.value.member
}

resource "google_model_armor_template" "agent_io" {
  location    = var.region
  template_id = var.model_armor_template_id
  labels      = local.labels
  filter_config {
    pi_and_jailbreak_filter_settings {
      filter_enforcement = "ENABLED"
      confidence_level   = "MEDIUM_AND_ABOVE"
    }
    malicious_uri_filter_settings {
      filter_enforcement = "ENABLED"
    }
    sdp_settings {
      basic_config {
        filter_enforcement = "ENABLED"
      }
    }
    rai_settings {
      rai_filters {
        filter_type      = "HATE_SPEECH"
        confidence_level = "MEDIUM_AND_ABOVE"
      }
      rai_filters {
        filter_type      = "HARASSMENT"
        confidence_level = "MEDIUM_AND_ABOVE"
      }
      rai_filters {
        filter_type      = "DANGEROUS"
        confidence_level = "MEDIUM_AND_ABOVE"
      }
      rai_filters {
        filter_type      = "SEXUALLY_EXPLICIT"
        confidence_level = "MEDIUM_AND_ABOVE"
      }
    }
  }
}
