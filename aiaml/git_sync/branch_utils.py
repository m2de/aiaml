"""Branch utilities for Git synchronization."""

import logging
import subprocess
from pathlib import Path

from ..platform import get_git_executable, get_platform_info


def check_remote_branch_exists(git_repo_dir: Path, branch_name: str) -> bool:
    """Check if a branch exists on the remote repository."""
    logger = logging.getLogger('aiaml.git_sync.branch_utils')
    
    try:
        git_executable = get_git_executable()
        platform_info = get_platform_info()
        
        # Fetch latest remote information to ensure we have up-to-date branch list
        subprocess.run(
            [git_executable, "fetch", "origin"],
            capture_output=True,
            cwd=git_repo_dir,
            timeout=30,
            shell=platform_info.is_windows
        )
        
        # Check if remote branch exists
        result = subprocess.run(
            [git_executable, "ls-remote", "--heads", "origin", branch_name],
            capture_output=True,
            text=True,
            cwd=git_repo_dir,
            timeout=30,
            shell=platform_info.is_windows
        )
        
        return result.returncode == 0 and result.stdout.strip()
        
    except Exception as e:
        logger.debug(f"Error checking remote branch existence for '{branch_name}': {e}")
        return False


def check_local_branch_exists(git_repo_dir: Path, branch_name: str) -> bool:
    """Check if a branch exists in the local repository."""
    logger = logging.getLogger('aiaml.git_sync.branch_utils')
    
    try:
        git_executable = get_git_executable()
        platform_info = get_platform_info()
        
        result = subprocess.run(
            [git_executable, "branch", "--list", branch_name],
            capture_output=True,
            text=True,
            cwd=git_repo_dir,
            timeout=10,
            shell=platform_info.is_windows
        )
        
        return result.returncode == 0 and result.stdout.strip()
        
    except Exception as e:
        logger.debug(f"Error checking local branch existence for '{branch_name}': {e}")
        return False


def get_current_local_branch(git_repo_dir: Path) -> str:
    """Get the current local branch name."""
    logger = logging.getLogger('aiaml.git_sync.branch_utils')
    git_dir = git_repo_dir / ".git"
    
    if not git_dir.exists():
        return None
    
    try:
        git_executable = get_git_executable()
        platform_info = get_platform_info()
        
        result = subprocess.run(
            [git_executable, "branch", "--show-current"],
            capture_output=True,
            text=True,
            cwd=git_repo_dir,
            timeout=10,
            shell=platform_info.is_windows
        )
        
        if result.returncode == 0:
            branch_name = result.stdout.strip()
            if branch_name:
                return branch_name
        
        return None
        
    except Exception as e:
        logger.debug(f"Error getting current local branch: {e}")
        return None


def check_upstream_tracking(git_repo_dir: Path, branch_name: str) -> bool:
    """Check if the specified branch has upstream tracking configured."""
    logger = logging.getLogger('aiaml.git_sync.branch_utils')
    git_dir = git_repo_dir / ".git"
    
    if not git_dir.exists():
        return False
    
    try:
        git_executable = get_git_executable()
        platform_info = get_platform_info()
        
        result = subprocess.run(
            [git_executable, "config", f"branch.{branch_name}.remote"],
            capture_output=True,
            text=True,
            cwd=git_repo_dir,
            timeout=10,
            shell=platform_info.is_windows
        )
        
        return result.returncode == 0 and result.stdout.strip()
        
    except Exception as e:
        logger.debug(f"Error checking upstream tracking for {branch_name}: {e}")
        return False