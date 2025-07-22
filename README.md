# AI Agnostic Memory Layer (AIAML)

A simple local-only memory system for AI agents that provides persistent storage and retrieval of memories using markdown files. This MCP (Model Context Protocol) server allows any AI agent to store, search, and retrieve memories across conversations using stdio transport for secure local connections.

## Features

- **Local-Only Operation**: Secure stdio transport with no network exposure
- **Simple Memory Storage**: Store memories as markdown files with metadata
- **Keyword Search**: Find relevant memories by searching topics and content
- **Memory Retrieval**: Retrieve complete memory details by ID
- **Agent Agnostic**: Works with any AI agent (Claude, GPT, Gemini, etc.)
- **Local Storage**: All memories stored locally for privacy and control
- **Simplified Configuration**: No network settings required

## Installation

### Option 1: Using uv (Recommended)

```bash
# Install uv if you haven't already
brew install uv  # On macOS
# or curl -LsSf https://astral.sh/uv/install.sh | sh

# Run the server directly (uv handles dependencies)
uv run --with "mcp[cli]" mcp run aiaml_server.py
```

### Option 2: Using pip

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
python3 aiaml_server.py
```

### Option 3: Using virtual environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python3 aiaml_server.py
```

## Usage

### Running the Server

```bash
python3 aiaml_server.py
```

### MCP Tools

The server provides three tools that can be used by any MCP-compatible AI client:

#### 1. `remember`
Store a new memory entry.

**Parameters:**
- `agent` (string): The AI agent name (e.g., "claude", "gemini", "chatgpt")
- `user` (string): The user identifier (e.g., "marco", "unknown")
- `topics` (array of strings): Keywords/domains for categorizing the memory
- `content` (string): The full content to remember

**Returns:**
- `memory_id` (string): Unique identifier for the stored memory
- `message` (string): Success or error message

**Example:**
```json
{
  "agent": "claude",
  "user": "marco",
  "topics": ["programming", "python", "mcp"],
  "content": "User prefers Python for backend development and has experience with Flask and FastAPI frameworks."
}
```

#### 2. `think`
Search for relevant memories by keywords.

**Parameters:**
- `keywords` (array of strings): Keywords to search for in memory topics and content

**Returns:**
- Array of matching memories, each containing:
  - `id` (string): Memory ID
  - `timestamp` (string): When the memory was created

**Example:**
```json
{
  "keywords": ["python", "programming"]
}
```

#### 3. `recall`
Retrieve full memory details by ID.

**Parameters:**
- `memory_ids` (array of strings): Memory IDs to retrieve

**Returns:**
- Array of complete memory objects with:
  - `id` (string): Memory ID
  - `timestamp` (string): Creation timestamp
  - `agent` (string): Agent that created the memory
  - `user` (string): User associated with the memory
  - `topics` (array of strings): Memory topics
  - `content` (string): Full memory content

**Example:**
```json
{
  "memory_ids": ["abc12345", "def67890"]
}
```

## Memory Storage Format

Memories are stored as markdown files in the `memory/` directory with the following format:

### File Naming Convention
```
YYYYMMDD_HHMMSS_[8-char-id].md
```

### File Structure
```markdown
---
id: abc12345
timestamp: 2024-01-15T10:30:00.123456
agent: claude
user: marco
topics: [programming, python, mcp]
---

User prefers Python for backend development and has experience with Flask and FastAPI frameworks.
```

## Integration with MCP Clients

### Claude Desktop Configuration

Add the following to your Claude Desktop configuration:

#### Option 1: Using the run script (Recommended)
```json
{
  "mcpServers": {
    "aiaml": {
      "command": "/Users/marcomark/Code/Personal/aiaml/run_server.sh"
    }
  }
}
```

#### Option 2: Using uv directly
```json
{
  "mcpServers": {
    "aiaml": {
      "command": "uv",
      "args": ["run", "--with", "mcp[cli]", "python", "aiaml_server.py"],
      "cwd": "/Users/marcomark/Code/Personal/aiaml"
    }
  }
}
```

#### Option 3: Using python3 with virtual environment
```json
{
  "mcpServers": {
    "aiaml": {
      "command": "/Users/marcomark/Code/Personal/aiaml/venv/bin/python",
      "args": ["/Users/marcomark/Code/Personal/aiaml/aiaml_server.py"]
    }
  }
}
```

**Note**: Replace `/Users/marcomark/Code/Personal/aiaml` with your actual project path.

### Testing with MCP Inspector

```bash
# Using uv (recommended)
uv run --with "mcp[cli]" mcp dev aiaml_server.py

# Or if you have mcp installed
mcp dev aiaml_server.py
```

