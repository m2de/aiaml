"""Repository cloning utilities for Git synchronization using GitPython."""

import logging
import shutil
from pathlib import Path
from typing import Optional

try:
    from git import Repo, GitCommandError
    HAS_GITPYTHON = True
except ImportError:
    HAS_GITPYTHON = False
    
    class GitCommandError(Exception):
        pass

from ..config import Config
from .utils import GitSyncResult, create_git_sync_result
from .validation import validate_cloned_repository
from .repository_info import RepositoryState, RepositoryInfo


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
        
        # Perform the Git clone operation using GitPython
        logger.info(f"Cloning repository from {config.git_remote_url}")
        
        if not HAS_GITPYTHON:
            return GitSyncResult(
                success=False,
                message="Git clone failed: GitPython not available. Please install with: pip install GitPython",
                operation="clone_repository",
                error_code="GITPYTHON_NOT_AVAILABLE"
            )
        
        try:
            # Clone with GitPython - much simpler!
            repo = Repo.clone_from(
                config.git_remote_url,
                git_repo_dir,
                depth=1,  # Shallow clone for faster operation
                single_branch=True  # Only clone the default branch initially
            )
            logger.info("Repository cloned successfully")
            
        except GitCommandError as e:
            error_msg = f"Git clone failed: {str(e)}"
            logger.error(error_msg)
            return create_git_sync_result(
                success=False,
                message=error_msg,
                operation="clone_repository",
                error_code="GIT_CLONE_FAILED"
            )
        
        # Validate the cloned repository structure
        validation_result = validate_cloned_repository(git_repo_dir, config.git_remote_url)
        if not validation_result.success:
            return validation_result
        
        # Set up Git configuration for the cloned repository using GitPython
        try:
            # Set up user configuration if not already set
            config_writer = repo.config_writer()
            try:
                repo.config_reader().get_value("user", "name")
            except:
                config_writer.set_value("user", "name", "AIAML Memory System")
            
            try:
                repo.config_reader().get_value("user", "email")  
            except:
                config_writer.set_value("user", "email", "aiaml@localhost")
            
            logger.debug("Git configuration set up for cloned repository")
        except Exception as e:
            logger.warning(f"Failed to set up cloned repository configuration: {e}")
        
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
        
        # Get current branch information using GitPython
        try:
            current_branch = repo.active_branch.name if repo.active_branch else "main"
        except:
            current_branch = "main"  # Fallback
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
        
        
    except Exception as e:
        error_msg = f"Unexpected error during repository clone: {e}"
        logger.error(error_msg, exc_info=True)
        return GitSyncResult(
            success=False,
            message=error_msg,
            operation="clone_repository",
            error_code="CLONE_UNEXPECTED_ERROR"
        )

