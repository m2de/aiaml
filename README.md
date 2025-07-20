# AI Agnostic Memory Layer (AIAML)

A simple local memory system for AI agents that provides persistent storage and retrieval of memories using markdown files. This MCP (Model Context Protocol) server allows any AI agent to store, search, and retrieve memories across conversations.

## Features

- **Simple Memory Storage**: Store memories as markdown files with metadata
- **Keyword Search**: Find relevant memories by searching topics and content
- **Memory Retrieval**: Retrieve complete memory details by ID
- **Agent Agnostic**: Works with any AI agent (Claude, GPT, Gemini, etc.)
- **Local Storage**: All memories stored locally for privacy and control

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

This will start the MCP Inspector at `http://127.0.0.1:6274` where you can test the tools interactively.

### Connection Requirements

The MCP Inspector requires either:
- `uv` package manager (recommended) - install with `brew install uv`
- Or `mcp[cli]` package installed globally

## Remote Connections

AIAML supports both local and remote connections, allowing you to run the server on one machine and connect from remote AI agents or clients.

### Setting Up Remote Access

#### 1. Configure Environment Variables

Create a `.env` file in your project directory or set environment variables:

```bash
# Required for remote connections
export AIAML_API_KEY="your-secure-api-key-here"
export AIAML_HOST="0.0.0.0"  # Listen on all interfaces
export AIAML_PORT="8000"     # Default port

# Optional settings
export AIAML_LOG_LEVEL="INFO"
export AIAML_MEMORY_DIR="memory/files"
export AIAML_ENABLE_SYNC="true"
export AIAML_GITHUB_REMOTE="https://github.com/yourusername/your-memory-repo.git"
```

#### 2. Start Server for Remote Access

```bash
# Using environment variables
python3 aiaml_server.py

# Or set variables inline
AIAML_API_KEY="your-api-key" AIAML_HOST="0.0.0.0" python3 aiaml_server.py
```

The server will start and display connection information:
```
AI Agnostic Memory Layer (AIAML) MCP Server
Version: 1.0.0
============================================================
Remote connections: http://0.0.0.0:8000/sse
Local connections: also supported via stdio
Authentication: API key required for remote connections
Ready to accept MCP connections...
```

#### 3. Connect from Remote Clients

Remote clients can connect to your AIAML server using the SSE (Server-Sent Events) transport:

**Connection URL**: `http://your-server-ip:8000/sse`

**Authentication**: Include the API key in your client configuration.

### Security Considerations

- **API Key Required**: Remote connections require an API key for authentication
- **Network Security**: Consider using a VPN or secure network when exposing the server
- **Firewall**: Ensure port 8000 (or your chosen port) is accessible from client machines
- **HTTPS**: For production use, consider setting up a reverse proxy with SSL/TLS

### Example Remote Client Configuration

For MCP clients that support remote connections, use configuration similar to:

```json
{
  "mcpServers": {
    "aiaml-remote": {
      "transport": "sse",
      "url": "http://your-server-ip:8000/sse",
      "headers": {
        "Authorization": "Bearer your-api-key-here"
      }
    }
  }
}
```

### Testing Remote Connections

You can test remote connections using curl:

```bash
# Test server availability
curl -H "Authorization: Bearer your-api-key" \
     http://your-server-ip:8000/sse

# Test with MCP Inspector remotely
AIAML_API_KEY="your-api-key" \
uv run --with "mcp[cli]" mcp dev --transport sse \
http://your-server-ip:8000/sse
```

### Troubleshooting Remote Connections

**Connection Refused**:
- Check if server is running with correct host/port
- Verify firewall settings allow connections on the port
- Ensure `AIAML_HOST` is set to `0.0.0.0` not `127.0.0.1`

**Authentication Errors**:
- Verify `AIAML_API_KEY` is set on the server
- Check client is sending correct API key
- Ensure API key is at least 8 characters long

**Network Issues**:
- Test basic connectivity with `ping` or `telnet`
- Check if any proxy or VPN is interfering
- Verify DNS resolution if using hostnames

## Project Structure

```
aiaml/
├── aiaml_server.py           # Main MCP server implementation
├── requirements.txt          # Python dependencies
├── README.md                # This documentation
├── pyproject.toml           # Package configuration
└── memory/                  # Memory storage directory
    └── *.md                 # Individual memory files
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

- All memories are stored locally on your machine
- No external network connections are made
- Memory files are stored as plain text markdown for transparency
- Users have full control over their memory data

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