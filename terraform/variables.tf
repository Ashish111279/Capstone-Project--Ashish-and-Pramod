variable "aws_region" {
  description = "AWS region for the network, EKS cluster, and ECR repository."
  type        = string
  default     = "us-east-1"
}

variable "cluster_name" {
  description = "Name used for the EKS cluster and related resources."
  type        = string
  default     = "capstone"
}

variable "kubernetes_version" {
  description = "EKS Kubernetes version; update to a version supported in the selected region."
  type        = string
  default     = "1.35"
}

variable "single_nat_gateway" {
  description = "Use one NAT gateway to reduce cost; set false for one per availability zone."
  type        = bool
  default     = true
}

variable "tags" {
  description = "Tags applied to created resources."
  type        = map(string)
  default = {
    Project   = "devops-capstone"
    ManagedBy = "terraform"
  }
}