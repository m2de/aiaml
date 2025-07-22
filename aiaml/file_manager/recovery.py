"""
File recovery functionality for AIAML file management.

This module handles repairing corrupted memory files and salvaging content
from damaged files.
"""

import shutil
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

from ..config import Config
from .backup import BackupManager


class FileRecovery:
    """Handles file recovery and repair operations."""
    
    def __init__(self, config: Config, backup_manager: BackupManager, backup_dir: Path):
        """
        Initialize FileRecovery.
        
        Args:
            config: Server configuration
            backup_manager: BackupManager instance for restoration
            backup_dir: Directory for storing corrupted file backups
        """
        self.config = config
        self.backup_manager = backup_manager
        self.backup_dir = backup_dir
        self.logger = logging.getLogger('aiaml.file_manager.recovery')
    
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
            if self.backup_manager.restore_from_backup(memory_file_path):
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