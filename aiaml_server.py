#!/usr/bin/env python3
"""
AI Agnostic Memory Layer (AIAML) MCP Server

A simple local memory system for AI agents that provides persistent storage
and retrieval of memories using markdown files.
"""

import json
import re
import uuid
import threading
import subprocess
import os
import logging
import time
import functools
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable

from mcp.server.fastmcp import FastMCP


@dataclass
class Config:
    """Configuration class for AIAML server with validation and defaults."""
    
    # Authentication
    api_key: Optional[str] = None
    
    # Git synchronization
    enable_git_sync: bool = True
    git_remote_url: Optional[str] = None
    git_retry_attempts: int = 3
    git_retry_delay: float = 1.0
    
    # Storage
    memory_dir: Path = field(default_factory=lambda: Path("memory/files"))
    
    # Logging
    log_level: str = "INFO"
    
    # Performance
    max_search_results: int = 25
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        # Convert string path to Path object if needed
        if isinstance(self.memory_dir, str):
            self.memory_dir = Path(self.memory_dir)
        
        # Validate log level
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.log_level.upper() not in valid_log_levels:
            raise ValueError(f"Invalid log level: {self.log_level}. Must be one of {valid_log_levels}")
        
        # Validate retry attempts
        if self.git_retry_attempts < 0:
            raise ValueError("git_retry_attempts must be non-negative")
        
        # Validate retry delay
        if self.git_retry_delay < 0:
            raise ValueError("git_retry_delay must be non-negative")
        
        # Validate max search results
        if self.max_search_results <= 0:
            raise ValueError("max_search_results must be positive")


def load_configuration() -> Config:
    """Load configuration from environment variables with sensible defaults."""
    try:
        config = Config(
            api_key=os.getenv("AIAML_API_KEY"),
            enable_git_sync=os.getenv("AIAML_ENABLE_SYNC", "false").lower() == "true",
            git_remote_url=os.getenv("AIAML_GITHUB_REMOTE"),
            git_retry_attempts=int(os.getenv("AIAML_GIT_RETRY_ATTEMPTS", "3")),
            git_retry_delay=float(os.getenv("AIAML_GIT_RETRY_DELAY", "1.0")),
            memory_dir=Path(os.getenv("AIAML_MEMORY_DIR", "memory/files")),
            log_level=os.getenv("AIAML_LOG_LEVEL", "INFO").upper(),
            max_search_results=int(os.getenv("AIAML_MAX_SEARCH_RESULTS", "25"))
        )
        return config
    except (ValueError, TypeError) as e:
        raise ValueError(f"Configuration error: {e}")


def validate_configuration(config: Config) -> List[str]:
    """Validate configuration and return any errors or warnings."""
    errors = []
    warnings = []
    
    # Check if memory directory is accessible
    try:
        config.memory_dir.mkdir(exist_ok=True, parents=True)
        if not config.memory_dir.is_dir():
            errors.append(f"Memory directory is not accessible: {config.memory_dir}")
    except Exception as e:
        errors.append(f"Cannot create memory directory {config.memory_dir}: {e}")
    
    # Check Git configuration
    if config.enable_git_sync:
        if not config.git_remote_url:
            warnings.append("Git sync is enabled but no remote URL is configured (AIAML_GITHUB_REMOTE)")
        
        # Check if git is available
        try:
            subprocess.run(["git", "--version"], check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            errors.append("Git sync is enabled but git command is not available")
    
    # Check API key for security
    if config.api_key and len(config.api_key) < 16:
        warnings.append("API key is shorter than recommended minimum of 16 characters")
    
    # Combine errors and warnings
    all_issues = []
    all_issues.extend([f"ERROR: {error}" for error in errors])
    all_issues.extend([f"WARNING: {warning}" for warning in warnings])
    
    return all_issues


def setup_logging(config: Config) -> None:
    """Setup comprehensive logging configuration with structured logging."""
    # Create custom formatter for structured logging
    class StructuredFormatter(logging.Formatter):
        """Custom formatter that adds structured context to log messages."""
        
        def format(self, record):
            # Add structured fields to the record
            if not hasattr(record, 'operation'):
                record.operation = 'general'
            if not hasattr(record, 'memory_id'):
                record.memory_id = None
            if not hasattr(record, 'user'):
                record.user = None
            if not hasattr(record, 'duration_ms'):
                record.duration_ms = None
            if not hasattr(record, 'connection_type'):
                record.connection_type = None
            
            # Format the base message
            formatted = super().format(record)
            
            # Add structured context if available
            context_parts = []
            if record.operation != 'general':
                context_parts.append(f"op={record.operation}")
            if record.memory_id:
                context_parts.append(f"memory_id={record.memory_id}")
            if record.user:
                context_parts.append(f"user={record.user}")
            if record.duration_ms is not None:
                context_parts.append(f"duration_ms={record.duration_ms}")
            if record.connection_type:
                context_parts.append(f"connection={record.connection_type}")
            
            if context_parts:
                formatted += f" [{' '.join(context_parts)}]"
            
            return formatted
    
    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.log_level))
    
    # Clear any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create console handler with structured formatter
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, config.log_level))
    
    formatter = StructuredFormatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)


