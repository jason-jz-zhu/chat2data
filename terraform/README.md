# Chat2Data AWS Infrastructure - Terraform

This directory contains Terraform configurations for deploying Chat2Data infrastructure on AWS.

## Architecture Components

- **VPC**: Virtual Private Cloud with public and private subnets across multiple AZs
- **Aurora PostgreSQL**: Managed relational database for marketing data
- **OpenSearch**: Vector database with k-NN for semantic search
- **ElastiCache Redis**: In-memory cache for query results
- **ECS Fargate**: Container orchestration for Chat2Data API
- **Cognito**: User authentication and authorization
- **Application Load Balancer**: Load balancing and SSL termination
- **Secrets Manager**: Secure storage for database credentials

## Prerequisites

1. **AWS CLI** configured with appropriate credentials
   ```bash
   aws configure
   ```

2. **Terraform** installed (>= 1.0)
   ```bash
   # macOS
   brew install terraform

   # Or download from https://www.terraform.io/downloads
   ```

3. **S3 bucket** for Terraform state (recommended for production)
   ```bash
   aws s3 mb s3://chat2data-terraform-state-<your-account-id>
   ```

## Quick Start

### 1. Configure Variables

```bash
# Copy example variables file
cp terraform.tfvars.example terraform.tfvars

# Edit terraform.tfvars with your values
vi terraform.tfvars
```

### 2. Initialize Terraform

```bash
terraform init
```

### 3. Review Plan

```bash
terraform plan
```

### 4. Apply Configuration

```bash
# Development environment
terraform apply -var="environment=dev"

# Production environment
terraform apply -var="environment=prod"
```

## Module Structure

```
terraform/
├── main.tf                 # Main configuration
├── variables.tf            # Variable definitions
├── outputs.tf             # Output definitions
├── terraform.tfvars.example # Example variables
├── modules/
│   ├── vpc/               # VPC and networking
│   ├── aurora/            # Aurora PostgreSQL cluster
│   ├── opensearch/        # OpenSearch domain
│   ├── redis/             # ElastiCache Redis
│   ├── ecs/               # ECS Fargate service
│   └── cognito/           # Cognito user pools
└── environments/
    ├── dev/               # Development environment
    ├── staging/           # Staging environment
    └── prod/              # Production environment
```

## Environments

### Development
- Minimal resources for cost optimization
- Single-AZ deployments where possible
- Smaller instance types

```bash
terraform workspace select dev
terraform apply -var-file="environments/dev/terraform.tfvars"
```

### Staging
- Production-like configuration
- Multi-AZ for testing HA scenarios
- Medium instance types

```bash
terraform workspace select staging
terraform apply -var-file="environments/staging/terraform.tfvars"
```

### Production
- Full redundancy and high availability
- Multi-AZ deployments
- Production-grade instance types
- Extended backup retention

```bash
terraform workspace select prod
terraform apply -var-file="environments/prod/terraform.tfvars"
```

## Cost Estimation

### Development (~$200/month)
- Aurora: db.t3.medium (1 instance) - ~$65
- OpenSearch: t3.small.search (1 node) - ~$40
- Redis: cache.t3.micro (1 node) - ~$15
- ECS Fargate: 1 task (1 vCPU, 2GB) - ~$30
- NAT Gateway: ~$35
- Data Transfer: ~$15

### Production (~$2,200/month)
- Aurora: db.r6g.large (2 instances) - ~$430
- OpenSearch: r6g.large.search (3 nodes) - ~$520
- Redis: cache.r6g.large (2 nodes) - ~$190
- ECS Fargate: 2 tasks (2 vCPU, 4GB each) - ~$175
- Application Load Balancer: ~$25
- NAT Gateway: ~$70
- CloudWatch & Logs: ~$45
- Bedrock (API calls): ~$650
- Data Transfer: ~$95

## Security Considerations

1. **Network Isolation**: All data services in private subnets
2. **Encryption**: At-rest and in-transit encryption enabled
3. **Secrets Management**: Database credentials in AWS Secrets Manager
4. **IAM Roles**: Least-privilege access for ECS tasks
5. **Security Groups**: Strict ingress/egress rules
6. **Multi-tenant Isolation**: Row-level security in PostgreSQL

## Deployment Steps

### Initial Deployment

1. Create Terraform state bucket (one-time)
   ```bash
   aws s3 mb s3://chat2data-terraform-state
   aws s3api put-bucket-versioning \
     --bucket chat2data-terraform-state \
     --versioning-configuration Status=Enabled
   ```

2. Initialize Terraform with remote state
   ```bash
   terraform init -backend-config="bucket=chat2data-terraform-state"
   ```

3. Create workspace
   ```bash
   terraform workspace new dev
   ```

4. Apply configuration
   ```bash
   terraform apply
   ```

### Updating Infrastructure

```bash
# Review changes
terraform plan

# Apply changes
terraform apply

# Destroy (be careful!)
terraform destroy
```

## Troubleshooting

### Common Issues

**Issue**: Terraform state lock
```bash
# Force unlock (use carefully)
terraform force-unlock <lock-id>
```

**Issue**: Resource already exists
```bash
# Import existing resource
terraform import module.vpc.aws_vpc.main vpc-xxxxx
```

**Issue**: Insufficient permissions
- Ensure your AWS credentials have appropriate IAM permissions
- Required permissions: EC2, RDS, OpenSearch, ECS, ElastiCache, Cognito, Secrets Manager

## Maintenance

### Backup Strategy
- Aurora: Automated daily backups (30-day retention in prod)
- OpenSearch: Daily snapshots to S3
- Terraform State: Versioned S3 bucket

### Monitoring
- CloudWatch Alarms for all critical resources
- SNS notifications for alerts
- X-Ray tracing for API requests

### Updates
- Apply Terraform changes during maintenance windows
- Test in dev/staging before production
- Use `terraform plan` to review changes

## Additional Resources

- [AWS Well-Architected Framework](https://aws.amazon.com/architecture/well-architected/)
- [Terraform AWS Provider Documentation](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [Chat2Data Documentation](../AWS_INTEGRATION_ARCHITECTURE.md)

## Support

For questions or issues:
- GitHub Issues: [link-to-repo]
- Internal Wiki: [link-to-wiki]
- DevOps Team: devops@company.com
