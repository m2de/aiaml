"""Upstream tracking operations for Git repositories."""

import logging
from pathlib import Path

from git import Repo, GitCommandError
from ..config import Config
from ..platform import get_git_executable, get_platform_info
from .branch_utils import check_remote_branch_exists, check_local_branch_exists, get_current_local_branch, check_upstream_tracking
from .remote_utils import check_local_remote_configured
from .utils import GitSyncResult, create_git_sync_result
from .validation import validate_upstream_tracking


def setup_upstream_tracking(config: Config, git_repo_dir: Path, branch_name: str, logger: logging.Logger) -> GitSyncResult:
    """
    Set up upstream tracking for a local branch with the remote branch.
    
    This function performs the following operations:
    1. Validates that the local repository exists
    2. Checks if the remote is configured
    3. Creates the local branch if it doesn't exist
    4. Sets up upstream tracking to the remote branch
    5. Validates the tracking configuration
    
    Args:
        config: Server configuration containing Git settings
        git_repo_dir: Path to the Git repository directory
        branch_name: Name of the branch to set up tracking for
        logger: Logger instance for this operation
        
    Returns:
        GitSyncResult indicating success or failure of the tracking setup
        
    Requirements: 4.1, 4.2, 4.3
    """
    try:
        logger.info(f"Setting up upstream tracking for branch: {branch_name}")
        
        git_dir = git_repo_dir / ".git"
        
        # Validate that local repository exists
        if not git_dir.exists():
            error_msg = "Cannot set up upstream tracking: local Git repository does not exist"
            logger.error(error_msg)
            return GitSyncResult(
                success=False,
                message=error_msg,
                operation="setup_upstream_tracking",
                error_code="NO_LOCAL_REPO"
            )
        
        # Validate that remote URL is configured
        if not config.git_remote_url:
            error_msg = "Cannot set up upstream tracking: no remote URL configured"
            logger.error(error_msg)
            return GitSyncResult(
                success=False,
                message=error_msg,
                operation="setup_upstream_tracking",
                error_code="NO_REMOTE_URL"
            )
        
        # Check if remote is configured in the local repository
        if not check_local_remote_configured(git_repo_dir):
            error_msg = "Cannot set up upstream tracking: remote 'origin' not configured in local repository"
            logger.error(error_msg)
            return GitSyncResult(
                success=False,
                message=error_msg,
                operation="setup_upstream_tracking",
                error_code="NO_LOCAL_REMOTE"
            )
        
        try:
            repo = Repo(git_repo_dir)
        except Exception as e:
            error_msg = f"Failed to access Git repository: {e}"
            logger.error(error_msg)
            return GitSyncResult(
                success=False,
                message=error_msg,
                operation="setup_upstream_tracking",
                error_code="REPO_ACCESS_ERROR"
            )
        
        # Check if the remote branch exists
        remote_branch_exists = check_remote_branch_exists(git_repo_dir, branch_name)
        if not remote_branch_exists:
            error_msg = f"Cannot set up upstream tracking: remote branch 'origin/{branch_name}' does not exist"
            logger.error(error_msg)
            return GitSyncResult(
                success=False,
                message=error_msg,
                operation="setup_upstream_tracking",
                error_code="REMOTE_BRANCH_NOT_FOUND"
            )
        
        # Check if local branch exists
        local_branch_exists = check_local_branch_exists(git_repo_dir, branch_name)
        
        if not local_branch_exists:
            # Create local branch from remote
            logger.debug(f"Creating local branch '{branch_name}' from remote")
            
            try:
                origin = repo.remotes.origin
                remote_branch = origin.refs[branch_name]
                new_branch = repo.create_head(branch_name, remote_branch)
                new_branch.set_tracking_branch(remote_branch)
                new_branch.checkout()
                
                logger.info(f"Created local branch '{branch_name}' from remote")
                
                # Verify tracking was set up
                if new_branch.tracking_branch():
                    logger.info(f"Upstream tracking automatically configured for branch '{branch_name}'")
                    return GitSyncResult(
                        success=True,
                        message=f"Successfully created branch '{branch_name}' with upstream tracking",
                        operation="setup_upstream_tracking"
                    )
            except Exception as e:
                error_msg = f"Failed to create local branch '{branch_name}': {e}"
                logger.error(error_msg)
                return GitSyncResult(
                    success=False,
                    message=error_msg,
                    operation="setup_upstream_tracking",
                    error_code="BRANCH_CREATION_FAILED"
                )
        else:
            # Local branch exists, check if tracking is already configured
            if check_upstream_tracking(git_repo_dir, branch_name):
                logger.info(f"Upstream tracking already configured for branch '{branch_name}'")
                return GitSyncResult(
                    success=True,
                    message=f"Upstream tracking already configured for branch '{branch_name}'",
                    operation="setup_upstream_tracking"
                )
            
            # Switch to the branch if not already on it
            current_branch = get_current_local_branch(git_repo_dir)
            if current_branch != branch_name:
                logger.debug(f"Switching to branch '{branch_name}'")
                
                try:
                    repo.heads[branch_name].checkout()
                except Exception as e:
                    error_msg = f"Failed to switch to branch '{branch_name}': {e}"
                    logger.error(error_msg)
                    return GitSyncResult(
                        success=False,
                        message=error_msg,
                        operation="setup_upstream_tracking",
                        error_code="BRANCH_CHECKOUT_FAILED"
                    )
        
        # Set up upstream tracking manually
        logger.debug(f"Setting up upstream tracking for branch '{branch_name}'")
        
        try:
            local_branch = repo.heads[branch_name]
            remote_branch = repo.remotes.origin.refs[branch_name]
            local_branch.set_tracking_branch(remote_branch)
        except Exception as e:
            error_msg = f"Failed to set upstream tracking for branch '{branch_name}': {e}"
            logger.error(error_msg)
            return GitSyncResult(
                success=False,
                message=error_msg,
                operation="setup_upstream_tracking",
                error_code="UPSTREAM_SETUP_FAILED"
            )
        
        # Validate that tracking is now configured
        validation_result = validate_upstream_tracking(git_repo_dir, branch_name)
        if not validation_result.success:
            return validation_result
        
        logger.info(f"Successfully set up upstream tracking for branch '{branch_name}'")
        
        return GitSyncResult(
            success=True,
            message=f"Successfully set up upstream tracking for branch '{branch_name}'",
            operation="setup_upstream_tracking"
        )
        
    except GitCommandError as e:
        error_msg = f"Git command error during upstream tracking setup for branch '{branch_name}': {e}"
        logger.error(error_msg)
        return GitSyncResult(
            success=False,
            message=error_msg,
            operation="setup_upstream_tracking",
            error_code="GIT_COMMAND_ERROR"
        )
        
    except Exception as e:
        error_msg = f"Unexpected error during upstream tracking setup for branch '{branch_name}': {e}"
        logger.error(error_msg, exc_info=True)
        return GitSyncResult(
            success=False,
            message=error_msg,
            operation="setup_upstream_tracking",
            error_code="UPSTREAM_SETUP_UNEXPECTED_ERROR"
        )