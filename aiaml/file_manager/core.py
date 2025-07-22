"""
Core file management functionality for AIAML.

This module contains the main FileManager class and directory initialization logic.
"""

import os
import stat
import logging
from pathlib import Path
from typing import Dict, Any

from ..config import Config
from ..platform import get_platform_info, normalize_path
from .backup import BackupManager
from .git_init import GitInitializer
from .recovery import FileRecovery


class FileManager:
    """
    Comprehensive file and directory management for AIAML.
    
    Features:
    - Automatic directory creation with proper permissions
    - Git repository initialization on first run
    - Backup and recovery mechanisms for memory files
    - Cross-platform file permission handling
    - Directory structure validation and repair
    """
    
    def __init__(self, config: Config):
        """
        Initialize FileManager with configuration.
        
        Args:
            config: Server configuration
        """
        self.config = config
        self.logger = logging.getLogger('aiaml.file_manager')
        self.platform_info = get_platform_info()
        
        # Define directory structure using config properties
        self.base_dir = normalize_path(config.memory_dir)  # Base AIAML directory
        self.memory_dir = normalize_path(config.files_dir)  # Memory files directory  
        self.backup_dir = normalize_path(config.backup_dir)
        self.temp_dir = normalize_path(config.temp_dir)
        self.lock_dir = normalize_path(config.lock_dir)
        
        # Git repository directory is the base directory
        self.git_repo_dir = normalize_path(config.git_repo_dir)
        
        # Initialize sub-managers
        self.backup_manager = BackupManager(config, self.backup_dir)
        self.git_initializer = GitInitializer(config, self.git_repo_dir)
        self.file_recovery = FileRecovery(config, self.backup_manager, self.backup_dir)
    
    def initialize_directory_structure(self) -> bool:
        """
        Initialize the complete directory structure with proper permissions.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            self.logger.info("Initializing AIAML directory structure")
            
            # Define all required directories
            directories = [
                (self.memory_dir, "Memory storage directory"),
                (self.backup_dir, "Backup directory"),
                (self.temp_dir, "Temporary files directory"),
                (self.lock_dir, "File locks directory")
            ]
            
            # Create each directory with proper permissions
            for directory, description in directories:
                success = self._create_directory_with_permissions(directory, description)
                if not success:
                    return False
            
            # Validate directory structure
            if not self._validate_directory_structure():
                return False
            
            self.logger.info("Directory structure initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize directory structure: {e}", exc_info=True)
            return False
    
    def _create_directory_with_permissions(self, directory: Path, description: str) -> bool:
        """
        Create a directory with appropriate permissions for the platform.
        
        Args:
            directory: Directory path to create
            description: Human-readable description for logging
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create directory if it doesn't exist
            if not directory.exists():
                directory.mkdir(parents=True, exist_ok=True)
                self.logger.info(f"Created {description}: {directory}")
            else:
                self.logger.debug(f"{description} already exists: {directory}")
            
            # Set appropriate permissions
            return self._set_directory_permissions(directory, description)
            
        except PermissionError as e:
            self.logger.error(f"Permission denied creating {description} at {directory}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Failed to create {description} at {directory}: {e}")
            return False
    
    def _set_directory_permissions(self, directory: Path, description: str) -> bool:
        """
        Set appropriate permissions for a directory based on platform.
        
        Args:
            directory: Directory path
            description: Human-readable description for logging
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if self.platform_info.is_windows:
                # On Windows, check if we can write to the directory
                test_file = directory / ".permission_test"
                try:
                    test_file.write_text("test")
                    test_file.unlink()
                    self.logger.debug(f"Write permissions verified for {description}")
                    return True
                except PermissionError:
                    self.logger.error(f"No write permission for {description} at {directory}")
                    return False
            else:
                # On Unix-like systems, set proper permissions
                # Owner: read, write, execute (7)
                # Group: read, execute (5)  
                # Others: read, execute (5)
                directory.chmod(0o755)
                
                # Verify permissions
                current_perms = oct(directory.stat().st_mode)[-3:]
                self.logger.debug(f"Set permissions {current_perms} for {description}")
                return True
                
        except Exception as e:
            self.logger.warning(f"Could not set permissions for {description}: {e}")
            # Don't fail if we can't set permissions, just warn
            return True
    
    def _validate_directory_structure(self) -> bool:
        """
        Validate that all required directories exist and are accessible.
        
        Returns:
            True if valid, False otherwise
        """
        try:
            directories_to_check = [
                (self.memory_dir, "memory directory"),
                (self.backup_dir, "backup directory"),
                (self.temp_dir, "temp directory"),
                (self.lock_dir, "lock directory")
            ]
            
            for directory, name in directories_to_check:
                if not directory.exists():
                    self.logger.error(f"Required {name} does not exist: {directory}")
                    return False
                
                if not directory.is_dir():
                    self.logger.error(f"Required {name} is not a directory: {directory}")
                    return False
                
                # Test write access
                test_file = directory / ".access_test"
                try:
                    test_file.write_text("test")
                    test_file.unlink()
                except Exception as e:
                    self.logger.error(f"No write access to {name}: {e}")
                    return False
            
            self.logger.debug("Directory structure validation passed")
            return True
            
        except Exception as e:
            self.logger.error(f"Directory structure validation failed: {e}")
            return False
    
    def initialize_git_repository_on_first_run(self) -> bool:
        """
        Initialize Git repository on first run if Git sync is enabled.
        
        Returns:
            True if successful or not needed, False if failed
        """
        return self.git_initializer.initialize_git_repository_on_first_run()
    
    def create_backup(self, memory_file_path: Path):
        """Create a backup of a memory file."""
        return self.backup_manager.create_backup(memory_file_path)
    
    def restore_from_backup(self, memory_file_path: Path, backup_path=None):
        """Restore a memory file from backup."""
        return self.backup_manager.restore_from_backup(memory_file_path, backup_path)
    
    def cleanup_old_backups(self, max_age_days: int = 30, max_count: int = 100):
        """Clean up old backup files."""
        return self.backup_manager.cleanup_old_backups(max_age_days, max_count)
    
    def repair_corrupted_file(self, memory_file_path: Path):
        """Attempt to repair a corrupted memory file."""
        return self.file_recovery.repair_corrupted_file(memory_file_path)
    
    def get_directory_status(self) -> Dict[str, Any]:
        """
        Get comprehensive status of the directory structure.
        
        Returns:
            Dictionary containing directory status information
        """
        try:
            status = {
                'initialized': False,
                'directories': {},
                'git_repository': self.git_initializer.get_git_status(),
                'backup_info': self.backup_manager.get_backup_info(),
                'disk_usage': {},
                'permissions': {}
            }
            
            # Check each directory
            directories_to_check = [
                ('memory_dir', self.memory_dir, "Memory storage"),
                ('backup_dir', self.backup_dir, "Backup storage"),
                ('temp_dir', self.temp_dir, "Temporary files"),
                ('lock_dir', self.lock_dir, "File locks")
            ]
            
            all_exist = True
            for key, directory, description in directories_to_check:
                dir_status = {
                    'path': str(directory),
                    'exists': directory.exists(),
                    'is_directory': directory.is_dir() if directory.exists() else False,
                    'writable': False,
                    'file_count': 0,
                    'size_bytes': 0
                }
                
                if dir_status['exists'] and dir_status['is_directory']:
                    # Test write access
                    try:
                        test_file = directory / ".status_test"
                        test_file.write_text("test")
                        test_file.unlink()
                        dir_status['writable'] = True
                    except:
                        pass
                    
                    # Count files and calculate size
                    try:
                        files = list(directory.iterdir())
                        dir_status['file_count'] = len([f for f in files if f.is_file()])
                        dir_status['size_bytes'] = sum(f.stat().st_size for f in files if f.is_file())
                    except:
                        pass
                else:
                    all_exist = False
                
                status['directories'][key] = dir_status
            
            status['initialized'] = all_exist
            
            return status
            
        except Exception as e:
            self.logger.error(f"Error getting directory status: {e}")
            return {'error': str(e)}