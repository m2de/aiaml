"""Main server implementation for AIAML MCP server."""

import logging
import sys
import threading
import time
from pathlib import Path
from typing import List

from mcp.server.fastmcp import FastMCP

from .config import Config, load_configuration, validate_configuration
from .auth import create_authentication_middleware, connection_manager
from .memory import (
    store_memory_atomic, search_memories_optimized, recall_memories,
    validate_memory_input, validate_search_input, validate_recall_input,
    get_search_performance_stats
)
from .performance import get_performance_stats
from .benchmarks import run_performance_benchmark
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
        'aiaml.auth',
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
    """Register MCP tools with the server instance and authentication middleware."""
    
    # Create authentication middleware
    auth_middleware = create_authentication_middleware(server_config)
    
    @server.tool()
    @auth_middleware
    def remember(agent: str, user: str, topics: List[str], content: str) -> dict:
        """
        Store a new memory entry.
        
        Args:
            agent: Name of the AI agent storing the memory
            user: User identifier associated with the memory
            topics: List of topic tags for categorization
            content: The actual memory content to store
            
        Returns:
            Dictionary containing memory_id and confirmation message
        """
        # Validate input parameters
        validation_error = validate_memory_input(agent, user, topics, content)
        if validation_error:
            return validation_error.to_dict()
        
        # Store the memory using atomic operations
        return store_memory_atomic(agent, user, topics, content, server_config)
    
    @server.tool()
    @auth_middleware
    def think(keywords: List[str]) -> List[dict]:
        """
        Search for relevant memories by keywords.
        
        Args:
            keywords: List of keywords to search for in memory content and topics
            
        Returns:
            List of matching memories with relevance scores
        """
        # Validate input parameters
        validation_error = validate_search_input(keywords)
        if validation_error:
            return [validation_error.to_dict()]
        
        # Search for memories using optimized search
        return search_memories_optimized(keywords, server_config)
    
    @server.tool()
    @auth_middleware
    def recall(memory_ids: List[str]) -> List[dict]:
        """
        Retrieve full memory details by memory IDs.
        
        Args:
            memory_ids: List of memory IDs to retrieve
            
        Returns:
            List of complete memory objects
        """
        # Validate input parameters
        validation_error = validate_recall_input(memory_ids)
        if validation_error:
            return [validation_error.to_dict()]
        
        # Recall memories
        return recall_memories(memory_ids, server_config)
    
    @server.tool()
    @auth_middleware
    def performance_stats() -> dict:
        """
        Get search performance statistics and monitoring data.
        
        Returns:
            Dictionary containing performance metrics including search times,
            cache hit rates, and other optimization statistics
        """
        return get_search_performance_stats()
    
    @server.tool()
    @auth_middleware
    def system_performance() -> dict:
        """
        Get comprehensive system performance monitoring data.
        
        Returns:
            Dictionary containing detailed performance metrics including:
            - Operation timing statistics (memory store, search, recall)
            - System resource usage (memory, CPU, disk I/O)
            - Performance threshold compliance
            - Optimization recommendations
        """
        return get_performance_stats(server_config)
    
    @server.tool()
    @auth_middleware
    def run_benchmark() -> dict:
        """
        Run comprehensive performance benchmark suite.
        
        This tool runs performance benchmarks to validate compliance with
        requirements 6.1, 6.2, and 6.3:
        - Memory storage operations < 1 second
        - Memory search operations < 2 seconds for 10,000+ memories
        - No significant performance degradation with multiple clients
        
        Returns:
            Dictionary containing benchmark results and performance assessment
        """
        return run_performance_benchmark(server_config)
    
    # Log successful tool registration
    auth_logger = logging.getLogger('aiaml.auth')
    auth_logger.info(
        "MCP tools registered with authentication middleware",
        extra={
            'operation': 'register_tools',
            'tools': ['remember', 'think', 'recall', 'performance_stats', 'system_performance', 'run_benchmark'],
            'auth_enabled': server_config.api_key is not None
        }
    )


