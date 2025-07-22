"""Main server implementation for AIAML MCP server."""

import logging
import sys
import threading
import time
from pathlib import Path
from typing import List

from mcp.server.fastmcp import FastMCP

from .config import Config, load_configuration, validate_configuration
from .memory import (
    store_memory_atomic, search_memories_optimized, recall_memories,
    validate_memory_input, validate_search_input, validate_recall_input
)
from .errors import error_handler


def setup_logging(config: Config) -> None:
    """Setup comprehensive logging configuration with structured logging."""
    # Create custom formatter for structured logging
    class StructuredFormatter(logging.Formatter):
        def format(self, record):
            # Add structured data if available
            if hasattr(record, 'operation'):
                record.msg = f"[{record.operation}] {record.msg}"
            return super().format(record)
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, config.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Set up specific loggers
    loggers = [
        'aiaml.init',
        'aiaml.memory',
        'aiaml.git_sync',
        'aiaml.error_handler',
        'aiaml.performance'
    ]
    
    formatter = StructuredFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    for logger_name in loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(getattr(logging, config.log_level))
        
        # Add console handler if not already present
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.propagate = False


def register_tools(server: FastMCP, server_config: Config) -> None:
    """Register MCP tools with the server instance."""
    
    @server.tool()
    def remember(agent: str, user: str, topics: List[str], content: str) -> dict:
        """
        Store a new memory entry.
        
        Use this tool when the user explicitly asks you to remember something, or when 
        important information emerges that would be valuable to recall in future conversations.
        This creates persistent memory that survives across conversation boundaries.
        
        Args:
            agent: Name of the AI agent storing the memory (use your model name, e.g., "claude-sonnet-4")
            user: User identifier - use the actual user's name or a consistent identifier
            topics: List of topic tags for categorisation (2-5 relevant keywords that describe the content)
            content: The actual memory content to store (be comprehensive but concise - include context and key details)
            
        Returns:
            Dictionary containing memory_id and confirmation message
            
        Examples:
            - User says "remember that I'm vegetarian": topics=["dietary_preferences", "vegetarian"], content="User follows a vegetarian diet"
            - User shares project details: topics=["work", "project_alpha"], content="Working on Project Alpha - deadline March 15th, team of 5 developers"
            - User mentions preferences: topics=["preferences", "communication"], content="Prefers direct communication style, dislikes lengthy explanations"
        """
        # Validate input parameters
        validation_error = validate_memory_input(agent, user, topics, content)
        if validation_error:
            return validation_error.to_dict()
        
        # Store the memory using atomic operations
        return store_memory_atomic(agent, user, topics, content, server_config)
    
    @server.tool()
    def think(keywords: List[str]) -> List[dict]:
        """
        Search for relevant memories by keywords.
        
        Automatically search when users ask about their personal details, relationships, preferences, work, or any 'my/mine' references.
        Use this tool when you need to recall information that might have been discussed before.
        This searches through stored memories to find relevant context for the current conversation.
        Always use this before answering questions that might benefit from previous context.
        
        Args:
            keywords: List of keywords to search for in memory content and topics (2-6 words work best)
                     - Use synonyms and related terms to cast a wide net
                     - Include both specific terms and general categories
                     - Examples: ["vegetarian", "diet"], ["project", "deadline"], ["preferences", "communication"]
            
        Returns:
            List of matching memories with relevance scores (higher scores = better matches)
            Use the relevance scores to prioritise which memories to recall for full details
            No need to use recall if content_preview_is_truncated is false
            
        Usage pattern:
            1. Use 'think' to search for potentially relevant memories
            2. Examine the results and their relevance scores  
            3. Use 'recall' to get full details of the most relevant memories if needed
            4. Apply that context to your response
        """
        # Validate input parameters
        validation_error = validate_search_input(keywords)
        if validation_error:
            return [validation_error.to_dict()]
        
        # Search for memories using optimized search
        return search_memories_optimized(keywords, server_config)
    
    @server.tool()
    def recall(memory_ids: List[str]) -> List[dict]:
        """
        Retrieve full memory details by memory IDs.
        
        Use this tool after 'think' to get complete details of specific memories.
        This provides the full context needed to inform your responses with previous knowledge.
        
        Args:
            memory_ids: List of memory IDs to retrieve (get these from 'think' results)
                       - Prioritise memories with higher relevance scores from 'think'
                       - Usually recall 2-5 most relevant memories to avoid information overload
            
        Returns:
            List of complete memory objects containing:
            - Full memory content
            - Topics and metadata
            - Creation timestamps
            - Associated user and agent information
            
        Typical workflow:
            1. User asks a question
            2. Use 'think' with relevant keywords
            3. Use 'recall' on the most promising memory_ids
            4. Incorporate recalled information naturally into your response
            5. Don't explicitly mention you've recalled memories unless relevant
        """
        # Validate input parameters
        validation_error = validate_recall_input(memory_ids)
        if validation_error:
            return [validation_error.to_dict()]
        
        # Recall memories
        return recall_memories(memory_ids, server_config)
    
    
    # Log successful tool registration
    init_logger = logging.getLogger('aiaml.init')
    init_logger.info("MCP tools registered successfully")

