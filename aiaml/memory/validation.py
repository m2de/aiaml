"""Comprehensive input validation for memory operations with sanitization and security checks."""

import html
import re
import unicodedata
from pathlib import Path
from typing import List, Optional, Any, Dict

from ..errors import ErrorResponse, error_handler, ErrorCategory


# Security patterns for input sanitization
DANGEROUS_PATTERNS = [
    r'<script[^>]*>.*?</script>',  # Script tags
    r'javascript:',                # JavaScript URLs
    r'on\w+\s*=',                 # Event handlers
    r'<iframe[^>]*>.*?</iframe>',  # Iframe tags
    r'<object[^>]*>.*?</object>',  # Object tags
    r'<embed[^>]*>.*?</embed>',    # Embed tags
]


def sanitize_string_input(value: str, field_name: str = "input") -> str:
    """
    Sanitize string input to prevent XSS and other injection attacks.
    
    Args:
        value: Input string to sanitize
        field_name: Name of the field for error reporting
        
    Returns:
        Sanitized string
        
    Raises:
        ValueError: If input contains dangerous patterns
    """
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    
    # Check for dangerous patterns
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, value, re.IGNORECASE):
            raise ValueError(f"{field_name} contains potentially dangerous content")
    
    # HTML escape the content
    sanitized = html.escape(value)
    
    # Normalize unicode characters
    sanitized = unicodedata.normalize('NFKC', sanitized)
    
    # Remove null bytes and other control characters
    sanitized = ''.join(char for char in sanitized if ord(char) >= 32 or char in '\n\r\t')
    
    return sanitized


def validate_memory_id_format(memory_id: str) -> bool:
    """
    Validate memory ID format (8 character hexadecimal).
    
    Args:
        memory_id: Memory ID to validate
        
    Returns:
        True if valid format, False otherwise
    """
    if not isinstance(memory_id, str):
        return False
    
    # Memory IDs should be exactly 8 characters, hexadecimal (lowercase)
    return bool(re.match(r'^[a-f0-9]{8}$', memory_id.strip()))


def validate_filename_safety(filename: str) -> bool:
    """
    Validate that a filename is safe for filesystem operations.
    
    Args:
        filename: Filename to validate
        
    Returns:
        True if safe, False otherwise
    """
    if not isinstance(filename, str) or not filename.strip():
        return False
    
    # Check for directory traversal
    if '..' in filename:
        return False
    
    # Check for invalid filename characters
    if re.search(r'[<>:"|?*]', filename):
        return False
    
    # Check for Windows reserved names (case-insensitive)
    base_name = filename.split('.')[0].upper()
    reserved_names = ['CON', 'PRN', 'AUX', 'NUL'] + [f'COM{i}' for i in range(1, 10)] + [f'LPT{i}' for i in range(1, 10)]
    if base_name in reserved_names:
        return False
    
    # Check length limits
    if len(filename) > 255:  # Most filesystems limit to 255 characters
        return False
    
    # Check for valid characters only
    if not re.match(r'^[a-zA-Z0-9._-]+$', filename):
        return False
    
    return True


