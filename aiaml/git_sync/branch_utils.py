"""Branch utilities for Git synchronization using GitPython."""

import logging
from pathlib import Path

try:
    from git import Repo, GitCommandError
    HAS_GITPYTHON = True
except ImportError:
    HAS_GITPYTHON = False
    
    class GitCommandError(Exception):
        pass


def check_remote_branch_exists(git_repo_dir: Path, branch_name: str) -> bool:
    """Check if a branch exists on the remote repository using GitPython."""
    logger = logging.getLogger('aiaml.git_sync.branch_utils')
    
    if not HAS_GITPYTHON:
        logger.warning("GitPython not available for remote branch check")
        return False
    
    try:
        repo = Repo(git_repo_dir)
        
        # Fetch latest remote information
        repo.remotes.origin.fetch()
        
        # Check if remote branch exists
        remote_refs = [ref.name for ref in repo.remotes.origin.refs]
        return f'origin/{branch_name}' in remote_refs
        
    except Exception as e:
        logger.debug(f"Error checking remote branch existence for '{branch_name}': {e}")
        return False


def check_local_branch_exists(git_repo_dir: Path, branch_name: str) -> bool:
    """Check if a branch exists in the local repository using GitPython."""
    logger = logging.getLogger('aiaml.git_sync.branch_utils')
    
    if not HAS_GITPYTHON:
        logger.warning("GitPython not available for local branch check")
        return False
    
    try:
        repo = Repo(git_repo_dir)
        branch_names = [head.name for head in repo.heads]
        return branch_name in branch_names
        
    except Exception as e:
        logger.debug(f"Error checking local branch existence for '{branch_name}': {e}")
        return False


def get_current_local_branch(git_repo_dir: Path) -> str:
    """Get the current local branch name using GitPython."""
    logger = logging.getLogger('aiaml.git_sync.branch_utils')
    git_dir = git_repo_dir / ".git"
    
    if not git_dir.exists():
        return None
    
    if not HAS_GITPYTHON:
        logger.warning("GitPython not available for branch detection")
        return None
    
    try:
        repo = Repo(git_repo_dir)
        return repo.active_branch.name if repo.active_branch else None
        
    except Exception as e:
        logger.debug(f"Error getting current local branch: {e}")
        return None


def check_upstream_tracking(git_repo_dir: Path, branch_name: str) -> bool:
    """Check if the specified branch has upstream tracking configured using GitPython."""
    logger = logging.getLogger('aiaml.git_sync.branch_utils')
    git_dir = git_repo_dir / ".git"
    
    if not git_dir.exists():
        return False

    if not HAS_GITPYTHON:
        logger.warning("GitPython not available for upstream tracking check")
        return False
    
    try:
        repo = Repo(git_repo_dir)
        for head in repo.heads:
            if head.name == branch_name:
                return head.tracking_branch() is not None
        return False
        
    except Exception as e:
        logger.debug(f"Error checking upstream tracking for {branch_name}: {e}")
        return False