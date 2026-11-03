terraform {
  required_version = ">= 1.6"
  required_providers {
    google = { source = "hashicorp/google", version = ">= 6.40" }
  }
}

variable "project_id" { type = string }
variable "region" {
  type    = string
  default = "us-central1"
}
variable "env" {
  type    = string
  default = "sandbox"
}
variable "cost_center" { type = string }

locals {
  labels = { env = var.env, owner = "platform-team", cost-center = var.cost_center, app = "agent-platform" }
  apis = [
    "aiplatform.googleapis.com",
    "bigquery.googleapis.com",
    "secretmanager.googleapis.com",
    "modelarmor.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "cloudtrace.googleapis.com",
    "telemetry.googleapis.com",
    "compute.googleapis.com",
    "apigee.googleapis.com",
    "cloudkms.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
  ]
  agent_roles = [
    "roles/aiplatform.user",
    "roles/mcp.toolUser",
    "roles/bigquery.jobUser",
    "roles/modelarmor.user",
    "roles/logging.logWriter",
    "roles/cloudtrace.agent",
    "roles/monitoring.metricWriter",
    "roles/serviceusage.serviceUsageConsumer",
  ]
}

provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_project_service" "apis" {
  for_each           = toset(local.apis)
  service            = each.value
  disable_on_destroy = false
}

resource "google_compute_network" "vpc" {
  name                    = "mc-platform-vpc"
  auto_create_subnetworks = false
  depends_on              = [google_project_service.apis]
}

resource "google_compute_subnetwork" "subnet" {
  name                     = "mc-${var.region}"
  network                  = google_compute_network.vpc.id
  region                   = var.region
  ip_cidr_range            = "10.10.0.0/24"
  private_ip_google_access = true
}

resource "google_storage_bucket" "staging" {
  name                        = "${var.project_id}-mc-agent-staging"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  labels                      = merge(local.labels, { bu = "platform" })
}

resource "google_service_account" "agent" {
  account_id   = "mc-agent-runtime"
  display_name = "MC agent runtime identity"
}

resource "google_project_iam_member" "agent" {
  for_each = toset(local.agent_roles)
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.agent.email}"
}

resource "google_bigquery_dataset" "media" {
  dataset_id = "media_analytics"
  location   = var.region
  labels     = merge(local.labels, { bu = "platform" })
}

resource "google_bigquery_dataset_iam_member" "agent_reader" {
  dataset_id = google_bigquery_dataset.media.dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.agent.email}"
}

resource "google_secret_manager_secret" "apigee_key" {
  for_each  = toset(["news", "entertainment"])
  secret_id = "mc-apigee-key-${each.value}"
  labels    = merge(local.labels, { bu = each.value })
  replication {
    auto {}
  }
}

resource "google_model_armor_template" "agent_io" {
  location    = var.region
  template_id = "mc-agent-io"
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
  depends_on = [google_project_service.apis]
}

output "agent_service_account" { value = google_service_account.agent.email }
