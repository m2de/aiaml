"""Repository cloning utilities for Git synchronization."""

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from ..config import Config
from ..platform import get_git_executable, get_platform_info, get_platform_specific_git_config
from .utils import GitSyncResult, create_git_sync_result
from .validation import validate_cloned_repository
from .repository_info import RepositoryState, RepositoryInfo
from .branch_utils import get_current_local_branch


def clone_existing_repository(config: Config, git_repo_dir: Path) -> GitSyncResult:
    """
    Clone an existing remote repository to the local directory.
    
    This function performs the following operations:
    1. Validates that a remote URL is configured
    2. Ensures the local directory is empty or doesn't exist
    3. Clones the remote repository using Git clone
    4. Validates the cloned repository structure
    5. Sets up proper Git configuration
    
    Args:
        config: Server configuration containing Git settings
        git_repo_dir: Path to the Git repository directory
        
    Returns:
        GitSyncResult indicating success or failure of the clone operation
        
    Requirements: 1.3, 3.1, 3.2
    """
    logger = logging.getLogger('aiaml.git_sync.clone')
    git_dir = git_repo_dir / ".git"
    temp_backup_dir = None
    
    try:
        logger.info("Starting repository clone operation")
        
        # Validate that remote URL is configured
        if not config.git_remote_url:
            error_msg = "Cannot clone repository: no remote URL configured"
            logger.error(error_msg)
            return GitSyncResult(
                success=False,
                message=error_msg,
                operation="clone_repository",
                error_code="NO_REMOTE_URL"
            )
        
        # Check if local repository already exists
        if git_dir.exists():
            error_msg = "Cannot clone repository: local Git repository already exists"
            logger.error(error_msg)
            return GitSyncResult(
                success=False,
                message=error_msg,
                operation="clone_repository",
                error_code="LOCAL_REPO_EXISTS"
            )
        
        # Ensure parent directory exists
        git_repo_dir.parent.mkdir(parents=True, exist_ok=True)
        
        # If the target directory exists and is not empty, we need to handle it
        if git_repo_dir.exists():
            # Check if directory is empty
            if any(git_repo_dir.iterdir()):
                # Directory exists and is not empty
                # Check if it contains only expected files (like .gitignore, README, etc.)
                existing_files = list(git_repo_dir.iterdir())
                allowed_files = {'.gitignore', 'README.md', 'README.txt', 'LICENSE', 'LICENSE.txt'}
                
                non_allowed_files = [
                    f for f in existing_files 
                    if f.name not in allowed_files and not f.name.startswith('.')
                ]
                
                if non_allowed_files:
                    error_msg = f"Cannot clone repository: target directory contains files: {[f.name for f in non_allowed_files]}"
                    logger.error(error_msg)
                    return GitSyncResult(
                        success=False,
                        message=error_msg,
                        operation="clone_repository",
                        error_code="TARGET_DIR_NOT_EMPTY"
                    )
                else:
                    # Directory contains only allowed files, move them temporarily
                    temp_backup_dir = git_repo_dir.parent / f"{git_repo_dir.name}_backup_temp"
                    temp_backup_dir.mkdir(exist_ok=True)
                    
                    # Move allowed files to temporary location
                    for file_path in existing_files:
                        shutil.move(str(file_path), str(temp_backup_dir / file_path.name))
                    
                    # Remove the now-empty directory
                    git_repo_dir.rmdir()
        
        # Perform the Git clone operation
        logger.info(f"Cloning repository from {config.git_remote_url}")
        
        git_executable = get_git_executable()
        platform_info = get_platform_info()
        
        # Use git clone with appropriate options
        clone_command = [
            git_executable, "clone",
            config.git_remote_url,
            str(git_repo_dir)
        ]
        
        # Add additional clone options for better reliability
        clone_command.extend([
            "--single-branch",  # Only clone the default branch initially
            "--depth", "1"      # Shallow clone for faster operation
        ])
        
        result = subprocess.run(
            clone_command,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout for clone operations
            shell=platform_info.is_windows
        )
        
        if result.returncode != 0:
            error_msg = f"Git clone failed: {result.stderr if result.stderr else result.stdout}"
            logger.error(error_msg)
            return create_git_sync_result(
                success=False,
                message=error_msg,
                operation="clone_repository",
                error_code="GIT_CLONE_FAILED"
            )
        
        logger.info("Repository cloned successfully")
        
        # Validate the cloned repository structure
        validation_result = validate_cloned_repository(git_repo_dir, config.git_remote_url)
        if not validation_result.success:
            return validation_result
        
        # Set up Git configuration for the cloned repository
        setup_result = setup_cloned_repository_config(git_repo_dir)
        if not setup_result.success:
            # Log warning but don't fail the clone operation
            logger.warning(f"Failed to set up cloned repository configuration: {setup_result.message}")
        
        # Restore any backed up files
        if temp_backup_dir and temp_backup_dir.exists():
            try:
                for backup_file in temp_backup_dir.iterdir():
                    target_path = git_repo_dir / backup_file.name
                    if not target_path.exists():  # Don't overwrite cloned files
                        shutil.move(str(backup_file), str(target_path))
                
                # Clean up temporary backup directory
                if not any(temp_backup_dir.iterdir()):  # Only remove if empty
                    temp_backup_dir.rmdir()
                else:
                    # If not empty, remove remaining files first
                    for remaining_file in temp_backup_dir.iterdir():
                        if remaining_file.is_file():
                            remaining_file.unlink()
                        elif remaining_file.is_dir():
                            shutil.rmtree(remaining_file)
                    temp_backup_dir.rmdir()
                
                logger.debug("Restored backed up files after clone")
            except Exception as e:
                logger.warning(f"Failed to restore backed up files: {e}")
        
        logger.info(f"Repository clone completed successfully from {config.git_remote_url}")
        
        # Detect the current branch after cloning
        current_branch = get_current_local_branch(git_repo_dir)
        if not current_branch:
            current_branch = "main"  # Fallback
        
        # Create repository info for the cloned repository
        # After successful cloning, we have a synchronized local repository
        repo_info = RepositoryInfo(
            state=RepositoryState.SYNCHRONIZED,
            local_exists=True,
            remote_exists=True,
            remote_url=config.git_remote_url,
            default_branch=current_branch,
            local_branch=current_branch,
            tracking_configured=True,  # Clone sets up tracking automatically
            needs_sync=False
        )
        
        return create_git_sync_result(
            success=True,
            message=f"Repository cloned successfully from {config.git_remote_url}",
            operation="clone_repository",
            repository_info=repo_info,
            branch_used=current_branch
        )
        
    except subprocess.TimeoutExpired:
        error_msg = "Repository clone operation timed out"
        logger.error(error_msg)
        return create_git_sync_result(
            success=False,
            message=error_msg,
            operation="clone_repository",
            error_code="CLONE_TIMEOUT"
        )
        
    except Exception as e:
        error_msg = f"Unexpected error during repository clone: {e}"
        logger.error(error_msg, exc_info=True)
        return GitSyncResult(
            success=False,
            message=error_msg,
            operation="clone_repository",
            error_code="CLONE_UNEXPECTED_ERROR"
        )


