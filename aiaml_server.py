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
from enum import Enum
import socket
import ipaddress


class ErrorCategory(Enum):
    """Categories of errors for structured error handling."""
    AUTHENTICATION = "authentication"
    MEMORY_OPERATION = "memory_operation"
    GIT_SYNC = "git_sync"
    CONFIGURATION = "configuration"
    FILE_IO = "file_io"
    VALIDATION = "validation"
    NETWORK = "network"
    SYSTEM = "system"


@dataclass
class ErrorResponse:
    """Standardized error response format."""
    error: str
    error_code: str
    message: str
    timestamp: str
    category: str
    context: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error response to dictionary format."""
        result = {
            "error": self.error,
            "error_code": self.error_code,
            "message": self.message,
            "timestamp": self.timestamp,
            "category": self.category
        }
        if self.context:
            result["context"] = self.context
        return result


class ErrorHandler:
    """Enhanced error handling framework with categorized error handling."""
    
    def __init__(self):
        self.logger = logging.getLogger('aiaml.error_handler')
    
    def handle_authentication_error(self, error: Exception, context: Dict[str, Any] = None) -> ErrorResponse:
        """Handle authentication errors with appropriate responses."""
        context = context or {}
        
        # Determine specific error code based on error type and context
        if "invalid" in str(error).lower() or "unauthorized" in str(error).lower():
            error_code = "AUTH_INVALID_KEY"
            message = "The provided API key is invalid"
        elif "missing" in str(error).lower() or "required" in str(error).lower():
            error_code = "AUTH_MISSING_KEY"
            message = "API key is required for remote connections"
        elif "expired" in str(error).lower():
            error_code = "AUTH_EXPIRED_KEY"
            message = "The provided API key has expired"
        else:
            error_code = "AUTH_GENERAL_ERROR"
            message = f"Authentication failed: {str(error)}"
        
        error_response = ErrorResponse(
            error="Authentication failed",
            error_code=error_code,
            message=message,
            timestamp=datetime.now().isoformat(),
            category=ErrorCategory.AUTHENTICATION.value,
            context=context
        )
        
        # Log the authentication error
        self.logger.error(
            f"Authentication error: {message}",
            extra={
                'operation': 'auth_error',
                'error_code': error_code,
                'connection_type': context.get('connection_type'),
                'remote_address': context.get('remote_address')
            }
        )
        
        return error_response
    
    def handle_memory_error(self, error: Exception, context: Dict[str, Any] = None) -> ErrorResponse:
        """Handle memory operation errors gracefully."""
        context = context or {}
        
        # Determine specific error code based on error type
        if isinstance(error, FileNotFoundError):
            error_code = "MEMORY_NOT_FOUND"
            message = f"Memory file not found: {context.get('memory_id', 'unknown')}"
        elif isinstance(error, PermissionError):
            error_code = "MEMORY_PERMISSION_DENIED"
            message = "Permission denied accessing memory file"
        elif isinstance(error, UnicodeDecodeError):
            error_code = "MEMORY_ENCODING_ERROR"
            message = "Memory file has encoding issues and cannot be read"
        elif "corrupted" in str(error).lower() or "invalid" in str(error).lower():
            error_code = "MEMORY_CORRUPTED"
            message = "Memory file appears to be corrupted"
        elif isinstance(error, OSError):
            error_code = "MEMORY_IO_ERROR"
            message = f"File system error: {str(error)}"
        else:
            error_code = "MEMORY_GENERAL_ERROR"
            message = f"Memory operation failed: {str(error)}"
        
        error_response = ErrorResponse(
            error="Memory operation failed",
            error_code=error_code,
            message=message,
            timestamp=datetime.now().isoformat(),
            category=ErrorCategory.MEMORY_OPERATION.value,
            context=context
        )
        
        # Log the memory error
        self.logger.error(
            f"Memory operation error: {message}",
            extra={
                'operation': 'memory_error',
                'error_code': error_code,
                'memory_id': context.get('memory_id'),
                'file_path': context.get('file_path'),
                'user': context.get('user')
            }
        )
        
        return error_response
    
    def handle_git_error(self, error: Exception, context: Dict[str, Any] = None) -> ErrorResponse:
        """Handle Git sync errors without affecting main operations."""
        context = context or {}
        
        # Determine specific error code based on error type
        if isinstance(error, subprocess.CalledProcessError):
            if error.returncode == 128:
                error_code = "GIT_REPOSITORY_ERROR"
                message = "Git repository configuration error"
            elif error.returncode == 1:
                error_code = "GIT_COMMAND_ERROR"
                message = "Git command execution failed"
            else:
                error_code = "GIT_PROCESS_ERROR"
                message = f"Git process failed with return code {error.returncode}"
        elif isinstance(error, FileNotFoundError):
            error_code = "GIT_NOT_INSTALLED"
            message = "Git is not installed or not found in PATH"
        elif "network" in str(error).lower() or "connection" in str(error).lower():
            error_code = "GIT_NETWORK_ERROR"
            message = "Network error during Git synchronization"
        elif "permission" in str(error).lower() or "access" in str(error).lower():
            error_code = "GIT_PERMISSION_ERROR"
            message = "Permission denied during Git operation"
        else:
            error_code = "GIT_GENERAL_ERROR"
            message = f"Git synchronization failed: {str(error)}"
        
        error_response = ErrorResponse(
            error="Git synchronization failed",
            error_code=error_code,
            message=message,
            timestamp=datetime.now().isoformat(),
            category=ErrorCategory.GIT_SYNC.value,
            context=context
        )
        
        # Log the Git error (as warning since it doesn't affect main operations)
        self.logger.warning(
            f"Git sync error: {message}",
            extra={
                'operation': 'git_error',
                'error_code': error_code,
                'memory_id': context.get('memory_id'),
                'git_command': context.get('git_command'),
                'return_code': getattr(error, 'returncode', None)
            }
        )
        
        return error_response
    
    def handle_configuration_error(self, error: Exception, context: Dict[str, Any] = None) -> ErrorResponse:
        """Handle configuration errors with fallbacks."""
        context = context or {}
        
        # Determine specific error code based on error type
        if "validation" in str(error).lower():
            error_code = "CONFIG_VALIDATION_ERROR"
            message = f"Configuration validation failed: {str(error)}"
        elif "missing" in str(error).lower() or "required" in str(error).lower():
            error_code = "CONFIG_MISSING_VALUE"
            message = f"Required configuration value missing: {str(error)}"
        elif "invalid" in str(error).lower():
            error_code = "CONFIG_INVALID_VALUE"
            message = f"Invalid configuration value: {str(error)}"
        elif isinstance(error, PermissionError):
            error_code = "CONFIG_PERMISSION_ERROR"
            message = "Permission denied accessing configuration"
        else:
            error_code = "CONFIG_GENERAL_ERROR"
            message = f"Configuration error: {str(error)}"
        
        error_response = ErrorResponse(
            error="Configuration error",
            error_code=error_code,
            message=message,
            timestamp=datetime.now().isoformat(),
            category=ErrorCategory.CONFIGURATION.value,
            context=context
        )
        
        # Log the configuration error
        self.logger.error(
            f"Configuration error: {message}",
            extra={
                'operation': 'config_error',
                'error_code': error_code,
                'config_key': context.get('config_key')
            }
        )
        
        return error_response
    
    def handle_validation_error(self, error: Exception, context: Dict[str, Any] = None) -> ErrorResponse:
        """Handle input validation errors."""
        context = context or {}
        
        # Determine specific error code based on error type
        if "memory_id" in str(error).lower():
            error_code = "VALIDATION_INVALID_MEMORY_ID"
            message = "Invalid memory ID format"
        elif "keywords" in str(error).lower():
            error_code = "VALIDATION_INVALID_KEYWORDS"
            message = "Invalid keywords provided"
        elif "topics" in str(error).lower():
            error_code = "VALIDATION_INVALID_TOPICS"
            message = "Invalid topics format"
        elif "content" in str(error).lower():
            error_code = "VALIDATION_INVALID_CONTENT"
            message = "Invalid content provided"
        else:
            error_code = "VALIDATION_GENERAL_ERROR"
            message = f"Input validation failed: {str(error)}"
        
        error_response = ErrorResponse(
            error="Validation error",
            error_code=error_code,
            message=message,
            timestamp=datetime.now().isoformat(),
            category=ErrorCategory.VALIDATION.value,
            context=context
        )
        
        # Log the validation error
        self.logger.warning(
            f"Validation error: {message}",
            extra={
                'operation': 'validation_error',
                'error_code': error_code,
                'field': context.get('field'),
                'value': context.get('value')
            }
        )
        
        return error_response
    
    def handle_general_error(self, error: Exception, category: ErrorCategory, context: Dict[str, Any] = None) -> ErrorResponse:
        """Handle general errors with appropriate categorization."""
        context = context or {}
        
        error_code = f"{category.value.upper()}_GENERAL_ERROR"
        message = f"{category.value.replace('_', ' ').title()} error: {str(error)}"
        
        error_response = ErrorResponse(
            error=f"{category.value.replace('_', ' ').title()} failed",
            error_code=error_code,
            message=message,
            timestamp=datetime.now().isoformat(),
            category=category.value,
            context=context
        )
        
        # Log the general error
        self.logger.error(
            f"General error in {category.value}: {message}",
            extra={
                'operation': f'{category.value}_error',
                'error_code': error_code,
                'error_type': type(error).__name__
            }
        )
        
        return error_response
    
    def create_success_response(self, operation: str, data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Create a standardized success response."""
        response = {
            "success": True,
            "operation": operation,
            "timestamp": datetime.now().isoformat(),
            "data": data
        }
        
        if context:
            response["context"] = context
        
        return response