def log_authentication_attempt(success: bool, connection_info: Dict[str, Any]) -> None:
    """Log authentication attempts for security monitoring."""
    auth_logger = logging.getLogger('aiaml.auth')
    
    connection_type = connection_info.get('connection_type', 'unknown')
    remote_address = connection_info.get('remote_address', 'unknown')
    user_agent = connection_info.get('user_agent', 'unknown')
    
    if success:
        auth_logger.info(
            "Authentication successful",
            extra={
                'operation': 'auth_success',
                'connection_type': connection_type,
                'remote_address': remote_address,
                'user_agent': user_agent
            }
        )
    else:
        auth_logger.warning(
            "Authentication failed",
            extra={
                'operation': 'auth_failure',
                'connection_type': connection_type,
                'remote_address': remote_address,
                'user_agent': user_agent
            }
        )


def log_operation_error(operation: str, error: Exception, context: Dict[str, Any] = None) -> None:
    """Log operation errors with comprehensive context."""
    error_logger = logging.getLogger('aiaml.error')
    
    context = context or {}
    
    error_logger.error(
        f"Operation failed: {str(error)}",
        extra={
            'operation': operation,
            'error_type': type(error).__name__,
            'memory_id': context.get('memory_id'),
            'user': context.get('user'),
            'keywords': context.get('keywords'),
            'file_path': context.get('file_path')
        },
        exc_info=True
    )


def log_performance_metric(operation: str, duration_ms: float, context: Dict[str, Any] = None) -> None:
    """Log performance metrics for monitoring."""
    perf_logger = logging.getLogger('aiaml.performance')
    
    context = context or {}
    
    # Log performance metric
    perf_logger.info(
        f"Operation completed",
        extra={
            'operation': operation,
            'duration_ms': round(duration_ms, 2),
            'memory_id': context.get('memory_id'),
            'user': context.get('user'),
            'result_count': context.get('result_count'),
            'keywords_count': context.get('keywords_count')
        }
    )
    
    # Log warning for slow operations
    if duration_ms > 2000:  # More than 2 seconds
        perf_logger.warning(
            f"Slow operation detected: {operation} took {duration_ms:.2f}ms",
            extra={
                'operation': f"{operation}_slow",
                'duration_ms': round(duration_ms, 2)
            }
        )


