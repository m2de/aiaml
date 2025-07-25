"""Repository state management for enhanced Git synchronization."""

import logging
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

from ..config import Config
from ..platform import get_git_executable, get_platform_info
from .utils import GitSyncResult


class RepositoryState(Enum):
    """Enumeration of possible repository states."""
    NEW_LOCAL = "new_local"           # No local .git, no remote configured
    EXISTING_LOCAL = "existing_local" # Local .git exists, may have remote
    EXISTING_REMOTE = "existing_remote" # Remote exists, needs cloning
    SYNCHRONIZED = "synchronized"     # Local and remote in sync


@dataclass
class RepositoryInfo:
    """Information about repository state and configuration."""
    state: RepositoryState
    local_exists: bool
    remote_exists: bool
    remote_url: Optional[str]
    default_branch: str
    local_branch: Optional[str]
    tracking_configured: bool
    needs_sync: bool


class RepositoryStateManager:
    """
    Manages repository state detection and synchronization with existing repositories.
    
    This class provides functionality to:
    - Detect the current state of local and remote repositories
    - Determine default branch names dynamically
    - Set up upstream tracking for branches
    - Synchronize with existing remote content
    - Clone existing repositories when needed
    """
    
    def __init__(self, config: Config, git_repo_dir: Path):
        """
        Initialize RepositoryStateManager.
        
        Args:
            config: Server configuration containing Git settings
            git_repo_dir: Path to the Git repository directory
        """
        self.config = config
        self.git_repo_dir = git_repo_dir
        self.git_dir = git_repo_dir / ".git"
        self.logger = logging.getLogger('aiaml.git_sync.state')
        
        # Cache for detected information to avoid repeated operations
        self._cached_default_branch: Optional[str] = None
        self._cached_repo_info: Optional[RepositoryInfo] = None
    
    def detect_repository_state(self) -> RepositoryState:
        """
        Detect the current state of the repository.
        
        Returns:
            RepositoryState indicating the current repository state
        """
        try:
            self.logger.debug("Detecting repository state")
            
            # Check if local .git directory exists
            local_exists = self.git_dir.exists()
            
            # Check if remote URL is configured
            remote_url = self.config.git_remote_url
            remote_configured = bool(remote_url)
            
            # If no local repo and no remote configured, it's a new local repo
            if not local_exists and not remote_configured:
                self.logger.debug("Repository state: NEW_LOCAL (no local .git, no remote)")
                return RepositoryState.NEW_LOCAL
            
            # If local repo exists, check its state
            if local_exists:
                # Check if remote is configured in the local repo
                has_remote = self._check_local_remote_configured()
                
                if remote_configured and not has_remote:
                    # Remote URL provided but not configured locally
                    self.logger.debug("Repository state: EXISTING_LOCAL (local exists, remote needs setup)")
                    return RepositoryState.EXISTING_LOCAL
                elif has_remote:
                    # Check if local and remote are synchronized
                    is_synced = self._check_synchronization_status()
                    if is_synced:
                        self.logger.debug("Repository state: SYNCHRONIZED")
                        return RepositoryState.SYNCHRONIZED
                    else:
                        self.logger.debug("Repository state: EXISTING_LOCAL (needs sync)")
                        return RepositoryState.EXISTING_LOCAL
                else:
                    # Local repo exists but no remote
                    self.logger.debug("Repository state: EXISTING_LOCAL (local only)")
                    return RepositoryState.EXISTING_LOCAL
            
            # If no local repo but remote is configured, need to clone
            if not local_exists and remote_configured:
                # Check if remote actually exists and is accessible
                remote_exists = self._check_remote_accessibility(remote_url)
                if remote_exists:
                    self.logger.debug("Repository state: EXISTING_REMOTE (needs cloning)")
                    return RepositoryState.EXISTING_REMOTE
                else:
                    # Remote configured but not accessible, treat as new local
                    self.logger.debug("Repository state: NEW_LOCAL (remote not accessible)")
                    return RepositoryState.NEW_LOCAL
            
            # Default fallback
            self.logger.debug("Repository state: NEW_LOCAL (fallback)")
            return RepositoryState.NEW_LOCAL
            
        except Exception as e:
            self.logger.error(f"Error detecting repository state: {e}", exc_info=True)
            # Safe fallback to NEW_LOCAL
            return RepositoryState.NEW_LOCAL
    
    def get_repository_info(self) -> RepositoryInfo:
        """
        Get comprehensive repository information.
        
        Returns:
            RepositoryInfo containing detailed repository state
        """
        if self._cached_repo_info is not None:
            return self._cached_repo_info
        
        try:
            # Detect basic state
            state = self.detect_repository_state()
            local_exists = self.git_dir.exists()
            remote_url = self.config.git_remote_url
            
            # Check remote accessibility
            remote_exists = False
            if remote_url:
                remote_exists = self._check_remote_accessibility(remote_url)
            
            # Get default branch
            default_branch = self.get_default_branch()
            
            # Get local branch information
            local_branch = None
            tracking_configured = False
            if local_exists:
                local_branch = self._get_current_local_branch()
                if local_branch:
                    tracking_configured = self._check_upstream_tracking(local_branch)
            
            # Determine if sync is needed
            needs_sync = self._determine_sync_needed(state, local_exists, remote_exists)
            
            repo_info = RepositoryInfo(
                state=state,
                local_exists=local_exists,
                remote_exists=remote_exists,
                remote_url=remote_url,
                default_branch=default_branch,
                local_branch=local_branch,
                tracking_configured=tracking_configured,
                needs_sync=needs_sync
            )
            
            # Cache the result
            self._cached_repo_info = repo_info
            
            self.logger.debug(f"Repository info: {repo_info}")
            return repo_info
            
        except Exception as e:
            self.logger.error(f"Error getting repository info: {e}", exc_info=True)
            # Return safe defaults
            return RepositoryInfo(
                state=RepositoryState.NEW_LOCAL,
                local_exists=False,
                remote_exists=False,
                remote_url=remote_url,
                default_branch="main",
                local_branch=None,
                tracking_configured=False,
                needs_sync=False
            )
    
    def get_default_branch(self) -> str:
        """
        Get the default branch name, using cached value if available.
        
        Returns:
            Default branch name (e.g., "main", "master", "develop")
        """
        if self._cached_default_branch is not None:
            return self._cached_default_branch
        
        try:
            # Try to detect from remote if available
            if self.config.git_remote_url:
                detected_branch = self._detect_remote_default_branch()
                if detected_branch:
                    self._cached_default_branch = detected_branch
                    self.logger.debug(f"Detected default branch from remote: {detected_branch}")
                    return detected_branch
            
            # Try to detect from local repository
            if self.git_dir.exists():
                local_branch = self._get_current_local_branch()
                if local_branch:
                    self._cached_default_branch = local_branch
                    self.logger.debug(f"Using current local branch as default: {local_branch}")
                    return local_branch
            
            # Fallback to "main"
            self._cached_default_branch = "main"
            self.logger.debug("Using fallback default branch: main")
            return "main"
            
        except Exception as e:
            self.logger.error(f"Error detecting default branch: {e}", exc_info=True)
            # Safe fallback
            self._cached_default_branch = "main"
            return "main"
    
    def _check_local_remote_configured(self) -> bool:
        """Check if a remote is configured in the local repository."""
        if not self.git_dir.exists():
            return False
        
        try:
            git_executable = get_git_executable()
            platform_info = get_platform_info()
            
            result = subprocess.run(
                [git_executable, "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                cwd=self.git_repo_dir,
                timeout=10,
                shell=platform_info.is_windows
            )
            
            return result.returncode == 0
            
        except Exception as e:
            self.logger.debug(f"Error checking local remote configuration: {e}")
            return False
    
    def _check_remote_accessibility(self, remote_url: str) -> bool:
        """Check if the remote repository is accessible."""
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
            self.logger.debug(f"Error checking remote accessibility for {remote_url}: {e}")
            return False
    
    def _check_synchronization_status(self) -> bool:
        """Check if local and remote repositories are synchronized."""
        if not self.git_dir.exists():
            return False
        
        try:
            git_executable = get_git_executable()
            platform_info = get_platform_info()
            
            # Fetch latest remote information
            subprocess.run(
                [git_executable, "fetch", "origin"],
                capture_output=True,
                cwd=self.git_repo_dir,
                timeout=30,
                shell=platform_info.is_windows
            )
            
            # Check if local branch is up to date with remote
            current_branch = self._get_current_local_branch()
            if not current_branch:
                return False
            
            result = subprocess.run(
                [git_executable, "rev-list", "--count", f"HEAD..origin/{current_branch}"],
                capture_output=True,
                text=True,
                cwd=self.git_repo_dir,
                timeout=10,
                shell=platform_info.is_windows
            )
            
            if result.returncode == 0:
                behind_count = int(result.stdout.strip())
                return behind_count == 0
            
            return False
            
        except Exception as e:
            self.logger.debug(f"Error checking synchronization status: {e}")
            return False
    
    def _detect_remote_default_branch(self) -> Optional[str]:
        """Detect the default branch of the remote repository."""
        if not self.config.git_remote_url:
            return None
        
        try:
            git_executable = get_git_executable()
            platform_info = get_platform_info()
            
            # Use git ls-remote to get symbolic reference
            result = subprocess.run(
                [git_executable, "ls-remote", "--symref", self.config.git_remote_url, "HEAD"],
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
                        self.logger.debug(f"Detected remote default branch: {branch_name}")
                        return branch_name
            
            # Fallback: try common branch names
            common_branches = ["main", "master", "develop"]
            for branch in common_branches:
                result = subprocess.run(
                    [git_executable, "ls-remote", "--heads", self.config.git_remote_url, branch],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    shell=platform_info.is_windows
                )
                
                if result.returncode == 0 and result.stdout.strip():
                    self.logger.debug(f"Found remote branch using fallback: {branch}")
                    return branch
            
            return None
            
        except Exception as e:
            self.logger.debug(f"Error detecting remote default branch: {e}")
            return None
    
    def _get_current_local_branch(self) -> Optional[str]:
        """Get the current local branch name."""
        if not self.git_dir.exists():
            return None
        
        try:
            git_executable = get_git_executable()
            platform_info = get_platform_info()
            
            result = subprocess.run(
                [git_executable, "branch", "--show-current"],
                capture_output=True,
                text=True,
                cwd=self.git_repo_dir,
                timeout=10,
                shell=platform_info.is_windows
            )
            
            if result.returncode == 0:
                branch_name = result.stdout.strip()
                if branch_name:
                    return branch_name
            
            return None
            
        except Exception as e:
            self.logger.debug(f"Error getting current local branch: {e}")
            return None
    
    def _check_upstream_tracking(self, branch_name: str) -> bool:
        """Check if the specified branch has upstream tracking configured."""
        if not self.git_dir.exists():
            return False
        
        try:
            git_executable = get_git_executable()
            platform_info = get_platform_info()
            
            result = subprocess.run(
                [git_executable, "config", f"branch.{branch_name}.remote"],
                capture_output=True,
                text=True,
                cwd=self.git_repo_dir,
                timeout=10,
                shell=platform_info.is_windows
            )
            
            return result.returncode == 0 and result.stdout.strip()
            
        except Exception as e:
            self.logger.debug(f"Error checking upstream tracking for {branch_name}: {e}")
            return False
    
    def _determine_sync_needed(self, state: RepositoryState, local_exists: bool, remote_exists: bool) -> bool:
        """Determine if synchronization is needed based on repository state."""
        if state == RepositoryState.SYNCHRONIZED:
            return False
        elif state == RepositoryState.EXISTING_REMOTE:
            return True  # Need to clone
        elif state == RepositoryState.EXISTING_LOCAL and remote_exists:
            return True  # Need to sync with remote
        else:
            return False
    
    def clear_cache(self) -> None:
        """Clear cached repository information to force re-detection."""
        self._cached_default_branch = None
        self._cached_repo_info = None
        self.logger.debug("Repository state cache cleared")