# Initialize global error handler
error_handler = ErrorHandler()


def parse_memory_file_safe(file_path: Path) -> Optional[Dict[str, Any]]:
    """Parse a memory file with comprehensive error handling and graceful recovery."""
    try:
        return parse_memory_file(file_path)
    except Exception as e:
        # Handle corrupted memory files gracefully
        error_response = error_handler.handle_memory_error(e, {
            'file_path': str(file_path),
            'operation': 'parse_memory_file_safe'
        })
        
        # Log the error but continue processing other files
        logger = logging.getLogger('aiaml.memory_recovery')
        logger.warning(
            f"Skipping corrupted memory file {file_path.name}: {error_response.message}",
            extra={
                'operation': 'memory_file_recovery',
                'file_path': str(file_path),
                'error_code': error_response.error_code
            }
        )
        
        return None


def validate_memory_input(agent: str, user: str, topics: List[str], content: str) -> Optional[ErrorResponse]:
    """Validate memory input parameters."""
    try:
        # Validate agent
        if not agent or not isinstance(agent, str) or len(agent.strip()) == 0:
            raise ValueError("Agent name is required and must be a non-empty string")
        
        # Validate user
        if not user or not isinstance(user, str) or len(user.strip()) == 0:
            raise ValueError("User identifier is required and must be a non-empty string")
        
        # Validate topics
        if not isinstance(topics, list):
            raise ValueError("Topics must be a list")
        
        for topic in topics:
            if not isinstance(topic, str) or len(topic.strip()) == 0:
                raise ValueError("Each topic must be a non-empty string")
        
        # Validate content
        if not content or not isinstance(content, str) or len(content.strip()) == 0:
            raise ValueError("Content is required and must be a non-empty string")
        
        # Additional validation rules
        if len(agent.strip()) > 50:
            raise ValueError("Agent name must be 50 characters or less")
        
        if len(user.strip()) > 50:
            raise ValueError("User identifier must be 50 characters or less")
        
        if len(topics) > 20:
            raise ValueError("Maximum 20 topics allowed")
        
        for topic in topics:
            if len(topic.strip()) > 30:
                raise ValueError("Each topic must be 30 characters or less")
        
        if len(content.strip()) > 100000:  # 100KB limit
            raise ValueError("Content must be 100,000 characters or less")
        
        return None
        
    except ValueError as e:
        return error_handler.handle_validation_error(e, {
            'agent': agent,
            'user': user,
            'topics_count': len(topics) if isinstance(topics, list) else 0,
            'content_length': len(content) if isinstance(content, str) else 0
        })


