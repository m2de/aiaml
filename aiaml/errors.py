"""Error handling framework for AIAML local-only MCP server."""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional


class ErrorCategory(Enum):
    """Categories of errors for structured error handling."""
    MEMORY_OPERATION = "memory_operation"
    GIT_SYNC = "git_sync"
    CONFIGURATION = "configuration"
    FILE_IO = "file_io"
    VALIDATION = "validation"
    SYSTEM = "system"


@dataclass
class ErrorResponse:
    """Standardized error response format for memory operations."""
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
    """Error handling framework focused on memory operations."""
    
    def __init__(self):
        self.logger = logging.getLogger('aiaml.error_handler')
    
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
            message = f"Input validation failed: {str(error)}"
        elif "keywords" in str(error).lower():
            error_code = "VALIDATION_INVALID_KEYWORDS"
            message = f"Input validation failed: {str(error)}"
        elif "topics" in str(error).lower():
            error_code = "VALIDATION_INVALID_TOPICS"
            message = f"Input validation failed: {str(error)}"
        elif "content" in str(error).lower():
            error_code = "VALIDATION_INVALID_CONTENT"
            message = f"Input validation failed: {str(error)}"
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
    
    def handle_git_sync_error(self, error: Exception, context: Dict[str, Any] = None) -> ErrorResponse:
        """Handle Git synchronization errors."""
        context = context or {}
        
        # Determine specific error code based on error type
        if "not a git repository" in str(error).lower():
            error_code = "GIT_NOT_REPOSITORY"
            message = "Git repository not initialized"
        elif "remote" in str(error).lower():
            error_code = "GIT_REMOTE_ERROR"
            message = f"Git remote operation failed: {str(error)}"
        elif "permission" in str(error).lower():
            error_code = "GIT_PERMISSION_ERROR"
            message = "Permission denied for Git operation"
        else:
            error_code = "GIT_GENERAL_ERROR"
            message = f"Git operation failed: {str(error)}"
        
        error_response = ErrorResponse(
            error="Git sync operation failed",
            error_code=error_code,
            message=message,
            timestamp=datetime.now().isoformat(),
            category=ErrorCategory.GIT_SYNC.value,
            context=context
        )
        
        # Log the Git sync error
        self.logger.warning(
            f"Git sync error: {message}",
            extra={
                'operation': 'git_sync_error',
                'error_code': error_code,
                'repository_path': context.get('repository_path')
            }
        )
        
        return error_response
    
    def handle_file_io_error(self, error: Exception, context: Dict[str, Any] = None) -> ErrorResponse:
        """Handle file I/O errors."""
        context = context or {}
        
        # Determine specific error code based on error type
        if isinstance(error, FileNotFoundError):
            error_code = "FILE_NOT_FOUND"
            message = f"File not found: {context.get('file_path', 'unknown')}"
        elif isinstance(error, PermissionError):
            error_code = "FILE_PERMISSION_DENIED"
            message = "Permission denied accessing file"
        elif isinstance(error, OSError):
            error_code = "FILE_IO_ERROR"
            message = f"File system error: {str(error)}"
        else:
            error_code = "FILE_GENERAL_ERROR"
            message = f"File operation failed: {str(error)}"
        
        error_response = ErrorResponse(
            error="File operation failed",
            error_code=error_code,
            message=message,
            timestamp=datetime.now().isoformat(),
            category=ErrorCategory.FILE_IO.value,
            context=context
        )
        
        # Log the file I/O error
        self.logger.error(
            f"File I/O error: {message}",
            extra={
                'operation': 'file_io_error',
                'error_code': error_code,
                'file_path': context.get('file_path')
            }
        )
        
        return error_response
    
    def create_success_response(self, operation: str, data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Create a standardized success response for memory operations."""
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