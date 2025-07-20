"""
AI Agnostic Memory Layer (AIAML) - A simple local memory system for AI agents.

This package provides persistent storage and retrieval of memories using markdown files
through the Model Context Protocol (MCP).
"""

__version__ = "1.0.0"
__author__ = "AIAML Team"
__description__ = "AI Agnostic Memory Layer - Local memory system for AI agents"

# Conditionally import server main function (requires MCP dependencies)
try:
    from .server import main
    _server_available = True
except ImportError:
    _server_available = False
    def main():
        raise ImportError("MCP dependencies not available. Install with: pip install 'mcp[cli]>=1.0.0'")

__all__ = ["main"]