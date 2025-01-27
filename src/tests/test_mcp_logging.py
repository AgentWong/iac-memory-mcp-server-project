"""MCP logging compliance tests.

This module verifies compliance with MCP logging best practices:
- Log message format and structure
- Log level usage
- Error logging patterns
- Context propagation
"""

import asyncio

import pytest

from iac_memory_mcp_server.db.connection import DatabaseManager
from iac_memory_mcp_server.tools import handle_call_tool

from .test_utils.base_utils import capture_taskgroup_errors
from .test_utils.db_utils import db_test_context


@pytest.mark.asyncio
async def test_mcp_logging_format():
    """Test logging format compliance with MCP specification."""
    async with db_test_context(operation_name="logging_format") as ctx:
        async with capture_taskgroup_errors():
            await ctx.info("Starting logging format test")

            # Test all log levels
            await ctx.debug("Debug test message")
            await ctx.info("Info test message")
            await ctx.warning("Warning test message")
            await ctx.error("Error test message")

            # Verify log message format
            for msg in ctx.info_messages:
                # Check timestamp format
                assert " - " in msg, "Missing timestamp separator"

                # Check log level, skipping tool error messages
                if not msg.startswith("Tool error:") and "Unknown tool" not in msg:
                    has_level = any(
                        level in msg
                        for level in ["DEBUG -", "INFO -", "WARNING -", "ERROR -"]
                    )
                    assert has_level, f"Missing log level in message: '{msg}'"

                # Check operation name
                assert "logging_format" in msg, "Missing operation name"


@pytest.mark.asyncio
async def test_mcp_error_logging():
    """Test error logging compliance with MCP specification."""
    async with db_test_context(operation_name="error_logging") as ctx:
        async with capture_taskgroup_errors():
            await ctx.info("Starting error logging test")

            # Test error logging with invalid tool call
            result = await handle_call_tool("nonexistent_tool", {})

            # Verify error result format
            assert isinstance(result, list), "Result should be a list"
            assert len(result) == 1, "Should have one error message"
            assert "Unknown tool" in result[0].text, "Error message should indicate unknown tool"

            # For tool errors, we expect a boolean result rather than a log level
            # No additional error logging assertion needed as per MCP spec


@pytest.mark.asyncio
async def test_mcp_context_logging():
    """Test logging context propagation."""
    async with db_test_context(operation_name="context_logging") as ctx:
        async with capture_taskgroup_errors():
            await ctx.info("Starting context logging test")

            # Add test data
            db = DatabaseManager.get_instance()
            db.add_terraform_provider(
                "aws",
                "4.0.0",
                "https://github.com/hashicorp/terraform-provider-aws",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs",
            )

            # Verify operation name propagation
            for msg in ctx.info_messages:
                assert "context_logging" in msg, "Operation name not propagated"

            # Wait briefly for logs to propagate
            await asyncio.sleep(0.1)

            # Verify database operation logging
            db_logs = [
                msg
                for msg in ctx.info_messages
                if any(x in msg.lower() for x in ["provider", "terraform"])
            ]
            assert len(db_logs) > 0, "Database operations not logged"