def validate_search_input(keywords: List[str]) -> Optional[ErrorResponse]:
    """Validate search input parameters."""
    try:
        # Validate keywords
        if not isinstance(keywords, list):
            raise ValueError("Keywords must be a list")
        
        if len(keywords) == 0:
            raise ValueError("At least one keyword is required")
        
        if len(keywords) > 10:
            raise ValueError("Maximum 10 keywords allowed")
        
        for keyword in keywords:
            if not isinstance(keyword, str) or len(keyword.strip()) == 0:
                raise ValueError("Each keyword must be a non-empty string")
            
            if len(keyword.strip()) > 50:
                raise ValueError("Each keyword must be 50 characters or less")
        
        return None
        
    except ValueError as e:
        return error_handler.handle_validation_error(e, {
            'keywords_count': len(keywords) if isinstance(keywords, list) else 0,
            'keywords': keywords if isinstance(keywords, list) else None
        })


def validate_recall_input(memory_ids: List[str]) -> Optional[ErrorResponse]:
    """Validate recall input parameters."""
    try:
        # Validate memory_ids
        if not isinstance(memory_ids, list):
            raise ValueError("Memory IDs must be a list")
        
        if len(memory_ids) == 0:
            raise ValueError("At least one memory ID is required")
        
        if len(memory_ids) > 50:
            raise ValueError("Maximum 50 memory IDs allowed")
        
        for memory_id in memory_ids:
            if not isinstance(memory_id, str) or len(memory_id.strip()) == 0:
                raise ValueError("Each memory ID must be a non-empty string")
            
            # Validate memory ID format (8 character alphanumeric)
            if not re.match(r'^[a-f0-9]{8}$', memory_id.strip()):
                raise ValueError(f"Invalid memory ID format: {memory_id}")
        
        return None
        
    except ValueError as e:
        return error_handler.handle_validation_error(e, {
            'memory_ids_count': len(memory_ids) if isinstance(memory_ids, list) else 0,
            'memory_ids': memory_ids if isinstance(memory_ids, list) else None
        })


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


@dataclass
class ConnectionInfo:
    """Connection metadata for authentication and logging."""
    is_local: bool
    remote_address: Optional[str] = None
    api_key: Optional[str] = None
    user_agent: Optional[str] = None
    connection_type: str = field(init=False)
    
    def __post_init__(self):
        """Set connection type based on is_local flag."""
        self.connection_type = "local" if self.is_local else "remote"


def is_local_connection(connection_info: Dict[str, Any]) -> bool:
    """
    Determine if a connection is local or remote based on connection metadata.
    
    Args:
        connection_info: Dictionary containing connection metadata
        
    Returns:
        True if connection is local, False if remote
    """
    auth_logger = logging.getLogger('aiaml.auth')
    
    try:
        # Extract connection details
        remote_address = connection_info.get('remote_address', '')
        client_host = connection_info.get('client_host', '')
        peer_name = connection_info.get('peer_name', '')
        
        # Check for various indicators of local connection
        local_indicators = [
            '127.0.0.1',
            'localhost',
            '::1',  # IPv6 localhost
            '0.0.0.0',  # Sometimes used for local binding
        ]
        
        # Check remote address
        if remote_address:
            # Parse IP address if possible
            try:
                ip_str = remote_address.split(':')[0]  # Remove port if present
                ip = ipaddress.ip_address(ip_str)
                
                # Check if it's a loopback address
                if ip.is_loopback:
                    auth_logger.debug(f"Connection identified as local: loopback address {ip}")
                    return True
                
                # Check for special local addresses
                if ip_str in ['0.0.0.0']:
                    auth_logger.debug(f"Connection identified as local: special local address {ip}")
                    return True
                
                # For authentication purposes, only loopback addresses are considered truly local
                # Private network addresses should still require authentication for security
                auth_logger.debug(f"Connection identified as remote: non-loopback address {ip}")
                return False
                    
            except ValueError:
                # Not a valid IP address, check string patterns
                remote_lower = remote_address.lower()
                for indicator in local_indicators:
                    if indicator in remote_lower:
                        auth_logger.debug(f"Connection identified as local: address contains {indicator}")
                        return True
        
        # Check client host
        if client_host:
            client_lower = client_host.lower()
            for indicator in local_indicators:
                if indicator in client_lower:
                    auth_logger.debug(f"Connection identified as local: client host contains {indicator}")
                    return True
        
        # Check peer name
        if peer_name:
            peer_lower = peer_name.lower()
            for indicator in local_indicators:
                if indicator in peer_lower:
                    auth_logger.debug(f"Connection identified as local: peer name contains {indicator}")
                    return True
        
        # If no connection info is available, assume local (for backward compatibility)
        if not remote_address and not client_host and not peer_name:
            auth_logger.debug("No connection info available, assuming local connection")
            return True
        
        # Default to remote if we have connection info but no local indicators
        auth_logger.debug(f"Connection identified as remote: {remote_address or client_host or peer_name}")
        return False
        
    except Exception as e:
        # Log error but default to local for safety
        auth_logger.warning(f"Error determining connection type, defaulting to local: {e}")
        return True


