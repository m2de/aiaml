"""Git command operations and execution logic."""

import logging
import subprocess
import time
from pathlib import Path
from typing import List, Dict, Any

from ..config import Config
from .utils import GitSyncResult


def execute_git_command_with_retry(
    command: List[str], 
    operation: str, 
    git_repo_dir: Path,
    config: Config,
    timeout: int = 30
) -> GitSyncResult:
    """
    Execute a Git command with retry logic and exponential backoff.
    
    Args:
        command: Git command to execute
        operation: Description of the operation for logging
        git_repo_dir: Git repository directory
        config: Server configuration
        timeout: Command timeout in seconds
        
    Returns:
        GitSyncResult indicating success or failure
    """
    logger = logging.getLogger('aiaml.git_sync')
    max_attempts = config.git_retry_attempts
    base_delay = config.git_retry_delay
    
    for attempt in range(1, max_attempts + 1):
        try:
            logger.debug(f"Executing Git command (attempt {attempt}/{max_attempts}): {' '.join(command)}")
            
            result = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                cwd=git_repo_dir,
                timeout=timeout
            )
            
            logger.debug(f"Git command succeeded on attempt {attempt}")
            
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
                logger.error(error_msg)
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
                logger.warning(f"{error_msg}, retrying in {delay:.1f}s")
                time.sleep(delay)
        
        except subprocess.TimeoutExpired:
            error_msg = f"{operation} timed out (attempt {attempt}/{max_attempts})"
            
            if attempt == max_attempts:
                logger.error(error_msg)
                return GitSyncResult(
                    success=False,
                    message=error_msg,
                    operation=operation,
                    attempts=attempt,
                    error_code="GIT_COMMAND_TIMEOUT"
                )
            else:
                delay = base_delay * (2 ** (attempt - 1))
                logger.warning(f"{error_msg}, retrying in {delay:.1f}s")
                time.sleep(delay)
        
        except Exception as e:
            error_msg = f"Unexpected error during {operation} (attempt {attempt}/{max_attempts}): {e}"
            
            if attempt == max_attempts:
                logger.error(error_msg, exc_info=True)
                return GitSyncResult(
                    success=False,
                    message=error_msg,
                    operation=operation,
                    attempts=attempt,
                    error_code="GIT_COMMAND_UNEXPECTED_ERROR"
                )
            else:
                delay = base_delay * (2 ** (attempt - 1))
                logger.warning(f"{error_msg}, retrying in {delay:.1f}s")
                time.sleep(delay)
    
    # This should never be reached, but just in case
    return GitSyncResult(
        success=False,
        message=f"{operation} failed after {max_attempts} attempts",
        operation=operation,
        attempts=max_attempts,
        error_code="GIT_COMMAND_MAX_RETRIES_EXCEEDED"
    )


def setup_initial_git_config(git_repo_dir: Path) -> None:
    """Set up initial Git configuration for the repository."""
    logger = logging.getLogger('aiaml.git_sync')
    
    try:
        # Set default branch to main
        subprocess.run(
            ["git", "config", "init.defaultBranch", "main"],
            check=True,
            capture_output=True,
            cwd=git_repo_dir,
            timeout=10
        )
        
        # Set user name and email if not already configured
        try:
            subprocess.run(
                ["git", "config", "user.name"],
                check=True,
                capture_output=True,
                cwd=git_repo_dir,
                timeout=10
            )
        except subprocess.CalledProcessError:
            # User name not configured, set a default
            subprocess.run(
                ["git", "config", "user.name", "AIAML Memory System"],
                check=True,
                capture_output=True,
                cwd=git_repo_dir,
                timeout=10
            )
        
        try:
            subprocess.run(
                ["git", "config", "user.email"],
                check=True,
                capture_output=True,
                cwd=git_repo_dir,
                timeout=10
            )
        except subprocess.CalledProcessError:
            # User email not configured, set a default
            subprocess.run(
                ["git", "config", "user.email", "aiaml@localhost"],
                check=True,
                capture_output=True,
                cwd=git_repo_dir,
                timeout=10
            )
        
        logger.debug("Initial Git configuration completed")
        
    except Exception as e:
        logger.warning(f"Failed to set up initial Git configuration: {e}")


def validate_git_configuration(git_repo_dir: Path, git_dir: Path, config: Config) -> GitSyncResult:
    """
    Validate Git repository configuration.
    
    Returns:
        GitSyncResult indicating validation success or failure
    """
    logger = logging.getLogger('aiaml.git_sync')
    
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
        if not git_dir.exists():
            validation_errors.append("Git repository not initialized")
        
        # Check Git configuration
        try:
            subprocess.run(
                ["git", "config", "user.name"],
                check=True,
                capture_output=True,
                cwd=git_repo_dir,
                timeout=5
            )
        except subprocess.CalledProcessError:
            validation_errors.append("Git user.name not configured")
        
        try:
            subprocess.run(
                ["git", "config", "user.email"],
                check=True,
                capture_output=True,
                cwd=git_repo_dir,
                timeout=5
            )
        except subprocess.CalledProcessError:
            validation_errors.append("Git user.email not configured")
        
        # Check remote configuration if URL is provided
        if config.git_remote_url:
            try:
                result = subprocess.run(
                    ["git", "remote", "get-url", "origin"],
                    check=True,
                    capture_output=True,
                    text=True,
                    cwd=git_repo_dir,
                    timeout=5
                )
                remote_url = result.stdout.strip()
                if remote_url != config.git_remote_url:
                    validation_errors.append(f"Git remote URL mismatch: expected {config.git_remote_url}, got {remote_url}")
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
        logger.error(error_msg, exc_info=True)
        
        return GitSyncResult(
            success=False,
            message=error_msg,
            operation="validate_config",
            error_code="GIT_CONFIG_VALIDATION_UNEXPECTED_ERROR"
        )


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
        from .manager import get_git_sync_manager
        git_manager = get_git_sync_manager(config)
        git_manager.sync_memory_background(memory_id, filename)
    except Exception as e:
        logger = logging.getLogger('aiaml.git_sync')
        logger.error(f"Failed to start Git sync for memory {memory_id}: {e}", exc_info=True)