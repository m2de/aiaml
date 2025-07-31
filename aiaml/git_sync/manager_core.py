"""Core GitSyncManager functionality."""

import logging
import threading
from pathlib import Path
from typing import Optional, Dict, Any
from contextlib import nullcontext

try:
    import git  
    from git import Repo, GitCommandError, InvalidGitRepositoryError
    HAS_GITPYTHON = True
except ImportError:
    HAS_GITPYTHON = False
    
    class GitCommandError(Exception):
        pass
    
    class InvalidGitRepositoryError(Exception):
        pass

from ..config import Config
from ..platform import get_platform_info
from .utils import GitSyncResult, create_git_sync_result
from .operations import (
    execute_git_operation_with_retry,
    setup_initial_git_config,
    validate_git_configuration
)
from .state import RepositoryStateManager
from .error_recovery import EnhancedErrorHandler, ErrorCategory
from .performance_logger import get_performance_logger
from .repository_info import RepositoryState


class GitSyncManagerCore:
    """
    Core Git synchronization manager functionality.
    
    This class provides the essential initialization and configuration
    methods for the Git sync manager.
    """
    
    def __init__(self, config: Config):
        """
        Initialize GitSyncManager core.
        
        Args:
            config: Server configuration containing Git settings
        """
        self.config = config
        self.logger = logging.getLogger('aiaml.git_sync')
        self._sync_lock = threading.Lock()
        self._initialized = False
        
        # Git repository directory (the base AIAML directory contains the git repo)
        self.git_repo_dir = config.git_repo_dir  # This is the base AIAML directory
        self.git_dir = self.git_repo_dir / ".git"
        
        # Repository state manager for enhanced Git sync
        self.repo_state_manager = RepositoryStateManager(config, self.git_repo_dir)
        
        # Enhanced error handler for comprehensive error recovery
        try:
            self.error_handler = EnhancedErrorHandler(config, self.git_repo_dir)
        except Exception as e:
            self.logger.warning(f"⚠️ Enhanced error handler initialization failed, using fallback: {e}")
            self.error_handler = None
        
        # Performance logger for monitoring Git operations
        try:
            self.perf_logger = get_performance_logger()
        except Exception as e:
            self.logger.warning(f"⚠️ Performance logger initialization failed, continuing without monitoring: {e}")
            self.perf_logger = None
    
    def _safe_performance_operation(self, operation_name: str, context=None):
        """
        Safely execute performance logging operation with fallback.
        
        Args:
            operation_name: Name of the operation to time
            context: Optional context information
            
        Returns:
            Context manager for timing or no-op fallback
        """
        if self.perf_logger:
            try:
                return self.perf_logger.time_operation(operation_name, context)
            except Exception as e:
                self.logger.debug(f"Performance logging failed for {operation_name}: {e}")
        
        # Fallback: return a no-op context manager
        return nullcontext()
    
    def _safe_error_handling(self, error_message: str, operation: str, error_code: str = None, context: dict = None) -> GitSyncResult:
        """
        Safely use enhanced error handling with fallback to basic error result.
        
        Args:
            error_message: The error message
            operation: The operation that failed
            error_code: Optional error code
            context: Optional context information
            
        Returns:
            GitSyncResult with enhanced error info or basic fallback
        """
        if self.error_handler:
            try:
                return self.error_handler.handle_error(error_message, operation, error_code, context)
            except Exception as e:
                self.logger.warning(f"Enhanced error handling failed, using fallback: {e}")
        
        # Fallback to basic error result
        return create_git_sync_result(
            success=False,
            message=error_message,
            operation=operation,
            error_code=error_code or "BASIC_ERROR"
        )
    
    def initialize(self) -> GitSyncResult:
        """
        Initialize Git repository based on detected repository state.
        
        This method now handles different repository states:
        - NEW_LOCAL: Initialize a new local repository
        - EXISTING_LOCAL: Configure existing local repository with remote
        - EXISTING_REMOTE: Clone existing remote repository
        - SYNCHRONIZED: Verify configuration
        
        Returns:
            GitSyncResult indicating success or failure
        """
        try:
            with self._safe_performance_operation("git_sync_initialization", {
                "git_sync_enabled": self.config.enable_git_sync,
                "remote_url_configured": bool(self.config.git_remote_url),
                "repo_dir": str(self.git_repo_dir)
            }):
                self.logger.info("Initializing Git synchronization manager")
                
                # Ensure the repository directory exists
                self.git_repo_dir.mkdir(parents=True, exist_ok=True)
                
                # Detect repository state using RepositoryStateManager
                with self._safe_performance_operation("repository_state_detection"):
                    repo_info = self.repo_state_manager.get_repository_info()
                    
                self.logger.info(f"🏠 Detected repository state: {repo_info.state}")
                self.logger.debug(f"📋 Repository details: local_exists={repo_info.local_exists}, "
                                f"remote_exists={repo_info.remote_exists}, "
                                f"default_branch={repo_info.default_branch}, "
                                f"needs_sync={repo_info.needs_sync}")
            
                # Handle different repository states
                if repo_info.state == RepositoryState.NEW_LOCAL:
                    # Initialize new local repository
                    result = self._handle_new_local(repo_info)
                    if not result.success:
                        return result
                        
                elif repo_info.state == RepositoryState.EXISTING_REMOTE:
                    # Clone existing remote repository
                    result = self._handle_existing_remote(repo_info)
                    if not result.success:
                        return result
                        
                elif repo_info.state == RepositoryState.EXISTING_LOCAL:
                    # Handle existing local repository
                    result = self._handle_existing_local(repo_info)
                    if not result.success:
                        return result
                        
                elif repo_info.state == RepositoryState.SYNCHRONIZED:
                    # Repository is already synchronized, just verify configuration
                    self.logger.info("✅ Repository is already synchronized")
                
                # Validate Git configuration
                validation_result = validate_git_configuration(
                    self.git_repo_dir, self.git_dir, self.config
                )
                if not validation_result.success:
                    self.logger.warning(f"Git configuration validation failed: {validation_result.message}")
                
                self._initialized = True
                self.logger.info("Git synchronization manager initialized successfully")
                
                # Get updated repository info for result
                updated_repo_info = self.repo_state_manager.get_repository_info()
                
                return create_git_sync_result(
                    success=True,
                    message=f"Git synchronization manager initialized (state: {updated_repo_info.state})",
                    operation="initialize",
                    repository_info=updated_repo_info,
                    branch_used=updated_repo_info.default_branch
                )
            
        except Exception as e:
            error_msg = f"Failed to initialize Git synchronization manager: {e}"
            self.logger.error(error_msg, exc_info=True)
            
            # Use enhanced error handling with fallback for better user guidance
            return self._safe_error_handling(
                error_message=error_msg,
                operation="initialize",
                error_code="GIT_INIT_FAILED",
                context={
                    "git_repo_dir": str(self.git_repo_dir),
                    "git_remote_url": self.config.git_remote_url,
                    "enable_git_sync": self.config.enable_git_sync
                }
            )
    
    def _handle_new_local(self, repo_info) -> GitSyncResult:
        """Handle NEW_LOCAL repository state."""
        with self._safe_performance_operation("new_repository_initialization"):
            self.logger.info("🆕 Initializing new local repository")
            result = self._init_git_repository()
            if not result.success:
                return result
            
            # Configure Git remote if specified
            if self.config.git_remote_url:
                self.logger.debug(f"🔗 Configuring remote: {self.config.git_remote_url}")
                result = self._configure_git_remote()
                if not result.success:
                    self.logger.warning(f"⚠️ Git remote configuration failed: {result.message}")
                    # Don't fail initialization if remote config fails
        
        return create_git_sync_result(success=True, message="New local repository initialized", operation="handle_new_local")
    
    def _handle_existing_remote(self, repo_info) -> GitSyncResult:
        """Handle EXISTING_REMOTE repository state."""
        with self._safe_performance_operation("existing_repository_clone", {
            "remote_url": repo_info.remote_url,
            "default_branch": repo_info.default_branch
        }):
            self.logger.info(f"📥 Cloning existing remote repository: {repo_info.remote_url}")
            result = self.repo_state_manager.clone_existing_repository()
            if not result.success:
                return result
                
            # Set up upstream tracking for the default branch
            self.logger.debug(f"🔀 Setting up upstream tracking for branch: {repo_info.default_branch}")
            result = self.repo_state_manager.setup_upstream_tracking(repo_info.default_branch)
            if not result.success:
                self.logger.warning(f"⚠️ Failed to set up upstream tracking: {result.message}")
        
        return create_git_sync_result(success=True, message="Existing remote repository cloned", operation="handle_existing_remote")
    
    def _handle_existing_local(self, repo_info) -> GitSyncResult:
        """Handle EXISTING_LOCAL repository state."""
        with self._safe_performance_operation("existing_local_setup", {
            "has_remote": repo_info.remote_exists,
            "needs_sync": repo_info.needs_sync,
            "tracking_configured": repo_info.tracking_configured
        }):
            self.logger.info("🏠 Configuring existing local repository")
            
            if self.config.git_remote_url and not repo_info.remote_exists:
                # Configure remote if not already configured
                self.logger.debug(f"🔗 Adding remote configuration: {self.config.git_remote_url}")
                result = self._configure_git_remote()
                if not result.success:
                    self.logger.warning(f"⚠️ Git remote configuration failed: {result.message}")
            
            # If we have a remote and need sync, try to synchronize
            if repo_info.needs_sync and repo_info.remote_exists:
                self.logger.info("🔄 Synchronizing existing local repository with remote")
                result = self.repo_state_manager.synchronize_with_remote()
                if not result.success:
                    self.logger.warning(f"⚠️ Repository synchronization failed: {result.message}")
                    # Don't fail initialization if sync fails
                    
            # Set up upstream tracking if not configured
            if self.config.git_remote_url and not repo_info.tracking_configured and repo_info.local_branch:
                self.logger.debug(f"🔀 Setting up upstream tracking for local branch: {repo_info.local_branch}")
                result = self.repo_state_manager.setup_upstream_tracking(repo_info.local_branch)
                if not result.success:
                    self.logger.warning(f"⚠️ Failed to set up upstream tracking: {result.message}")
        
        return create_git_sync_result(success=True, message="Existing local repository configured", operation="handle_existing_local")
    
    def _init_git_repository(self) -> GitSyncResult:
        """
        Initialize a new Git repository using GitPython.
        
        Returns:
            GitSyncResult indicating success or failure
        """
        def init_operation():
            """GitPython operation to initialize repository."""
            repo = Repo.init(self.git_repo_dir)
            self.logger.info("Git repository initialized successfully")
            
            # Set up initial configuration
            setup_initial_git_config(self.git_repo_dir)
            return repo
            
        return execute_git_operation_with_retry(
            init_operation,
            "git_init",
            self.git_repo_dir,
            self.config
        )
    
    def _configure_git_remote(self) -> GitSyncResult:
        """
        Configure Git remote URL using GitPython.
        
        Returns:
            GitSyncResult indicating success or failure
        """
        def configure_remote_operation():
            """GitPython operation to configure remote."""
            repo = Repo(self.git_repo_dir)
            
            # Check if remote already exists
            try:
                origin_remote = repo.remote('origin')
                existing_urls = list(origin_remote.urls)
                
                if existing_urls and existing_urls[0] == self.config.git_remote_url:
                    self.logger.debug("Git remote already configured correctly")
                    return "already_configured"
                else:
                    # Update existing remote
                    origin_remote.set_url(self.config.git_remote_url)
                    self.logger.info(f"Git remote updated to: {self.config.git_remote_url}")
                    return "updated"
                    
            except GitCommandError:
                # Remote doesn't exist, create it
                repo.create_remote('origin', self.config.git_remote_url)
                self.logger.info(f"Git remote added: {self.config.git_remote_url}")
                return "added"
        
        self.logger.info(f"Configuring Git remote: {self.config.git_remote_url}")
        
        return execute_git_operation_with_retry(
            configure_remote_operation,
            "configure_remote",
            self.git_repo_dir,
            self.config
        )
    
    @property
    def initialized(self) -> bool:
        """Check if the Git sync manager is properly initialized."""
        return self._initialized and (not self.config.enable_git_sync or self.git_dir.exists())