# Resource URIs

This document describes the URI schemes used by the IaC Memory MCP Server for accessing Infrastructure as Code (IaC) components.

## Terraform Resources

### Provider URIs
```
terraform://{provider_name}/{version}
```

Example:
```
terraform://aws/4.0.0
```

### Resource URIs
```
terraform://{provider_name}/{resource_type}
```

Example:
```
terraform://aws/aws_instance
```

## Ansible Resources

### Collection URIs
```
ansible://{collection_name}/{version}
```

Example:
```
ansible://community.aws/3.0.0
```

### Module URIs
```
ansible://{collection_name}/{module_name}
```

Example:
```
ansible://community.aws/ec2_instance
```

## URI Components

- `provider_name`: Name of the Terraform provider (e.g., aws, google, azure)
- `version`: Semantic version of the provider/collection
- `resource_type`: Type of Terraform resource (e.g., aws_instance, aws_s3_bucket)
- `collection_name`: Name of the Ansible collection (e.g., community.aws)
- `module_name`: Name of the Ansible module (e.g., ec2_instance)

## Resource Content

All resources return JSON-formatted content containing:
- Component metadata
- Schema information
- Documentation links
- Version compatibility data
