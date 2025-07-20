"""Git synchronization manager for AIAML."""

import logging
import subprocess
import threading
from pathlib import Path
from typing import Optional, Dict, Any

from ..config import Config
from ..platform import get_platform_info, get_git_executable
from .utils import GitSyncResult
from .operations import (
    execute_git_command_with_retry,
    setup_initial_git_config,
    validate_git_configuration
)


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
        self._sync_lock = threading.Lock()
        self._initialized = False
        
        # Git repository directory (the memory directory itself contains the git repo)
        # config.memory_dir is "memory/files", so parent is "memory" which contains the .git
        self.git_repo_dir = config.memory_dir.parent  # This is the memory/ directory
        self.git_dir = self.git_repo_dir / ".git"
        
        # Initialize if Git sync is enabled
        if config.enable_git_sync:
            init_result = self._initialize_repository()
            if not init_result.success:
                self.logger.warning(f"Git repository initialization failed: {init_result.message}")
    
    def _initialize_repository(self) -> GitSyncResult:
        """
        Initialize Git repository if it doesn't exist and configure remote.
        
        Returns:
            GitSyncResult indicating success or failure
        """
        try:
            self.logger.info("Initializing Git synchronization manager")
            
            # Ensure the repository directory exists
            self.git_repo_dir.mkdir(parents=True, exist_ok=True)
            
            # Initialize Git repository if needed
            if not self.git_dir.exists():
                result = self._init_git_repository()
                if not result.success:
                    return result
            
            # Configure Git remote if specified
            if self.config.git_remote_url:
                result = self._configure_git_remote()
                if not result.success:
                    self.logger.warning(f"Git remote configuration failed: {result.message}")
                    # Don't fail initialization if remote config fails
            
            # Validate Git configuration
            validation_result = validate_git_configuration(
                self.git_repo_dir, self.git_dir, self.config
            )
            if not validation_result.success:
                self.logger.warning(f"Git configuration validation failed: {validation_result.message}")
            
            self._initialized = True
            self.logger.info("Git synchronization manager initialized successfully")
            
            return GitSyncResult(
                success=True,
                message="Git synchronization manager initialized",
                operation="initialize"
            )
            
        except Exception as e:
            error_msg = f"Failed to initialize Git synchronization manager: {e}"
            self.logger.error(error_msg, exc_info=True)
            
            return GitSyncResult(
                success=False,
                message=error_msg,
                operation="initialize",
                error_code="GIT_INIT_FAILED"
            )
    
    def _init_git_repository(self) -> GitSyncResult:
        """
        Initialize a new Git repository.
        
        Returns:
            GitSyncResult indicating success or failure
        """
        try:
            self.logger.info("Initializing new Git repository for memory synchronization")
            
            # Run git init with cross-platform executable
            git_executable = get_git_executable()
            platform_info = get_platform_info()
            
            result = subprocess.run(
                [git_executable, "init"],
                check=True,
                capture_output=True,
                text=True,
                cwd=self.git_repo_dir,
                timeout=30,
                shell=platform_info.is_windows
            )
            
            self.logger.info("Git repository initialized successfully")
            
            # Set up initial configuration
            setup_initial_git_config(self.git_repo_dir)
            
            return GitSyncResult(
                success=True,
                message="Git repository initialized",
                operation="git_init"
            )
            
        except subprocess.CalledProcessError as e:
            error_msg = f"Git init failed: {e.stderr if e.stderr else str(e)}"
            self.logger.error(error_msg)
            
            return GitSyncResult(
                success=False,
                message=error_msg,
                operation="git_init",
                error_code="GIT_INIT_COMMAND_FAILED"
            )
        
        except subprocess.TimeoutExpired:
            error_msg = "Git init timed out"
            self.logger.error(error_msg)
            
            return GitSyncResult(
                success=False,
                message=error_msg,
                operation="git_init",
                error_code="GIT_INIT_TIMEOUT"
            )
        
        except Exception as e:
            error_msg = f"Unexpected error during Git init: {e}"
            self.logger.error(error_msg, exc_info=True)
            
            return GitSyncResult(
                success=False,
                message=error_msg,
                operation="git_init",
                error_code="GIT_INIT_UNEXPECTED_ERROR"
            )
    
    def _configure_git_remote(self) -> GitSyncResult:
        """
        Configure Git remote URL.
        
        Returns:
            GitSyncResult indicating success or failure
        """
        try:
            self.logger.info(f"Configuring Git remote: {self.config.git_remote_url}")
            
            git_executable = get_git_executable()
            platform_info = get_platform_info()
            
            # Check if remote already exists
            result = subprocess.run(
                [git_executable, "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                cwd=self.git_repo_dir,
                timeout=10,
                shell=platform_info.is_windows
            )
            
            if result.returncode == 0:
                # Remote exists, check if it matches our configuration
                existing_url = result.stdout.strip()
                if existing_url == self.config.git_remote_url:
                    self.logger.debug("Git remote already configured correctly")
                    return GitSyncResult(
                        success=True,
                        message="Git remote already configured",
                        operation="configure_remote"
                    )
                else:
                    # Update existing remote
                    subprocess.run(
                        [git_executable, "remote", "set-url", "origin", self.config.git_remote_url],
                        check=True,
                        capture_output=True,
                        cwd=self.git_repo_dir,
                        timeout=10,
                        shell=platform_info.is_windows
                    )
                    self.logger.info(f"Git remote updated to: {self.config.git_remote_url}")
            else:
                # Add new remote
                subprocess.run(
                    [git_executable, "remote", "add", "origin", self.config.git_remote_url],
                    check=True,
                    capture_output=True,
                    cwd=self.git_repo_dir,
                    timeout=10,
                    shell=platform_info.is_windows
                )
                self.logger.info(f"Git remote added: {self.config.git_remote_url}")
            
            return GitSyncResult(
                success=True,
                message="Git remote configured successfully",
                operation="configure_remote"
            )
            
        except subprocess.CalledProcessError as e:
            error_msg = f"Failed to configure Git remote: {e.stderr if e.stderr else str(e)}"
            self.logger.error(error_msg)
            
            return GitSyncResult(
                success=False,
                message=error_msg,
                operation="configure_remote",
                error_code="GIT_REMOTE_CONFIG_FAILED"
            )
        
        except subprocess.TimeoutExpired:
            error_msg = "Git remote configuration timed out"
            self.logger.error(error_msg)
            
            return GitSyncResult(
                success=False,
                message=error_msg,
                operation="configure_remote",
                error_code="GIT_REMOTE_CONFIG_TIMEOUT"
            )
        
        except Exception as e:
            error_msg = f"Unexpected error configuring Git remote: {e}"
            self.logger.error(error_msg, exc_info=True)
            
            return GitSyncResult(
                success=False,
                message=error_msg,
                operation="configure_remote",
                error_code="GIT_REMOTE_CONFIG_UNEXPECTED_ERROR"
            )
    
    def sync_memory_with_retry(self, memory_id: str, filename: str) -> GitSyncResult:
        """
        Synchronize a memory file to Git with retry logic.
        
        This method performs the following operations:
        1. Add the memory file to Git
        2. Commit the changes
        3. Push to remote (if configured)
        
        Args:
            memory_id: Unique identifier for the memory
            filename: Name of the memory file
            
        Returns:
            GitSyncResult indicating success or failure
        """
        if not self.config.enable_git_sync:
            return GitSyncResult(
                success=False,
                message="Git sync is disabled",
                operation="sync_memory",
                error_code="GIT_SYNC_DISABLED"
            )
        
        if not self._initialized:
            init_result = self._initialize_repository()
            if not init_result.success:
                return init_result
        
        with self._sync_lock:
            try:
                self.logger.info(f"Starting Git sync for memory {memory_id} (file: {filename})")
                
                # Step 1: Add the file to Git
                add_result = execute_git_command_with_retry(
                    ["git", "add", f"files/{filename}"],
                    f"add memory file {filename}",
                    self.git_repo_dir,
                    self.config
                )
                
                if not add_result.success:
                    return add_result
                
                # Step 2: Commit the changes
                commit_message = f"Add memory {memory_id}"
                commit_result = execute_git_command_with_retry(
                    ["git", "commit", "-m", commit_message],
                    f"commit memory {memory_id}",
                    self.git_repo_dir,
                    self.config
                )
                
                if not commit_result.success:
                    return commit_result
                
                # Step 3: Push to remote if configured
                if self.config.git_remote_url:
                    push_result = execute_git_command_with_retry(
                        ["git", "push", "origin", "main"],
                        f"push memory {memory_id} to remote",
                        self.git_repo_dir,
                        self.config,
                        timeout=60  # Longer timeout for network operations
                    )
                    
                    if not push_result.success:
                        # Log warning but don't fail the entire operation
                        self.logger.warning(f"Failed to push memory {memory_id} to remote: {push_result.message}")
                        return GitSyncResult(
                            success=True,
                            message=f"Memory {memory_id} committed locally (push failed: {push_result.message})",
                            operation="sync_memory",
                            attempts=push_result.attempts
                        )
                    
                    self.logger.info(f"Memory {memory_id} synced to Git and pushed to remote successfully")
                    return GitSyncResult(
                        success=True,
                        message=f"Memory {memory_id} synced to Git and pushed to remote",
                        operation="sync_memory",
                        attempts=max(add_result.attempts, commit_result.attempts, push_result.attempts)
                    )
                else:
                    self.logger.info(f"Memory {memory_id} committed to Git locally (no remote configured)")
                    return GitSyncResult(
                        success=True,
                        message=f"Memory {memory_id} committed to Git locally",
                        operation="sync_memory",
                        attempts=max(add_result.attempts, commit_result.attempts)
                    )
                
            except Exception as e:
                error_msg = f"Unexpected error during Git sync for memory {memory_id}: {e}"
                self.logger.error(error_msg, exc_info=True)
                
                return GitSyncResult(
                    success=False,
                    message=error_msg,
                    operation="sync_memory",
                    error_code="GIT_SYNC_UNEXPECTED_ERROR"
                )
    
    def sync_memory_background(self, memory_id: str, filename: str) -> None:
        """
        Synchronize a memory file to Git in a background thread.
        
        This method starts a background thread to perform Git synchronization
        without blocking the main memory storage operation.
        
        Args:
            memory_id: Unique identifier for the memory
            filename: Name of the memory file
        """
        if not self.config.enable_git_sync:
            self.logger.debug("Git sync disabled, skipping background sync")
            return
        
        def sync_worker():
            try:
                result = self.sync_memory_with_retry(memory_id, filename)
                if result.success:
                    self.logger.info(f"Background Git sync completed for memory {memory_id}")
                else:
                    self.logger.warning(f"Background Git sync failed for memory {memory_id}: {result.message}")
            except Exception as e:
                self.logger.error(f"Unexpected error in background Git sync for memory {memory_id}: {e}", exc_info=True)
        
        # Start background thread
        sync_thread = threading.Thread(
            target=sync_worker,
            name=f"GitSync-{memory_id}",
            daemon=True
        )
        sync_thread.start()
        
        self.logger.debug(f"Started background Git sync thread for memory {memory_id}")
    
    def get_repository_status(self) -> Dict[str, Any]:
        """
        Get the current status of the Git repository.
        
        Returns:
            Dictionary containing repository status information
        """
        status = {
            'initialized': self._initialized,
            'git_sync_enabled': self.config.enable_git_sync,
            'repository_exists': self.git_dir.exists(),
            'remote_configured': False,
            'remote_url': self.config.git_remote_url,
            'last_error': None
        }
        
        if not self.config.enable_git_sync:
            return status
        
        try:
            # Check remote configuration
            if self.git_dir.exists():
                git_executable = get_git_executable()
                platform_info = get_platform_info()
                
                result = subprocess.run(
                    [git_executable, "remote", "get-url", "origin"],
                    capture_output=True,
                    text=True,
                    cwd=self.git_repo_dir,
                    timeout=5,
                    shell=platform_info.is_windows
                )
                
                if result.returncode == 0:
                    status['remote_configured'] = True
                    status['actual_remote_url'] = result.stdout.strip()
            
        except Exception as e:
            status['last_error'] = str(e)
        
        return status
    
    def is_initialized(self) -> bool:
        """Check if the Git sync manager is properly initialized."""
        return self._initialized and (not self.config.enable_git_sync or self.git_dir.exists())


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