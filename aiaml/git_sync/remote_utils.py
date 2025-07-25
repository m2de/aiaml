"""Remote repository utilities for Git synchronization."""

import logging
import subprocess
from pathlib import Path
from typing import Optional

from ..platform import get_git_executable, get_platform_info


def check_remote_accessibility(remote_url: str) -> bool:
    """Check if the remote repository is accessible."""
    logger = logging.getLogger('aiaml.git_sync.remote_utils')
    
    try:
        git_executable = get_git_executable()
        platform_info = get_platform_info()
        
        # Use git ls-remote to check if remote is accessible
        result = subprocess.run(
            [git_executable, "ls-remote", "--heads", remote_url],
            capture_output=True,
            text=True,
            timeout=30,
            shell=platform_info.is_windows
        )
        
        return result.returncode == 0
        
    except Exception as e:
        logger.debug(f"Error checking remote accessibility for {remote_url}: {e}")
        return False


def detect_remote_default_branch(remote_url: str) -> Optional[str]:
    """Detect the default branch of the remote repository."""
    logger = logging.getLogger('aiaml.git_sync.remote_utils')
    
    if not remote_url:
        return None
    
    try:
        git_executable = get_git_executable()
        platform_info = get_platform_info()
        
        # Use git ls-remote to get symbolic reference
        result = subprocess.run(
            [git_executable, "ls-remote", "--symref", remote_url, "HEAD"],
            capture_output=True,
            text=True,
            timeout=30,
            shell=platform_info.is_windows
        )
        
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            for line in lines:
                if line.startswith('ref: refs/heads/'):
                    # Extract branch name from "ref: refs/heads/main"
                    branch_name = line.split('refs/heads/')[-1]
                    logger.debug(f"Detected remote default branch: {branch_name}")
                    return branch_name
        
        # Fallback: try common branch names
        common_branches = ["main", "master", "develop"]
        for branch in common_branches:
            result = subprocess.run(
                [git_executable, "ls-remote", "--heads", remote_url, branch],
                capture_output=True,
                text=True,
                timeout=10,
                shell=platform_info.is_windows
            )
            
            if result.returncode == 0 and result.stdout.strip():
                logger.debug(f"Found remote branch using fallback: {branch}")
                return branch
        
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
        git_executable = get_git_executable()
        platform_info = get_platform_info()
        
        result = subprocess.run(
            [git_executable, "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            cwd=git_repo_dir,
            timeout=10,
            shell=platform_info.is_windows
        )
        
        return result.returncode == 0
        
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
        git_executable = get_git_executable()
        platform_info = get_platform_info()
        
        # Import here to avoid circular imports
        from .branch_utils import get_current_local_branch
        
        # Fetch latest remote information
        subprocess.run(
            [git_executable, "fetch", "origin"],
            capture_output=True,
            cwd=git_repo_dir,
            timeout=30,
            shell=platform_info.is_windows
        )
        
        # Check if local branch is up to date with remote
        current_branch = get_current_local_branch(git_repo_dir)
        if not current_branch:
            return False
        
        result = subprocess.run(
            [git_executable, "rev-list", "--count", f"HEAD..origin/{current_branch}"],
            capture_output=True,
            text=True,
            cwd=git_repo_dir,
            timeout=10,
            shell=platform_info.is_windows
        )
        
        if result.returncode == 0:
            behind_count = int(result.stdout.strip())
            return behind_count == 0
        
        return False
        
    except Exception as e:
        logger.debug(f"Error checking synchronization status: {e}")
        return False