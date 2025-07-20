"""
Automated directory and file management for AIAML.

This module provides comprehensive file and directory management functionality
including automatic directory creation, Git repository initialization,
backup and recovery mechanisms, and file permission handling.
"""

import os
import shutil
import stat
import logging
import tempfile
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta

from .config import Config
from .platform import get_platform_info, normalize_path, create_secure_temp_file
from .errors import ErrorResponse


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
        
        # Define directory structure
        self.memory_dir = normalize_path(config.memory_dir)
        self.backup_dir = self.memory_dir.parent / "backups"
        self.temp_dir = self.memory_dir.parent / "temp"
        self.lock_dir = self.memory_dir.parent / "locks"
        
        # Git repository directory (parent of memory/files)
        self.git_repo_dir = self.memory_dir.parent
    
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
        try:
            if not self.config.enable_git_sync:
                self.logger.debug("Git sync disabled, skipping repository initialization")
                return True
            
            # Check if Git is available first
            from .platform import validate_git_availability
            git_available, git_error = validate_git_availability()
            
            if not git_available:
                self.logger.warning(f"Git not available, skipping repository initialization: {git_error}")
                return True  # Don't fail if Git is not available
            
            git_dir = self.git_repo_dir / ".git"
            
            if git_dir.exists():
                self.logger.debug("Git repository already exists")
                return True
            
            self.logger.info("Initializing Git repository on first run")
            
            # Ensure the Git repository directory exists first
            self.git_repo_dir.mkdir(parents=True, exist_ok=True)
            
            # Import Git sync manager to handle initialization
            from .git_sync import get_git_sync_manager
            
            git_manager = get_git_sync_manager(self.config)
            
            # Check if Git directory exists after manager creation
            git_dir_after = self.git_repo_dir / ".git"
            
            if git_manager.is_initialized() and git_dir_after.exists():
                self.logger.info("Git repository initialized successfully on first run")
                
                # Create initial .gitignore file
                self._create_initial_gitignore()
                
                return True
            else:
                self.logger.warning("Git repository initialization failed")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to initialize Git repository on first run: {e}", exc_info=True)
            return False
    
    def _create_initial_gitignore(self) -> None:
        """Create initial .gitignore file for the memory repository."""
        try:
            gitignore_path = self.git_repo_dir / ".gitignore"
            
            if not gitignore_path.exists():
                gitignore_content = """# AIAML Memory Repository
# Ignore temporary files and system files
*.tmp
*.temp
.DS_Store
Thumbs.db
.memory_lock
.access_test
.permission_test

# Ignore backup directory (backups are local only)
backups/

# Ignore temp directory
temp/

# Ignore lock directory
locks/

# Python cache files
__pycache__/
*.pyc
*.pyo
"""
                gitignore_path.write_text(gitignore_content)
                self.logger.info("Created initial .gitignore file")
                
        except Exception as e:
            self.logger.warning(f"Could not create .gitignore file: {e}")
    
    def create_backup(self, memory_file_path: Path) -> Optional[Path]:
        """
        Create a backup of a memory file.
        
        Args:
            memory_file_path: Path to the memory file to backup
            
        Returns:
            Path to backup file if successful, None otherwise
        """
        try:
            if not memory_file_path.exists():
                self.logger.warning(f"Cannot backup non-existent file: {memory_file_path}")
                return None
            
            # Generate backup filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"{memory_file_path.stem}_{timestamp}.backup"
            backup_path = self.backup_dir / backup_filename
            
            # Copy file to backup location
            shutil.copy2(memory_file_path, backup_path)
            
            self.logger.debug(f"Created backup: {backup_path}")
            return backup_path
            
        except Exception as e:
            self.logger.error(f"Failed to create backup for {memory_file_path}: {e}")
            return None
    
    def restore_from_backup(self, memory_file_path: Path, backup_path: Optional[Path] = None) -> bool:
        """
        Restore a memory file from backup.
        
        Args:
            memory_file_path: Path where the memory file should be restored
            backup_path: Specific backup to restore from (if None, finds latest)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if backup_path is None:
                backup_path = self._find_latest_backup(memory_file_path)
            
            if backup_path is None or not backup_path.exists():
                self.logger.error(f"No backup found for {memory_file_path}")
                return False
            
            # Create backup of current file if it exists
            if memory_file_path.exists():
                current_backup = self.create_backup(memory_file_path)
                if current_backup:
                    self.logger.info(f"Created backup of current file before restore: {current_backup}")
            
            # Restore from backup
            shutil.copy2(backup_path, memory_file_path)
            
            self.logger.info(f"Restored {memory_file_path} from backup {backup_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to restore {memory_file_path} from backup: {e}")
            return False
    
    def _find_latest_backup(self, memory_file_path: Path) -> Optional[Path]:
        """
        Find the latest backup for a memory file.
        
        Args:
            memory_file_path: Original memory file path
            
        Returns:
            Path to latest backup or None if not found
        """
        try:
            file_stem = memory_file_path.stem
            backup_pattern = f"{file_stem}_*.backup"
            
            backup_files = list(self.backup_dir.glob(backup_pattern))
            
            if not backup_files:
                return None
            
            # Sort by modification time, newest first
            backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            return backup_files[0]
            
        except Exception as e:
            self.logger.error(f"Error finding latest backup for {memory_file_path}: {e}")
            return None
    
    def cleanup_old_backups(self, max_age_days: int = 30, max_count: int = 100) -> int:
        """
        Clean up old backup files based on age and count limits.
        
        Args:
            max_age_days: Maximum age of backups to keep (days)
            max_count: Maximum number of backups to keep per file
            
        Returns:
            Number of backups cleaned up
        """
        try:
            if not self.backup_dir.exists():
                return 0
            
            cleaned_count = 0
            cutoff_time = datetime.now() - timedelta(days=max_age_days)
            
            # Get all backup files
            backup_files = list(self.backup_dir.glob("*.backup"))
            
            # Group backups by original file
            backup_groups = {}
            for backup_file in backup_files:
                # Extract original filename from backup name
                parts = backup_file.stem.split('_')
                if len(parts) >= 3:  # filename_timestamp.backup
                    original_name = '_'.join(parts[:-2])  # Remove timestamp parts
                    if original_name not in backup_groups:
                        backup_groups[original_name] = []
                    backup_groups[original_name].append(backup_file)
            
            # Clean up each group
            for original_name, backups in backup_groups.items():
                # Sort by modification time, newest first
                backups.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                
                # Remove old backups
                for backup_file in backups:
                    file_time = datetime.fromtimestamp(backup_file.stat().st_mtime)
                    
                    # Remove if too old or beyond count limit
                    should_remove = (
                        file_time < cutoff_time or
                        backups.index(backup_file) >= max_count
                    )
                    
                    if should_remove:
                        try:
                            backup_file.unlink()
                            cleaned_count += 1
                            self.logger.debug(f"Cleaned up old backup: {backup_file}")
                        except Exception as e:
                            self.logger.warning(f"Could not remove backup {backup_file}: {e}")
            
            if cleaned_count > 0:
                self.logger.info(f"Cleaned up {cleaned_count} old backup files")
            
            return cleaned_count
            
        except Exception as e:
            self.logger.error(f"Error during backup cleanup: {e}")
            return 0
    
    def repair_corrupted_file(self, memory_file_path: Path) -> bool:
        """
        Attempt to repair a corrupted memory file.
        
        Args:
            memory_file_path: Path to the corrupted file
            
        Returns:
            True if repair was successful, False otherwise
        """
        try:
            self.logger.info(f"Attempting to repair corrupted file: {memory_file_path}")
            
            # First, try to restore from backup
            if self.restore_from_backup(memory_file_path):
                self.logger.info(f"Successfully repaired {memory_file_path} from backup")
                return True
            
            # If no backup available, try to salvage what we can
            if memory_file_path.exists():
                try:
                    content = memory_file_path.read_text(encoding='utf-8', errors='replace')
                    
                    # Try to extract any salvageable content
                    salvaged_content = self._salvage_file_content(content, memory_file_path)
                    
                    if salvaged_content:
                        # Create backup of corrupted file
                        corrupted_backup = self.backup_dir / f"{memory_file_path.name}.corrupted"
                        shutil.copy2(memory_file_path, corrupted_backup)
                        
                        # Write salvaged content
                        memory_file_path.write_text(salvaged_content, encoding='utf-8')
                        
                        self.logger.info(f"Salvaged content from corrupted file: {memory_file_path}")
                        return True
                        
                except Exception as e:
                    self.logger.error(f"Could not salvage content from {memory_file_path}: {e}")
            
            self.logger.error(f"Could not repair corrupted file: {memory_file_path}")
            return False
            
        except Exception as e:
            self.logger.error(f"Error during file repair for {memory_file_path}: {e}")
            return False
    
    def _salvage_file_content(self, content: str, file_path: Path) -> Optional[str]:
        """
        Attempt to salvage content from a corrupted memory file.
        
        Args:
            content: Raw file content
            file_path: Original file path for context
            
        Returns:
            Salvaged content or None if nothing could be salvaged
        """
        try:
            # Try to extract basic information
            lines = content.split('\n')
            
            # Look for YAML frontmatter
            yaml_start = -1
            yaml_end = -1
            
            for i, line in enumerate(lines):
                if line.strip() == '---':
                    if yaml_start == -1:
                        yaml_start = i
                    else:
                        yaml_end = i
                        break
            
            # Extract file ID from filename if possible
            file_id = None
            if '_' in file_path.stem:
                parts = file_path.stem.split('_')
                if len(parts) >= 3:
                    file_id = parts[-1]  # Last part should be the ID
            
            # Create minimal valid memory file
            timestamp = datetime.now().isoformat()
            
            salvaged_frontmatter = f"""---