def initialize_server() -> FastMCP:
    """Initialize MCP server with enhanced configuration and validation for both local and remote connections."""
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
        init_logger.info(
            "Configuration loaded successfully",
            extra={
                'operation': 'config_load',
                'memory_dir': str(server_config.memory_dir),
                'git_sync_enabled': server_config.enable_git_sync,
                'log_level': server_config.log_level,
                'api_key_configured': server_config.api_key is not None,
                'host': server_config.host,
                'port': server_config.port
            }
        )
        
        # Initialize automated directory and file management
        try:
            from .file_manager import initialize_aiaml_directories
            
            if not initialize_aiaml_directories(server_config):
                init_logger.error("Failed to initialize AIAML directory structure")
                raise RuntimeError("Directory initialization failed")
            
            init_logger.info(
                "AIAML directory structure initialized successfully",
                extra={'operation': 'directory_setup'}
            )
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
        
        # Initialize the MCP server with remote connection support
        init_logger.info("Initializing MCP server with remote connection support")
        server = FastMCP(
            "AI Agnostic Memory Layer",
            host=server_config.host,
            port=server_config.port,
            log_level=server_config.log_level.upper()
        )
        
        # Register MCP tools with authentication middleware
        init_logger.info("Registering MCP tools with authentication middleware")
        register_tools(server, server_config)
        
        # Log connection configuration
        init_logger.info(
            f"Server configured for connections on {server_config.host}:{server_config.port}",
            extra={
                'operation': 'connection_config',
                'host': server_config.host,
                'port': server_config.port,
                'supports_local': True,
                'supports_remote': True
            }
        )
        
        # Log authentication configuration
        if server_config.api_key:
            init_logger.info(
                "API key authentication enabled for remote connections",
                extra={
                    'operation': 'auth_config',
                    'auth_enabled': True
                }
            )
        else:
            init_logger.warning(
                "API key authentication is not configured - remote connections will not require authentication",
                extra={
                    'operation': 'auth_config',
                    'auth_enabled': False
                }
            )
        
        init_logger.info(
            "AIAML MCP server initialized successfully",
            extra={
                'operation': 'server_init',
                'version': '1.0.0',
                'features': {
                    'git_sync': server_config.enable_git_sync,
                    'authentication': server_config.api_key is not None,
                    'memory_dir': str(server_config.memory_dir),
                    'local_connections': True,
                    'remote_connections': True,
                    'multi_client': True,
                    'host': server_config.host,
                    'port': server_config.port
                }
            }
        )
        
        return server
        
    except Exception as e:
        # Use basic logging if our logging setup failed
        if 'init_logger' not in locals():
            logging.basicConfig(level=logging.ERROR)
            init_logger = logging.getLogger('aiaml.init')
        
        init_logger.critical(f"Server initialization failed: {e}", exc_info=True)
        raise


def start_connection_monitoring():
    """Start background thread for connection monitoring and logging."""
    def monitor_connections():
        monitor_logger = logging.getLogger('aiaml.connection_monitor')
        
        while True:
            try:
                # Log connection summary every 5 minutes
                time.sleep(300)  # 5 minutes
                connection_manager.log_connection_summary()
                
            except Exception as e:
                monitor_logger.error(f"Connection monitoring error: {e}")
                time.sleep(60)  # Wait 1 minute before retrying
    
    # Start monitoring thread as daemon so it doesn't prevent shutdown
    monitor_thread = threading.Thread(target=monitor_connections, daemon=True)
    monitor_thread.start()
    
    logging.getLogger('aiaml.init').info("Connection monitoring started")


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


def run_server_with_transport(server: FastMCP, config: Config, startup_logger: logging.Logger):
    """Run the server with appropriate transport based on configuration and connection monitoring."""
    # Start connection monitoring
    start_connection_monitoring()
    
    # Start file maintenance
    start_file_maintenance()
    
    # Determine transport mode based on host configuration
    if config.host == "127.0.0.1" or config.host == "localhost":
        # Local-only configuration - use stdio for compatibility
        startup_logger.info("Starting server in local mode (stdio transport)")
        startup_logger.info("Server will accept local MCP connections via stdio")
        startup_logger.info("Background services: Connection monitoring and file maintenance active")
        server.run(transport="stdio")
    else:
        # Remote configuration - use SSE transport for HTTP-based connections
        startup_logger.info(f"Starting server in remote mode (SSE transport) on {config.host}:{config.port}")
        startup_logger.info("Server will accept both local and remote MCP connections")
        startup_logger.info(f"Remote clients can connect to: http://{config.host}:{config.port}/sse")
        startup_logger.info("Background services: Connection monitoring and file maintenance active")
        server.run(transport="sse")


def main():
    """Main entry point for the AIAML server package with comprehensive startup validation and multi-client support."""
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
        startup_logger.info("Version: 1.0.0")
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
        
        # Initialize server with enhanced configuration
        startup_logger.info("Initializing server with remote connection support...")
        server = initialize_server()
        
        # Load configuration for transport selection
        config = load_configuration()
        
        startup_logger.info("=" * 60)
        startup_logger.info("Server startup completed successfully!")
        startup_logger.info("Multi-client connection support enabled")
        
        # Log connection information
        if config.host == "127.0.0.1" or config.host == "localhost":
            startup_logger.info("Local connections: stdio transport")
        else:
            startup_logger.info(f"Remote connections: http://{config.host}:{config.port}/sse")
            startup_logger.info("Local connections: also supported via stdio")
        
        if config.api_key:
            startup_logger.info("Authentication: API key required for remote connections")
        else:
            startup_logger.warning("Authentication: No API key configured (not recommended for remote access)")
        
        startup_logger.info("Ready to accept MCP connections...")
        startup_logger.info("=" * 60)
        
        # Start the server with appropriate transport
        run_server_with_transport(server, config, startup_logger)
        
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