def performance_monitor(operation: str):
    """Decorator to monitor and log performance of operations."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                
                # Calculate duration
                duration_ms = (time.time() - start_time) * 1000
                
                # Extract context from function arguments and result
                context = {}
                
                # Try to extract common context information
                if 'memory_id' in kwargs:
                    context['memory_id'] = kwargs['memory_id']
                elif len(args) > 0 and hasattr(args[0], 'get'):
                    # For dict-like first argument
                    context['memory_id'] = args[0].get('memory_id')
                
                if 'user' in kwargs:
                    context['user'] = kwargs['user']
                elif len(args) > 1:
                    # For user parameter in remember function
                    if operation == 'remember' and len(args) >= 2:
                        context['user'] = args[1]
                
                if 'keywords' in kwargs:
                    context['keywords'] = kwargs['keywords']
                    context['keywords_count'] = len(kwargs['keywords']) if kwargs['keywords'] else 0
                elif operation == 'think' and len(args) > 0:
                    context['keywords'] = args[0]
                    context['keywords_count'] = len(args[0]) if args[0] else 0
                
                # Extract result count for search operations
                if isinstance(result, list):
                    context['result_count'] = len(result)
                
                # Log performance metric
                log_performance_metric(operation, duration_ms, context)
                
                return result
                
            except Exception as e:
                # Calculate duration even for failed operations
                duration_ms = (time.time() - start_time) * 1000
                
                # Extract context for error logging
                error_context = {}
                if 'memory_id' in kwargs:
                    error_context['memory_id'] = kwargs['memory_id']
                if 'user' in kwargs:
                    error_context['user'] = kwargs['user']
                if 'keywords' in kwargs:
                    error_context['keywords'] = kwargs['keywords']
                
                # Log the error with context
                log_operation_error(operation, e, error_context)
                
                # Log performance for failed operation
                log_performance_metric(f"{operation}_failed", duration_ms, error_context)
                
                raise
        
        return wrapper
    return decorator


# Load and validate configuration
try:
    config = load_configuration()
    validation_issues = validate_configuration(config)
    
    # Setup logging
    setup_logging(config)
    logger = logging.getLogger(__name__)
    
    # Log configuration issues
    for issue in validation_issues:
        if issue.startswith("ERROR:"):
            logger.error(issue[7:])  # Remove "ERROR: " prefix
        elif issue.startswith("WARNING:"):
            logger.warning(issue[9:])  # Remove "WARNING: " prefix
    
    # Exit if there are critical errors
    error_count = sum(1 for issue in validation_issues if issue.startswith("ERROR:"))
    if error_count > 0:
        logger.critical(f"Configuration validation failed with {error_count} error(s). Exiting.")
        exit(1)
    
    logger.info("Configuration loaded successfully")
    logger.debug(f"Memory directory: {config.memory_dir}")
    logger.debug(f"Git sync enabled: {config.enable_git_sync}")
    logger.debug(f"Log level: {config.log_level}")
    
except Exception as e:
    # Fallback logging setup for configuration errors
    logging.basicConfig(level=logging.ERROR)
    logger = logging.getLogger(__name__)
    logger.critical(f"Failed to load configuration: {e}")
    exit(1)

# Initialize the MCP server
mcp = FastMCP("AI Agnostic Memory Layer")

# Legacy compatibility - maintain existing global variables for backward compatibility
MEMORY_DIR = config.memory_dir
MEMORY_BACKUP_DIR = config.memory_dir.parent
ENABLE_GITHUB_SYNC = config.enable_git_sync
GITHUB_REMOTE_URL = config.git_remote_url or ""


def generate_memory_id() -> str:
    """Generate a unique 8-character memory ID."""
    return str(uuid.uuid4()).replace("-", "")[:8]


def create_timestamp() -> str:
    """Create a timestamp string for file naming."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def create_memory_filename(memory_id: str) -> str:
    """Create a memory filename with timestamp and ID."""
    timestamp = create_timestamp()
    return f"{timestamp}_{memory_id}.md"


