# Available Tools

This document describes the tools provided by the IaC Memory MCP Server for managing Infrastructure as Code (IaC) components.

## Terraform Tools

### add_terraform_provider
Adds a new Terraform provider to the database.

**Arguments:**
```json
{
  "name": "string",
  "version": "string",
  "source_url": "string",
  "doc_url": "string"
}
```

### add_terraform_resource
Adds a new Terraform resource definition.

**Arguments:**
```json
{
  "provider_id": "string",
  "name": "string",
  "resource_type": "string",
  "schema": "string",
  "version": "string",
  "doc_url": "string"
}
```

## Ansible Tools

### add_ansible_collection
Adds a new Ansible collection.

**Arguments:**
```json
{
  "name": "string",
  "version": "string",
  "source_url": "string",
  "doc_url": "string"
}
```

### add_ansible_module
Adds a new Ansible module definition.

**Arguments:**
```json
{
  "collection_id": "string",
  "name": "string",
  "module_type": "string",
  "schema": "string",
  "version": "string",
  "doc_url": "string"
}
```

## Error Handling

All tools follow standard MCP error handling:
- Invalid arguments return INVALID_REQUEST (code -32602)
- Missing resources return METHOD_NOT_FOUND (code -32601)
- Database errors return INTERNAL_ERROR (code -32603)

## Logging

Tools log operations using MCP logging standards:
- Operation start/completion
- Error conditions
- Resource updates
