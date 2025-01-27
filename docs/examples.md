# Usage Examples

This document provides examples of using the IaC Memory MCP Server through various clients.

## Adding Terraform Components

```python
# Add AWS provider
result = await handle_call_tool(
    "add_terraform_provider",
    {
        "name": "aws",
        "version": "4.0.0",
        "source_url": "https://github.com/hashicorp/terraform-provider-aws",
        "doc_url": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs"
    }
)

# Add EC2 instance resource
result = await handle_call_tool(
    "add_terraform_resource",
    {
        "provider_id": provider_id,
        "name": "instance",
        "resource_type": "aws_instance",
        "schema": '{"type": "object"}',
        "version": "4.0.0",
        "doc_url": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/instance"
    }
)
```

## Adding Ansible Components

```python
# Add AWS collection
result = await handle_call_tool(
    "add_ansible_collection",
    {
        "name": "community.aws",
        "version": "3.0.0",
        "source_url": "https://github.com/ansible-collections/community.aws",
        "doc_url": "https://docs.ansible.com/ansible/latest/collections/community/aws/"
    }
)

# Add EC2 instance module
result = await handle_call_tool(
    "add_ansible_module",
    {
        "collection_id": collection_id,
        "name": "ec2_instance",
        "module_type": "cloud",
        "schema": '{"type": "object"}',
        "version": "3.0.0",
        "doc_url": "https://docs.ansible.com/ansible/latest/collections/community/aws/ec2_instance_module.html"
    }
)
```

## Reading Resources

```python
# List available resources
resources = await handle_list_resources()

# Read specific resource
content = await handle_read_resource("terraform://aws/aws_instance")
```

## Error Handling

```python
try:
    result = await handle_call_tool("nonexistent_tool", {})
except McpError as e:
    print(f"Error {e.error.code}: {e.error.message}")
```
