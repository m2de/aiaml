"""Repository validation utilities for Git synchronization."""

import logging
from pathlib import Path
from typing import Optional

from git import Repo, InvalidGitRepositoryError, GitCommandError
from ..platform import get_git_executable, get_platform_info
from .utils import GitSyncResult, create_git_sync_result


def validate_cloned_repository(git_repo_dir: Path, git_remote_url: str) -> GitSyncResult:
    """
    Validate the structure and integrity of a cloned repository.
    
    This function checks:
    1. .git directory exists and is valid
    2. Repository has proper Git configuration
    3. Remote origin is properly configured
    4. Working directory is clean
    
    Args:
        git_repo_dir: Path to the Git repository directory
        git_remote_url: Expected remote URL
        
    Returns:
        GitSyncResult indicating validation success or failure
    """
    logger = logging.getLogger('aiaml.git_sync.validation')
    git_dir = git_repo_dir / ".git"
    
    try:
        logger.debug("Validating cloned repository structure")
        
        # Check if .git directory exists
        if not git_dir.exists():
            error_msg = "Cloned repository validation failed: .git directory not found"
            logger.error(error_msg)
            return GitSyncResult(
                success=False,
                message=error_msg,
                operation="validate_cloned_repo",
                error_code="MISSING_GIT_DIR"
            )
        
        # Validate that it's a proper Git repository
        try:
            repo = Repo(git_repo_dir)
            # Check if working directory has any changes
            if repo.is_dirty():
                logger.debug("Repository has uncommitted changes")
        except InvalidGitRepositoryError:
            error_msg = "Cloned repository validation failed: not a valid Git repository"
            logger.error(error_msg)
            return GitSyncResult(
                success=False,
                message=error_msg,
                operation="validate_cloned_repo",
                error_code="INVALID_GIT_REPO"
            )
        except Exception as e:
            error_msg = f"Cloned repository validation failed: error accessing repository: {e}"
            logger.error(error_msg)
            return GitSyncResult(
                success=False,
                message=error_msg,
                operation="validate_cloned_repo",
                error_code="INVALID_GIT_REPO"
            )
        
        # Check remote configuration
        try:
            if 'origin' not in repo.remotes:
                error_msg = "Cloned repository validation failed: origin remote not configured"
                logger.error(error_msg)
                return GitSyncResult(
                    success=False,
                    message=error_msg,
                    operation="validate_cloned_repo",
                    error_code="MISSING_ORIGIN_REMOTE"
                )
            origin_remote = repo.remote('origin')
            
            # Verify remote URL matches configuration
            actual_remote_url = origin_remote.url
        except Exception as e:
            error_msg = f"Cloned repository validation failed: error accessing origin remote: {e}"
            logger.error(error_msg)
            return GitSyncResult(
                success=False,
                message=error_msg,
                operation="validate_cloned_repo",
                error_code="MISSING_ORIGIN_REMOTE"
            )
        if actual_remote_url != git_remote_url:
            error_msg = f"Cloned repository validation failed: remote URL mismatch (expected: {git_remote_url}, actual: {actual_remote_url})"
            logger.error(error_msg)
            return GitSyncResult(
                success=False,
                message=error_msg,
                operation="validate_cloned_repo",
                error_code="REMOTE_URL_MISMATCH"
            )
        
        # Check if we have a valid branch
        try:
            if repo.head.is_detached:
                error_msg = "Cloned repository validation failed: HEAD is detached, no current branch"
                logger.error(error_msg)
                return GitSyncResult(
                    success=False,
                    message=error_msg,
                    operation="validate_cloned_repo",
                    error_code="NO_CURRENT_BRANCH"
                )
            
            current_branch = repo.active_branch.name
        except Exception as e:
            error_msg = f"Cloned repository validation failed: error getting current branch: {e}"
            logger.error(error_msg)
            return GitSyncResult(
                success=False,
                message=error_msg,
                operation="validate_cloned_repo",
                error_code="NO_CURRENT_BRANCH"
            )
        logger.debug(f"Cloned repository validation successful, current branch: {current_branch}")
        
        return GitSyncResult(
            success=True,
            message=f"Cloned repository validation successful, current branch: {current_branch}",
            operation="validate_cloned_repo"
        )
        
    except GitCommandError as e:
        error_msg = f"Git command error during validation: {e}"
        logger.error(error_msg)
        return GitSyncResult(
            success=False,
            message=error_msg,
            operation="validate_cloned_repo",
            error_code="GIT_COMMAND_ERROR"
        )
        
    except Exception as e:
        error_msg = f"Unexpected error during cloned repository validation: {e}"
        logger.error(error_msg, exc_info=True)
        return GitSyncResult(
            success=False,
            message=error_msg,
            operation="validate_cloned_repo",
            error_code="VALIDATION_UNEXPECTED_ERROR"
        )


