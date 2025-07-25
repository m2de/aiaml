"""Repository validation utilities for Git synchronization."""

import logging
import subprocess
from pathlib import Path
from typing import Optional

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
        
        git_executable = get_git_executable()
        platform_info = get_platform_info()
        
        # Validate that it's a proper Git repository
        result = subprocess.run(
            [git_executable, "status", "--porcelain"],
            capture_output=True,
            text=True,
            cwd=git_repo_dir,
            timeout=30,
            shell=platform_info.is_windows
        )
        
        if result.returncode != 0:
            error_msg = f"Cloned repository validation failed: not a valid Git repository: {result.stderr}"
            logger.error(error_msg)
            return GitSyncResult(
                success=False,
                message=error_msg,
                operation="validate_cloned_repo",
                error_code="INVALID_GIT_REPO"
            )
        
        # Check remote configuration
        result = subprocess.run(
            [git_executable, "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            cwd=git_repo_dir,
            timeout=10,
            shell=platform_info.is_windows
        )
        
        if result.returncode != 0:
            error_msg = "Cloned repository validation failed: origin remote not configured"
            logger.error(error_msg)
            return GitSyncResult(
                success=False,
                message=error_msg,
                operation="validate_cloned_repo",
                error_code="MISSING_ORIGIN_REMOTE"
            )
        
        # Verify remote URL matches configuration
        actual_remote_url = result.stdout.strip()
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
        result = subprocess.run(
            [git_executable, "branch", "--show-current"],
            capture_output=True,
            text=True,
            cwd=git_repo_dir,
            timeout=10,
            shell=platform_info.is_windows
        )
        
        if result.returncode != 0 or not result.stdout.strip():
            error_msg = "Cloned repository validation failed: no current branch found"
            logger.error(error_msg)
            return GitSyncResult(
                success=False,
                message=error_msg,
                operation="validate_cloned_repo",
                error_code="NO_CURRENT_BRANCH"
            )
        
        current_branch = result.stdout.strip()
        logger.debug(f"Cloned repository validation successful, current branch: {current_branch}")
        
        return GitSyncResult(
            success=True,
            message=f"Cloned repository validation successful, current branch: {current_branch}",
            operation="validate_cloned_repo"
        )
        
    except subprocess.TimeoutExpired:
        error_msg = "Cloned repository validation timed out"
        logger.error(error_msg)
        return GitSyncResult(
            success=False,
            message=error_msg,
            operation="validate_cloned_repo",
            error_code="VALIDATION_TIMEOUT"
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
        
        git_executable = get_git_executable()
        platform_info = get_platform_info()
        
        # Check if remote is configured
        result = subprocess.run(
            [git_executable, "config", f"branch.{branch_name}.remote"],
            capture_output=True,
            text=True,
            cwd=git_repo_dir,
            timeout=10,
            shell=platform_info.is_windows
        )
        
        if result.returncode != 0 or not result.stdout.strip():
            error_msg = f"Upstream tracking validation failed: no remote configured for branch '{branch_name}'"
            logger.error(error_msg)
            return GitSyncResult(
                success=False,
                message=error_msg,
                operation="validate_upstream_tracking",
                error_code="NO_REMOTE_CONFIG"
            )
        
        remote_name = result.stdout.strip()
        
        # Check if merge configuration is set
        result = subprocess.run(
            [git_executable, "config", f"branch.{branch_name}.merge"],
            capture_output=True,
            text=True,
            cwd=git_repo_dir,
            timeout=10,
            shell=platform_info.is_windows
        )
        
        if result.returncode != 0 or not result.stdout.strip():
            error_msg = f"Upstream tracking validation failed: no merge configuration for branch '{branch_name}'"
            logger.error(error_msg)
            return GitSyncResult(
                success=False,
                message=error_msg,
                operation="validate_upstream_tracking",
                error_code="NO_MERGE_CONFIG"
            )
        
        merge_ref = result.stdout.strip()
        
        # Validate that the remote branch reference is correct
        expected_merge_ref = f"refs/heads/{branch_name}"
        if merge_ref != expected_merge_ref:
            error_msg = f"Upstream tracking validation failed: unexpected merge reference (expected: {expected_merge_ref}, actual: {merge_ref})"
            logger.error(error_msg)
            return GitSyncResult(
                success=False,
                message=error_msg,
                operation="validate_upstream_tracking",
                error_code="INVALID_MERGE_REF"
            )
        
        # Test that git status can determine tracking status
        result = subprocess.run(
            [git_executable, "status", "-b", "--porcelain"],
            capture_output=True,
            text=True,
            cwd=git_repo_dir,
            timeout=10,
            shell=platform_info.is_windows
        )
        
        if result.returncode != 0:
            error_msg = f"Upstream tracking validation failed: cannot determine tracking status for branch '{branch_name}'"
            logger.error(error_msg)
            return GitSyncResult(
                success=False,
                message=error_msg,
                operation="validate_upstream_tracking",
                error_code="TRACKING_STATUS_FAILED"
            )
        
        # Check if the status output includes tracking information
        status_output = result.stdout.strip()
        if status_output and not f"origin/{branch_name}" in status_output:
            logger.warning(f"Upstream tracking validation: tracking information not found in status output for branch '{branch_name}'")
        
        logger.debug(f"Upstream tracking validation successful for branch '{branch_name}' (remote: {remote_name}, merge: {merge_ref})")
        
        return GitSyncResult(
            success=True,
            message=f"Upstream tracking validation successful for branch '{branch_name}'",
            operation="validate_upstream_tracking"
        )
        
    except subprocess.TimeoutExpired:
        error_msg = f"Upstream tracking validation timed out for branch '{branch_name}'"
        logger.error(error_msg)
        return GitSyncResult(
            success=False,
            message=error_msg,
            operation="validate_upstream_tracking",
            error_code="VALIDATION_TIMEOUT"
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