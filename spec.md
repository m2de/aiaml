# AI Agnostic Memory Layer (AIAML) - Product Specification

## Overview

The AI Agnostic Memory Layer (AIAML) is a persistent memory system designed to enable AI agents to store, search, and retrieve contextual information across multiple conversations and sessions. The system operates as a universal memory service that can be used by any AI agent regardless of their underlying architecture or platform.

## Core Purpose

AIAML solves the fundamental problem of AI agents having no persistent memory between conversations. Without this capability, AI agents must rediscover user preferences, context, and previously established knowledge in every new interaction. AIAML provides a standardized way for AI agents to maintain continuity and build upon previous interactions.

## System Architecture

### MCP Server Interface
AIAML operates as a Model Context Protocol (MCP) server providing exactly three tools that AI agents can use:

1. **`remember`** - Store new memories with structured metadata
2. **`think`** - Search for relevant memories using keywords
3. **`recall`** - Retrieve complete memory details by ID

### Memory Storage Format
Memories are stored as individual markdown files with YAML frontmatter containing metadata and markdown content containing the actual memory text.

**File Naming Convention:**
```
YYYYMMDD_HHMMSS_[8-character-id].md
```

**File Structure:**
```markdown
---
id: [8-character-id]
timestamp: [ISO-8601-timestamp]
agent: [agent-name]
user: [user-identifier]
topics: [keyword1, keyword2, keyword3]
---

[Memory content as markdown text]
```

## Tool Specifications

### Tool 1: `remember`
Stores a new memory entry in the system.

**Purpose:** Allow AI agents to persistently store information about users, conversations, decisions, or any contextual information for future reference.

**Parameters:**
- `agent` (string, required): The AI agent name creating the memory (e.g., "claude", "gemini", "chatgpt")
- `user` (string, required): The user identifier associated with this memory (e.g., "marco", "john_doe", "unknown")
- `topics` (array of strings, required): Keywords for categorizing the memory. Each keyword should be a single word (e.g., ["programming", "python", "preferences"], not ["programming languages"] or ["user_preferences"])
- `content` (string, required): The full content to remember as markdown text

**Behavior:**
1. Generates unique 8-character memory ID
2. Creates ISO 8601 timestamp
3. Writes memory file with YAML frontmatter and content
4. Optionally triggers background Git synchronization (if enabled)
5. Returns success response with memory ID

**Returns:**
```json
{
  "memory_id": "abc12345",
  "message": "Memory stored successfully with ID: abc12345"
}
```

**Error Handling:**
If storage fails, returns:
```json
{
  "memory_id": "",
  "message": "Error storing memory: [error description]"
}
```

**Note:** Git synchronization errors do not affect the success of memory storage operations.

**Usage Guidelines for AI Agents:**
- Use `remember` to store user preferences, project details, decisions, or any information that should persist across conversations
- Choose descriptive, single-word topics that will help with future searches
- Include enough context in the content so the memory is useful when retrieved later
- Store specific, actionable information rather than vague summaries

### Tool 2: `think`
Searches for relevant memories using keyword matching across topics and content.

**Purpose:** Allow AI agents to discover previously stored memories that are relevant to the current conversation or task.

**Parameters:**
- `keywords` (array of strings, required): Keywords to search for in memory topics and content. Use specific terms that are likely to appear in relevant memories.

**Returns:**
Array of matching memories (maximum 25 results), sorted by relevance score (highest first):
```json
[
  {
    "id": "abc12345",
    "timestamp": "2024-01-15T10:30:00.123456",
    "relevance_score": 8,
    "matching_keywords": ["python", "programming"]
  },
  {
    "id": "def67890",
    "timestamp": "2024-01-14T15:45:00.789012", 
    "relevance_score": 5,
    "matching_keywords": ["python"]
  }
]
```

**Relevance Scoring Algorithm:**
- Topic matches are weighted 2x higher than content matches
- Exact word boundary matches receive bonus points
- Score = (topic_matches × 2) + content_matches + user_matches + agent_matches + exact_word_bonus
- Results sorted by relevance score (descending), then by timestamp (most recent first) as tiebreaker

**Error Handling:**
If search fails, returns:
```json
[{"error": "Search failed: [error description]"}]
```

