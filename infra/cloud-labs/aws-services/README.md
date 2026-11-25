# Optional AWS EC2, EKS, and Route 53 lab

This is a separate Terraform root so the AWS learning resources do not alter the main OpsBridge AWS baseline. It covers EC2, EKS, and Route 53 with all three resource groups disabled by default.

## Resources in this lab

- **EC2:** one private Amazon Linux 2023 instance, no public IP, IMDSv2 required, encrypted gp3 root disk, detailed monitoring, and an SSM instance profile instead of SSH access. The VPC needs outbound access to Systems Manager endpoints (through NAT or VPC endpoints).
- **EKS:** a private API endpoint, one managed node, EKS control-plane logs, and separate cluster/node IAM roles. The cluster needs two existing subnets in different Availability Zones. Access `kubectl` from a connected host in that VPC.
- **Route 53:** a private hosted zone associated with the supplied VPC; this does not create public DNS delegation.

## Validate without creating resources

```powershell
Copy-Item terraform.tfvars.example terraform.tfvars
terraform init
terraform validate
```

`terraform validate` checks the configuration without AWS credentials. `terraform plan` requires valid AWS credentials because the provider checks the caller identity, even when all feature flags are false. With the default false feature flags, the configuration has no lab resources to create. To study one service, enable only its `enable_*_lab` flag and fill in the matching existing VPC, subnet, and security-group values. Review `terraform plan` before any apply. Delete the lab with `terraform destroy` after the exercise.

EKS control planes, EC2 instances, and Route 53 hosted zones can incur charges; EKS also requires cluster network setup, IAM permissions, and a supported Kubernetes version in the selected region. Choose the current standard-support version using the [Amazon EKS version lifecycle](https://docs.aws.amazon.com/eks/latest/userguide/kubernetes-versions.html) before enabling it. Do not use a public SSH ingress rule or put credentials in the tfvars file.

The resources use the official Terraform AWS provider patterns for [`aws_instance`](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/instance), [`aws_eks_cluster`](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/eks_cluster), [`aws_eks_node_group`](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/eks_node_group), and [`aws_route53_zone`](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/route53_zone). This configuration has not been applied to an AWS account.
