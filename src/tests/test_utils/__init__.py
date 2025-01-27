"""Test utilities for database and MCP client testing.

This package provides utilities for two distinct testing approaches:
1. Direct database testing without MCP overhead
2. Full integration testing through MCP client protocol

Key components:
- Base utilities shared between both approaches
- Database-specific testing utilities
- MCP client testing utilities
- Common exception types
"""

from .base_utils import BaseTestContext, capture_taskgroup_errors
from .db_utils import DbTestContext, db_test_context
from .exceptions import (
    ContextError,
    DatabaseTestError,
    MCPTestError,
    TestUtilError,
    TimeoutError,
)
from .mcp_utils import create_server_params

__all__ = [
    "BaseTestContext",
    "capture_taskgroup_errors",
    "DbTestContext",
    "DbTestSession",
    "db_test_context",
    "create_server_params",
    "TestUtilError",
    "DatabaseTestError",
    "MCPTestError",
    "ContextError",
    "TimeoutError",
]
