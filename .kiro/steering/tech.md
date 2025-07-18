# Technology Stack

## Core Technologies

- **Python 3.10+**: Main implementation language
- **Model Context Protocol (MCP)**: Communication protocol with AI agents
- **FastMCP**: Python MCP server framework
- **Markdown + YAML**: Memory storage format with frontmatter metadata
- **Git**: Optional version control and synchronization

## Dependencies

- `mcp[cli]>=1.0.0`: Model Context Protocol library with CLI support
- Standard library modules: `uuid`, `datetime`, `pathlib`, `subprocess`, `threading`

## Package Management

- **uv**: Recommended Python package manager for development and deployment
- **pip**: Alternative package manager support
- **pyproject.toml**: Modern Python packaging configuration

## Common Commands

### Development Setup
```bash
# Using uv (recommended)
uv run --with "mcp[cli]" python aiaml_server.py

# Using pip
pip install -r requirements.txt
python aiaml_server.py

# Using the run script
./run_server.sh
```

### Testing with MCP Inspector
```bash
# Test MCP tools interactively
uv run --with "mcp[cli]" mcp dev aiaml_server.py
```

### Installation as Package
```bash
# Install in development mode
pip install -e .

# Run as installed package
aiaml
```

## Architecture Patterns

- **MCP Server Pattern**: Three-tool interface (`remember`, `think`, `recall`)
- **File-based Storage**: Individual markdown files with unique IDs
- **Background Processing**: Git sync operations in separate threads
- **Middleware Pattern**: Authentication wrapper for tool functions
- **Error Handling**: Structured error responses with categorization
- **Configuration**: Environment variable-based configuration with defaults

## Performance Considerations

- **Atomic File Operations**: Temporary files with rename for consistency
- **Lazy Loading**: Parse memory files only when needed during search
- **Search Limits**: Maximum 25 results to prevent performance issues
- **Background Sync**: Non-blocking Git operations
- **Graceful Degradation**: Continue operation despite individual file corruption