**Usage Guidelines for AI Agents:**
- Use `think` before attempting to recall specific memories or when looking for relevant context
- Use specific keywords that are likely to appear in memory topics or content
- Try multiple related keywords to cast a wider search net
- The relevance scoring helps prioritize the most relevant memories first

### Tool 3: `recall`
Retrieves complete memory details by memory ID.

**Purpose:** Allow AI agents to access the full content and metadata of specific memories identified through search.

**Parameters:**
- `memory_ids` (array of strings, required): List of memory IDs to retrieve (obtained from `think` results)

**Returns:**
Array of complete memory objects:
```json
[
  {
    "id": "abc12345",
    "timestamp": "2024-01-15T10:30:00.123456",
    "agent": "claude",
    "user": "marco",
    "topics": ["programming", "python", "preferences"],
    "content": "User prefers Python for backend development and has experience with Flask and FastAPI frameworks. Prefers type hints and comprehensive docstrings in code."
  }
]
```

**Error Handling:**
If a memory ID is not found:
```json
[
  {
    "id": "invalid123",
    "error": "Memory with ID invalid123 not found"
  }
]
```

If recall fails entirely:
```json
[{"error": "Recall failed: [error description]"}]
```

**Usage Guidelines for AI Agents:**
- Always use `think` first to discover memory IDs before using `recall`
- Can retrieve multiple memories in a single call for efficiency
- Focus only on relevant information from recalled memories - don't mention irrelevant details to users
- Use recalled information to provide more personalized and contextually aware responses

## User Stories

### Human User Stories

#### Memory Persistence
**As a human user, I want the AI to remember personal information about me** so that I don't have to repeat my preferences, background, and context in every conversation.

- **Example**: "I work at a tech startup in San Francisco, prefer vegetarian food, and have a dog named Max"
- **Expectation**: AI automatically incorporates this context into future conversations without me having to re-explain

#### Contextual Recommendations  
**As a human user, I want the AI to use my stored preferences when making recommendations** so that suggestions are personalized and relevant to my situation.

- **Example**: When I ask "Where should I have dinner tonight?", the AI knows I'm in San Francisco, prefer vegetarian food, and can suggest appropriate restaurants
- **Expectation**: Recommendations are immediately relevant without requiring me to specify location, dietary preferences, or other known context

#### Project Continuity
**As a human user, I want the AI to remember ongoing projects and their details** so that I can continue conversations about work or personal projects seamlessly across multiple sessions.

- **Example**: "I'm renovating my kitchen with a $15,000 budget, prefer modern farmhouse style, and am currently waiting for cabinet installation"
- **Expectation**: AI tracks project progress, remembers constraints, and provides relevant advice in subsequent conversations

#### Learning Progression
**As a human user, I want the AI to track my learning progress and knowledge gaps** so that tutoring and educational assistance builds upon previous sessions.

- **Example**: "I've mastered Python basics but struggle with object-oriented concepts and respond well to visual analogies"
- **Expectation**: AI continues education from where we left off, using effective teaching methods for my learning style

#### Simple Setup
**As a human user, I want to install and configure the memory system with minimal effort** so that I can start benefiting from persistent memory immediately.

- **Example**: Run one command and have the memory system working with my AI assistant
- **Expectation**: No complex configuration, works out-of-the-box, clear documentation for any optional features

#### Privacy Control
**As a human user, I want my memories stored locally on my device** so that I maintain complete control over my personal information and conversation history.

- **Example**: All memory files are stored on my computer, not sent to external services
- **Expectation**: Full transparency about what's stored, where it's stored, and ability to examine or delete memories

### AI Agent User Stories

#### Tool Discovery
**As an AI agent, I want clear documentation about available memory tools** so that I understand what capabilities are available to enhance user interactions.

- **Need**: Understand that I have three tools: `remember`, `think`, and `recall`
- **Expectation**: Clear descriptions of when and how to use each tool without human explanation

#### Memory Storage Guidance
**As an AI agent, I want to know what information is worth storing** so that I create useful memories that enhance future conversations.

- **Need**: Guidelines for storing user preferences, project details, learning progress, and contextual information
- **Expectation**: Understand how to choose appropriate topics and write useful content that will help in future interactions

#### Memory Discovery
**As an AI agent, I want to efficiently find relevant stored memories** so that I can incorporate appropriate context into my responses.

