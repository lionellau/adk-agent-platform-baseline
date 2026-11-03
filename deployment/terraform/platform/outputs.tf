output "bq_dataset" {
  value = google_bigquery_dataset.media.dataset_id
}

output "model_armor_template" {
  value = google_model_armor_template.agent_io.name
}

output "apigee_key_secrets" {
  value = { for bu, s in google_secret_manager_secret.apigee_key : bu => s.secret_id }
}