def initialize_server() -> FastMCP:
    """Initialize MCP server with stdio transport for local-only operation."""
    try:
        # Load and validate configuration
        server_config = load_configuration()
        validation_issues = validate_configuration(server_config)
        
        # Setup logging with the loaded configuration
        setup_logging(server_config)
        init_logger = logging.getLogger('aiaml.init')
        
        # Report configuration validation issues
        if validation_issues:
            for issue in validation_issues:
                if issue.startswith("ERROR:"):
                    init_logger.error(issue[7:])  # Remove "ERROR: " prefix
                elif issue.startswith("WARNING:"):
                    init_logger.warning(issue[9:])  # Remove "WARNING: " prefix
            
            # Exit if there are any errors
            error_count = sum(1 for issue in validation_issues if issue.startswith("ERROR:"))
            if error_count > 0:
                init_logger.critical(f"Server startup failed due to {error_count} configuration error(s)")
                exit(1)
        
        # Log successful configuration loading
        init_logger.info("Configuration loaded successfully")
        
        # Initialize automated directory and file management
        try:
            from .file_manager import initialize_aiaml_directories
            
            if not initialize_aiaml_directories(server_config):
                init_logger.error("Failed to initialize AIAML directory structure")
                raise RuntimeError("Directory initialization failed")
            
            init_logger.info("AIAML directory structure initialized successfully")
        except Exception as e:
            init_logger.error(f"Failed to initialize directory structure: {e}")
            raise
        
        # Initialize Git synchronization manager if Git sync is enabled
        if server_config.enable_git_sync:
            try:
                from .git_sync import get_git_sync_manager
                git_manager = get_git_sync_manager(server_config)
                
                if git_manager.is_initialized():
                    init_logger.info("Git synchronization manager initialized successfully")
                    
                    # Log repository status
                    status = git_manager.get_repository_status()
                    init_logger.info(
                        f"Git sync status: repository_exists={status['repository_exists']}, "
                        f"remote_configured={status['remote_configured']}"
                    )
                else:
                    init_logger.warning("Git synchronization manager initialization failed")
                    
            except FileNotFoundError:
                init_logger.warning("Git command not found - Git sync will be disabled")
            except Exception as e:
                init_logger.warning(f"Git synchronization manager initialization failed: {e}")
        
        # Initialize the MCP server with stdio transport only
        init_logger.info("Initializing MCP server with stdio transport")
        server = FastMCP(
            "AI Agnostic Memory Layer",
            log_level=server_config.log_level.upper()
        )
        
        # Register MCP tools
        init_logger.info("Registering MCP tools")
        register_tools(server, server_config)
        
        # Log server configuration
        init_logger.info("Server configured for stdio transport only")
        
        init_logger.info("AIAML MCP server initialized successfully")
        
        return server
        
    except Exception as e:
        # Use basic logging if our logging setup failed
        if 'init_logger' not in locals():
            logging.basicConfig(level=logging.ERROR)
            init_logger = logging.getLogger('aiaml.init')
        
        init_logger.critical(f"Server initialization failed: {e}", exc_info=True)
        raise


