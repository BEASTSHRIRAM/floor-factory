"""MCP manager: the factory's only door to its target systems.

Exposes ToolClient (client.py), which talks to the targets' MCP server
files (targets/*/mcp_server.py — stand-ins for Synapse-generated
`synapse_auto_server.py` output) over stdio with the official `mcp`
client, falling back to a direct execution of the same allowlisted
tool definitions if the stdio handshake fails. See client.py's
docstring for the honest details.
"""
from .client import SERVERS, TOOL_SPECS, ToolClient

__all__ = ["ToolClient", "TOOL_SPECS", "SERVERS"]
