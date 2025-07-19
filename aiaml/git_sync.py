"""Enhanced Git synchronization manager for AIAML."""

import logging
import os
import subprocess
import time
import threading
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from .config import Config
from .errors import ErrorResponse, error_handler, ErrorCategory


@dataclass
class GitSyncResult:
    """Result of a Git synchronization operation."""
    success: bool
    message: str
    operation: str
    attempts: int = 1
    error_code: Optional[str] = None


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
            self._initialize_repository()
    
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
            validation_result = self._validate_git_configuration()
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
            
            # Run git init
            result = subprocess.run(
                ["git", "init"],
                check=True,
                capture_output=True,
                text=True,
                cwd=self.git_repo_dir,
                timeout=30
            )
            
            self.logger.info("Git repository initialized successfully")
            
            # Set up initial configuration
            self._setup_initial_git_config()
            
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
    
    def _setup_initial_git_config(self) -> None:
        """Set up initial Git configuration for the repository."""
        try:
            # Set default branch to main
            subprocess.run(
                ["git", "config", "init.defaultBranch", "main"],
                check=True,
                capture_output=True,
                cwd=self.git_repo_dir,
                timeout=10
            )
            
            # Set user name and email if not already configured
            try:
                subprocess.run(
                    ["git", "config", "user.name"],
                    check=True,
                    capture_output=True,
                    cwd=self.git_repo_dir,
                    timeout=10
                )
            except subprocess.CalledProcessError:
                # User name not configured, set a default
                subprocess.run(
                    ["git", "config", "user.name", "AIAML Memory System"],
                    check=True,
                    capture_output=True,
                    cwd=self.git_repo_dir,
                    timeout=10
                )
            
            try:
                subprocess.run(
                    ["git", "config", "user.email"],
                    check=True,
                    capture_output=True,
                    cwd=self.git_repo_dir,
                    timeout=10
                )
            except subprocess.CalledProcessError:
                # User email not configured, set a default
                subprocess.run(
                    ["git", "config", "user.email", "aiaml@localhost"],
                    check=True,
                    capture_output=True,
                    cwd=self.git_repo_dir,
                    timeout=10
                )
            
            self.logger.debug("Initial Git configuration completed")
            
        except Exception as e:
            self.logger.warning(f"Failed to set up initial Git configuration: {e}")
    
    def _configure_git_remote(self) -> GitSyncResult:
        """
        Configure Git remote URL.
        
        Returns:
            GitSyncResult indicating success or failure
        """
        try:
            self.logger.info(f"Configuring Git remote: {self.config.git_remote_url}")
            
            # Check if remote already exists
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                cwd=self.git_repo_dir,
                timeout=10
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
                        ["git", "remote", "set-url", "origin", self.config.git_remote_url],
                        check=True,
                        capture_output=True,
                        cwd=self.git_repo_dir,
                        timeout=10
                    )
                    self.logger.info(f"Git remote updated to: {self.config.git_remote_url}")
            else:
                # Add new remote
                subprocess.run(
                    ["git", "remote", "add", "origin", self.config.git_remote_url],
                    check=True,
                    capture_output=True,
                    cwd=self.git_repo_dir,
                    timeout=10
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
    
    def _validate_git_configuration(self) -> GitSyncResult:
        """
        Validate Git repository configuration.
        
        Returns:
            GitSyncResult indicating validation success or failure
        """
        try:
            validation_errors = []
            
            # Check if Git is available
            try:
                subprocess.run(
                    ["git", "--version"],
                    check=True,
                    capture_output=True,
                    timeout=5
                )
            except (subprocess.CalledProcessError, FileNotFoundError):
                validation_errors.append("Git command not available")
            
            # Check if repository is properly initialized
            if not self.git_dir.exists():
                validation_errors.append("Git repository not initialized")
            
            # Check Git configuration
            try:
                subprocess.run(
                    ["git", "config", "user.name"],
                    check=True,
                    capture_output=True,
                    cwd=self.git_repo_dir,
                    timeout=5
                )
            except subprocess.CalledProcessError:
                validation_errors.append("Git user.name not configured")
            
            try:
                subprocess.run(
                    ["git", "config", "user.email"],
                    check=True,
                    capture_output=True,
                    cwd=self.git_repo_dir,
                    timeout=5
                )
            except subprocess.CalledProcessError:
                validation_errors.append("Git user.email not configured")
            
            # Check remote configuration if URL is provided
            if self.config.git_remote_url:
                try:
                    result = subprocess.run(
                        ["git", "remote", "get-url", "origin"],
                        check=True,
                        capture_output=True,
                        text=True,
                        cwd=self.git_repo_dir,
                        timeout=5
                    )
                    remote_url = result.stdout.strip()
                    if remote_url != self.config.git_remote_url:
                        validation_errors.append(f"Git remote URL mismatch: expected {self.config.git_remote_url}, got {remote_url}")
                except subprocess.CalledProcessError:
                    validation_errors.append("Git remote 'origin' not configured")
            
            if validation_errors:
                error_msg = f"Git configuration validation failed: {'; '.join(validation_errors)}"
                return GitSyncResult(
                    success=False,
                    message=error_msg,
                    operation="validate_config",
                    error_code="GIT_CONFIG_VALIDATION_FAILED"
                )
            
            return GitSyncResult(
                success=True,
                message="Git configuration validation passed",
                operation="validate_config"
            )
            
        except Exception as e:
            error_msg = f"Unexpected error during Git configuration validation: {e}"
            self.logger.error(error_msg, exc_info=True)
            
            return GitSyncResult(
                success=False,
                message=error_msg,
                operation="validate_config",
                error_code="GIT_CONFIG_VALIDATION_UNEXPECTED_ERROR"
            )
    
    def _execute_git_command_with_retry(self, command: List[str], operation: str, timeout: int = 30) -> GitSyncResult:
        """
        Execute a Git command with retry logic and exponential backoff.
        
        Args:
            command: Git command to execute
            operation: Description of the operation for logging
            timeout: Command timeout in seconds
            
        Returns:
            GitSyncResult indicating success or failure
        """
        max_attempts = self.config.git_retry_attempts
        base_delay = self.config.git_retry_delay
        
        for attempt in range(1, max_attempts + 1):
            try:
                self.logger.debug(f"Executing Git command (attempt {attempt}/{max_attempts}): {' '.join(command)}")
                
                result = subprocess.run(
                    command,
                    check=True,
                    capture_output=True,
                    text=True,
                    cwd=self.git_repo_dir,
                    timeout=timeout
                )
                
                self.logger.debug(f"Git command succeeded on attempt {attempt}")
                
                return GitSyncResult(
                    success=True,
                    message=f"{operation} completed successfully",
                    operation=operation,
                    attempts=attempt
                )
                
            except subprocess.CalledProcessError as e:
                error_msg = f"{operation} failed (attempt {attempt}/{max_attempts}): {e.stderr if e.stderr else str(e)}"
                
                if attempt == max_attempts:
                    # Final attempt failed
                    self.logger.error(error_msg)
                    return GitSyncResult(
                        success=False,
                        message=error_msg,
                        operation=operation,
                        attempts=attempt,
                        error_code="GIT_COMMAND_FAILED"
                    )
                else:
                    # Retry with exponential backoff
                    delay = base_delay * (2 ** (attempt - 1))
                    self.logger.warning(f"{error_msg}, retrying in {delay:.1f}s")
                    time.sleep(delay)
            
            except subprocess.TimeoutExpired:
                error_msg = f"{operation} timed out (attempt {attempt}/{max_attempts})"
                
                if attempt == max_attempts:
                    self.logger.error(error_msg)
                    return GitSyncResult(
                        success=False,
                        message=error_msg,
                        operation=operation,
                        attempts=attempt,
                        error_code="GIT_COMMAND_TIMEOUT"
                    )
                else:
                    delay = base_delay * (2 ** (attempt - 1))
                    self.logger.warning(f"{error_msg}, retrying in {delay:.1f}s")
                    time.sleep(delay)
            
            except Exception as e:
                error_msg = f"Unexpected error during {operation} (attempt {attempt}/{max_attempts}): {e}"
                
                if attempt == max_attempts:
                    self.logger.error(error_msg, exc_info=True)
                    return GitSyncResult(
                        success=False,
                        message=error_msg,
                        operation=operation,
                        attempts=attempt,
                        error_code="GIT_COMMAND_UNEXPECTED_ERROR"
                    )
                else:
                    delay = base_delay * (2 ** (attempt - 1))
                    self.logger.warning(f"{error_msg}, retrying in {delay:.1f}s")
                    time.sleep(delay)
        
        # This should never be reached, but just in case
        return GitSyncResult(
            success=False,
            message=f"{operation} failed after {max_attempts} attempts",
            operation=operation,
            attempts=max_attempts,
            error_code="GIT_COMMAND_MAX_RETRIES_EXCEEDED"
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
                add_result = self._execute_git_command_with_retry(
                    ["git", "add", f"files/{filename}"],
                    f"add memory file {filename}"
                )
                
                if not add_result.success:
                    return add_result
                
                # Step 2: Commit the changes
                commit_message = f"Add memory {memory_id}"
                commit_result = self._execute_git_command_with_retry(
                    ["git", "commit", "-m", commit_message],
                    f"commit memory {memory_id}"
                )
                
                if not commit_result.success:
                    return commit_result
                
                # Step 3: Push to remote if configured
                if self.config.git_remote_url:
                    push_result = self._execute_git_command_with_retry(
                        ["git", "push", "origin", "main"],
                        f"push memory {memory_id} to remote",
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
                result = subprocess.run(
                    ["git", "remote", "get-url", "origin"],
                    capture_output=True,
                    text=True,
                    cwd=self.git_repo_dir,
                    timeout=5
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


def sync_memory_to_git(memory_id: str, filename: str, config: Config) -> None:
    """
    Convenience function to sync a memory to Git using the global manager.
    
    This function is compatible with the existing sync_to_github function
    but uses the enhanced GitSyncManager.
    
    Args:
        memory_id: Unique identifier for the memory
        filename: Name of the memory file
        config: Server configuration
    """
    try:
        git_manager = get_git_sync_manager(config)
        git_manager.sync_memory_background(memory_id, filename)
    except Exception as e:
        logger = logging.getLogger('aiaml.git_sync')
        logger.error(f"Failed to start Git sync for memory {memory_id}: {e}", exc_info=True)