def setup_cloned_repository_config(git_repo_dir: Path) -> GitSyncResult:
    """
    Set up Git configuration for a cloned repository.
    
    This function ensures that the cloned repository has proper:
    1. User name and email configuration
    2. Platform-specific Git settings
    3. Any additional AIAML-specific configuration
    
    Args:
        git_repo_dir: Path to the Git repository directory
        
    Returns:
        GitSyncResult indicating setup success or failure
    """
    logger = logging.getLogger('aiaml.git_sync.clone')
    
    try:
        logger.debug("Setting up cloned repository configuration")
        
        git_executable = get_git_executable()
        platform_info = get_platform_info()
        
        # Check if user.name is configured
        result = subprocess.run(
            [git_executable, "config", "user.name"],
            capture_output=True,
            text=True,
            cwd=git_repo_dir,
            timeout=10,
            shell=platform_info.is_windows
        )
        
        if result.returncode != 0:
            # Set default user name
            subprocess.run(
                [git_executable, "config", "user.name", "AIAML Memory System"],
                check=True,
                capture_output=True,
                cwd=git_repo_dir,
                timeout=10,
                shell=platform_info.is_windows
            )
            logger.debug("Set default Git user.name for cloned repository")
        
        # Check if user.email is configured
        result = subprocess.run(
            [git_executable, "config", "user.email"],
            capture_output=True,
            text=True,
            cwd=git_repo_dir,
            timeout=10,
            shell=platform_info.is_windows
        )
        
        if result.returncode != 0:
            # Set default user email
            subprocess.run(
                [git_executable, "config", "user.email", "aiaml@localhost"],
                check=True,
                capture_output=True,
                cwd=git_repo_dir,
                timeout=10,
                shell=platform_info.is_windows
            )
            logger.debug("Set default Git user.email for cloned repository")
        
        # Apply platform-specific Git configuration
        platform_git_config = get_platform_specific_git_config()
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
                logger.debug(f"Set Git config {config_key} = {config_value} for cloned repository")
            except subprocess.CalledProcessError as e:
                logger.warning(f"Failed to set Git config {config_key} for cloned repository: {e}")
        
        logger.debug("Cloned repository configuration setup completed")
        
        return GitSyncResult(
            success=True,
            message="Cloned repository configuration setup completed",
            operation="setup_cloned_repo_config"
        )
        
    except subprocess.CalledProcessError as e:
        error_msg = f"Failed to set up cloned repository configuration: {e.stderr if e.stderr else str(e)}"
        logger.error(error_msg)
        return GitSyncResult(
            success=False,
            message=error_msg,
            operation="setup_cloned_repo_config",
            error_code="CONFIG_SETUP_FAILED"
        )
        
    except subprocess.TimeoutExpired:
        error_msg = "Cloned repository configuration setup timed out"
        logger.error(error_msg)
        return GitSyncResult(
            success=False,
            message=error_msg,
            operation="setup_cloned_repo_config",
            error_code="CONFIG_SETUP_TIMEOUT"
        )
        
    except Exception as e:
        error_msg = f"Unexpected error during cloned repository configuration setup: {e}"
        logger.error(error_msg, exc_info=True)
        return GitSyncResult(
            success=False,
            message=error_msg,
            operation="setup_cloned_repo_config",
            error_code="CONFIG_SETUP_UNEXPECTED_ERROR"
        )