# Connection monitoring removed for local-only server


def start_file_maintenance():
    """Start background thread for file maintenance tasks."""
    def file_maintenance():
        maintenance_logger = logging.getLogger('aiaml.file_maintenance')
        
        while True:
            try:
                # Run maintenance tasks every 30 minutes
                time.sleep(1800)  # 30 minutes
                
                # Load current configuration
                from .config import load_configuration
                from .file_manager import get_file_manager
                from .file_lock import cleanup_stale_locks
                
                config = load_configuration()
                file_manager = get_file_manager(config)
                
                # Clean up old backups (keep 30 days, max 100 per file)
                backup_count = file_manager.cleanup_old_backups(max_age_days=30, max_count=100)
                if backup_count > 0:
                    maintenance_logger.info(f"Cleaned up {backup_count} old backup files")
                
                # Clean up stale locks (older than 10 minutes)
                lock_count = cleanup_stale_locks(config, max_age_minutes=10)
                if lock_count > 0:
                    maintenance_logger.info(f"Cleaned up {lock_count} stale lock files")
                
            except Exception as e:
                maintenance_logger.error(f"File maintenance error: {e}")
                time.sleep(300)  # Wait 5 minutes before retrying
    
    # Start maintenance thread as daemon so it doesn't prevent shutdown
    maintenance_thread = threading.Thread(target=file_maintenance, daemon=True)
    maintenance_thread.start()
    
    logging.getLogger('aiaml.init').info("File maintenance started")


def main():
    """Main entry point for the AIAML server package with stdio transport."""
    startup_logger = None
    
    try:
        # Setup basic logging for startup
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        startup_logger = logging.getLogger('aiaml.startup')
        
        startup_logger.info("=" * 60)
        startup_logger.info("AI Agnostic Memory Layer (AIAML) MCP Server")
        startup_logger.info("Version: 1.0.0 (Local-Only)")
        startup_logger.info("=" * 60)
        
        # Perform startup validation
        startup_logger.info("Performing startup validation...")
        
        # Check Python version
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        if sys.version_info < (3, 10):
            startup_logger.error(f"Python 3.10+ required, found {python_version}")
            exit(1)
        
        startup_logger.info(f"Python version: {python_version} ✓")
        
        # Check required dependencies
        try:
            import mcp
            startup_logger.info("MCP dependency available ✓")
        except ImportError as e:
            startup_logger.error(f"Required dependency missing: {e}")
            startup_logger.error("Please install with: pip install 'mcp[cli]>=1.0.0'")
            exit(1)
        
        # Initialize server with stdio transport
        startup_logger.info("Initializing server with stdio transport...")
        server = initialize_server()
        
        startup_logger.info("=" * 60)
        startup_logger.info("Server startup completed successfully!")
        startup_logger.info("Ready to accept MCP connections via stdio transport")
        startup_logger.info("=" * 60)
        
        # Start file maintenance
        start_file_maintenance()
        
        # Start the server with stdio transport directly
        startup_logger.info("Starting server with stdio transport")
        server.run(transport="stdio")
        
    except KeyboardInterrupt:
        if startup_logger:
            startup_logger.info("Server stopped by user (Ctrl+C)")
        else:
            print("\nServer stopped by user")
    except SystemExit:
        # Re-raise SystemExit to preserve exit codes
        raise
    except Exception as e:
        if startup_logger:
            startup_logger.critical(f"Server failed to start: {e}", exc_info=True)
        else:
            print(f"CRITICAL: Server failed to start: {e}")
        exit(1)