"""
AI Agnostic Memory Layer (AIAML) - A simple local memory system for AI agents.

This package provides persistent storage and retrieval of memories using markdown files
through the Model Context Protocol (MCP).
"""

__version__ = "1.0.0"
__author__ = "AIAML Team"
__description__ = "AI Agnostic Memory Layer - Local memory system for AI agents"

from .server import main

__all__ = ["main"]