def validate_api_key(provided_key: str, configured_key: str) -> bool:
    """
    Validate provided API key against configured key.
    
    Args:
        provided_key: API key provided by the client
        configured_key: API key configured on the server
        
    Returns:
        True if keys match, False otherwise
    """
    if not provided_key or not configured_key:
        return False
    
    # Use constant-time comparison to prevent timing attacks
    try:
        import hmac
        return hmac.compare_digest(provided_key.strip(), configured_key.strip())
    except Exception:
        # Fallback to regular comparison if hmac fails
        return provided_key.strip() == configured_key.strip()


def authenticate_connection(connection_info: ConnectionInfo, server_config: Config) -> tuple[bool, Optional[ErrorResponse]]:
    """
    Authenticate a connection based on type and credentials.
    
    Args:
        connection_info: Connection metadata
        server_config: Server configuration
        
    Returns:
        Tuple of (success: bool, error_response: Optional[ErrorResponse])
    """
    auth_logger = logging.getLogger('aiaml.auth')
    
    try:
        # Local connections bypass authentication
        if connection_info.is_local:
            auth_logger.debug("Local connection detected, bypassing authentication")
            log_authentication_attempt(True, {
                'connection_type': connection_info.connection_type,
                'remote_address': connection_info.remote_address,
                'user_agent': connection_info.user_agent
            })
            return True, None
        
        # Remote connections require API key if configured
        if server_config.api_key:
            if not connection_info.api_key:
                error = ValueError("API key is required for remote connections")
                error_response = error_handler.handle_authentication_error(error, {
                    'connection_type': connection_info.connection_type,
                    'remote_address': connection_info.remote_address,
                    'user_agent': connection_info.user_agent,
                    'reason': 'missing_api_key'
                })
                
                log_authentication_attempt(False, {
                    'connection_type': connection_info.connection_type,
                    'remote_address': connection_info.remote_address,
                    'user_agent': connection_info.user_agent
                })
                
                return False, error_response
            
            # Validate the provided API key
            if not validate_api_key(connection_info.api_key, server_config.api_key):
                error = ValueError("Invalid API key provided")
                error_response = error_handler.handle_authentication_error(error, {
                    'connection_type': connection_info.connection_type,
                    'remote_address': connection_info.remote_address,
                    'user_agent': connection_info.user_agent,
                    'reason': 'invalid_api_key'
                })
                
                log_authentication_attempt(False, {
                    'connection_type': connection_info.connection_type,
                    'remote_address': connection_info.remote_address,
                    'user_agent': connection_info.user_agent
                })
                
                return False, error_response
            
            # API key is valid
            auth_logger.info(f"Remote connection authenticated successfully from {connection_info.remote_address}")
            log_authentication_attempt(True, {
                'connection_type': connection_info.connection_type,
                'remote_address': connection_info.remote_address,
                'user_agent': connection_info.user_agent
            })
            return True, None
        
        else:
            # No API key configured, allow remote connections (not recommended for production)
            auth_logger.warning("Remote connection allowed without authentication (no API key configured)")
            log_authentication_attempt(True, {
                'connection_type': connection_info.connection_type,
                'remote_address': connection_info.remote_address,
                'user_agent': connection_info.user_agent,
                'warning': 'no_auth_configured'
            })
            return True, None
            
    except Exception as e:
        # Handle unexpected authentication errors
        error_response = error_handler.handle_authentication_error(e, {
            'connection_type': connection_info.connection_type,
            'remote_address': connection_info.remote_address,
            'user_agent': connection_info.user_agent,
            'reason': 'unexpected_error'
        })
        
        log_authentication_attempt(False, {
            'connection_type': connection_info.connection_type,
            'remote_address': connection_info.remote_address,
            'user_agent': connection_info.user_agent
        })
        
        return False, error_response


