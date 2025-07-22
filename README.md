# AI Agnostic Memory Layer (AIAML)

A simple local memory system for AI agents that provides persistent storage and retrieval using the Model Context Protocol (MCP).

## Quick Start

### Installation

```bash
# Clone and run
git clone <repository-url>
cd aiaml
./run_server.sh
```

### Requirements

- Python 3.10+
- `uv` package manager (install with `brew install uv`)

## Usage

The server provides three MCP tools for AI agents:

- **`remember`** - Store new memories with metadata
- **`think`** - Search memories by keywords  
- **`recall`** - Retrieve full memory details by ID

### MCP Client Configuration

Add to your MCP client config:

```json
{
  "mcpServers": {
    "aiaml": {
      "command": "/path/to/aiaml/run_server.sh"
    }
  }
}
```

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

Optional environment variables:

```bash
export AIAML_MEMORY_DIR="memory/files"    # Storage directory
export AIAML_ENABLE_SYNC="true"          # Git sync
export AIAML_GITHUB_REMOTE="git@github..." # Git remote
export AIAML_LOG_LEVEL="INFO"            # Logging level
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