def sync_to_github(memory_id: str, filename: str) -> None:
    """
    Sync a new memory file to GitHub repository in the background.
    
    Args:
        memory_id: The memory ID that was created
        filename: The filename of the memory file
    """
    if not ENABLE_GITHUB_SYNC:
        return
    
    def _sync():
        git_logger = logging.getLogger('aiaml.git')
        start_time = time.time()
        
        try:
            git_logger.debug(
                f"Starting Git sync for memory {memory_id}",
                extra={
                    'operation': 'git_sync_start',
                    'memory_id': memory_id,
                    'filename': filename
                }
            )
            
            # Add the new file
            add_result = subprocess.run(
                ["git", "add", f"files/{filename}"], 
                check=True, 
                capture_output=True, 
                cwd=MEMORY_BACKUP_DIR,
                text=True
            )
            
            git_logger.debug(
                f"Git add completed for {filename}",
                extra={
                    'operation': 'git_add',
                    'memory_id': memory_id,
                    'filename': filename
                }
            )
            
            # Create commit message
            commit_message = f"Add memory {memory_id} ({filename})"
            commit_result = subprocess.run(
                ["git", "commit", "-m", commit_message], 
                check=True, 
                capture_output=True, 
                cwd=MEMORY_BACKUP_DIR,
                text=True
            )
            
            git_logger.debug(
                f"Git commit completed for {memory_id}",
                extra={
                    'operation': 'git_commit',
                    'memory_id': memory_id,
                    'commit_message': commit_message
                }
            )
            
            # Push to remote (always push, since we have remote configured)
            push_result = subprocess.run(
                ["git", "push", "origin", "main"], 
                check=True, 
                capture_output=True, 
                cwd=MEMORY_BACKUP_DIR,
                text=True
            )
            
            # Calculate total sync duration
            duration_ms = (time.time() - start_time) * 1000
            
            git_logger.info(
                f"Git sync completed successfully for memory {memory_id}",
                extra={
                    'operation': 'git_sync_success',
                    'memory_id': memory_id,
                    'duration_ms': round(duration_ms, 2),
                    'filename': filename
                }
            )
                
        except subprocess.CalledProcessError as e:
            # Calculate duration for failed operation
            duration_ms = (time.time() - start_time) * 1000
            
            # Log detailed error information
            error_context = {
                'memory_id': memory_id,
                'filename': filename,
                'git_command': ' '.join(e.cmd) if e.cmd else 'unknown',
                'return_code': e.returncode,
                'stdout': e.stdout.decode() if e.stdout else '',
                'stderr': e.stderr.decode() if e.stderr else ''
            }
            
            log_operation_error('git_sync', e, error_context)
            
            git_logger.warning(
                f"Git sync failed for memory {memory_id}: {e}",
                extra={
                    'operation': 'git_sync_failed',
                    'memory_id': memory_id,
                    'duration_ms': round(duration_ms, 2),
                    'error_type': 'CalledProcessError',
                    'return_code': e.returncode
                }
            )
            
        except Exception as e:
            # Calculate duration for failed operation
            duration_ms = (time.time() - start_time) * 1000
            
            # Log unexpected errors
            error_context = {
                'memory_id': memory_id,
                'filename': filename
            }
            
            log_operation_error('git_sync', e, error_context)
            
            git_logger.error(
                f"Unexpected error during Git sync for memory {memory_id}: {e}",
                extra={
                    'operation': 'git_sync_error',
                    'memory_id': memory_id,
                    'duration_ms': round(duration_ms, 2),
                    'error_type': type(e).__name__
                }
            )
    
    # Run sync in background thread
    thread = threading.Thread(target=_sync, daemon=True)
    thread.start()


def parse_memory_file(file_path: Path) -> Optional[Dict[str, Any]]:
    """Parse a memory file and return its contents with comprehensive error handling."""
    file_logger = logging.getLogger('aiaml.file')
    
    try:
        content = file_path.read_text(encoding="utf-8")
        
        # Split frontmatter and content
        if content.startswith("---\n"):
            parts = content.split("---\n", 2)
            if len(parts) >= 3:
                frontmatter = parts[1].strip()
                memory_content = parts[2].strip()
                
                # Parse frontmatter
                metadata = {}
                for line in frontmatter.split("\n"):
                    if ":" in line:
                        key, value = line.split(":", 1)
                        key = key.strip()
                        value = value.strip()
                        
                        # Handle topics as a list
                        if key == "topics":
                            # Remove brackets and split by comma
                            topics_str = value.strip("[]")
                            metadata[key] = [t.strip() for t in topics_str.split(",") if t.strip()]
                        else:
                            metadata[key] = value
                
                parsed_data = {
                    "id": metadata.get("id", ""),
                    "timestamp": metadata.get("timestamp", ""),
                    "agent": metadata.get("agent", ""),
                    "user": metadata.get("user", ""),
                    "topics": metadata.get("topics", []),
                    "content": memory_content
                }
                
                file_logger.debug(
                    f"Successfully parsed memory file {file_path.name}",
                    extra={
                        'operation': 'parse_memory_file',
                        'memory_id': parsed_data.get("id"),
                        'file_path': str(file_path)
                    }
                )
                
                return parsed_data
            else:
                file_logger.warning(
                    f"Memory file {file_path.name} has invalid frontmatter structure",
                    extra={
                        'operation': 'parse_memory_file_invalid',
                        'file_path': str(file_path),
                        'parts_count': len(parts)
                    }
                )
        else:
            file_logger.warning(
                f"Memory file {file_path.name} does not start with frontmatter",
                extra={
                    'operation': 'parse_memory_file_no_frontmatter',
                    'file_path': str(file_path)
                }
            )
            
    except UnicodeDecodeError as e:
        log_operation_error('parse_memory_file', e, {
            'file_path': str(file_path),
            'error_type': 'encoding'
        })
        file_logger.error(
            f"Encoding error reading memory file {file_path.name}: {e}",
            extra={
                'operation': 'parse_memory_file_encoding_error',
                'file_path': str(file_path)
            }
        )
    except Exception as e:
        log_operation_error('parse_memory_file', e, {
            'file_path': str(file_path)
        })
        file_logger.error(
            f"Unexpected error parsing memory file {file_path.name}: {e}",
            extra={
                'operation': 'parse_memory_file_error',
                'file_path': str(file_path),
                'error_type': type(e).__name__
            }
        )
    
    return None


