output "application_url" {
  value = "https://${aws_lb.api.dns_name}"
}

output "document_bucket" {
  value = aws_s3_bucket.documents.bucket
}

output "database_endpoint" {
  value = aws_db_instance.database.address
}

output "database_secret_arn" {
  value = aws_db_instance.database.master_user_secret[0].secret_arn
}

output "domain_events_queue_url" {
  value = aws_sqs_queue.domain_events.url
}

output "notification_topic_arn" {
  value = aws_sns_topic.notifications.arn
}