id: {file_id or 'recovered'}
timestamp: {timestamp}
agent: unknown
user: unknown
topics: ["recovered"]
---

# Recovered Memory File

This file was recovered from a corrupted memory file.
Original file: {file_path.name}
Recovery timestamp: {timestamp}

## Original Content (if recoverable):

"""
            
            # Try to extract any readable content after frontmatter
            content_start = yaml_end + 1 if yaml_end > -1 else 0
            if content_start < len(lines):
                original_content = '\n'.join(lines[content_start:])
                # Clean up the content a bit
                original_content = original_content.strip()
                if original_content:
                    salvaged_frontmatter += original_content
                else:
                    salvaged_frontmatter += "(No readable content could be recovered)"
            else:
                salvaged_frontmatter += "(No content section found)"
            
            return salvaged_frontmatter
            
        except Exception as e:
            self.logger.error(f"Error salvaging content: {e}")
            return None
    
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
                'git_repository': {
                    'exists': False,
                    'initialized': False
                },
                'backup_info': {
                    'backup_count': 0,
                    'oldest_backup': None,
                    'newest_backup': None
                },
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
            
            # Check Git repository
            git_dir = self.git_repo_dir / ".git"
            status['git_repository']['exists'] = git_dir.exists()
            if git_dir.exists():
                status['git_repository']['initialized'] = True
            
            # Backup information
            if self.backup_dir.exists():
                backup_files = list(self.backup_dir.glob("*.backup"))
                status['backup_info']['backup_count'] = len(backup_files)
                
                if backup_files:
                    backup_times = [f.stat().st_mtime for f in backup_files]
                    status['backup_info']['oldest_backup'] = datetime.fromtimestamp(min(backup_times)).isoformat()
                    status['backup_info']['newest_backup'] = datetime.fromtimestamp(max(backup_times)).isoformat()
            
            return status
            
        except Exception as e:
            self.logger.error(f"Error getting directory status: {e}")
            return {'error': str(e)}


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