This will start the MCP Inspector at `http://127.0.0.1:6274` where you can test the tools interactively using stdio transport.

### Connection Requirements

The MCP Inspector requires either:
- `uv` package manager (recommended) - install with `brew install uv`
- Or `mcp[cli]` package installed globally

**Note**: The server only supports stdio transport for local connections. Remote connections are not supported.

## Configuration

AIAML uses environment variables for configuration. All network-related settings have been removed for security and simplicity.

### Available Environment Variables

```bash
# Optional settings
export AIAML_LOG_LEVEL="INFO"                    # Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
export AIAML_MEMORY_DIR="memory/files"           # Memory storage directory
export AIAML_ENABLE_SYNC="true"                  # Enable Git synchronization
export AIAML_GITHUB_REMOTE="https://github.com/yourusername/your-memory-repo.git"  # Git remote URL
export AIAML_MAX_SEARCH_RESULTS="25"             # Maximum search results returned
```

### Removed Network Settings

The following environment variables are **no longer supported** and will be ignored:
- `AIAML_API_KEY` - Authentication removed for local-only operation
- `AIAML_HOST` - Network hosting removed
- `AIAML_PORT` - Network port configuration removed

If these variables are set, the server will log a message that they are being ignored and continue with local-only operation.

## Project Structure

```
aiaml/
├── aiaml_server.py           # Main entry point (compatibility wrapper)
├── aiaml/                    # Main package directory
│   ├── server.py            # MCP server implementation (stdio only)
│   ├── config.py            # Configuration management (network settings removed)
│   ├── memory/              # Memory operations modules
│   └── ...                  # Other core modules
├── requirements.txt          # Python dependencies
├── run_server.sh            # Execution script using uv
├── README.md                # This documentation
├── pyproject.toml           # Package configuration
└── memory/                  # Memory storage directory
    └── files/               # Individual memory markdown files
```

## Requirements

- Python 3.8+
- MCP Python SDK

## Error Handling

The server includes comprehensive error handling:

- Invalid memory IDs return appropriate error messages
- File system errors are caught and reported
- Malformed memory files are skipped during search
- Search failures return empty results with error information

## Security and Privacy

- **Local-Only Operation**: Server only accepts stdio connections, no network exposure
- **No Authentication Required**: Simplified security model for local use
- **All memories stored locally**: Complete data control on your machine
- **No external network connections**: Except optional Git synchronization
- **Transparent storage**: Memory files stored as plain text markdown
- **Full user control**: Direct access to all memory data

## Troubleshooting

### Common Issues

**Server won't start**:
- Ensure Python 3.10+ is installed
- Install MCP dependencies: `pip install 'mcp[cli]>=1.0.0'`
- Check memory directory permissions

**MCP client can't connect**:
- Verify the server is running with stdio transport
- Check that your MCP client configuration uses the correct path
- Ensure no network transport settings are configured

**Memory operations fail**:
- Check memory directory exists and is writable
- Verify sufficient disk space
- Review logs for specific error messages

**Git sync issues**:
- Ensure Git is installed and accessible
- Verify Git remote URL is correct
- Check network connectivity for Git operations

### Migration from Network Version

If you previously used a network-enabled version of AIAML:
- Remove any `AIAML_API_KEY`, `AIAML_HOST`, or `AIAML_PORT` environment variables
- Update MCP client configurations to remove network transport settings
- Existing memory files remain fully compatible

## Testing

The project includes a comprehensive test suite to ensure reliability and maintainability:

### Quick Testing (No Dependencies)
```bash
# Validate code structure and core functionality
python3 test_module_structure.py
python3 test_cross_platform.py
```

### Full Test Suite (Requires MCP)
```bash
# Run all tests
python3 run_tests.py

# Or run individual tests
uv run --with "mcp[cli]" python3 test_optimized_search.py
```

### Testing Documentation
- **[TESTING_GUIDE.md](TESTING_GUIDE.md)** - Comprehensive testing methodology
- **[TESTING_PATTERNS.md](TESTING_PATTERNS.md)** - Ready-to-use code patterns
- **[TESTING_SUMMARY.md](TESTING_SUMMARY.md)** - Documentation overview

## Contributing

This is a simple, focused implementation designed for reliability and ease of use. Contributions should maintain these principles while adding value for AI agent memory management.

### Development Standards
- **File Size Limit**: Maximum 500 lines per Python file
- **Testing Required**: All changes must include appropriate tests
- **Follow Patterns**: Use established testing patterns and code structure
- **Documentation**: Update relevant documentation for significant changes

See the testing documentation above for detailed guidelines and patterns.

## License

This project is provided as-is for educational and practical use in AI agent memory systems.