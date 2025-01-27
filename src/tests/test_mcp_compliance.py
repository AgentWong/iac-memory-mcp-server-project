"""MCP protocol compliance tests.

This module verifies compliance with the Model Context Protocol specification:
- Resource URI schemes
- Tool schemas and formats  
- Error codes and messages
- Response formats
- Logging standards
"""

import pytest
from mcp.shared.exceptions import McpError
from mcp.types import METHOD_NOT_FOUND

from iac_memory_mcp_server.db.connection import DatabaseManager
from iac_memory_mcp_server.resources import handle_list_resources, handle_read_resource
from iac_memory_mcp_server.tools import handle_call_tool, handle_list_tools

from .test_utils.base_utils import capture_taskgroup_errors
from .test_utils.db_utils import db_test_context


@pytest.mark.asyncio
async def test_mcp_uri_compliance():
    """Test URI scheme compliance with MCP specification."""
    async with db_test_context(operation_name="uri_compliance") as ctx:
        async with capture_taskgroup_errors():
            await ctx.info("Starting URI compliance test")

            # Add test data
            db = DatabaseManager.get_instance()
            db.add_terraform_provider(
                "aws",
                "4.0.0",
                "https://github.com/hashicorp/terraform-provider-aws",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs",
            )
            db.add_terraform_resource(
                "aws",
                "instance",
                "aws_instance",
                '{"type": "object"}',
                "4.0.0",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/instance",
            )

            # Test resource URIs
            result = await handle_list_resources(ctx)

            # Verify result has resources attribute
            assert isinstance(result, list), "Result should be a list"

            # Filter out template URIs (those containing {variable} placeholders)
            concrete_resources = [
                r
                for r in result
                if "{" not in str(r.uri) and "}" not in str(r.uri)
            ]

            # Verify concrete resource URIs
            for resource in concrete_resources:
                uri = str(resource.uri)
                # Verify URI scheme
                assert uri.startswith(
                    (
                        "resources://terraform/",
                        "resources://ansible/",
                        "resources://entities/",
                    )
                ), f"Invalid URI scheme: {uri}"

                # Verify URI format
                uri_parts = uri.split("/")
                assert len(uri_parts) >= 4, f"Invalid URI format: {uri}"

                # Check provider name for terraform resources
                if "terraform" in uri_parts:
                    if "resources" in uri_parts or "providers" in uri_parts:
                        provider_idx = uri_parts.index("terraform") + 2
                        assert (
                            uri_parts[provider_idx] == "aws"
                        ), "Missing provider in URI"

            # Verify we found some concrete resources
            assert len(concrete_resources) > 0, "No concrete resources found"


@pytest.mark.asyncio
async def test_mcp_tool_compliance():
    """Test tool schema compliance with MCP specification."""
    async with db_test_context(operation_name="tool_compliance") as ctx:
        async with capture_taskgroup_errors():
            await ctx.info("Starting tool compliance test")

            tools = await handle_list_tools(ctx)
            for tool in tools:
                # Verify required attributes
                assert hasattr(tool, "name"), "Tool missing name"
                assert hasattr(tool, "description"), "Tool missing description"
                assert hasattr(tool, "inputSchema"), "Tool missing inputSchema"

                # Verify schema format
                schema = tool.inputSchema
                assert isinstance(schema, dict), "Invalid schema format"
                assert "type" in schema, "Schema missing type"
                assert schema["type"] == "object", "Invalid schema type"
                assert "properties" in schema, "Schema missing properties"

                # Verify property formats
                for prop_name, prop_schema in schema["properties"].items():
                    assert "type" in prop_schema, f"Property {prop_name} missing type"
                    assert (
                        "description" in prop_schema
                    ), f"Property {prop_name} missing description"


@pytest.mark.asyncio
async def test_mcp_error_compliance():
    """Test error code compliance with MCP specification."""
    async with db_test_context(operation_name="error_compliance") as ctx:
        async with capture_taskgroup_errors():
            await ctx.info("Starting error compliance test")

            # Test invalid URI
            with pytest.raises(McpError) as exc_info:
                await handle_read_resource("invalid://uri")
            assert (
                exc_info.value.error.code == METHOD_NOT_FOUND
            ), "Incorrect error code for invalid URI"

            # Test nonexistent tool
            result = await handle_call_tool("nonexistent_tool", {})
            assert isinstance(result, list), "Result should be a list"
            assert len(result) == 1, "Should have one error message"
            assert "Unknown tool" in result[0].text, "Error message should indicate unknown tool"

            # Test invalid arguments
            result = await handle_call_tool("add_terraform_provider", {})
            assert isinstance(result, list), "Result should be a list"
            assert len(result) == 1, "Should have one error message"
            assert "Missing required arguments" in result[0].text, "Error message should indicate missing arguments"


@pytest.mark.asyncio
async def test_mcp_logging_compliance():
    """Test logging compliance with MCP specification."""
    async with db_test_context(operation_name="logging_compliance") as ctx:
        async with capture_taskgroup_errors():
            await ctx.info("Starting logging compliance test")

            # Test log levels
            await ctx.debug("Debug test message")
            await ctx.info("Info test message")
            await ctx.warning("Warning test message")
            await ctx.error("Error test message")

            # Verify log message format
            for msg in ctx.info_messages:
                # Check timestamp format
                assert " - " in msg, "Missing timestamp separator"

                # Check log level, skipping tool error responses which use boolean flags
                if not msg.startswith("Tool error:"):
                    has_level = any(
                        level in msg
                        for level in ["DEBUG -", "INFO -", "WARNING -", "ERROR -"]
                    )
                    assert has_level, f"Missing log level in message: '{msg}'"

                # Check operation name
                assert "logging_compliance" in msg, "Missing operation name"
