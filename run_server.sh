#!/bin/bash

# AIAML Local-Only MCP Server Launcher
# This script starts the AIAML server with stdio transport for local connections only.
# Network connections are not supported in this version.

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Change to the script directory
cd "$SCRIPT_DIR"

# Use uv to run the server with dependencies (stdio transport only)
exec uv run --with-requirements requirements.txt python aiaml_server.py