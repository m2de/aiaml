# AI Agnostic Memory Layer (AIAML)

A simple local memory system for AI agents that provides persistent storage and retrieval using the Model Context Protocol (MCP).

## Quick Start

### MCP Client Setup (Claude Desktop, etc.)

**Minimal setup** (uses defaults):
```json
{
  "mcpServers": {
    "aiaml": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/m2de/aiaml.git", "aiaml"]
    }
  }
}
```

Add this to your MCP client configuration (e.g., Claude Desktop's `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "aiaml": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/m2de/aiaml.git", "aiaml"],
      "env": {
        "AIAML_MEMORY_DIR": "/path/to/your/aiaml-data",
        "AIAML_ENABLE_SYNC": "true",
        "AIAML_GITHUB_REMOTE": "git@github.com:yourusername/your-memory-repo.git",
        "AIAML_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

That's it! No installation required - `uvx` will automatically handle dependencies.

### Requirements

- Python 3.10+
- `uv` (install with `brew install uv` or `pip install uv`)

### Alternative Setup Methods

If you prefer a local installation:

```json
{
  "mcpServers": {
    "aiaml": {
      "command": "uv",
      "args": ["--directory", "/path/to/aiaml", "run", "aiaml"]
    }
  }
}
```

## Memory Tools

The server provides three MCP tools for AI agents:

- **`remember`** - Store new memories with metadata
- **`think`** - Search memories by keywords  
- **`recall`** - Retrieve full memory details by ID

### Memory Format

Memories are stored as markdown files:

```markdown
---
id: abc12345
timestamp: 2024-01-15T10:30:00.123456
agent: claude
user: marco
topics: [programming, python]
---

Memory content goes here.
```

## Configuration

### Environment Variables

All configuration is done through environment variables (either in MCP config or `.env` file):

| Variable | Default | Description |
|----------|---------|-------------|
| `AIAML_MEMORY_DIR` | `~/.aiaml` | Base directory for all AIAML data |
| `AIAML_ENABLE_SYNC` | `true` | Enable Git synchronization |
| `AIAML_GITHUB_REMOTE` | `none` | Git remote URL for sync (optional) |
| `AIAML_LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `AIAML_MAX_SEARCH_RESULTS` | `20` | Maximum search results returned |
| `AIAML_GIT_RETRY_ATTEMPTS` | `3` | Git operation retry attempts |
| `AIAML_GIT_RETRY_DELAY` | `1.0` | Delay between git retries (seconds) |

### Directory Structure

When you set `AIAML_MEMORY_DIR="/path/to/aiaml"`, the following structure is created:

```
/path/to/aiaml/
├── files/        # Memory files (*.md)
├── backups/      # Backup files
├── temp/         # Temporary files
├── locks/        # File locks
└── .git/         # Git repository (if sync enabled)
```

### Local `.env` File

If running locally, you can create a `.env` file:

```bash
AIAML_MEMORY_DIR="/path/to/your/aiaml-data"
AIAML_ENABLE_SYNC="true"
AIAML_GITHUB_REMOTE="git@github.com:yourusername/your-memory-repo.git"
AIAML_LOG_LEVEL="INFO"
```

## Testing

```bash
# Run all tests
python3 test.py

# Run individual tests
python3 test_core_functionality.py
python3 test_mcp_integration.py
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

Keep it simple - this project focuses on reliable local memory storage for AI agents.

## License

MIT License - see LICENSE file for details.