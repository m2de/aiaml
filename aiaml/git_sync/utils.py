"""Utility classes and functions for Git synchronization."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class GitSyncResult:
    """Result of a Git synchronization operation."""
    success: bool
    message: str
    operation: str
    attempts: int = 1
    error_code: Optional[str] = None