def create_authentication_middleware(server_config: Config):
    """
    Create authentication middleware wrapper for MCP tools.
    
    Args:
        server_config: Server configuration containing API key
        
    Returns:
        Decorator function for wrapping MCP tools with authentication
    """
    def authenticate_tool(func: Callable) -> Callable:
        """
        Decorator to add authentication to MCP tool functions.
        
        Args:
            func: The MCP tool function to wrap
            
        Returns:
            Wrapped function with authentication
        """
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            auth_logger = logging.getLogger('aiaml.auth')
            
            try:
                # Extract connection information from the request context
                # In FastMCP, connection information is available in the request context
                # We'll extract it from the first argument which should be the request object
                request = args[0] if args else None
                
                # Extract connection metadata from request
                connection_data = {}
                
                # Check if we have a request object with connection info
                if request and hasattr(request, 'context') and hasattr(request.context, 'connection_info'):
                    # Extract connection info from FastMCP request context
                    conn_info = request.context.connection_info
                    connection_data = {
                        'remote_address': getattr(conn_info, 'remote_address', ''),
                        'client_host': getattr(conn_info, 'client_host', ''),
                        'peer_name': getattr(conn_info, 'peer_name', ''),
                        'user_agent': getattr(conn_info, 'user_agent', ''),
                    }
                    
                    # Extract API key from headers if available
                    if hasattr(request.context, 'headers'):
                        connection_data['api_key'] = request.context.headers.get('X-API-Key', '')
                else:
                    # Fallback to environment variables for testing or non-FastMCP contexts
                    connection_data = {
                        'remote_address': os.environ.get('MCP_CLIENT_ADDRESS', ''),
                        'client_host': os.environ.get('MCP_CLIENT_HOST', ''),
                        'peer_name': os.environ.get('MCP_PEER_NAME', ''),
                        'user_agent': os.environ.get('MCP_USER_AGENT', ''),
                        'api_key': os.environ.get('MCP_API_KEY', '')
                    }
                
                # Determine if connection is local
                is_local = is_local_connection(connection_data)
                
                # Create connection info object
                connection_info = ConnectionInfo(
                    is_local=is_local,
                    remote_address=connection_data.get('remote_address'),
                    api_key=connection_data.get('api_key'),
                    user_agent=connection_data.get('user_agent')
                )
                
                # Log connection attempt
                auth_logger.info(
                    f"Connection attempt to {func.__name__}",
                    extra={
                        'operation': 'connection_attempt',
                        'tool': func.__name__,
                        'connection_type': connection_info.connection_type,
                        'remote_address': connection_info.remote_address,
                        'user_agent': connection_info.user_agent
                    }
                )
                
                # Authenticate the connection
                auth_success, auth_error = authenticate_connection(connection_info, server_config)
                
                if not auth_success:
                    auth_logger.warning(f"Authentication failed for tool {func.__name__}")
                    return auth_error.to_dict() if auth_error else {"error": "Authentication failed"}
                
                # Authentication successful, proceed with the original function
                auth_logger.debug(f"Authentication successful for tool {func.__name__}")
                return func(*args, **kwargs)
                
            except Exception as e:
                # Handle unexpected errors in authentication middleware
                auth_logger.error(f"Authentication middleware error for tool {func.__name__}: {e}")
                error_response = error_handler.handle_authentication_error(e, {
                    'tool_name': func.__name__,
                    'operation': 'auth_middleware'
                })
                return error_response.to_dict()
        
        return wrapper
    
    return authenticate_tool


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


# Global configuration - will be loaded in initialize_server() or at module level for backward compatibility
config = None
logger = None

# Load configuration for backward compatibility when imported
try:
    config = load_configuration()
    validation_issues = validate_configuration(config)
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

