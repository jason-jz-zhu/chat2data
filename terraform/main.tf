# Main Terraform configuration for Chat2Data AWS infrastructure

terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    # Configure backend in backend.tf or via CLI
    # bucket = "chat2data-terraform-state"
    # key    = "prod/terraform.tfstate"
    # region = "us-east-1"
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "Chat2Data"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

# VPC Module
module "vpc" {
  source = "./modules/vpc"

  environment         = var.environment
  vpc_cidr            = var.vpc_cidr
  availability_zones  = var.availability_zones
  private_subnet_cidrs = var.private_subnet_cidrs
  public_subnet_cidrs  = var.public_subnet_cidrs
}

# Aurora PostgreSQL Module
module "aurora" {
  source = "./modules/aurora"

  environment           = var.environment
  cluster_identifier    = "chat2data-${var.environment}"
  engine_version        = var.aurora_engine_version
  instance_class        = var.aurora_instance_class
  instance_count        = var.aurora_instance_count

  database_name         = var.database_name
  master_username       = var.master_username

  vpc_id                = module.vpc.vpc_id
  subnet_ids            = module.vpc.private_subnet_ids
  allowed_cidr_blocks   = module.vpc.private_subnet_cidrs

  backup_retention_period = var.environment == "prod" ? 30 : 7
  preferred_backup_window = "03:00-04:00"
  preferred_maintenance_window = "mon:04:00-mon:05:00"
}

# OpenSearch Module
module "opensearch" {
  source = "./modules/opensearch"

  environment          = var.environment
  domain_name          = "chat2data-${var.environment}"
  opensearch_version   = var.opensearch_version
  instance_type        = var.opensearch_instance_type
  instance_count       = var.opensearch_instance_count
  ebs_volume_size      = var.opensearch_ebs_volume_size

  vpc_id               = module.vpc.vpc_id
  subnet_ids           = module.vpc.private_subnet_ids
  allowed_cidr_blocks  = module.vpc.private_subnet_cidrs
}

# ElastiCache Redis Module
module "redis" {
  source = "./modules/redis"

  environment         = var.environment
  cluster_id          = "chat2data-${var.environment}"
  node_type           = var.redis_node_type
  num_cache_nodes     = var.redis_num_nodes

  vpc_id              = module.vpc.vpc_id
  subnet_ids          = module.vpc.private_subnet_ids
  allowed_cidr_blocks = module.vpc.private_subnet_cidrs
}

# ECS Fargate Module
module "ecs" {
  source = "./modules/ecs"

  environment           = var.environment
  cluster_name          = "chat2data-${var.environment}"
  service_name          = "chat2data-api"

  container_image       = var.container_image
  container_port        = var.container_port
  desired_count         = var.ecs_desired_count
  cpu                   = var.ecs_cpu
  memory                = var.ecs_memory

  vpc_id                = module.vpc.vpc_id
  private_subnet_ids    = module.vpc.private_subnet_ids
  public_subnet_ids     = module.vpc.public_subnet_ids

  # Environment variables
  environment_variables = {
    AURORA_HOST          = module.aurora.cluster_endpoint
    AURORA_PORT          = "5432"
    AURORA_DATABASE      = var.database_name
    AURORA_USER          = var.master_username
    OPENSEARCH_ENDPOINT  = module.opensearch.domain_endpoint
    AWS_REGION           = var.aws_region
    REDIS_ENDPOINT       = module.redis.primary_endpoint
  }

  # Secrets from Secrets Manager
  secrets = {
    AURORA_PASSWORD = module.aurora.master_password_secret_arn
  }
}

# Cognito Module
module "cognito" {
  source = "./modules/cognito"

  environment      = var.environment
  user_pool_name   = "chat2data-${var.environment}"
  app_client_name  = "chat2data-api-client"
}

# Outputs
output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "aurora_cluster_endpoint" {
  description = "Aurora cluster endpoint"
  value       = module.aurora.cluster_endpoint
}

output "aurora_reader_endpoint" {
  description = "Aurora reader endpoint"
  value       = module.aurora.reader_endpoint
}

output "opensearch_endpoint" {
  description = "OpenSearch domain endpoint"
  value       = module.opensearch.domain_endpoint
}

output "redis_endpoint" {
  description = "Redis primary endpoint"
  value       = module.redis.primary_endpoint
}

output "api_load_balancer_dns" {
  description = "API load balancer DNS name"
  value       = module.ecs.load_balancer_dns
}

output "cognito_user_pool_id" {
  description = "Cognito user pool ID"
  value       = module.cognito.user_pool_id
}

output "cognito_app_client_id" {
  description = "Cognito app client ID"
  value       = module.cognito.app_client_id
}
