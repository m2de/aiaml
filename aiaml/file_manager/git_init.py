"""
Git repository initialization for AIAML file management.

This module handles initializing Git repositories on first run and creating
initial configuration files like .gitignore.
"""

import logging
from pathlib import Path

from ..config import Config


class GitInitializer:
    """Handles Git repository initialization for AIAML."""
    
    def __init__(self, config: Config, git_repo_dir: Path):
        """
        Initialize GitInitializer.
        
        Args:
            config: Server configuration
            git_repo_dir: Directory where Git repository should be initialized
        """
        self.config = config
        self.git_repo_dir = git_repo_dir
        self.logger = logging.getLogger('aiaml.file_manager.git_init')
    
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
            from ..platform import validate_git_availability
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
            from ..git_sync import get_git_sync_manager
            
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
    
    def get_git_status(self) -> dict:
        """
        Get Git repository status information.
        
        Returns:
            Dictionary with Git status information
        """
        try:
            git_dir = self.git_repo_dir / ".git"
            return {
                'exists': git_dir.exists(),
                'initialized': git_dir.exists()
            }
        except Exception as e:
            self.logger.error(f"Error getting Git status: {e}")
            return {'error': str(e)}