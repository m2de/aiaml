"""Git command operations and execution logic using GitPython."""

import logging
import time
from pathlib import Path
from typing import List, Dict, Any

try:
    import git
    from git import Repo, GitCommandError, InvalidGitRepositoryError
    HAS_GITPYTHON = True
except ImportError:
    # Fallback when GitPython is not available
    HAS_GITPYTHON = False
    
    class GitCommandError(Exception):
        pass
    
    class InvalidGitRepositoryError(Exception):
        pass

from ..config import Config
from ..platform import get_platform_info, validate_git_availability, get_platform_specific_git_config
from .utils import GitSyncResult, create_git_sync_result


def execute_git_operation_with_retry(
    operation_func,
    operation: str, 
    git_repo_dir: Path,
    config: Config
) -> GitSyncResult:
    """
    Execute a GitPython operation with retry logic and exponential backoff.
    
    Args:
        operation_func: Function that executes the GitPython operation
        operation: Description of the operation for logging
        git_repo_dir: Git repository directory
        config: Server configuration
        
    Returns:
        GitSyncResult indicating success or failure
    """
    logger = logging.getLogger('aiaml.git_sync')
    
    if not HAS_GITPYTHON:
        return GitSyncResult(
            success=False,
            message=f"{operation} failed: GitPython not available. Please install with: pip install GitPython",
            operation=operation,
            attempts=1,
            error_code="GITPYTHON_NOT_AVAILABLE"
        )
    
    max_attempts = config.git_retry_attempts
    base_delay = config.git_retry_delay
    
    for attempt in range(1, max_attempts + 1):
        try:
            logger.debug(f"Executing Git operation (attempt {attempt}/{max_attempts}): {operation}")
            
            # Execute the GitPython operation
            result = operation_func()
            
            logger.debug(f"Git operation succeeded on attempt {attempt}")
            
            return GitSyncResult(
                success=True,
                message=f"{operation} completed successfully",
                operation=operation,
                attempts=attempt
            )
            
        except GitCommandError as e:
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
        
        except InvalidGitRepositoryError as e:
            error_msg = f"{operation} failed - invalid repository (attempt {attempt}/{max_attempts}): {e}"
            
            if attempt == max_attempts:
                logger.error(error_msg)
                return GitSyncResult(
                    success=False,
                    message=error_msg,
                    operation=operation,
                    attempts=attempt,
                    error_code="INVALID_GIT_REPOSITORY"
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
    """Set up initial Git configuration for the repository using GitPython."""
    logger = logging.getLogger('aiaml.git_sync')
    
    if not HAS_GITPYTHON:
        logger.warning("GitPython not available, skipping git configuration setup")
        return
    
    try:
        repo = Repo(git_repo_dir)
        platform_git_config = get_platform_specific_git_config()
        
        # Apply platform-specific Git configuration
        for config_key, config_value in platform_git_config.items():
            try:
                repo.config_writer().set_value("core", config_key.split('.')[-1], config_value)
                logger.debug(f"Set Git config {config_key} = {config_value}")
            except Exception as e:
                logger.warning(f"Failed to set Git config {config_key}: {e}")
        
        # Set user name and email if not already configured
        try:
            with repo.config_reader() as config_reader:
                user_name = config_reader.get_value("user", "name", fallback=None)
                if not user_name:
                    repo.config_writer().set_value("user", "name", "AIAML Memory System")
                    logger.debug("Set default Git user name")
        except Exception as e:
            # Set default user name if config reading fails
            try:
                repo.config_writer().set_value("user", "name", "AIAML Memory System")
                logger.debug("Set default Git user name (fallback)")
            except Exception as config_e:
                logger.warning(f"Failed to set Git user name: {config_e}")
        
        try:
            with repo.config_reader() as config_reader:
                user_email = config_reader.get_value("user", "email", fallback=None)
                if not user_email:
                    repo.config_writer().set_value("user", "email", "aiaml@localhost")
                    logger.debug("Set default Git user email")
        except Exception as e:
            # Set default user email if config reading fails
            try:
                repo.config_writer().set_value("user", "email", "aiaml@localhost")
                logger.debug("Set default Git user email (fallback)")
            except Exception as config_e:
                logger.warning(f"Failed to set Git user email: {config_e}")
        
        logger.debug("Git configuration completed using GitPython")
        
    except Exception as e:
        logger.warning(f"Failed to set up Git configuration: {e}")


def validate_git_configuration(git_repo_dir: Path, git_dir: Path, config: Config) -> GitSyncResult:
    """
    Validate Git repository configuration using GitPython.
    
    Returns:
        GitSyncResult indicating validation success or failure
    """
    logger = logging.getLogger('aiaml.git_sync')
    
    if not HAS_GITPYTHON:
        return GitSyncResult(
            success=False,
            message="Git configuration validation failed: GitPython not available. Please install with: pip install GitPython",
            operation="validate_config",
            error_code="GITPYTHON_NOT_AVAILABLE"
        )
    
    try:
        validation_errors = []
        
        # Check if Git is available using cross-platform validation
        git_available, git_error = validate_git_availability()
        if not git_available:
            validation_errors.append(f"Git not available: {git_error}")
        
        # Check if repository is properly initialized
        if not git_dir.exists():
            validation_errors.append("Git repository not initialized")
            
        if validation_errors:
            # Return early if basic checks fail
            error_msg = f"Git configuration validation failed: {'; '.join(validation_errors)}"
            return GitSyncResult(
                success=False,
                message=error_msg,
                operation="validate_config",
                error_code="GIT_CONFIG_VALIDATION_FAILED"
            )
        
        # Use GitPython to validate configuration
        try:
            repo = Repo(git_repo_dir)
            
            # Check Git configuration
            try:
                with repo.config_reader() as config_reader:
                    user_name = config_reader.get_value("user", "name", fallback=None)
                    if not user_name:
                        validation_errors.append("Git user.name not configured")
            except Exception:
                validation_errors.append("Git user.name not configured")
            
            try:
                with repo.config_reader() as config_reader:
                    user_email = config_reader.get_value("user", "email", fallback=None)
                    if not user_email:
                        validation_errors.append("Git user.email not configured")
            except Exception:
                validation_errors.append("Git user.email not configured")
            
            # Check remote configuration if URL is provided
            if config.git_remote_url:
                try:
                    origin_remote = repo.remote('origin')
                    remote_urls = list(origin_remote.urls)
                    if not remote_urls or remote_urls[0] != config.git_remote_url:
                        expected_url = config.git_remote_url
                        actual_url = remote_urls[0] if remote_urls else "None"
                        validation_errors.append(f"Git remote URL mismatch: expected {expected_url}, got {actual_url}")
                except git.exc.GitCommandError:
                    validation_errors.append("Git remote 'origin' not configured")
                except Exception as e:
                    validation_errors.append(f"Error checking remote configuration: {e}")
                    
        except InvalidGitRepositoryError:
            validation_errors.append("Invalid Git repository")
        except Exception as e:
            validation_errors.append(f"Error accessing repository: {e}")
        
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
    Detect the default branch of a remote repository using GitPython.
    
    This function attempts to determine the default branch name by:
    1. Using GitPython's remote functionality to get symbolic references
    2. Falling back to common branch names (main, master, develop)
    3. Defaulting to "main" if detection fails
    
    Args:
        remote_url: URL of the remote repository
        config: Server configuration for retry settings
        git_repo_dir: Git repository directory for command execution
        
    Returns:
        str: The detected default branch name
    """
    logger = logging.getLogger('aiaml.git_sync')
    
    logger.debug(f"Detecting default branch for remote: {remote_url}")
    
    # Strategy 1: Use GitPython to get remote references
    try:
        logger.debug("Attempting to detect default branch using GitPython remote references")
        
        # Create a temporary repo object or use existing one
        try:
            repo = Repo(git_repo_dir)
        except InvalidGitRepositoryError:
            # If no repo exists, we'll use git command directly via GitPython
            repo = None
        
        if repo:
            try:
                # Try to get the origin remote and its refs
                origin = repo.remote('origin')
                refs = origin.refs
                
                # Look for HEAD reference
                for ref in refs:
                    if ref.name == 'origin/HEAD':
                        # Extract branch name from the reference
                        branch_name = str(ref.ref).replace('refs/heads/', '')
                        logger.info(f"Detected default branch via GitPython remote refs: {branch_name}")
                        return branch_name
            except Exception as e:
                logger.debug(f"Failed to get remote refs via GitPython: {e}")
        
        # Fallback: Use git command via GitPython
        try:
            git_cmd = git.Git()
            result = git_cmd.ls_remote('--symref', remote_url, 'HEAD')
            
            # Parse the output to find the symbolic reference
            # Expected format: "ref: refs/heads/main\tHEAD"
            for line in result.strip().split('\n'):
                if line.startswith('ref: refs/heads/'):
                    branch_name = line.split('ref: refs/heads/')[1].split('\t')[0].strip()
                    logger.info(f"Detected default branch via GitPython ls-remote: {branch_name}")
                    return branch_name
                    
        except GitCommandError as e:
            logger.warning(f"Failed to detect default branch via GitPython ls-remote: {e}")
        except Exception as e:
            logger.warning(f"Unexpected error detecting default branch via GitPython: {e}")
                
    except Exception as e:
        logger.warning(f"Unexpected error detecting default branch: {e}")
    
    # Strategy 2: Try common branch names by checking if they exist on remote
    common_branches = ["main", "master", "develop"]
    logger.debug(f"Falling back to checking common branch names: {common_branches}")
    
    for branch_name in common_branches:
        try:
            logger.debug(f"Checking if branch '{branch_name}' exists on remote")
            
            git_cmd = git.Git()
            result = git_cmd.ls_remote('--heads', remote_url, branch_name)
            
            # If the command succeeds and returns output, the branch exists
            if result.strip():
                logger.info(f"Found existing branch on remote: {branch_name}")
                return branch_name
                
        except GitCommandError as e:
            logger.debug(f"Branch '{branch_name}' not found on remote: {e}")
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