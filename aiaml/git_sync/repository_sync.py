"""Repository synchronization operations for Git repositories."""

import logging
import subprocess
from pathlib import Path

from ..platform import get_git_executable, get_platform_info
from .branch_utils import check_remote_branch_exists, check_local_branch_exists, get_current_local_branch, check_upstream_tracking
from .remote_utils import check_remote_accessibility, check_local_remote_configured
from .utils import GitSyncResult, create_git_sync_result


def synchronize_with_remote(git_repo_dir: Path, config, get_default_branch_func, setup_upstream_tracking_func, sync_ops, logger: logging.Logger) -> GitSyncResult:
    """
    Synchronize the local repository with the remote repository.
    
    This function performs the following operations:
    1. Validates that both local and remote repositories exist
    2. Fetches the latest changes from the remote
    3. Pulls changes with conflict resolution (prioritizing remote content)
    4. Validates existing memory files after synchronization
    5. Handles merge conflicts by prioritizing remote content
    
    Args:
        git_repo_dir: Path to the Git repository directory
        config: Server configuration containing Git settings
        get_default_branch_func: Function to get the default branch name
        setup_upstream_tracking_func: Function to set up upstream tracking
        sync_ops: SyncOperations instance for backup and validation operations
        logger: Logger instance for this operation
    
    Returns:
        GitSyncResult indicating success or failure of the synchronization
        
    Requirements: 3.1, 3.2, 3.3
    """
    try:
        logger.info("Starting repository synchronization with remote")
        
        git_dir = git_repo_dir / ".git"
        
        # Validate that local repository exists
        if not git_dir.exists():
            error_msg = "Cannot synchronize: local Git repository does not exist"
            logger.error(error_msg)
            return GitSyncResult(
                success=False,
                message=error_msg,
                operation="synchronize_with_remote",
                error_code="NO_LOCAL_REPO"
            )
        
        # Validate that remote URL is configured
        if not config.git_remote_url:
            error_msg = "Cannot synchronize: no remote URL configured"
            logger.error(error_msg)
            return GitSyncResult(
                success=False,
                message=error_msg,
                operation="synchronize_with_remote",
                error_code="NO_REMOTE_URL"
            )
        
        # Check if remote is configured in the local repository
        if not check_local_remote_configured(git_repo_dir):
            error_msg = "Cannot synchronize: remote 'origin' not configured in local repository"
            logger.error(error_msg)
            return GitSyncResult(
                success=False,
                message=error_msg,
                operation="synchronize_with_remote",
                error_code="NO_LOCAL_REMOTE"
            )
        
        # Check remote accessibility
        if not check_remote_accessibility(config.git_remote_url):
            error_msg = f"Cannot synchronize: remote repository is not accessible: {config.git_remote_url}"
            logger.error(error_msg)
            return GitSyncResult(
                success=False,
                message=error_msg,
                operation="synchronize_with_remote",
                error_code="REMOTE_NOT_ACCESSIBLE"
            )
        
        git_executable = get_git_executable()
        platform_info = get_platform_info()
        
        # Get the default branch to synchronize with
        default_branch = get_default_branch_func()
        
        # Ensure we're on the correct branch
        current_branch = get_current_local_branch(git_repo_dir)
        if current_branch != default_branch:
            logger.debug(f"Switching to default branch: {default_branch}")
            
            # Check if the local branch exists
            if not check_local_branch_exists(git_repo_dir, default_branch):
                # Create the branch from remote if it doesn't exist locally
                if check_remote_branch_exists(git_repo_dir, default_branch):
                    result = subprocess.run(
                        [git_executable, "checkout", "-b", default_branch, f"origin/{default_branch}"],
                        capture_output=True,
                        text=True,
                        cwd=git_repo_dir,
                        timeout=30,
                        shell=platform_info.is_windows
                    )
                    
                    if result.returncode != 0:
                        error_msg = f"Failed to create and switch to branch '{default_branch}': {result.stderr if result.stderr else result.stdout}"
                        logger.error(error_msg)
                        return GitSyncResult(
                            success=False,
                            message=error_msg,
                            operation="synchronize_with_remote",
                            error_code="BRANCH_CREATION_FAILED"
                        )
                else:
                    error_msg = f"Default branch '{default_branch}' does not exist on remote"
                    logger.error(error_msg)
                    return GitSyncResult(
                        success=False,
                        message=error_msg,
                        operation="synchronize_with_remote",
                        error_code="REMOTE_BRANCH_NOT_FOUND"
                    )
            else:
                # Switch to existing local branch
                result = subprocess.run(
                    [git_executable, "checkout", default_branch],
                    capture_output=True,
                    text=True,
                    cwd=git_repo_dir,
                    timeout=30,
                    shell=platform_info.is_windows
                )
                
                if result.returncode != 0:
                    error_msg = f"Failed to switch to branch '{default_branch}': {result.stderr if result.stderr else result.stdout}"
                    logger.error(error_msg)
                    return GitSyncResult(
                        success=False,
                        message=error_msg,
                        operation="synchronize_with_remote",
                        error_code="BRANCH_CHECKOUT_FAILED"
                    )
        
        # Ensure upstream tracking is configured
        if not check_upstream_tracking(git_repo_dir, default_branch):
            logger.debug(f"Setting up upstream tracking for branch: {default_branch}")
            tracking_result = setup_upstream_tracking_func(default_branch)
            if not tracking_result.success:
                logger.warning(f"Failed to set up upstream tracking, continuing with explicit remote: {tracking_result.message}")
        
        # Step 1: Fetch latest changes from remote
        logger.debug("Fetching latest changes from remote")
        
        result = subprocess.run(
            [git_executable, "fetch", "origin"],
            capture_output=True,
            text=True,
            cwd=git_repo_dir,
            timeout=60,
            shell=platform_info.is_windows
        )
        
        if result.returncode != 0:
            error_msg = f"Failed to fetch from remote: {result.stderr if result.stderr else result.stdout}"
            logger.error(error_msg)
            return GitSyncResult(
                success=False,
                message=error_msg,
                operation="synchronize_with_remote",
                error_code="FETCH_FAILED"
            )
        
        logger.debug("Successfully fetched changes from remote")
        
        # Step 2: Check if there are changes to pull
        result = subprocess.run(
            [git_executable, "rev-list", "--count", f"HEAD..origin/{default_branch}"],
            capture_output=True,
            text=True,
            cwd=git_repo_dir,
            timeout=10,
            shell=platform_info.is_windows
        )
        
        if result.returncode == 0:
            behind_count = int(result.stdout.strip())
            if behind_count == 0:
                logger.info("Repository is already up to date with remote")
                
                # Still validate existing memory files
                validation_result = sync_ops.validate_existing_memory_files()
                if not validation_result.success:
                    logger.warning(f"Memory file validation issues found: {validation_result.message}")
                
                return GitSyncResult(
                    success=True,
                    message="Repository is already synchronized with remote",
                    operation="synchronize_with_remote"
                )
            else:
                logger.info(f"Repository is {behind_count} commits behind remote, pulling changes")
        
        # Step 3: Create backup of current state before pulling
        sync_ops.create_sync_backup()
        
        # Step 4: Pull changes with conflict resolution strategy
        logger.debug(f"Pulling changes from origin/{default_branch}")
        
        # Use merge strategy that prioritizes remote content for conflicts
        result = subprocess.run(
            [git_executable, "pull", "--strategy=recursive", "--strategy-option=theirs", "origin", default_branch],
            capture_output=True,
            text=True,
            cwd=git_repo_dir,
            timeout=120,
            shell=platform_info.is_windows
        )
        
        if result.returncode != 0:
            # Check if it's a merge conflict that needs manual resolution
            if "CONFLICT" in result.stdout or "CONFLICT" in result.stderr:
                logger.warning("Merge conflicts detected, attempting automatic resolution")
                
                # Try to resolve conflicts by accepting remote changes
                conflict_resolution_result = sync_ops.resolve_merge_conflicts(default_branch)
                if not conflict_resolution_result.success:
                    return conflict_resolution_result
            else:
                error_msg = f"Failed to pull changes from remote: {result.stderr if result.stderr else result.stdout}"
                logger.error(error_msg)
                
                # Attempt to restore from backup
                sync_ops.restore_from_sync_backup()
                
                return GitSyncResult(
                    success=False,
                    message=error_msg,
                    operation="synchronize_with_remote",
                    error_code="PULL_FAILED"
                )
        
        logger.info("Successfully pulled changes from remote")
        
        # Step 5: Validate existing memory files after synchronization
        validation_result = sync_ops.validate_existing_memory_files()
        if not validation_result.success:
            logger.warning(f"Memory file validation issues found after sync: {validation_result.message}")
            # Continue operation but log the issues
        
        # Step 6: Clean up backup after successful sync
        sync_ops.cleanup_sync_backup()
        
        logger.info("Repository synchronization completed successfully")
        
        return GitSyncResult(
            success=True,
            message="Successfully synchronized repository with remote",
            operation="synchronize_with_remote"
        )
        
    except subprocess.TimeoutExpired:
        error_msg = "Repository synchronization timed out"
        logger.error(error_msg)
        
        # Attempt to restore from backup
        sync_ops.restore_from_sync_backup()
        
        return GitSyncResult(
            success=False,
            message=error_msg,
            operation="synchronize_with_remote",
            error_code="SYNC_TIMEOUT"
        )
        
    except Exception as e:
        error_msg = f"Unexpected error during repository synchronization: {e}"
        logger.error(error_msg, exc_info=True)
        
        # Attempt to restore from backup
        sync_ops.restore_from_sync_backup()
        
        return GitSyncResult(
            success=False,
            message=error_msg,
            operation="synchronize_with_remote",
            error_code="SYNC_UNEXPECTED_ERROR"
        )