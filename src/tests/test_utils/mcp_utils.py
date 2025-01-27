# mcp_utils.py
import sys
from typing import Dict, Optional

from mcp.client.stdio import StdioServerParameters


def create_server_params(
    operation_name: str = "test",
    env: Optional[Dict[str, str]] = None,
) -> StdioServerParameters:
    """Create server parameters for MCP test session."""
    base_env = {
        "PYTHONPATH": "src",
        "PYTHONUNBUFFERED": "1",
        "MCP_DEBUG": "1",
    }
    if env:
        base_env.update(env)

    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "iac_memory_mcp_server", "--debug"],
        env=base_env,
    )