- **Need**: Know how to search for memories using keywords that will return relevant results
- **Expectation**: Understand the search algorithm and how to craft effective keyword queries

#### Context Integration
**As an AI agent, I want to seamlessly incorporate recalled memories into conversations** so that responses are personalized and contextually aware.

- **Need**: Guidance on when to recall memories and how to use the information naturally
- **Expectation**: Provide personalized responses without explicitly mentioning that I'm using stored memories unless relevant

#### Error Handling
**As an AI agent, I want to gracefully handle memory system errors** so that conversation flow isn't disrupted when memory operations fail.

- **Need**: Understand how to continue providing helpful responses even if memory storage or retrieval fails
- **Expectation**: Memory failures don't break my ability to assist the user

#### Multi-Agent Collaboration
**As an AI agent, I want to access memories created by other AI agents** so that I can provide consistent assistance across different specialized tools.

- **Need**: Ability to discover and use memories created by coding assistants, writing helpers, or other specialized agents
- **Expectation**: Seamless collaboration where context is shared appropriately between different AI tools

#### Privacy Awareness
**As an AI agent, I want to understand privacy implications of memory storage** so that I handle sensitive information appropriately.

- **Need**: Know that memories are stored locally and understand user privacy expectations
- **Expectation**: Be thoughtful about what information to store and how to use recalled information respectfully

## Workflow Examples

### Example 1: Personal Preference Management
**Situation:** User mentions they prefer detailed project breakdowns in their work style.

**AI Agent Workflow:**
1. **Store Preference:** `remember(agent="claude", user="john_doe", topics=["preferences", "work", "style"], content="User prefers detailed project breakdowns and likes to review progress weekly. Prefers structured task lists over general descriptions.")`
2. **Later Session - Search:** `think(keywords=["preferences", "work"])`
3. **Retrieve Details:** `recall(memory_ids=["abc12345"])`
4. **Apply Knowledge:** AI automatically provides detailed breakdowns without user having to re-explain preferences

### Example 2: Project Context Continuity
**Situation:** User working on a home renovation project across multiple conversations.

**AI Agent Workflow:**
1. **Initial Storage:** `remember(agent="claude", user="sarah_m", topics=["renovation", "kitchen", "budget"], content="Home renovation project focusing on kitchen remodel. Budget constraint of $15,000. Prefers modern farmhouse style. Timeline: 3 months.")`
2. **Progress Update:** `remember(agent="claude", user="sarah_m", topics=["renovation", "kitchen", "progress"], content="Cabinets ordered from Home Depot. Installation scheduled for next week. Still need to select countertops - considering quartz within budget.")`
3. **Context Retrieval:** `think(keywords=["renovation", "kitchen"])` returns both memories
4. **Informed Response:** AI provides relevant suggestions based on style preferences, budget constraints, and current progress

### Example 3: Multi-Agent Collaboration
**Situation:** User works with coding assistant and writing helper on documentation project.

**Coding Assistant Workflow:**
1. **Store Technical Details:** `remember(agent="coding_assistant", user="dev_mike", topics=["project", "architecture", "python"], content="API project uses FastAPI framework with SQLAlchemy ORM. Database: PostgreSQL. Authentication via JWT tokens. Prefers type hints and comprehensive docstrings.")`

**Writing Assistant Workflow:**
2. **Discover Context:** `think(keywords=["project", "API"])` finds coding assistant's memory
3. **Recall Details:** `recall(memory_ids=["def67890"])`
4. **Informed Documentation:** Writing assistant creates documentation that matches the technical architecture without user re-explaining the setup

### Example 4: Learning Progress Tracking
**Situation:** User learning Python programming with AI tutor across multiple sessions.

**AI Tutor Workflow:**
1. **Assessment Storage:** `remember(agent="tutor", user="student_alex", topics=["python", "learning", "progress"], content="Completed basic syntax and control structures. Understands functions and modules. Struggles with object-oriented concepts - responds well to visual analogies.")`
2. **Next Session:** `think(keywords=["python", "learning", "progress"])`
3. **Personalized Teaching:** AI continues from where previous session ended, using preferred teaching methods (visual analogies) for challenging topics

## Implementation Requirements

