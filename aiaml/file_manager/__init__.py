"""
AIAML File Manager Package

This package provides comprehensive file and directory management functionality
for AIAML, including directory initialization, backup management, Git repository
setup, and file recovery operations.
"""

import logging
from typing import Optional

from ..config import Config
from .core import FileManager

# Global file manager instance
_file_manager: Optional[FileManager] = None


def get_file_manager(config: Config) -> FileManager:
    """
    Get or create the global file manager instance.
    
    Args:
        config: Server configuration
        
    Returns:
        FileManager instance
    """
    global _file_manager
    
    if _file_manager is None:
        _file_manager = FileManager(config)
    
    return _file_manager


def initialize_aiaml_directories(config: Config) -> bool:
    """
    Initialize all AIAML directories and file management systems.
    
    This is the main entry point for automated directory and file management.
    
    Args:
        config: Server configuration
        
    Returns:
        True if successful, False otherwise
    """
    try:
        file_manager = get_file_manager(config)
        
        # Initialize directory structure
        if not file_manager.initialize_directory_structure():
            return False
        
        # Initialize Git repository on first run
        git_init_result = file_manager.initialize_git_repository_on_first_run()
        if not git_init_result:
            # Log warning but don't fail the entire initialization
            logger = logging.getLogger('aiaml.file_manager')
            logger.warning("Git repository initialization failed, but continuing with other initialization")
        
        # Clean up old backups
        file_manager.cleanup_old_backups()
        
        return True
        
    except Exception as e:
        logger = logging.getLogger('aiaml.file_manager')
        logger.error(f"Failed to initialize AIAML directories: {e}", exc_info=True)
        return False


# Export main classes and functions
__all__ = [
    'FileManager',
    'get_file_manager', 
    'initialize_aiaml_directories'
]