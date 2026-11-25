output "ec2_instance_id" {
  description = "ID of the optional private EC2 instance."
  value       = try(aws_instance.demo[0].id, null)
}

output "eks_cluster_name" {
  description = "Name of the optional private EKS cluster."
  value       = try(aws_eks_cluster.demo[0].name, null)
}

output "eks_cluster_endpoint" {
  description = "Private API endpoint of the optional EKS cluster. Access requires network connectivity to its VPC."
  value       = try(aws_eks_cluster.demo[0].endpoint, null)
}

output "route53_private_zone_id" {
  description = "ID of the optional private Route 53 hosted zone."
  value       = try(aws_route53_zone.private[0].zone_id, null)
}
