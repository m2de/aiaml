"""
Backup and recovery functionality for AIAML file management.

This module handles creating backups of memory files, restoring from backups,
and cleaning up old backup files.
"""

import shutil
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta

from ..config import Config


class BackupManager:
    """Handles backup and recovery operations for memory files."""
    
    def __init__(self, config: Config, backup_dir: Path):
        """
        Initialize BackupManager.
        
        Args:
            config: Server configuration
            backup_dir: Directory for storing backups
        """
        self.config = config
        self.backup_dir = backup_dir
        self.logger = logging.getLogger('aiaml.file_manager.backup')
    
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
    
    def get_backup_info(self) -> dict:
        """
        Get information about available backups.
        
        Returns:
            Dictionary with backup information
        """
        try:
            info = {
                'backup_count': 0,
                'oldest_backup': None,
                'newest_backup': None
            }
            
            if self.backup_dir.exists():
                backup_files = list(self.backup_dir.glob("*.backup"))
                info['backup_count'] = len(backup_files)
                
                if backup_files:
                    backup_times = [f.stat().st_mtime for f in backup_files]
                    info['oldest_backup'] = datetime.fromtimestamp(min(backup_times)).isoformat()
                    info['newest_backup'] = datetime.fromtimestamp(max(backup_times)).isoformat()
            
            return info
            
        except Exception as e:
            self.logger.error(f"Error getting backup info: {e}")
            return {'error': str(e)}