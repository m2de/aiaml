"""Error handling framework for AIAML."""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional


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