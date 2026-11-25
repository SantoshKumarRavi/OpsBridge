locals {
  common_tags = merge(var.tags, { Lab = var.lab_name })
}

# No lab resources are created unless the corresponding enable_* variable is true.
resource "aws_iam_role" "ec2" {
  count = var.enable_ec2_lab ? 1 : 0
  name  = "${var.lab_name}-ec2-ssm"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })
  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "ec2_ssm" {
  count      = var.enable_ec2_lab ? 1 : 0
  role       = aws_iam_role.ec2[0].name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "ec2" {
  count = var.enable_ec2_lab ? 1 : 0
  name  = "${var.lab_name}-ec2-ssm"
  role  = aws_iam_role.ec2[0].name
  tags  = local.common_tags
}

resource "aws_instance" "demo" {
  count         = var.enable_ec2_lab ? 1 : 0
  ami           = "resolve:ssm:/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
  instance_type = var.ec2_instance_type
  subnet_id     = var.aws_lab_ec2_subnet_id

  vpc_security_group_ids      = var.aws_lab_ec2_security_group_ids
  associate_public_ip_address = false
  iam_instance_profile        = aws_iam_instance_profile.ec2[0].name
  monitoring                  = true

  metadata_options {
    http_endpoint = "enabled"
    http_tokens   = "required"
  }

  root_block_device {
    encrypted   = true
    volume_type = "gp3"
    volume_size = 8
  }

  tags = merge(local.common_tags, { Name = "${var.lab_name}-ec2" })

  depends_on = [aws_iam_role_policy_attachment.ec2_ssm]
}

resource "aws_iam_role" "eks_cluster" {
  count = var.enable_eks_lab ? 1 : 0
  name  = "${var.lab_name}-eks-cluster"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = ["sts:AssumeRole", "sts:TagSession"]
      Principal = { Service = "eks.amazonaws.com" }
    }]
  })
  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "eks_cluster" {
  count      = var.enable_eks_lab ? 1 : 0
  role       = aws_iam_role.eks_cluster[0].name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
}

resource "aws_iam_role" "eks_nodes" {
  count = var.enable_eks_lab ? 1 : 0
  name  = "${var.lab_name}-eks-nodes"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })
  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "eks_nodes" {
  for_each = var.enable_eks_lab ? toset([
    "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy",
    "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy",
    "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
  ]) : toset([])

  role       = aws_iam_role.eks_nodes[0].name
  policy_arn = each.value
}

resource "aws_eks_cluster" "demo" {
  count    = var.enable_eks_lab ? 1 : 0
  name     = "${var.lab_name}-eks"
  role_arn = aws_iam_role.eks_cluster[0].arn
  version  = var.eks_kubernetes_version

  vpc_config {
    subnet_ids              = var.aws_lab_subnet_ids
    endpoint_private_access = true
    endpoint_public_access  = false
  }

  enabled_cluster_log_types = ["api", "audit", "authenticator"]
  tags                      = local.common_tags

  depends_on = [aws_iam_role_policy_attachment.eks_cluster]
}

resource "aws_eks_node_group" "demo" {
  count           = var.enable_eks_lab ? 1 : 0
  cluster_name    = aws_eks_cluster.demo[0].name
  node_group_name = "${var.lab_name}-workers"
  node_role_arn   = aws_iam_role.eks_nodes[0].arn
  subnet_ids      = var.aws_lab_subnet_ids
  instance_types  = [var.eks_node_instance_type]

  scaling_config {
    min_size     = 0
    desired_size = 1
    max_size     = 1
  }

  update_config {
    max_unavailable = 1
  }

  tags = local.common_tags

  depends_on = [aws_iam_role_policy_attachment.eks_nodes]
}

resource "aws_route53_zone" "private" {
  count = var.enable_route53_lab ? 1 : 0
  name  = var.route53_private_zone_name

  vpc {
    vpc_id = var.aws_lab_vpc_id
  }

  comment       = "Private OpsBridge learning zone; not delegated on the public internet."
  force_destroy = false
  tags          = local.common_tags
}
