from typing import Optional


class IacMemoryError(Exception):
    """Base exception class for IaC Memory MCP Server."""

    def __init__(self, message: str, correlation_id: Optional[str] = None):
        super().__init__(message)
        self.correlation_id = correlation_id


class ProtocolError(IacMemoryError):
    """Raised when there are MCP protocol-related errors."""

    pass


class ResourceError(IacMemoryError):
    """Raised when there are resource-related errors."""

    pass


class ToolError(IacMemoryError):
    """Raised when there are tool execution errors."""

    pass


class DatabaseError(IacMemoryError):
    """Raised when there are database-related errors."""

    pass


class ValidationError(IacMemoryError):
    """Raised when validation fails."""

    pass
