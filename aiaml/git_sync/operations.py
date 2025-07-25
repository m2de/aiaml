"""Git command operations and execution logic."""

import logging
import subprocess
import time
from pathlib import Path
from typing import List, Dict, Any

from ..config import Config
from ..platform import get_platform_info, get_git_executable, validate_git_availability, get_platform_specific_git_config
from .utils import GitSyncResult, create_git_sync_result


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
    
    # Use platform-specific Git executable
    git_executable = get_git_executable()
    if command[0] == "git":
        command[0] = git_executable
    
    for attempt in range(1, max_attempts + 1):
        try:
            logger.debug(f"Executing Git command (attempt {attempt}/{max_attempts}): {' '.join(command)}")
            
            result = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                cwd=git_repo_dir,
                timeout=timeout,
                shell=get_platform_info().is_windows  # Use shell on Windows for better compatibility
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
    """Set up initial Git configuration for the repository with cross-platform support."""
    logger = logging.getLogger('aiaml.git_sync')
    
    try:
        git_executable = get_git_executable()
        platform_info = get_platform_info()
        platform_git_config = get_platform_specific_git_config()
        
        # Apply platform-specific Git configuration
        for config_key, config_value in platform_git_config.items():
            try:
                subprocess.run(
                    [git_executable, "config", config_key, config_value],
                    check=True,
                    capture_output=True,
                    cwd=git_repo_dir,
                    timeout=10,
                    shell=platform_info.is_windows
                )
                logger.debug(f"Set Git config {config_key} = {config_value}")
            except subprocess.CalledProcessError as e:
                logger.warning(f"Failed to set Git config {config_key}: {e}")
        
        # Set user name and email if not already configured
        try:
            subprocess.run(
                [git_executable, "config", "user.name"],
                check=True,
                capture_output=True,
                cwd=git_repo_dir,
                timeout=10,
                shell=platform_info.is_windows
            )
        except subprocess.CalledProcessError:
            # User name not configured, set a default
            subprocess.run(
                [git_executable, "config", "user.name", "AIAML Memory System"],
                check=True,
                capture_output=True,
                cwd=git_repo_dir,
                timeout=10,
                shell=platform_info.is_windows
            )
        
        try:
            subprocess.run(
                [git_executable, "config", "user.email"],
                check=True,
                capture_output=True,
                cwd=git_repo_dir,
                timeout=10,
                shell=platform_info.is_windows
            )
        except subprocess.CalledProcessError:
            # User email not configured, set a default
            subprocess.run(
                [git_executable, "config", "user.email", "aiaml@localhost"],
                check=True,
                capture_output=True,
                cwd=git_repo_dir,
                timeout=10,
                shell=platform_info.is_windows
            )
        
        logger.debug("Cross-platform Git configuration completed")
        
    except Exception as e:
        logger.warning(f"Failed to set up cross-platform Git configuration: {e}")


def validate_git_configuration(git_repo_dir: Path, git_dir: Path, config: Config) -> GitSyncResult:
    """
    Validate Git repository configuration with cross-platform support.
    
    Returns:
        GitSyncResult indicating validation success or failure
    """
    logger = logging.getLogger('aiaml.git_sync')
    
    try:
        validation_errors = []
        git_executable = get_git_executable()
        platform_info = get_platform_info()
        
        # Check if Git is available using cross-platform validation
        git_available, git_error = validate_git_availability()
        if not git_available:
            validation_errors.append(f"Git not available: {git_error}")
        
        # Check if repository is properly initialized
        if not git_dir.exists():
            validation_errors.append("Git repository not initialized")
        
        # Check Git configuration
        try:
            subprocess.run(
                [git_executable, "config", "user.name"],
                check=True,
                capture_output=True,
                cwd=git_repo_dir,
                timeout=5,
                shell=platform_info.is_windows
            )
        except subprocess.CalledProcessError:
            validation_errors.append("Git user.name not configured")
        
        try:
            subprocess.run(
                [git_executable, "config", "user.email"],
                check=True,
                capture_output=True,
                cwd=git_repo_dir,
                timeout=5,
                shell=platform_info.is_windows
            )
        except subprocess.CalledProcessError:
            validation_errors.append("Git user.email not configured")
        
        # Check remote configuration if URL is provided
        if config.git_remote_url:
            try:
                result = subprocess.run(
                    [git_executable, "remote", "get-url", "origin"],
                    check=True,
                    capture_output=True,
                    text=True,
                    cwd=git_repo_dir,
                    timeout=5,
                    shell=platform_info.is_windows
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


def detect_remote_default_branch(remote_url: str, config: Config, git_repo_dir: Path) -> str:
    """
    Detect the default branch of a remote repository.
    
    This function attempts to determine the default branch name by:
    1. Using `git ls-remote --symref` to get symbolic references
    2. Parsing the symbolic reference to extract branch name
    3. Falling back to common branch names (main, master, develop)
    4. Defaulting to "main" if detection fails
    
    Args:
        remote_url: URL of the remote repository
        config: Server configuration for retry settings
        git_repo_dir: Git repository directory for command execution
        
    Returns:
        str: The detected default branch name
        
    Requirements: 2.1, 2.2, 2.3
    """
    logger = logging.getLogger('aiaml.git_sync')
    git_executable = get_git_executable()
    platform_info = get_platform_info()
    
    logger.debug(f"Detecting default branch for remote: {remote_url}")
    
    # Strategy 1: Use git ls-remote --symref to get symbolic reference
    try:
        logger.debug("Attempting to detect default branch using symbolic references")
        
        result = subprocess.run(
            [git_executable, "ls-remote", "--symref", remote_url, "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
            shell=platform_info.is_windows
        )
        
        # Parse the output to find the symbolic reference
        # Expected format: "ref: refs/heads/main\tHEAD"
        for line in result.stdout.strip().split('\n'):
            if line.startswith('ref: refs/heads/'):
                branch_name = line.split('ref: refs/heads/')[1].split('\t')[0].strip()
                logger.info(f"Detected default branch via symbolic reference: {branch_name}")
                return branch_name
                
    except subprocess.CalledProcessError as e:
        logger.warning(f"Failed to detect default branch via symbolic reference: {e.stderr if e.stderr else str(e)}")
    except subprocess.TimeoutExpired:
        logger.warning("Timeout while detecting default branch via symbolic reference")
    except Exception as e:
        logger.warning(f"Unexpected error detecting default branch via symbolic reference: {e}")
    
    # Strategy 2: Try common branch names by checking if they exist on remote
    common_branches = ["main", "master", "develop"]
    logger.debug(f"Falling back to checking common branch names: {common_branches}")
    
    for branch_name in common_branches:
        try:
            logger.debug(f"Checking if branch '{branch_name}' exists on remote")
            
            result = subprocess.run(
                [git_executable, "ls-remote", "--heads", remote_url, branch_name],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
                shell=platform_info.is_windows
            )
            
            # If the command succeeds and returns output, the branch exists
            if result.stdout.strip():
                logger.info(f"Found existing branch on remote: {branch_name}")
                return branch_name
                
        except subprocess.CalledProcessError as e:
            logger.debug(f"Branch '{branch_name}' not found on remote: {e.stderr if e.stderr else str(e)}")
        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout while checking branch '{branch_name}' on remote")
        except Exception as e:
            logger.debug(f"Error checking branch '{branch_name}' on remote: {e}")
    
    # Strategy 3: Default fallback
    default_branch = "main"
    logger.warning(f"Could not detect default branch, falling back to: {default_branch}")
    return default_branch


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