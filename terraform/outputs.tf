output "cluster_name" {
  description = "EKS cluster name."
  value       = module.eks.cluster_name
}

output "cluster_endpoint" {
  description = "Private Kubernetes API endpoint."
  value       = module.eks.cluster_endpoint
}

output "ecr_repository_url" {
  description = "URI of the application image repository."
  value       = aws_ecr_repository.app.repository_url
}

output "vpc_id" {
  description = "ID of the application VPC."
  value       = module.vpc.vpc_id
}