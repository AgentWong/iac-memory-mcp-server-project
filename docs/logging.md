# Logging Configuration Guide

## Overview

The IaC Memory MCP Server uses structured JSON logging with stream separation:
- INFO and DEBUG logs go to stdout
- ERROR and above logs go to stderr

## Basic Usage

```python
from iac_memory_mcp_server.utils.logging import setup_logging

logger = setup_logging("my_component")
logger.info("Normal operation")  # Goes to stdout
logger.error("Something went wrong")  # Goes to stderr
```

## Log Context

Use LogContext to add correlation IDs and operation names:

```python
from iac_memory_mcp_server.utils.logging import LogContext

with LogContext(logger, correlation_id, "operation_name"):
    logger.info("This log will have correlation_id and operation fields")
```

## JSON Format

All logs are formatted as JSON with these fields:
- timestamp: ISO format UTC timestamp
- level: Log level (DEBUG, INFO, ERROR, etc)
- message: Log message
- logger: Logger name
- correlation_id: (optional) Request correlation ID
- operation: (optional) Operation name
- exception: (optional) Exception details if present

## Testing

The logging system includes comprehensive test utilities in `test_utils.log_utils`:

```python
from tests.test_utils.log_utils import create_test_streams, assert_log_routing

with captured_logs() as (stdout, stderr):
    logger = setup_logging("test_component")
    logger.info("Test message")
    assert_log_routing(stdout, stderr)
```

### Test Utilities
- `create_test_streams()`: Creates mock stdout/stderr streams
- `assert_log_routing()`: Verifies correct log level routing
- `verify_json_formatting()`: Validates JSON structure
- `find_logs_with_correlation_id()`: Filters logs by correlation ID

## Troubleshooting

Common issues:

1. Missing logs
   - Check the correct stream (stdout/stderr)
   - Verify log level configuration
   - Ensure handlers are properly initialized
   - Use test utilities to verify routing

2. Invalid JSON
   - Check for proper string formatting
   - Avoid raw newlines in messages
   - Use extra fields for structured data
   - Run verify_json_formatting() on test output

3. Performance Issues
   - Minimize expensive operations in log messages
   - Use appropriate log levels
   - Consider debug mode impacts
   - Profile logging in integration tests

4. Testing Issues
   - Use MockLogStream for stream capture
   - Reset streams between tests
   - Check both stdout and stderr
   - Verify correlation ID propagation
