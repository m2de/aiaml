"""Core memory storage and retrieval operations."""

import json
import logging
import os
import tempfile
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from ..config import Config
from ..errors import ErrorResponse, error_handler, ErrorCategory
from ..file_lock import memory_file_lock
from ..platform import get_platform_info, create_secure_temp_file
# Performance monitoring removed for simplicity


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


def parse_memory_file(file_path: Path) -> Optional[Dict[str, Any]]:
    """Parse a memory file and extract metadata and content."""
    try:
        content = file_path.read_text(encoding='utf-8')
        
        # Split frontmatter and content
        if content.startswith('---\n'):
            parts = content.split('---\n', 2)
            if len(parts) >= 3:
                frontmatter_text = parts[1]
                memory_content = parts[2].strip()
                
                # Parse frontmatter as YAML-like format
                frontmatter = {}
                for line in frontmatter_text.strip().split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        key = key.strip()
                        value = value.strip()
                        
                        # Handle list values (topics)
                        if value.startswith('[') and value.endswith(']'):
                            # Parse as JSON array
                            try:
                                frontmatter[key] = json.loads(value)
                            except json.JSONDecodeError:
                                # Fallback: split by comma and clean up
                                items = value[1:-1].split(',')
                                frontmatter[key] = [item.strip().strip('"\'') for item in items if item.strip()]
                        else:
                            frontmatter[key] = value
                
                return {
                    'id': frontmatter.get('id'),
                    'timestamp': frontmatter.get('timestamp'),
                    'agent': frontmatter.get('agent'),
                    'user': frontmatter.get('user'),
                    'topics': frontmatter.get('topics', []),
                    'content': memory_content,
                    'file_path': str(file_path)
                }
        
        return None
        
    except Exception as e:
        logging.getLogger('aiaml.memory').error(f"Error parsing memory file {file_path}: {e}")
        return None


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
            f"Corrupted memory file detected: {file_path.name}: {error_response.message}",
            extra={
                'operation': 'memory_file_recovery',
                'file_path': str(file_path),
                'error_code': error_response.error_code
            }
        )
        
        # Attempt to repair the corrupted file using file manager
        try:
            from ..file_manager import get_file_manager
            from ..config import load_configuration
            
            config = load_configuration()
            file_manager = get_file_manager(config)
            
            if file_manager.repair_corrupted_file(file_path):
                logger.info(f"Successfully repaired corrupted file: {file_path.name}")
                # Try parsing again after repair
                try:
                    return parse_memory_file(file_path)
                except Exception as repair_error:
                    logger.error(f"File repair succeeded but parsing still failed: {repair_error}")
            else:
                logger.error(f"Failed to repair corrupted file: {file_path.name}")
                
        except Exception as repair_error:
            logger.error(f"Error during file repair attempt: {repair_error}")
        
        return None