# Initialize MCP server for backward compatibility
# This will be replaced by the enhanced initialization in main()
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
            
            # Use enhanced error handler for Git errors
            error_context = {
                'memory_id': memory_id,
                'filename': filename,
                'git_command': ' '.join(e.cmd) if e.cmd else 'unknown',
                'return_code': e.returncode,
                'stdout': e.stdout.decode() if e.stdout else '',
                'stderr': e.stderr.decode() if e.stderr else '',
                'duration_ms': round(duration_ms, 2)
            }
            
            error_response = error_handler.handle_git_error(e, error_context)
            
            git_logger.warning(
                f"Git sync failed for memory {memory_id}: {error_response.message}",
                extra={
                    'operation': 'git_sync_failed',
                    'memory_id': memory_id,
                    'duration_ms': round(duration_ms, 2),
                    'error_code': error_response.error_code,
                    'return_code': e.returncode
                }
            )
            
        except Exception as e:
            # Calculate duration for failed operation
            duration_ms = (time.time() - start_time) * 1000
            
            # Use enhanced error handler for unexpected Git errors
            error_context = {
                'memory_id': memory_id,
                'filename': filename,
                'duration_ms': round(duration_ms, 2)
            }
            
            error_response = error_handler.handle_git_error(e, error_context)
            
            git_logger.error(
                f"Unexpected error during Git sync for memory {memory_id}: {error_response.message}",
                extra={
                    'operation': 'git_sync_error',
                    'memory_id': memory_id,
                    'duration_ms': round(duration_ms, 2),
                    'error_code': error_response.error_code,
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
        memory_data = parse_memory_file_safe(memory_file)
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
        # Validate input parameters
        validation_error = validate_memory_input(agent, user, topics, content)
        if validation_error:
            return validation_error.to_dict()
        
        # Generate unique memory ID
        memory_id = generate_memory_id()
        
        # Create timestamp
        timestamp = datetime.now().isoformat()
        
        # Create memory file content
        frontmatter = f"""---
id: {memory_id}
timestamp: {timestamp}
agent: {agent.strip()}
user: {user.strip()}
topics: [{', '.join([topic.strip() for topic in topics])}]
---

{content.strip()}"""
        
        # Create filename and save
        filename = create_memory_filename(memory_id)
        file_path = MEMORY_DIR / filename
        
        # Ensure memory directory exists
        MEMORY_DIR.mkdir(exist_ok=True, parents=True)
        
        file_path.write_text(frontmatter, encoding="utf-8")
        
        # Trigger background sync to GitHub
        sync_to_github(memory_id, filename)
        
        return {
            "memory_id": memory_id,
            "message": f"Memory stored successfully with ID: {memory_id}"
        }
        
    except Exception as e:
        # Handle unexpected errors with proper error response
        error_response = error_handler.handle_memory_error(e, {
            'operation': 'remember',
            'agent': agent if isinstance(agent, str) else str(agent),
            'user': user if isinstance(user, str) else str(user),
            'topics_count': len(topics) if isinstance(topics, list) else 0,
            'content_length': len(content) if isinstance(content, str) else 0
        })
        
        return error_response.to_dict()


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
        # Validate input parameters
        validation_error = validate_search_input(keywords)
        if validation_error:
            return [validation_error.to_dict()]
        
        return search_memories(keywords)
        
    except Exception as e:
        # Handle unexpected errors with proper error response
        error_response = error_handler.handle_memory_error(e, {
            'operation': 'think',
            'keywords': keywords if isinstance(keywords, list) else str(keywords),
            'keywords_count': len(keywords) if isinstance(keywords, list) else 0
        })
        
        return [error_response.to_dict()]


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
    try:
        # Validate input parameters
        validation_error = validate_recall_input(memory_ids)
        if validation_error:
            return [validation_error.to_dict()]
        
        results = []
        
        for memory_id in memory_ids:
            try:
                # Find the memory file by ID
                found = False
                for memory_file in MEMORY_DIR.glob(f"*_{memory_id.strip()}.md"):
                    memory_data = parse_memory_file_safe(memory_file)
                    if memory_data and memory_data["id"] == memory_id.strip():
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
                    # Create a specific error response for not found memory
                    not_found_error = error_handler.handle_memory_error(
                        FileNotFoundError(f"Memory with ID {memory_id} not found"),
                        {
                            'memory_id': memory_id,
                            'operation': 'recall'
                        }
                    )
                    results.append(not_found_error.to_dict())
                    
            except Exception as e:
                # Handle individual memory retrieval errors
                memory_error = error_handler.handle_memory_error(e, {
                    'memory_id': memory_id,
                    'operation': 'recall_individual'
                })
                results.append(memory_error.to_dict())
        
        return results
                
    except Exception as e:
        # Handle unexpected errors with proper error response
        error_response = error_handler.handle_memory_error(e, {
            'operation': 'recall',
            'memory_ids': memory_ids if isinstance(memory_ids, list) else str(memory_ids),
            'memory_ids_count': len(memory_ids) if isinstance(memory_ids, list) else 0
        })
        
        return [error_response.to_dict()]


def initialize_server() -> FastMCP:
    """Initialize MCP server with enhanced configuration and validation."""
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
                'api_key_configured': server_config.api_key is not None
            }
        )
        
        # Create memory directory if it doesn't exist
        try:
            server_config.memory_dir.mkdir(parents=True, exist_ok=True)
            init_logger.info(
                f"Memory directory ready: {server_config.memory_dir}",
                extra={'operation': 'directory_setup'}
            )
        except Exception as e:
            init_logger.error(f"Failed to create memory directory: {e}")
            raise
        
        # Initialize Git repository if Git sync is enabled
        if server_config.enable_git_sync:
            try:
                git_repo_dir = server_config.memory_dir.parent
                git_dir = git_repo_dir / ".git"
                
                if not git_dir.exists():
                    init_logger.info("Initializing Git repository for memory synchronization")
                    subprocess.run(
                        ["git", "init"],
                        check=True,
                        capture_output=True,
                        cwd=git_repo_dir
                    )
                    init_logger.info("Git repository initialized successfully")
                
                # Configure Git remote if specified
                if server_config.git_remote_url:
                    try:
                        # Check if remote already exists
                        result = subprocess.run(
                            ["git", "remote", "get-url", "origin"],
                            capture_output=True,
                            cwd=git_repo_dir,
                            text=True
                        )
                        
                        if result.returncode != 0:
                            # Add remote if it doesn't exist
                            subprocess.run(
                                ["git", "remote", "add", "origin", server_config.git_remote_url],
                                check=True,
                                capture_output=True,
                                cwd=git_repo_dir
                            )
                            init_logger.info(f"Git remote configured: {server_config.git_remote_url}")
                        else:
                            init_logger.debug("Git remote already configured")
                            
                    except subprocess.CalledProcessError as e:
                        init_logger.warning(f"Failed to configure Git remote: {e}")
                        
            except subprocess.CalledProcessError as e:
                init_logger.warning(f"Git repository initialization failed: {e}")
            except FileNotFoundError:
                init_logger.warning("Git command not found - Git sync will be disabled")
        
        # Initialize the MCP server
        server = FastMCP("AI Agnostic Memory Layer")
        
        # Register MCP tools with authentication middleware
        init_logger.info("Registering MCP tools with authentication middleware")
        register_tools(server, server_config)
        
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
                    'remote_connections': True
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