### Deployment and Installation
- **Simple Installation**: The server must be installable and runnable with minimal setup steps
- **Package Manager Support**: Support installation via common package managers (e.g., `npm`/`npx` for Node.js, `pip`/`uv` for Python, `cargo` for Rust)
- **Script-Based Execution**: Provide simple execution scripts that handle dependency management automatically
- **Zero Configuration**: Run with sensible defaults without requiring configuration files
- **Cross-Platform**: Work consistently across Windows, macOS, and Linux operating systems
- **Dependency Management**: Automatically handle all required dependencies during installation
- **Single Command Start**: Enable server startup with a single command (e.g., `npx aiaml-server`, `uv run aiaml-server`, `./run_server.sh`)
- **MCP Library Requirement**: Must include Model Context Protocol library with CLI support (e.g., `mcp[cli]>=1.0.0` for Python)
- **Minimum Runtime Requirements**: Support modern runtime versions (e.g., Python >=3.10, Node.js >=18, etc.)

### Core Functionality
- **Three MCP Tools Only**: The server must provide exactly three tools: `remember`, `think`, and `recall`
- **MCP Server Initialization**: Initialize server with name "AI Agnostic Memory Layer"
- **Memory ID Generation**: Generate unique 8-character hexadecimal identifiers using UUID4 (first 8 characters after removing hyphens)
- **File-Based Storage**: Store memories as markdown files with YAML frontmatter in a dedicated directory
- **Relevance Scoring**: Implement keyword-based relevance scoring with topic matches weighted 2x higher than content matches
- **Search Limits**: Return maximum 25 results from `think` searches, sorted by relevance score
- **Server Entry Point**: Provide main execution entry point that starts the MCP server

### File System Structure
- **Memory Directory**: Create and maintain a dedicated directory for memory files (e.g., `memory/files/`)
- **File Naming**: Use format `YYYYMMDD_HHMMSS_[memory-id].md` for all memory files
- **File Format**: YAML frontmatter with required fields: `id`, `timestamp`, `agent`, `user`, `topics`
- **Content Encoding**: Use UTF-8 encoding for all file operations
- **Directory Creation**: Automatically create memory directory if it doesn't exist

### Optional GitHub Synchronization
- **Environment Configuration**: Support `AIAML_ENABLE_SYNC` environment variable (default: "true")
- **Remote URL Configuration**: Support `AIAML_GITHUB_REMOTE` environment variable for specifying Git remote (optional)
- **Git Repository Integration**: If enabled, automatically sync new memories to a Git repository
- **Background Processing**: Run Git operations in background threads to avoid blocking memory creation
- **Error Isolation**: Git sync failures must not affect memory storage operations
- **Commit Format**: Use commit message format: "Add memory [memory-id] ([filename])"
- **Git Operations**: Perform `git add`, `git commit`, and `git push origin main` for each new memory
- **Working Directory**: Execute Git commands from the memory directory parent (e.g., `memory/` folder)
- **File Path**: Add files using relative path `files/[filename]` from the Git repository root

### Memory Processing
- **Frontmatter Parsing**: Parse YAML frontmatter to extract metadata using simple key-value parsing
- **Topic Parsing**: Handle topics as comma-separated list in square brackets format: `[topic1, topic2, topic3]`
- **Frontmatter Validation**: Require frontmatter to start with `---\n` and split on `---\n` delimiters
- **Key-Value Extraction**: Parse each line containing `:` as key-value pairs, trimming whitespace
- **Topic List Processing**: Strip square brackets from topics value and split on commas, filtering empty strings
- **Timestamp Format**: Use ISO 8601 format for all timestamps
- **Error Handling**: Gracefully handle malformed files by skipping them during search operations (return None from parsing)
- **Case-Insensitive Search**: Perform all keyword matching in lowercase for consistency
- **Content Extraction**: Extract content as everything after the closing `---\n` delimiter, trimmed of whitespace

### Tool Behavior Specifications
- **remember Tool**: Must generate unique ID using UUID4 (first 8 hex chars), create ISO 8601 timestamp, format frontmatter, write file atomically, and return ID with success message
- **think Tool**: Must search all `*.md` files in memory directory, calculate relevance scores, sort results, limit to 25 items, and return structured results with matching keywords
- **recall Tool**: Must find memory files using glob pattern `*_{memory-id}.md`, parse content, validate ID matches, and return complete memory objects or error for missing IDs

