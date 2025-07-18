#!/usr/bin/env python3
"""
AI Agnostic Memory Layer (AIAML) MCP Server

A simple local memory system for AI agents that provides persistent storage
and retrieval of memories using markdown files.

This is a compatibility wrapper that imports the main function from the
refactored aiaml package.
"""

from aiaml import main

if __name__ == "__main__":
    main()