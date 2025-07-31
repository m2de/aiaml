"""Simplified Git synchronization manager for AIAML."""

import logging
from pathlib import Path
from typing import Optional, Dict, Any

try:
    import git
    from git import Repo, InvalidGitRepositoryError, GitCommandError
    HAS_GITPYTHON = True
except ImportError:
    HAS_GITPYTHON = False
    
    class InvalidGitRepositoryError(Exception):
        pass

from ..config import Config
from ..platform import get_platform_info
from .utils import GitSyncResult, create_git_sync_result
from .manager_core import GitSyncManagerCore
from .manager_sync import GitSyncManagerSync
from .error_recovery import ErrorCategory


class GitSyncManager:
    """
    Enhanced Git synchronization manager with comprehensive error handling,
    retry logic, and automatic repository initialization.
    
    Features:
    - Automatic Git repository initialization
    - Retry logic with exponential backoff
    - Git remote configuration and validation
    - Background synchronization operations
    - Comprehensive error handling and logging
    """
    
    def __init__(self, config: Config):
        """
        Initialize GitSyncManager with configuration.
        
        Args:
            config: Server configuration containing Git settings
        """
        self.config = config
        self.logger = logging.getLogger('aiaml.git_sync')
        
        # Initialize core functionality
        self.core = GitSyncManagerCore(config)
        
        # Initialize sync functionality  
        self.sync = GitSyncManagerSync(self.core)
        
        # Expose commonly used properties
        self.git_repo_dir = self.core.git_repo_dir
        self.git_dir = self.core.git_dir
        self.repo_state_manager = self.core.repo_state_manager
        self.error_handler = self.core.error_handler
        self.perf_logger = self.core.perf_logger
        
        # Initialize if Git sync is enabled
        if config.enable_git_sync:
            init_result = self._initialize_repository()
            if not init_result.success:
                self.logger.warning(f"Git repository initialization failed: {init_result.message}")
    
    def _initialize_repository(self) -> GitSyncResult:
        """Initialize Git repository using core functionality."""
        return self.core.initialize()
    
    def sync_memory_with_retry(self, memory_id: str, filename: str) -> GitSyncResult:
        """Synchronize a memory file to Git with retry logic."""
        return self.sync.sync_memory_with_retry(memory_id, filename)
    
    def sync_memory_background(self, memory_id: str, filename: str) -> None:
        """Synchronize a memory file to Git in a background thread."""
        return self.sync.sync_memory_background(memory_id, filename)
    
    def get_repository_status(self) -> Dict[str, Any]:
        """
        Get the current status of the Git repository.
        
        Returns:
            Dictionary containing repository status information
        """
        status = {
            'initialized': self.core.initialized,
            'git_sync_enabled': self.config.enable_git_sync,
            'repository_exists': self.git_dir.exists(),
            'remote_configured': False,
            'remote_url': self.config.git_remote_url,
            'last_error': None
        }
        
        if not self.config.enable_git_sync:
            return status
        
        try:
            # Check remote configuration using GitPython
            if self.git_dir.exists() and HAS_GITPYTHON:
                try:
                    repo = Repo(self.git_repo_dir)
                    origin_remote = repo.remote('origin')
                    remote_urls = list(origin_remote.urls)
                    
                    if remote_urls:
                        status['remote_configured'] = True
                        status['actual_remote_url'] = remote_urls[0]
                    
                except GitCommandError:
                    # Remote 'origin' doesn't exist
                    status['remote_configured'] = False
                except InvalidGitRepositoryError:
                    # Not a valid git repository
                    status['remote_configured'] = False
            elif not HAS_GITPYTHON:
                status['last_error'] = "GitPython not available"
            
        except Exception as e:
            status['last_error'] = str(e)
        
        return status
    
    def is_initialized(self) -> bool:
        """Check if the Git sync manager is properly initialized."""
        return self.core.initialized
    
    def recover_from_error(self, error_result: GitSyncResult) -> GitSyncResult:
        """
        Attempt to recover from a Git sync error using enhanced error handling.
        
        Args:
            error_result: The failed GitSyncResult to recover from
            
        Returns:
            GitSyncResult indicating recovery success or failure
        """
        if error_result.success:
            return error_result  # Nothing to recover from
        
        # Categorize the error (with fallback if error handler not available)
        if self.error_handler:
            try:
                category = self.error_handler.categorize_error(
                    error_result.message, 
                    error_result.error_code
                )
            except Exception as e:
                self.logger.warning(f"Error categorization failed, using fallback: {e}")
                category = ErrorCategory.UNKNOWN
        else:
            category = ErrorCategory.UNKNOWN
        
        self.logger.info(f"Attempting recovery for {category} error")
        
        # Define recovery functions based on error category
        def recovery_function() -> GitSyncResult:
            if category == ErrorCategory.REPOSITORY_CORRUPTION:
                # Attempt repository corruption recovery
                if self.error_handler:
                    return self.error_handler.recover_corrupted_repository()
                else:
                    return self._initialize_repository()
            elif category == ErrorCategory.NETWORK:
                # For network errors, try to reinitialize
                return self._initialize_repository()
            elif category == ErrorCategory.BRANCH_DETECTION:
                # Clear cache and retry branch detection
                self.repo_state_manager.clear_cache()
                return self._initialize_repository()
            else:
                # For other errors, try basic reinitialization
                return self._initialize_repository()
        
        # Attempt recovery (with fallback if error handler not available)
        if self.error_handler:
            try:
                recovery_result = self.error_handler.attempt_recovery(
                    category, 
                    recovery_function,
                    context={
                        "original_operation": error_result.operation,
                        "original_error": error_result.message
                    }
                )
            except Exception as e:
                self.logger.warning(f"Enhanced recovery failed, attempting basic recovery: {e}")
                recovery_result = recovery_function()
        else:
            # Fallback to basic recovery function
            recovery_result = recovery_function()
        
        if recovery_result.success:
            self.logger.info("Error recovery successful")
        else:
            self.logger.warning(f"Error recovery failed: {recovery_result.message}")
        
        return recovery_result
    
    def validate_and_recover(self) -> GitSyncResult:
        """
        Validate repository integrity and attempt recovery if needed.
        
        Returns:
            GitSyncResult indicating validation/recovery status
        """
        # First validate repository integrity (with fallback)
        if self.error_handler:
            try:
                integrity_result = self.error_handler.validate_repository_integrity()
            except Exception as e:
                self.logger.warning(f"Enhanced integrity validation failed, using basic check: {e}")
                # Basic fallback - just check if .git exists
                integrity_result = create_git_sync_result(
                    success=self.git_dir.exists(),
                    message="Basic repository check" if self.git_dir.exists() else "No .git directory found",
                    operation="basic_integrity_check"
                )
        else:
            # Basic fallback - just check if .git exists
            integrity_result = create_git_sync_result(
                success=self.git_dir.exists(),
                message="Basic repository check" if self.git_dir.exists() else "No .git directory found",
                operation="basic_integrity_check"
            )
        
        if integrity_result.success:
            return create_git_sync_result(
                success=True,
                message="Repository validation passed",
                operation="validate_and_recover"
            )
        
        # If validation failed, attempt recovery
        self.logger.warning("Repository validation failed, attempting recovery")
        
        return self.recover_from_error(integrity_result)
    
    def log_performance_summary(self) -> None:
        """Log a summary of Git sync performance metrics."""
        if self.perf_logger:
            try:
                self.perf_logger.log_performance_summary()
                self.logger.info("📊 Git sync performance summary logged")
            except Exception as e:
                self.logger.warning(f"⚠️ Performance summary logging failed: {e}")
        else:
            self.logger.debug("📊 Performance logging not available")


# Global Git sync manager instance
_git_sync_manager: Optional[GitSyncManager] = None


def get_git_sync_manager(config: Config) -> GitSyncManager:
    """
    Get or create the global Git sync manager instance.
    
    Args:
        config: Server configuration
        
    Returns:
        GitSyncManager instance
    """
    global _git_sync_manager
    
    if _git_sync_manager is None:
        _git_sync_manager = GitSyncManager(config)
    
    return _git_sync_manager