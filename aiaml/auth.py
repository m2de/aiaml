"""Authentication and connection handling for AIAML."""

import logging
import socket
import ipaddress
import functools
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Callable, Tuple, Set
from datetime import datetime

from .config import Config
from .errors import error_handler, ErrorResponse


@dataclass
class ConnectionInfo:
    """Connection metadata for authentication and logging."""
    is_local: bool
    remote_address: Optional[str] = None
    api_key: Optional[str] = None
    user_agent: Optional[str] = None
    connection_type: str = field(init=False)
    connection_id: str = field(default_factory=lambda: f"conn_{int(time.time() * 1000)}")
    connected_at: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """Set connection type based on is_local flag."""
        self.connection_type = "local" if self.is_local else "remote"


class ConnectionManager:
    """Manages active connections and provides monitoring capabilities."""
    
    def __init__(self):
        self._active_connections: Dict[str, ConnectionInfo] = {}
        self._connection_stats = {
            'total_connections': 0,
            'active_connections': 0,
            'local_connections': 0,
            'remote_connections': 0,
            'failed_authentications': 0
        }
        self._lock = threading.Lock()
        self._logger = logging.getLogger('aiaml.connection_manager')
    
    def add_connection(self, connection_info: ConnectionInfo) -> None:
        """Add a new active connection."""
        with self._lock:
            self._active_connections[connection_info.connection_id] = connection_info
            self._connection_stats['total_connections'] += 1
            self._connection_stats['active_connections'] = len(self._active_connections)
            
            if connection_info.is_local:
                self._connection_stats['local_connections'] += 1
            else:
                self._connection_stats['remote_connections'] += 1
            
            self._logger.info(
                f"New {connection_info.connection_type} connection established",
                extra={
                    'operation': 'connection_established',
                    'connection_id': connection_info.connection_id,
                    'connection_type': connection_info.connection_type,
                    'remote_address': connection_info.remote_address,
                    'user_agent': connection_info.user_agent,
                    'active_connections': self._connection_stats['active_connections']
                }
            )
    
    def remove_connection(self, connection_id: str) -> None:
        """Remove an active connection."""
        with self._lock:
            if connection_id in self._active_connections:
                connection_info = self._active_connections.pop(connection_id)
                self._connection_stats['active_connections'] = len(self._active_connections)
                
                self._logger.info(
                    f"{connection_info.connection_type.title()} connection closed",
                    extra={
                        'operation': 'connection_closed',
                        'connection_id': connection_id,
                        'connection_type': connection_info.connection_type,
                        'duration_seconds': (datetime.now() - connection_info.connected_at).total_seconds(),
                        'active_connections': self._connection_stats['active_connections']
                    }
                )
    
    def record_failed_authentication(self) -> None:
        """Record a failed authentication attempt."""
        with self._lock:
            self._connection_stats['failed_authentications'] += 1
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get current connection statistics."""
        with self._lock:
            return self._connection_stats.copy()
    
    def get_active_connections(self) -> Dict[str, ConnectionInfo]:
        """Get all active connections."""
        with self._lock:
            return self._active_connections.copy()
    
    def log_connection_summary(self) -> None:
        """Log a summary of connection statistics."""
        stats = self.get_connection_stats()
        self._logger.info(
            "Connection summary",
            extra={
                'operation': 'connection_summary',
                **stats
            }
        )


# Global connection manager instance
connection_manager = ConnectionManager()


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


def authenticate_connection(connection_info: ConnectionInfo, server_config: Config) -> Tuple[bool, Optional[ErrorResponse]]:
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
    Create authentication middleware wrapper for MCP tools with connection monitoring.
    
    Args:
        server_config: Server configuration containing API key
        
    Returns:
        Decorator function for wrapping MCP tools with authentication
    """
    auth_logger = logging.getLogger('aiaml.auth')
    
    def authenticate_tool(func: Callable) -> Callable:
        """
        Decorator to add authentication to MCP tool functions.
        
        Args:
            func: The MCP tool function to wrap
            
        Returns:
            Wrapped function with authentication and connection monitoring
        """
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Log tool access for monitoring
            auth_logger.debug(
                f"Tool '{func.__name__}' accessed",
                extra={
                    'operation': 'tool_access',
                    'tool_name': func.__name__,
                    'args_count': len(args),
                    'kwargs_count': len(kwargs)
                }
            )
            
            # For MCP tools, authentication is handled at the transport level
            # This middleware provides logging and monitoring capabilities
            try:
                result = func(*args, **kwargs)
                
                # Log successful tool execution
                auth_logger.debug(
                    f"Tool '{func.__name__}' executed successfully",
                    extra={
                        'operation': 'tool_success',
                        'tool_name': func.__name__
                    }
                )
                
                return result
                
            except Exception as e:
                # Log tool execution errors
                auth_logger.error(
                    f"Tool '{func.__name__}' execution failed: {e}",
                    extra={
                        'operation': 'tool_error',
                        'tool_name': func.__name__,
                        'error': str(e)
                    }
                )
                raise
        
        return wrapper
    
    return authenticate_tool


def log_authentication_attempt(success: bool, connection_info: Dict[str, Any]) -> None:
    """Log authentication attempts for security monitoring."""
    auth_logger = logging.getLogger('aiaml.auth')
    
    log_data = {
        'operation': 'authentication_attempt',
        'success': success,
        'connection_type': connection_info.get('connection_type', 'unknown'),
        'remote_address': connection_info.get('remote_address'),
        'user_agent': connection_info.get('user_agent'),
        'timestamp': connection_info.get('timestamp')
    }
    
    # Add warning context if present
    if 'warning' in connection_info:
        log_data['warning'] = connection_info['warning']
    
    if success:
        auth_logger.info(
            f"Authentication successful for {connection_info.get('connection_type', 'unknown')} connection",
            extra=log_data
        )
    else:
        auth_logger.warning(
            f"Authentication failed for {connection_info.get('connection_type', 'unknown')} connection",
            extra=log_data
        )