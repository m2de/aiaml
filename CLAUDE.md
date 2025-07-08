# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is AIAML (AI Agnostic Memory Layer) - a Model Context Protocol (MCP) server that provides persistent memory storage for AI agents. The system stores memories as markdown files with YAML frontmatter and provides three main tools: `remember`, `think`, and `recall`.

## Architecture

The project consists of a single Python file `aiaml_server.py` that implements an MCP server using FastMCP. Key components:

- **Memory Storage**: Markdown files in `memory/files/` directory with YAML frontmatter containing metadata
- **GitHub Backup**: Automatic background sync to separate GitHub repository after each memory creation
- **Search System**: Keyword-based search with relevance scoring that prioritizes topic matches over content matches
- **MCP Tools**: Three tools exposed via MCP protocol for storing, searching, and retrieving memories
- **File Format**: `YYYYMMDD_HHMMSS_[8-char-id].md` naming convention

## Common Development Commands

### Running the Server
```bash
# Preferred method using uv (handles dependencies automatically)
uv run --with "mcp[cli]" python aiaml_server.py

# Using the provided shell script
./run_server.sh

# Using virtual environment
source venv/bin/activate
python aiaml_server.py
```

### Testing with MCP Inspector
```bash
# Start MCP Inspector for interactive testing
uv run --with "mcp[cli]" mcp dev aiaml_server.py
```

### Development Setup
```bash
# Install dependencies with uv
uv sync

# Or with pip
pip install -r requirements.txt

# Or create virtual environment
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Memory File Structure

Memory files are stored in `memory/files/` and follow this format:
```markdown
---
id: abc12345
timestamp: 2024-01-15T10:30:00.123456
agent: claude
user: marco
topics: [programming, python, mcp]
---

Memory content goes here...
```

## GitHub Backup Configuration

The system automatically backs up memories to a separate GitHub repository:

### Environment Variables
- `AIAML_ENABLE_SYNC`: Enable/disable GitHub sync (default: "true")
- `AIAML_GITHUB_REMOTE`: GitHub repository URL for backup

### Setup
1. Create a GitHub repository for memory backup
2. Set the remote URL: `cd memory && git remote add origin <your-repo-url>`
3. Configure environment variables if needed
4. The system will automatically commit and push new memories

## Key Functions

- `remember()`: Store new memories with agent, user, topics, and content (triggers GitHub sync)
- `think()`: Search memories by keywords with relevance scoring
- `recall()`: Retrieve full memory details by ID
- `sync_to_github()`: Background sync of new memories to GitHub repository
- `parse_memory_file()`: Parse markdown files with YAML frontmatter
- `calculate_relevance_score()`: Score memories based on keyword matches

## Relevance Scoring Algorithm

The search system uses a weighted scoring approach:
- Topic matches: 2x weight
- Content matches: 1x weight
- User/agent matches: 1x weight
- Exact word matches: bonus points

Results are sorted by relevance score (descending) then timestamp (most recent first).

## Configuration for Claude Desktop

Add to Claude Desktop config:
```json
{
  "mcpServers": {
    "aiaml": {
      "command": "/path/to/aiaml/run_server.sh"
    }
  }
}
```

## Dependencies

- Python 3.10+
- `mcp[cli]>=1.0.0` (only dependency)
- `uv` package manager (recommended for development)

## File Locations

- Main server: `aiaml_server.py`
- Memory storage: `memory/` directory
- Run script: `run_server.sh`
- Dependencies: `requirements.txt`, `pyproject.toml`