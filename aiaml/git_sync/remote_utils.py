"""Remote repository utilities for Git synchronization."""

import logging
from pathlib import Path
from typing import Optional

from git import Repo, GitCommandError, RemoteProgress
from ..platform import get_git_executable, get_platform_info


def check_remote_accessibility(remote_url: str) -> bool:
    """Check if the remote repository is accessible."""
    logger = logging.getLogger('aiaml.git_sync.remote_utils')
    
    try:
        # Create a temporary repo-like object to test remote connectivity
        from git import cmd
        git_cmd = cmd.Git()
        
        # Use git ls-remote to check if remote is accessible
        git_cmd.ls_remote('--heads', remote_url)
        return True
        
    except GitCommandError as e:
        logger.debug(f"Git command error checking remote accessibility for {remote_url}: {e}")
        return False
    except Exception as e:
        logger.debug(f"Error checking remote accessibility for {remote_url}: {e}")
        return False


def detect_remote_default_branch(remote_url: str) -> Optional[str]:
    """Detect the default branch of the remote repository."""
    logger = logging.getLogger('aiaml.git_sync.remote_utils')
    
    if not remote_url:
        return None
    
    try:
        from git import cmd
        git_cmd = cmd.Git()
        
        # Use git ls-remote to get symbolic reference
        try:
            output = git_cmd.ls_remote('--symref', remote_url, 'HEAD')
            lines = output.strip().split('\n')
            for line in lines:
                if line.startswith('ref: refs/heads/'):
                    # Extract branch name from "ref: refs/heads/main\tHEAD"
                    branch_name = line.split('refs/heads/')[-1].split('\t')[0].strip()
                    logger.debug(f"Detected remote default branch: {branch_name}")
                    return branch_name
        except GitCommandError:
            logger.debug("Could not get symbolic ref for HEAD, trying fallback")
        
        # Fallback: try common branch names
        common_branches = ["main", "master", "develop"]
        for branch in common_branches:
            try:
                output = git_cmd.ls_remote('--heads', remote_url, branch)
                if output.strip():
                    logger.debug(f"Found remote branch using fallback: {branch}")
                    return branch
            except GitCommandError:
                continue
        
        return None
        
    except Exception as e:
        logger.debug(f"Error detecting remote default branch: {e}")
        return None


def check_local_remote_configured(git_repo_dir: Path) -> bool:
    """Check if a remote is configured in the local repository."""
    logger = logging.getLogger('aiaml.git_sync.remote_utils')
    git_dir = git_repo_dir / ".git"
    
    if not git_dir.exists():
        return False
    
    try:
        repo = Repo(git_repo_dir)
        # Check if origin remote exists
        try:
            origin_remote = repo.remote('origin')
            return origin_remote is not None
        except Exception:
            return False
        
    except Exception as e:
        logger.debug(f"Error checking local remote configuration: {e}")
        return False


def check_synchronization_status(git_repo_dir: Path) -> bool:
    """Check if local and remote repositories are synchronized."""
    logger = logging.getLogger('aiaml.git_sync.remote_utils')
    git_dir = git_repo_dir / ".git"
    
    if not git_dir.exists():
        return False
    
    try:
        repo = Repo(git_repo_dir)
        
        # Import here to avoid circular imports
        from .branch_utils import get_current_local_branch
        
        # Fetch latest remote information
        try:
            origin = repo.remotes.origin
            origin.fetch()
        except GitCommandError as e:
            logger.debug(f"Failed to fetch from origin: {e}")
            return False
        
        # Check if local branch is up to date with remote
        current_branch = get_current_local_branch(git_repo_dir)
        if not current_branch:
            return False
        
        try:
            # Get current commit and remote commit
            current_commit = repo.head.commit
            remote_branch = repo.remotes.origin.refs[current_branch]
            remote_commit = remote_branch.commit
            
            # Check if we're behind the remote
            return current_commit == remote_commit
        except Exception as e:
            logger.debug(f"Error comparing commits: {e}")
            return False
        
    except Exception as e:
        logger.debug(f"Error checking synchronization status: {e}")
        return False