### Data Integrity
- **Atomic Operations**: Ensure memory files are written completely or not at all
- **Unique IDs**: Guarantee memory IDs are unique across all stored memories
- **File Consistency**: Maintain consistent file format across all memory files
- **Content Preservation**: Preserve exact content formatting including whitespace and markdown
- **Metadata Validation**: Validate required frontmatter fields are present and properly formatted

### Search Algorithm Requirements
- **Multi-Field Search**: Search across topics, content, user, and agent fields
- **Text Processing**: Convert all text to lowercase before matching for case-insensitive search
- **Relevance Calculation**: 
  - Topic matches: weight × 2
  - Content matches: weight × 1  
  - User field matches: weight × 1
  - Agent field matches: weight × 1
  - Exact word boundary matches: bonus points using regex `\b{keyword}\b`
- **Score Calculation**: `(topic_matches × 2) + content_matches + user_matches + agent_matches + exact_matches`
- **Result Sorting**: Primary sort by relevance score (descending), secondary sort by timestamp (newest first)
- **Keyword Processing**: Convert all keywords to lowercase before matching
- **Match Tracking**: Track which keywords matched for each result, removing duplicates
- **Match Counting**: Use simple string `.count()` method for substring matching in each field

### Performance Requirements
- **Memory Creation**: Complete `remember` operations in under 1 second
- **Search Performance**: Complete `think` operations across thousands of memories in under 2 seconds  
- **File Operations**: Use efficient file I/O operations to minimize disk access
- **Memory Usage**: Minimize memory footprint during search operations
- **Concurrent Access**: Handle multiple simultaneous requests without file corruption

### Error Handling
- **Graceful Degradation**: Continue operating even if individual memory files are corrupted
- **Descriptive Errors**: Return clear error messages for debugging
- **Exception Safety**: Catch and handle all exceptions to prevent server crashes
- **Logging**: Log errors for debugging while continuing operation
- **Validation**: Validate all input parameters before processing

## Validation Criteria

### Functional Validation
- **Tool Interface**: Server provides exactly three MCP tools with correct parameter types and return formats
- **Memory Storage**: Successfully stores memories with all required metadata fields
- **Search Accuracy**: Returns relevant memories based on keyword matching with proper relevance scoring
- **ID Uniqueness**: Generates unique 8-character memory IDs for all stored memories
- **File Format**: Creates correctly formatted markdown files with YAML frontmatter
- **Cross-Platform**: Works consistently across different operating systems and Python environments
- **Git Sync (Optional)**: If enabled, successfully commits and pushes new memories to Git repository without affecting core functionality

### Performance Validation  
- **Storage Speed**: `remember` tool completes within 1 second for typical memory content
- **Search Speed**: `think` tool returns results within 2 seconds across 1000+ memories
- **Scalability**: Maintains performance as memory collection grows to 10,000+ items
- **Memory Efficiency**: Uses reasonable system memory during operations
- **File I/O**: Efficient disk operations without excessive file system calls

### Data Integrity Validation
- **File Consistency**: All memory files maintain consistent YAML frontmatter format
- **Content Preservation**: Memory content stored and retrieved without modification
- **Metadata Accuracy**: All required metadata fields present and correctly formatted
- **Search Reliability**: Search results remain consistent across multiple identical queries
- **Error Recovery**: System continues operating despite individual corrupted memory files

### API Compatibility
- **MCP Compliance**: Full compatibility with Model Context Protocol specifications
- **Tool Signatures**: Correct parameter names, types, and descriptions for AI agent understanding
- **Return Formats**: Consistent JSON response structures across all tools
- **Error Handling**: Proper error responses that don't break AI agent integrations
- **Documentation**: Tool descriptions clear enough for AI agents to use without human explanation

### Deployment Validation
- **Installation Simplicity**: Can be installed with a single package manager command
- **Startup Speed**: Server starts and becomes ready to accept connections within 5 seconds
- **Dependency Resolution**: All required dependencies install automatically without manual intervention
- **Platform Compatibility**: Successfully runs on Windows, macOS, and Linux without platform-specific modifications
- **Default Configuration**: Works out-of-the-box without requiring configuration files or environment variables (except optional Git sync)
- **Resource Requirements**: Minimal system resource requirements suitable for development and production environments

This specification provides complete implementation guidance for recreating the AIAML MCP server in any programming language while maintaining full compatibility with the existing API.