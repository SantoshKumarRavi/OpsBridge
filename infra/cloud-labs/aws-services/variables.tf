variable "aws_region" {
  type        = string
  description = "AWS region for this isolated, optional services lab."
  default     = "ap-south-1"
}

variable "lab_name" {
  type        = string
  description = "Short prefix used for lab resource names."
  default     = "opsbridge-lab"
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to supported resources."
  default     = { Project = "OpsBridge", Purpose = "LearningLab" }
}

variable "enable_ec2_lab" {
  type        = bool
  description = "Create one private, encrypted Amazon Linux EC2 instance."
  default     = false
}

variable "enable_eks_lab" {
  type        = bool
  description = "Create one private-endpoint EKS cluster and a one-node managed group. This incurs ongoing charges while active."
  default     = false
}

variable "enable_route53_lab" {
  type        = bool
  description = "Create a private Route 53 hosted zone associated with the supplied VPC."
  default     = false
}

variable "aws_lab_vpc_id" {
  type        = string
  description = "Existing VPC ID used by the EC2, EKS, and private Route 53 labs."
  default     = ""
  validation {
    condition     = !var.enable_route53_lab || length(var.aws_lab_vpc_id) > 0
    error_message = "Provide aws_lab_vpc_id when enable_route53_lab is true."
  }
}

variable "aws_lab_subnet_ids" {
  type        = list(string)
  description = "Existing private subnet IDs in at least two Availability Zones for EKS."
  default     = []
  validation {
    condition     = !var.enable_eks_lab || length(var.aws_lab_subnet_ids) >= 2
    error_message = "When EKS is enabled, provide at least two subnet IDs in separate Availability Zones."
  }
}

variable "aws_lab_ec2_subnet_id" {
  type        = string
  description = "Existing private subnet ID for the optional EC2 instance."
  default     = ""
  validation {
    condition     = !var.enable_ec2_lab || length(var.aws_lab_ec2_subnet_id) > 0
    error_message = "Provide aws_lab_ec2_subnet_id when enable_ec2_lab is true."
  }
}

variable "aws_lab_ec2_security_group_ids" {
  type        = list(string)
  description = "Existing security groups for the private EC2 instance. Do not allow public SSH ingress."
  default     = []
  validation {
    condition     = !var.enable_ec2_lab || length(var.aws_lab_ec2_security_group_ids) > 0
    error_message = "Provide at least one private security group when enable_ec2_lab is true."
  }
}

variable "eks_kubernetes_version" {
  type        = string
  description = "Kubernetes version offered by EKS in the chosen region; update this before applying as support changes."
  default     = "1.37"
}

variable "route53_private_zone_name" {
  type        = string
  description = "Private DNS zone name, for example lab.opsbridge.internal."
  default     = "lab.opsbridge.internal"
}

variable "ec2_instance_type" {
  type        = string
  description = "Instance type for the optional EC2 learning instance."
  default     = "t3.micro"
}

variable "eks_node_instance_type" {
  type        = string
  description = "Instance type for the optional EKS managed node group."
  default     = "t3.small"
}