def calculate_relevance_score(memory_data: Dict[str, Any], keywords: List[str]) -> Dict[str, Any]:
    """Calculate relevance score for a memory based on keyword matches."""
    if not keywords:
        return {"score": 0, "matching_keywords": []}
    
    keywords_lower = [k.lower() for k in keywords]
    topics_text = " ".join(memory_data.get("topics", [])).lower()
    content_text = memory_data.get("content", "").lower()
    user_text = memory_data.get("user", "").lower()
    agent_text = memory_data.get("agent", "").lower()
    
    matching_keywords = []
    topic_matches = 0
    content_matches = 0
    user_matches = 0
    agent_matches = 0
    exact_matches = 0
    
    for keyword in keywords_lower:
        # Count matches in topics (weighted 2x)
        topic_count = topics_text.count(keyword)
        if topic_count > 0:
            topic_matches += topic_count
            matching_keywords.append(keyword)
        
        # Count matches in content
        content_count = content_text.count(keyword)
        if content_count > 0:
            content_matches += content_count
            if keyword not in matching_keywords:
                matching_keywords.append(keyword)
        
        # Count matches in user field
        user_count = user_text.count(keyword)
        if user_count > 0:
            user_matches += user_count
            if keyword not in matching_keywords:
                matching_keywords.append(keyword)
        
        # Count matches in agent field
        agent_count = agent_text.count(keyword)
        if agent_count > 0:
            agent_matches += agent_count
            if keyword not in matching_keywords:
                matching_keywords.append(keyword)
        
        # Count exact word matches (bonus points)
        combined_text = f"{topics_text} {content_text} {user_text} {agent_text}"
        exact_word_matches = len(re.findall(r'\b' + re.escape(keyword) + r'\b', combined_text))
        if exact_word_matches > 0:
            exact_matches += exact_word_matches
    
    # Calculate relevance score: (topic_matches * 2) + content_matches + user_matches + agent_matches + exact_matches
    relevance_score = (topic_matches * 2) + content_matches + user_matches + agent_matches + exact_matches
    
    return {
        "score": relevance_score,
        "matching_keywords": list(set(matching_keywords))  # Remove duplicates
    }


def search_memories(keywords: List[str]) -> List[Dict[str, Any]]:
    """Search for memories containing the specified keywords, sorted by relevance."""
    search_logger = logging.getLogger('aiaml.search')
    results = []
    
    if not keywords:
        search_logger.debug("Empty keywords provided for search")
        return results
    
    search_logger.debug(
        f"Starting memory search with {len(keywords)} keywords",
        extra={
            'operation': 'search_start',
            'keywords_count': len(keywords),
            'keywords': keywords
        }
    )
    
    # Convert keywords to lowercase for case-insensitive search
    keywords_lower = [k.lower() for k in keywords]
    
    files_processed = 0
    files_matched = 0
    
    for memory_file in MEMORY_DIR.glob("*.md"):
        files_processed += 1
        memory_data = parse_memory_file(memory_file)
        if not memory_data:
            continue
        
        # Calculate relevance score
        relevance_info = calculate_relevance_score(memory_data, keywords)
        
        # Only include memories that have at least one matching keyword
        if relevance_info["score"] > 0:
            files_matched += 1
            results.append({
                "id": memory_data["id"],
                "timestamp": memory_data["timestamp"],
                "relevance_score": relevance_info["score"],
                "matching_keywords": relevance_info["matching_keywords"]
            })
    
    # Sort by relevance score (descending), then by timestamp (most recent first) as tiebreaker
    results.sort(key=lambda x: (x["relevance_score"], x["timestamp"]), reverse=True)
    
    # Limit to configured maximum results
    limited_results = results[:config.max_search_results]
    
    search_logger.info(
        f"Search completed: processed {files_processed} files, found {files_matched} matches, returning {len(limited_results)} results",
        extra={
            'operation': 'search_complete',
            'files_processed': files_processed,
            'files_matched': files_matched,
            'results_returned': len(limited_results),
            'keywords_count': len(keywords)
        }
    )
    
    return limited_results