def initialize_server() -> FastMCP:
    """Initialize MCP server with enhanced configuration and validation."""
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
                'api_key_configured': server_config.api_key is not None
            }
        )
        
        # Create memory directory if it doesn't exist
        try:
            server_config.memory_dir.mkdir(parents=True, exist_ok=True)
            init_logger.info(
                f"Memory directory ready: {server_config.memory_dir}",
                extra={'operation': 'directory_setup'}
            )
        except Exception as e:
            init_logger.error(f"Failed to create memory directory: {e}")
            raise
        
        # Initialize Git repository if Git sync is enabled
        if server_config.enable_git_sync:
            try:
                git_repo_dir = server_config.memory_dir.parent
                git_dir = git_repo_dir / ".git"
                
                if not git_dir.exists():
                    init_logger.info("Initializing Git repository for memory synchronization")
                    subprocess.run(
                        ["git", "init"],
                        check=True,
                        capture_output=True,
                        cwd=git_repo_dir
                    )
                    init_logger.info("Git repository initialized successfully")
                
                # Configure Git remote if specified
                if server_config.git_remote_url:
                    try:
                        # Check if remote already exists
                        result = subprocess.run(
                            ["git", "remote", "get-url", "origin"],
                            capture_output=True,
                            cwd=git_repo_dir,
                            text=True
                        )
                        
                        if result.returncode != 0:
                            # Add remote if it doesn't exist
                            subprocess.run(
                                ["git", "remote", "add", "origin", server_config.git_remote_url],
                                check=True,
                                capture_output=True,
                                cwd=git_repo_dir
                            )
                            init_logger.info(f"Git remote configured: {server_config.git_remote_url}")
                        else:
                            init_logger.debug("Git remote already configured")
                            
                    except subprocess.CalledProcessError as e:
                        init_logger.warning(f"Failed to configure Git remote: {e}")
                        
            except subprocess.CalledProcessError as e:
                init_logger.warning(f"Git repository initialization failed: {e}")
            except FileNotFoundError:
                init_logger.warning("Git command not found - Git sync will be disabled")
        
        # Initialize the MCP server
        server = FastMCP("AI Agnostic Memory Layer")
        
        # Register the tools with authentication middleware
        register_tools(server, server_config)
        
        init_logger.info(
            "AIAML MCP server initialized successfully",
            extra={
                'operation': 'server_init',
                'version': '1.0.0',
                'features': {
                    'git_sync': server_config.enable_git_sync,
                    'authentication': server_config.api_key is not None,
                    'memory_dir': str(server_config.memory_dir)
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


def register_tools(server: FastMCP, server_config: Config) -> None:
    """Register MCP tools with the server instance and authentication middleware."""
    
    # Create authentication middleware
    authenticate = create_authentication_middleware(server_config)
    
    # Remove existing tools if they exist (for re-registration)
    if hasattr(server, 'tools'):
        tool_names = ['remember', 'think', 'recall']
        for name in tool_names:
            if name in server.tools:
                server.tools.pop(name, None)
    
    @server.tool()
    @authenticate
    @performance_monitor('remember')
    def remember(agent: str, user: str, topics: List[str], content: str) -> Dict[str, str]:
        """Store a new memory entry with validation and error handling."""
        try:
            # Validate input parameters
            validation_error = validate_memory_input(agent, user, topics, content)
            if validation_error:
                return validation_error.to_dict()
            
            # Generate memory ID and create filename
            memory_id = generate_memory_id()
            filename = create_memory_filename(memory_id)
            file_path = MEMORY_DIR / filename
            
            # Create memory content with metadata
            timestamp = datetime.now().isoformat()
            memory_content = f"""---
id: {memory_id}
timestamp: {timestamp}
agent: {agent}
user: {user}
topics: [{', '.join([topic.strip() for topic in topics])}]
---

{content}
"""
            
            # Store memory atomically
            try:
                # Ensure memory directory exists
                MEMORY_DIR.mkdir(parents=True, exist_ok=True)
                
                # Write to temporary file first, then rename for atomicity
                temp_file_path = file_path.with_suffix('.tmp')
                temp_file_path.write_text(memory_content, encoding='utf-8')
                temp_file_path.rename(file_path)
                
                logger.info(
                    f"Memory stored successfully: {memory_id}",
                    extra={
                        'operation': 'remember',
                        'memory_id': memory_id,
                        'user': user,
                        'agent': agent,
                        'topics_count': len(topics),
                        'content_length': len(content)
                    }
                )
                
            except Exception as e:
                # Handle file I/O errors
                error_response = error_handler.handle_memory_error(e, {
                    'memory_id': memory_id,
                    'file_path': str(file_path),
                    'operation': 'store_memory'
                })
                return error_response.to_dict()
            
            # Sync to GitHub in background (non-blocking)
            if ENABLE_GITHUB_SYNC:
                threading.Thread(
                    target=sync_to_github,
                    args=(memory_id, filename),
                    daemon=True
                ).start()
            
            return error_handler.create_success_response(
                'remember',
                {
                    'memory_id': memory_id,
                    'message': f'Memory stored successfully with ID: {memory_id}'
                },
                {
                    'filename': filename,
                    'user': user,
                    'agent': agent
                }
            )
            
        except Exception as e:
            # Handle unexpected errors
            error_response = error_handler.handle_memory_error(e, {
                'operation': 'remember',
                'user': user,
                'agent': agent,
                'topics': topics,
                'content_length': len(content) if isinstance(content, str) else 0
            })
            return error_response.to_dict()

    @server.tool()
    @authenticate
    @performance_monitor('think')
    def think(keywords: List[str]) -> List[Dict[str, Any]]:
        """Search for relevant memories by keywords with enhanced error handling."""
        try:
            # Validate input parameters
            validation_error = validate_search_input(keywords)
            if validation_error:
                return [validation_error.to_dict()]
            
            # Search for memories
            memories = []
            
            if not MEMORY_DIR.exists():
                logger.warning("Memory directory does not exist")
                return []
            
            # Process each memory file with error handling
            for file_path in MEMORY_DIR.glob("*.md"):
                try:
                    memory_data = parse_memory_file_safe(file_path)
                    if memory_data is None:
                        continue  # Skip corrupted files
                    
                    # Calculate relevance score
                    relevance_score = 0
                    search_text = f"{' '.join(memory_data.get('topics', []))} {memory_data.get('content', '')}".lower()
                    
                    for keyword in keywords:
                        keyword_lower = keyword.lower()
                        if keyword_lower in search_text:
                            # Higher score for topic matches
                            if keyword_lower in ' '.join(memory_data.get('topics', [])).lower():
                                relevance_score += 2
                            else:
                                relevance_score += 1
                    
                    if relevance_score > 0:
                        memory_data['relevance_score'] = relevance_score
                        memories.append(memory_data)
                        
                except Exception as e:
                    # Log individual file processing errors but continue
                    logger.warning(
                        f"Error processing memory file {file_path.name}: {e}",
                        extra={
                            'operation': 'think_file_processing',
                            'file_path': str(file_path),
                            'keywords': keywords
                        }
                    )
                    continue
            
            # Sort by relevance score and limit results
            memories.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
            memories = memories[:config.max_search_results]
            
            logger.info(
                f"Search completed: found {len(memories)} relevant memories",
                extra={
                    'operation': 'think',
                    'keywords': keywords,
                    'result_count': len(memories)
                }
            )
            
            return memories
            
        except Exception as e:
            # Handle unexpected errors
            error_response = error_handler.handle_memory_error(e, {
                'operation': 'think',
                'keywords': keywords
            })
            return [error_response.to_dict()]

    @server.tool()
    @authenticate
    @performance_monitor('recall')
    def recall(memory_ids: List[str]) -> List[Dict[str, Any]]:
        """Retrieve full memory details by ID with comprehensive error handling."""
        try:
            # Validate input parameters
            validation_error = validate_recall_input(memory_ids)
            if validation_error:
                return [validation_error.to_dict()]
            
            results = []
            
            if not MEMORY_DIR.exists():
                error_response = error_handler.handle_memory_error(
                    FileNotFoundError("Memory directory does not exist"),
                    {'operation': 'recall', 'memory_ids': memory_ids}
                )
                return [error_response.to_dict()]
            
            # Process each requested memory ID
            for memory_id in memory_ids:
                try:
                    found = False
                    
                    # Search for the memory file
                    for file_path in MEMORY_DIR.glob("*.md"):
                        try:
                            memory_data = parse_memory_file_safe(file_path)
                            if memory_data and memory_data.get('id') == memory_id:
                                results.append(memory_data)
                                found = True
                                break
                        except Exception as e:
                            # Log file processing errors but continue searching
                            logger.warning(
                                f"Error processing memory file {file_path.name} during recall: {e}",
                                extra={
                                    'operation': 'recall_file_processing',
                                    'file_path': str(file_path),
                                    'memory_id': memory_id
                                }
                            )
                            continue
                    
                    if not found:
                        # Create a specific error response for not found memory
                        not_found_error = error_handler.handle_memory_error(
                            FileNotFoundError(f"Memory with ID {memory_id} not found"),
                            {
                                'memory_id': memory_id,
                                'operation': 'recall'
                            }
                        )
                        results.append(not_found_error.to_dict())
                        
                except Exception as e:
                    # Handle individual memory retrieval errors
                    memory_error = error_handler.handle_memory_error(e, {
                        'memory_id': memory_id,
                        'operation': 'recall_individual'
                    })
                    results.append(memory_error.to_dict())
            
            return results
                    
        except Exception as e:
            # Handle unexpected errors with proper error response
            error_response = error_handler.handle_memory_error(e, {
                'operation': 'recall',
                'memory_ids': memory_ids if isinstance(memory_ids, list) else str(memory_ids),
                'memory_ids_count': len(memory_ids) if isinstance(memory_ids, list) else 0
            })
            
            return [error_response.to_dict()]
            
    # Log successful tool registration
    auth_logger = logging.getLogger('aiaml.auth')
    auth_logger.info(
        "MCP tools registered with authentication middleware",
        extra={
            'operation': 'register_tools',
            'tools': ['remember', 'think', 'recall'],
            'auth_enabled': server_config.api_key is not None
        }
    )


def main():
    """Main entry point for the AIAML server package with comprehensive startup validation."""
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
        import sys
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
        startup_logger.info("Initializing server...")
        server = initialize_server()
        
        startup_logger.info("=" * 60)
        startup_logger.info("Server startup completed successfully!")
        startup_logger.info("Ready to accept MCP connections...")
        startup_logger.info("=" * 60)
        
        # Start the server
        server.run()
        
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


if __name__ == "__main__":
    main()