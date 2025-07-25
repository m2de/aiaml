"""Error types and categorization for Git synchronization operations."""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class ErrorCategory(Enum):
    """Categories of Git sync errors for appropriate handling."""
    NETWORK = "network"
    AUTHENTICATION = "authentication"
    REPOSITORY_ACCESS = "repository_access"
    BRANCH_DETECTION = "branch_detection"
    MERGE_CONFLICT = "merge_conflict"
    REPOSITORY_CORRUPTION = "repository_corruption"
    CONFIGURATION = "configuration"
    UNKNOWN = "unknown"


class RecoveryAction(Enum):
    """Types of recovery actions that can be taken."""
    RETRY = "retry"
    FALLBACK = "fallback"
    USER_ACTION_REQUIRED = "user_action_required"
    ABORT = "abort"
    REINITIALIZE = "reinitialize"


@dataclass
class ErrorResolution:
    """Information about how to resolve a specific error."""
    category: ErrorCategory
    action: RecoveryAction
    user_message: str
    technical_message: str
    resolution_steps: List[str]
    retry_delay: Optional[float] = None
    max_retries: int = 0