def validate_memory_input(agent: str, user: str, topics: List[str], content: str) -> Optional[ErrorResponse]:
    """
    Validate and sanitize memory input parameters with comprehensive security checks.
    
    Args:
        agent: Agent name
        user: User identifier
        topics: List of topic tags
        content: Memory content
        
    Returns:
        ErrorResponse if validation fails, None if valid
    """
    try:
        # Validate and sanitize agent
        if not agent or not isinstance(agent, str):
            raise ValueError("Agent name is required and must be a string")
        
        agent = agent.strip()
        if len(agent) == 0:
            raise ValueError("Agent name cannot be empty")
        
        if len(agent) > 50:
            raise ValueError("Agent name must be 50 characters or less")
        
        # Sanitize agent name
        try:
            sanitized_agent = sanitize_string_input(agent, "agent name")
        except ValueError as e:
            raise ValueError(f"Agent name validation failed: {str(e)}")
        
        # Validate and sanitize user
        if not user or not isinstance(user, str):
            raise ValueError("User identifier is required and must be a string")
        
        user = user.strip()
        if len(user) == 0:
            raise ValueError("User identifier cannot be empty")
        
        if len(user) > 50:
            raise ValueError("User identifier must be 50 characters or less")
        
        # Sanitize user identifier
        try:
            sanitized_user = sanitize_string_input(user, "user identifier")
        except ValueError as e:
            raise ValueError(f"User identifier validation failed: {str(e)}")
        
        # Validate topics
        if not isinstance(topics, list):
            raise ValueError("Topics must be a list")
        
        if len(topics) == 0:
            raise ValueError("At least one topic is required")
        
        if len(topics) > 20:
            raise ValueError("Maximum 20 topics allowed")
        
        sanitized_topics = []
        for i, topic in enumerate(topics):
            if not isinstance(topic, str):
                raise ValueError(f"Topic {i+1} must be a string")
            
            topic = topic.strip()
            if len(topic) == 0:
                raise ValueError(f"Topic {i+1} cannot be empty")
            
            if len(topic) > 30:
                raise ValueError(f"Topic {i+1} must be 30 characters or less")
            
            # Sanitize topic
            try:
                sanitized_topic = sanitize_string_input(topic, f"topic {i+1}")
                sanitized_topics.append(sanitized_topic)
            except ValueError as e:
                raise ValueError(f"Topic {i+1} validation failed: {str(e)}")
        
        # Validate and sanitize content
        if not content or not isinstance(content, str):
            raise ValueError("Content is required and must be a string")
        
        content = content.strip()
        if len(content) == 0:
            raise ValueError("Content cannot be empty")
        
        if len(content) > 100000:  # 100KB limit
            raise ValueError("Content must be 100,000 characters or less")
        
        # Sanitize content
        try:
            sanitized_content = sanitize_string_input(content, "content")
        except ValueError as e:
            raise ValueError(f"Content validation failed: {str(e)}")
        
        return None
        
    except ValueError as e:
        return error_handler.handle_validation_error(e, {
            'operation': 'validate_memory_input',
            'agent': agent if isinstance(agent, str) else type(agent).__name__,
            'user': user if isinstance(user, str) else type(user).__name__,
            'topics_count': len(topics) if isinstance(topics, list) else 0,
            'content_length': len(content) if isinstance(content, str) else 0
        })


def validate_search_input(keywords: List[str]) -> Optional[ErrorResponse]:
    """
    Validate and sanitize search input parameters.
    
    Args:
        keywords: List of search keywords
        
    Returns:
        ErrorResponse if validation fails, None if valid
    """
    try:
        # Validate keywords type
        if not isinstance(keywords, list):
            raise ValueError("Keywords must be a list")
        
        if len(keywords) == 0:
            raise ValueError("At least one keyword is required")
        
        if len(keywords) > 10:
            raise ValueError("Maximum 10 keywords allowed")
        
        sanitized_keywords = []
        for i, keyword in enumerate(keywords):
            if not isinstance(keyword, str):
                raise ValueError(f"Keyword {i+1} must be a string")
            
            keyword = keyword.strip()
            if len(keyword) == 0:
                raise ValueError(f"Keyword {i+1} cannot be empty")
            
            if len(keyword) > 50:
                raise ValueError(f"Keyword {i+1} must be 50 characters or less")
            
            # Sanitize keyword
            try:
                sanitized_keyword = sanitize_string_input(keyword, f"keyword {i+1}")
                sanitized_keywords.append(sanitized_keyword)
            except ValueError as e:
                raise ValueError(f"Keyword {i+1} validation failed: {str(e)}")
        
        return None
        
    except ValueError as e:
        return error_handler.handle_validation_error(e, {
            'operation': 'validate_search_input',
            'keywords_count': len(keywords) if isinstance(keywords, list) else 0,
            'keywords': keywords if isinstance(keywords, list) else str(type(keywords))
        })