@mcp.tool()
@performance_monitor('remember')
def remember(agent: str, user: str, topics: List[str], content: str) -> Dict[str, str]:
    """
    Store a new memory entry.
    
    Args:
        agent: The AI agent name (e.g., "claude", "gemini", "chatgpt")
        user: The user identifier (e.g., "marco", "unknown")
        topics: List of keywords/domains for categorizing the memory (each keyword should be a single word, e.g. ["todo", "list"], not ["todo list"] or ["to_do_list"])
        content: The full content to remember
    
    Returns:
        Dictionary containing the memory ID and success message
    """
    try:
        # Generate unique memory ID
        memory_id = generate_memory_id()
        
        # Create timestamp
        timestamp = datetime.now().isoformat()
        
        # Create memory file content
        frontmatter = f"""---
id: {memory_id}
timestamp: {timestamp}
agent: {agent}
user: {user}
topics: [{', '.join(topics)}]
---

{content}"""
        
        # Create filename and save
        filename = create_memory_filename(memory_id)
        file_path = MEMORY_DIR / filename
        
        file_path.write_text(frontmatter, encoding="utf-8")
        
        # Trigger background sync to GitHub
        sync_to_github(memory_id, filename)
        
        return {
            "memory_id": memory_id,
            "message": f"Memory stored successfully with ID: {memory_id}"
        }
        
    except Exception as e:
        return {
            "memory_id": "",
            "message": f"Error storing memory: {str(e)}"
        }


@mcp.tool()
@performance_monitor('think')
def think(keywords: List[str]) -> List[Dict[str, Any]]:
    """
    Search for relevant memories by keywords, sorted by relevance.
    
    Args:
        keywords: List of keywords to search for in memory topics and content
    
    Returns:
        List of up to 25 matching memories, sorted by relevance score (descending).
        Each memory contains:
        - id: Memory ID
        - timestamp: When the memory was created
        - relevance_score: Number indicating how well the memory matches the keywords
        - matching_keywords: List of keywords that matched in this memory (each keyword should be a single word, e.g. ["todo", "list"], not ["todo list"] or ["to_do_list"])
        
        Memories that match more keywords or have keywords in topics (vs content) 
        will have higher relevance scores and appear first.
    """
    try:
        return search_memories(keywords)
    except Exception as e:
        return [{"error": f"Search failed: {str(e)}"}]


@mcp.tool()
@performance_monitor('recall')
def recall(memory_ids: List[str]) -> List[Dict[str, Any]]:
    """
    Retrieve full memory details by ID. Should use `think` first to get IDs.
    Use this to recall specific memories. When interpreting them, focus only on what's relevant, don't mention anything that isn't relevant.
    The consumer doesn't see all the details, so no need to refer to things that are no longer needed or not important to the conversation.
    
    Args:
        memory_ids: List of memory IDs to retrieve
    
    Returns:
        List of complete memory objects with agent, user, topics, and content
    """
    results = []
    
    try:
        for memory_id in memory_ids:
            # Find the memory file by ID
            found = False
            for memory_file in MEMORY_DIR.glob(f"*_{memory_id}.md"):
                memory_data = parse_memory_file(memory_file)
                if memory_data and memory_data["id"] == memory_id:
                    results.append({
                        "id": memory_data["id"],
                        "timestamp": memory_data["timestamp"],
                        "agent": memory_data["agent"],
                        "user": memory_data["user"],
                        "topics": memory_data["topics"],
                        "content": memory_data["content"]
                    })
                    found = True
                    break
            
            if not found:
                results.append({
                    "id": memory_id,
                    "error": f"Memory with ID {memory_id} not found"
                })
                
    except Exception as e:
        results.append({"error": f"Recall failed: {str(e)}"})
    
    return results


def main():
    """Main entry point for the AIAML server package."""
    try:
        logger.info("Starting AIAML MCP server...")
        mcp.run()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.critical(f"Server failed to start: {e}")
        exit(1)


if __name__ == "__main__":
    main()