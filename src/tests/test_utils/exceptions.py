"""Exception types for test utilities.

This module defines the exception hierarchy used by the test utilities:

TestUtilError
├── DatabaseTestError - Database-specific errors
├── MCPTestError - MCP client-specific errors  
├── ContextError - Context management errors
└── TimeoutError - Timeout-related errors
"""


class TestUtilError(Exception):
    """Base exception for test utilities."""

    pass


class DatabaseTestError(TestUtilError):
    """Exception raised for database test-specific errors."""

    pass


class MCPTestError(TestUtilError):
    """Exception raised for MCP client test-specific errors."""

    pass


class ContextError(TestUtilError):
    """Exception raised for context-related errors."""

    pass


class TimeoutError(TestUtilError):
    """Exception raised for timeout-related errors."""

    pass