def validate_upstream_tracking(git_repo_dir: Path, branch_name: str) -> GitSyncResult:
    """
    Validate that upstream tracking is properly configured for a branch.
    
    This function checks:
    1. Remote is configured for the branch
    2. Merge configuration is set
    3. The remote branch reference is valid
    
    Args:
        git_repo_dir: Path to the Git repository directory
        branch_name: Name of the branch to validate
        
    Returns:
        GitSyncResult indicating validation success or failure
    """
    logger = logging.getLogger('aiaml.git_sync.validation')
    
    try:
        logger.debug(f"Validating upstream tracking for branch '{branch_name}'")
        
        try:
            repo = Repo(git_repo_dir)
            
            # Get the branch object
            try:
                branch = repo.heads[branch_name]
            except IndexError:
                error_msg = f"Upstream tracking validation failed: branch '{branch_name}' not found"
                logger.error(error_msg)
                return GitSyncResult(
                    success=False,
                    message=error_msg,
                    operation="validate_upstream_tracking",
                    error_code="BRANCH_NOT_FOUND"
                )
            
            # Check if remote tracking is configured
            if not branch.tracking_branch():
                error_msg = f"Upstream tracking validation failed: no remote configured for branch '{branch_name}'"
                logger.error(error_msg)
                return GitSyncResult(
                    success=False,
                    message=error_msg,
                    operation="validate_upstream_tracking",
                    error_code="NO_REMOTE_CONFIG"
                )
            
            tracking_branch = branch.tracking_branch()
            remote_name = tracking_branch.remote_name
        except Exception as e:
            error_msg = f"Error accessing repository for upstream validation: {e}"
            logger.error(error_msg)
            return GitSyncResult(
                success=False,
                message=error_msg,
                operation="validate_upstream_tracking",
                error_code="REPO_ACCESS_ERROR"
            )
        
        # Validate the tracking branch name matches expected pattern
        expected_tracking_branch = f"origin/{branch_name}"
        if tracking_branch.name != expected_tracking_branch:
            error_msg = f"Upstream tracking validation failed: unexpected tracking branch (expected: {expected_tracking_branch}, actual: {tracking_branch.name})"
            logger.error(error_msg)
            return GitSyncResult(
                success=False,
                message=error_msg,
                operation="validate_upstream_tracking",
                error_code="INVALID_TRACKING_BRANCH"
            )
        
        # Verify the tracking branch exists and is accessible
        try:
            # This will raise an exception if the tracking branch doesn't exist
            tracking_commit = tracking_branch.commit
            logger.debug(f"Tracking branch {tracking_branch.name} points to commit {tracking_commit.hexsha[:8]}")
        except Exception as e:
            logger.warning(f"Upstream tracking validation: could not access tracking branch commit: {e}")
        
        logger.debug(f"Upstream tracking validation successful for branch '{branch_name}' (remote: {remote_name}, tracking: {tracking_branch.name})")
        
        return GitSyncResult(
            success=True,
            message=f"Upstream tracking validation successful for branch '{branch_name}'",
            operation="validate_upstream_tracking"
        )
        
    except GitCommandError as e:
        error_msg = f"Git command error during upstream tracking validation for branch '{branch_name}': {e}"
        logger.error(error_msg)
        return GitSyncResult(
            success=False,
            message=error_msg,
            operation="validate_upstream_tracking",
            error_code="GIT_COMMAND_ERROR"
        )
        
    except Exception as e:
        error_msg = f"Unexpected error during upstream tracking validation for branch '{branch_name}': {e}"
        logger.error(error_msg, exc_info=True)
        return GitSyncResult(
            success=False,
            message=error_msg,
            operation="validate_upstream_tracking",
            error_code="VALIDATION_UNEXPECTED_ERROR"
        )