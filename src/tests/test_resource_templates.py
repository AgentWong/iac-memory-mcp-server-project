"""Tests for resource template functionality.

This module verifies the resource template capabilities:
- Template URI listing
- Template variable extraction
- Template-based resource access
- Error handling
"""

import pytest
from mcp.shared.exceptions import McpError
from pydantic import AnyUrl

from iac_memory_mcp_server.resources import (
    RESOURCE_TEMPLATES,
    extract_template_variables,
    handle_list_resources,
    handle_read_resource,
)

from .test_utils.base_utils import capture_taskgroup_errors
from .test_utils.db_utils import db_test_context


@pytest.mark.asyncio
async def test_list_resource_templates():
    """Test that templates are included in resource listings."""
    async with db_test_context(operation_name="list_templates") as ctx:
        async with capture_taskgroup_errors():
            await ctx.info("Starting template listing test")

            # Get resource listing
            result = await handle_list_resources(ctx)

            # Verify result has resources attribute
            assert isinstance(result, list), "Result should be a list"

            # Verify templates are included
            found_templates = set()
            for resource in result:
                assert hasattr(resource, "uri"), "Resource should have uri attribute"
                resource_uri = str(resource.uri)
                for template in RESOURCE_TEMPLATES:
                    if template["uriTemplate"] == resource_uri:
                        found_templates.add(resource_uri)
                        break

            # Print diagnostic information
            missing_templates = (
                set(t["uriTemplate"] for t in RESOURCE_TEMPLATES) - found_templates
            )
            if missing_templates:
                print("Missing templates:")
                for uri in missing_templates:
                    print(f"  {uri}")
                print("Found URIs:")
                for uri in [str(r.uri) for r in result]:
                    print(f"  {uri}")

            assert len(found_templates) == len(
                RESOURCE_TEMPLATES
            ), f"Not all templates included in resource listing. Found {len(found_templates)} of {len(RESOURCE_TEMPLATES)}"

            # Verify template format for found templates
            for resource in result:
                assert hasattr(resource, "uri"), "Template missing URI"
                assert hasattr(resource, "name"), "Template missing name"
                assert hasattr(resource, "description"), "Template missing description"
                assert hasattr(resource, "mimeType"), "Template missing MIME type"


@pytest.mark.asyncio
async def test_template_variable_extraction():
    """Test template variable extraction functionality."""
    async with db_test_context(operation_name="template_variables") as ctx:
        async with capture_taskgroup_errors():
            await ctx.info("Testing template variable extraction")

            # Test valid template matches
            test_cases = [
                (
                    "resources://terraform/providers/aws",
                    "resources://terraform/providers/{provider_name}",
                    {"provider_name": "aws"},
                ),
                (
                    "resources://terraform/resources/aws/ec2_instance",
                    "resources://terraform/resources/{provider_name}/{resource_type}",
                    {"provider_name": "aws", "resource_type": "ec2_instance"},
                ),
                (
                    "resources://entities/123/relationships",
                    "resources://entities/{entity_id}/relationships",
                    {"entity_id": "123"},
                ),
            ]

            for uri, template, expected_vars in test_cases:
                variables = extract_template_variables(uri, template)
                assert (
                    variables == expected_vars
                ), f"Variable extraction failed for {uri}"

            # Test non-matching templates
            non_matching = [
                "resources://invalid/path",
                "resources://terraform/invalid",
                "resources://entities/123/invalid",
            ]

            for uri in non_matching:
                for template in (t["uriTemplate"] for t in RESOURCE_TEMPLATES):
                    variables = extract_template_variables(uri, template)
                    assert (
                        variables is None
                    ), f"Should not extract variables from non-matching URI: {uri}"


@pytest.mark.asyncio
async def test_template_resource_access(db):
    """Test accessing resources through templates."""
    async with db_test_context(operation_name="template_access") as ctx:
        async with capture_taskgroup_errors():
            await ctx.info("Starting template resource access test")

            # Add test data
            provider_id = db.add_terraform_provider(
                "aws",
                "4.0.0",
                "https://github.com/hashicorp/terraform-provider-aws",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs",
            )
            db.add_terraform_resource(
                provider_id,
                "instance",
                "aws_instance",
                '{"type": "object"}',
                "4.0.0",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/instance",
            )

            # Test provider template access
            provider_uri = AnyUrl("resources://terraform/providers/aws")
            provider_content = await handle_read_resource(provider_uri, ctx)
            assert "Provider: aws" in provider_content
            assert "Version: 4.0.0" in provider_content

            # Test resource template access
            resource_uri = AnyUrl("resources://terraform/resources/aws/aws_instance")
            resource_content = await handle_read_resource(resource_uri, ctx)
            assert "Resource: instance" in resource_content
            assert "Type: aws_instance" in resource_content


@pytest.mark.asyncio
async def test_template_error_handling():
    """Test error handling for template operations."""
    async with db_test_context(operation_name="template_errors") as ctx:
        async with capture_taskgroup_errors():
            await ctx.info("Testing template error handling")

            # Test invalid template URI format
            with pytest.raises(McpError) as exc_info:
                await handle_read_resource(AnyUrl("resources://invalid/path"))
            assert any(
                phrase in str(exc_info.value)
                for phrase in [
                    "Invalid resource path",
                    "Invalid resource path - unsupported resource type",
                    "Invalid resource path - must include type and category",
                ]
            ), f"Unexpected error message: {str(exc_info.value)}"

            # Test non-existent resource through template
            with pytest.raises(McpError) as exc_info:
                await handle_read_resource(
                    AnyUrl("resources://terraform/providers/nonexistent")
                )
            assert "Resource not found" in str(exc_info.value)

            # Test malformed template URI
            with pytest.raises(McpError) as exc_info:
                await handle_read_resource(
                    AnyUrl("resources://terraform/resources/missing_parts")
                )
            assert "Invalid" in str(exc_info.value)