def validate_recall_input(memory_ids: List[str]) -> Optional[ErrorResponse]:
    """
    Validate recall input parameters with memory ID format validation.
    
    Args:
        memory_ids: List of memory IDs to recall
        
    Returns:
        ErrorResponse if validation fails, None if valid
    """
    try:
        # Validate memory_ids type
        if not isinstance(memory_ids, list):
            raise ValueError("Memory IDs must be a list")
        
        if len(memory_ids) == 0:
            raise ValueError("At least one memory ID is required")
        
        if len(memory_ids) > 50:
            raise ValueError("Maximum 50 memory IDs allowed")
        
        for i, memory_id in enumerate(memory_ids):
            if not isinstance(memory_id, str):
                raise ValueError(f"Memory ID {i+1} must be a string")
            
            memory_id = memory_id.strip()
            if len(memory_id) == 0:
                raise ValueError(f"Memory ID {i+1} cannot be empty")
            
            # Validate memory ID format
            if not validate_memory_id_format(memory_id):
                raise ValueError(f"Memory ID {i+1} has invalid format (must be 8 hexadecimal characters): {memory_id}")
        
        return None
        
    except ValueError as e:
        return error_handler.handle_validation_error(e, {
            'operation': 'validate_recall_input',
            'memory_ids_count': len(memory_ids) if isinstance(memory_ids, list) else 0,
            'memory_ids': memory_ids if isinstance(memory_ids, list) else str(type(memory_ids))
        })


def validate_configuration_input(config_dict: Dict[str, Any]) -> List[str]:
    """
    Validate configuration input parameters.
    
    Args:
        config_dict: Configuration dictionary to validate
        
    Returns:
        List of validation error messages
    """
    errors = []
    
    try:
        # Validate memory directory path (more lenient for relative paths)
        if 'memory_dir' in config_dict:
            memory_dir = config_dict['memory_dir']
            if isinstance(memory_dir, str):
                try:
                    path = Path(memory_dir)
                    # Only check for obvious path traversal attempts
                    if '../' in memory_dir or '..\\' in memory_dir:
                        errors.append("Memory directory path contains path traversal attempts")
                except Exception:
                    errors.append("Invalid memory directory path format")
            elif memory_dir is not None:
                errors.append("Memory directory must be a string path")
        
        # Validate Git remote URL if provided
        if 'git_remote_url' in config_dict and config_dict['git_remote_url'] is not None:
            git_url = config_dict['git_remote_url']
            if not isinstance(git_url, str):
                errors.append("Git remote URL must be a string")
            elif not (git_url.startswith('https://') or git_url.startswith('git@')):
                errors.append("Git remote URL must use HTTPS or SSH protocol")
        
        # Validate log level
        if 'log_level' in config_dict:
            log_level = config_dict['log_level']
            if not isinstance(log_level, str):
                errors.append("Log level must be a string")
            elif log_level.upper() not in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
                errors.append("Log level must be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL")
    
    except Exception as e:
        errors.append(f"Configuration validation error: {str(e)}")
    
    return errors


def validate_tool_parameters(tool_name: str, parameters: Dict[str, Any]) -> Optional[ErrorResponse]:
    """
    Validate parameters for MCP tools with tool-specific validation rules.
    
    Args:
        tool_name: Name of the MCP tool
        parameters: Dictionary of parameters to validate
        
    Returns:
        ErrorResponse if validation fails, None if valid
    """
    try:
        if tool_name == "remember":
            # Validate remember tool parameters
            required_params = ['agent', 'user', 'topics', 'content']
            for param in required_params:
                if param not in parameters:
                    raise ValueError(f"Missing required parameter: {param}")
            
            return validate_memory_input(
                parameters['agent'],
                parameters['user'],
                parameters['topics'],
                parameters['content']
            )
        
        elif tool_name == "think":
            # Validate think tool parameters
            if 'keywords' not in parameters:
                raise ValueError("Missing required parameter: keywords")
            
            return validate_search_input(parameters['keywords'])
        
        elif tool_name == "recall":
            # Validate recall tool parameters
            if 'memory_ids' not in parameters:
                raise ValueError("Missing required parameter: memory_ids")
            
            return validate_recall_input(parameters['memory_ids'])
        
        elif tool_name == "performance_stats":
            # Performance stats tool has no parameters to validate
            return None
        
        else:
            raise ValueError(f"Unknown tool: {tool_name}")
    
    except ValueError as e:
        return error_handler.handle_validation_error(e, {
            'operation': 'validate_tool_parameters',
            'tool_name': tool_name,
            'parameters': list(parameters.keys()) if isinstance(parameters, dict) else str(type(parameters))
        })