def store_memory_atomic(agent: str, user: str, topics: List[str], content: str, config: Config) -> Dict[str, Any]:
    """
    Store a new memory with enhanced atomic file operations, file locking, and backup integration.
    
    This function implements:
    1. Enhanced file locking to prevent concurrent write conflicts
    2. Secure temporary file creation with proper permissions
    3. Atomic rename to ensure file consistency
    4. Automatic backup creation for existing files
    5. Comprehensive error handling and recovery mechanisms
    6. Performance monitoring and optimization tracking
    
    Args:
    agent: Name of the agent creating the memory
    user: User identifier
    topics: List of topics for the memory
    content: Memory content text
    config: Server configuration
    
    Returns:
    Dictionary with operation result
    """
    from .validation import validate_memory_input
    from ..git_sync import sync_memory_to_git
    from ..file_manager import get_file_manager
    
    logger = logging.getLogger('aiaml.memory')
    temp_file = None
    # Performance monitoring removed for simplicity
    
    try:
        # Validate input parameters
        validation_error = validate_memory_input(agent, user, topics, content)
        if validation_error:
            return validation_error.to_dict()
        
        # Generate unique memory ID and filename
        memory_id = generate_memory_id()
        filename = create_memory_filename(memory_id)
        file_path = config.files_dir / filename
        
        # Record file operation for performance tracking
        # File operation logged (performance monitoring removed)
        
        # Get file manager for backup operations
        file_manager = get_file_manager(config)
        
        # Use enhanced memory file locking
        logger.debug(f"Attempting to acquire enhanced file lock for memory storage: {memory_id}")
        
        with memory_file_lock(config, file_path, timeout=30.0) as lock:
            logger.debug(f"Enhanced file lock acquired for memory storage: {memory_id}")
            
            # Create backup if file already exists (shouldn't happen with unique IDs, but safety first)
            if file_path.exists():
                backup_path = file_manager.create_backup(file_path)
                if backup_path:
                    logger.info(f"Created backup before overwrite: {backup_path}")
            
            # Create memory metadata
            timestamp = datetime.now().isoformat()
            
            # Create memory file content with frontmatter
            memory_content = f"""---
id: {memory_id}
timestamp: {timestamp}
agent: {agent}
user: {user}
topics: {json.dumps(topics)}
---

{content}"""
            
            # Create a secure temporary file in the same directory using cross-platform method
            try:
                # Use cross-platform secure temporary file creation
                fd, temp_file = create_secure_temp_file(config.files_dir, suffix='.tmp')
                
                # Write content to temporary file
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    f.write(memory_content)
                    # Ensure data is written to disk
                    f.flush()
                    os.fsync(fd)
                
                # Perform atomic rename
                temp_file.rename(file_path)
                logger.debug(f"Memory file created successfully: {file_path}")
                
                # Sync to Git in background if enabled
                if config.enable_git_sync:
                    sync_memory_to_git(memory_id, filename, config)
                
                return {
                    "memory_id": memory_id,
                    "message": f"Memory stored successfully with ID: {memory_id}",
                    "timestamp": timestamp,
                    "filename": filename
                }
                
            except Exception as e:
                # Handle specific file operation errors
                if isinstance(e, PermissionError):
                    error_code = "MEMORY_PERMISSION_DENIED"
                    message = f"Permission denied when writing memory file: {e}"
                elif isinstance(e, OSError):
                    error_code = "MEMORY_IO_ERROR"
                    message = f"File system error when writing memory: {e}"
                else:
                    error_code = "MEMORY_WRITE_ERROR"
                    message = f"Failed to write memory file: {e}"
                
                # Clean up temporary file if it exists
                if temp_file and temp_file.exists():
                    try:
                        temp_file.unlink()
                    except:
                        pass
                
                logger.error(message)
                error_response = ErrorResponse(
                    error="Memory storage failed",
                    error_code=error_code,
                    message=message,
                    timestamp=datetime.now().isoformat(),
                    category=ErrorCategory.MEMORY_OPERATION.value,
                    context={
                        'memory_id': memory_id,
                        'operation': 'store_memory_atomic',
                        'file_path': str(file_path)
                    }
                )
                return error_response.to_dict()
            
    except TimeoutError as e:
        # Handle lock timeout specifically
        error_msg = f"Failed to acquire file lock for memory storage within timeout: {e}"
        logger.error(error_msg)
        error_response = ErrorResponse(
            error="Memory storage failed",
            error_code="MEMORY_LOCK_TIMEOUT",
            message=error_msg,
            timestamp=datetime.now().isoformat(),
            category=ErrorCategory.MEMORY_OPERATION.value,
            context={
                'memory_id': memory_id if 'memory_id' in locals() else 'unknown',
                'operation': 'store_memory_atomic'
            }
        )
        return error_response.to_dict()
        
    except Exception as e:
        # Handle unexpected errors
        error_response = error_handler.handle_memory_error(e, {
            'operation': 'store_memory_atomic',
            'agent': agent,
            'user': user,
            'topics_count': len(topics) if isinstance(topics, list) else 0,
            'content_length': len(content) if isinstance(content, str) else 0
        })
        return error_response.to_dict()


def recall_memories(memory_ids: List[str], config: Config) -> List[Dict[str, Any]]:
    """Retrieve full memory details by IDs with performance monitoring."""
    # Performance monitoring removed for simplicity
    
    try:
        results = []
        memory_files = list(config.files_dir.glob("*.md"))
        
        # Performance monitoring removed for simplicity
        
        for memory_id in memory_ids:
            try:
                found = False
                for file_path in memory_files:
                    try:
                        memory_data = parse_memory_file_safe(file_path)
                        if memory_data and memory_data.get('id') == memory_id:
                            results.append(memory_data)
                            found = True
                            break
                    except Exception as e:
                        # Log file processing errors but continue searching
                        logging.getLogger('aiaml.memory').warning(
                            f"Error processing memory file {file_path.name} during recall: {e}"
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