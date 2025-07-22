"""Memory storage and retrieval operations for AIAML."""

# Import all public functions from submodules
from .core import (
    store_memory_atomic,
    recall_memories,
    generate_memory_id,
    create_timestamp,
    create_memory_filename,
    parse_memory_file,
    parse_memory_file_safe
)

from .search import (
    search_memories_optimized
)

from .cache import (
    clear_memory_cache,
    get_search_performance_stats,
    reset_search_performance_stats
)

from .validation import (
    validate_memory_input,
    validate_search_input,
    validate_recall_input,
    validate_tool_parameters,
    validate_configuration_input,
    validate_memory_id_format,
    validate_filename_safety,
    sanitize_string_input
)

# Re-export for backward compatibility
__all__ = [
    'store_memory_atomic',
    'recall_memories',
    'search_memories_optimized',
    'get_search_performance_stats',
    'reset_search_performance_stats',
    'clear_memory_cache',
    'validate_memory_input',
    'validate_search_input',
    'validate_recall_input',
    'validate_tool_parameters',
    'validate_configuration_input',
    'validate_memory_id_format',
    'validate_filename_safety',
    'sanitize_string_input',
    'generate_memory_id',
    'create_timestamp',
    'create_memory_filename',
    'parse_memory_file',
    'parse_memory_file_safe'
]