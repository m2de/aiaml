"""Repository information and state management data structures."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


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