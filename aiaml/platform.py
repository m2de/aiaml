"""Cross-platform compatibility utilities for AIAML."""

import os
import sys
import platform
import tempfile
import time
from pathlib import Path
from typing import Optional, Dict, Any, Union
from enum import Enum


class PlatformType(Enum):
    """Supported platform types."""
    WINDOWS = "windows"
    MACOS = "macos"
    LINUX = "linux"
    UNKNOWN = "unknown"


class PlatformInfo:
    """Platform information and utilities."""
    
    def __init__(self):
        """Initialize platform detection."""
        self._platform_type = self._detect_platform()
        self._is_windows = self._platform_type == PlatformType.WINDOWS
        self._is_unix = self._platform_type in (PlatformType.LINUX, PlatformType.MACOS)
    
    def _detect_platform(self) -> PlatformType:
        """Detect the current platform."""
        system = platform.system().lower()
        
        if system == "windows":
            return PlatformType.WINDOWS
        elif system == "darwin":
            return PlatformType.MACOS
        elif system == "linux":
            return PlatformType.LINUX
        else:
            return PlatformType.UNKNOWN
    
    @property
    def platform_type(self) -> PlatformType:
        """Get the detected platform type."""
        return self._platform_type
    
    @property
    def is_windows(self) -> bool:
        """Check if running on Windows."""
        return self._is_windows
    
    @property
    def is_unix(self) -> bool:
        """Check if running on Unix-like system (Linux/macOS)."""
        return self._is_unix
    
    @property
    def is_macos(self) -> bool:
        """Check if running on macOS."""
        return self._platform_type == PlatformType.MACOS
    
    @property
    def is_linux(self) -> bool:
        """Check if running on Linux."""
        return self._platform_type == PlatformType.LINUX
    
    def get_platform_name(self) -> str:
        """Get human-readable platform name."""
        return self._platform_type.value
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get comprehensive system information."""
        return {
            'platform': self.get_platform_name(),
            'system': platform.system(),
            'release': platform.release(),
            'version': platform.version(),
            'machine': platform.machine(),
            'processor': platform.processor(),
            'python_version': platform.python_version(),
            'python_implementation': platform.python_implementation(),
            'is_windows': self.is_windows,
            'is_unix': self.is_unix,
            'is_macos': self.is_macos,
            'is_linux': self.is_linux
        }


# Global platform info instance
_platform_info: Optional[PlatformInfo] = None


def get_platform_info() -> PlatformInfo:
    """Get the global platform info instance."""
    global _platform_info
    if _platform_info is None:
        _platform_info = PlatformInfo()
    return _platform_info


def normalize_path(path: Union[str, Path]) -> Path:
    """
    Normalize a path for the current platform.
    
    Args:
        path: Path to normalize
        
    Returns:
        Normalized Path object
    """
    if isinstance(path, str):
        path = Path(path)
    
    # Expand user home directory (~) first, then resolve to absolute path
    return path.expanduser().resolve()


def get_platform_specific_defaults() -> Dict[str, Any]:
    """
    Get platform-specific configuration defaults.
    
    Returns:
        Dictionary of platform-specific defaults
    """
    platform_info = get_platform_info()
    
    defaults = {
        'memory_dir': Path.home() / ".aiaml",  # Base directory for all AIAML data
        'log_level': "INFO",
        'git_retry_attempts': 3,
        'git_retry_delay': 1.0,
        'max_search_results': 25
        # Network-related defaults (host, port) removed for local-only server
    }
    
    # Platform-specific adjustments
    if platform_info.is_windows:
        # Windows-specific defaults
        defaults.update({
            'git_retry_attempts': 5,  # Windows may need more retries for Git operations
            'git_retry_delay': 1.5,   # Slightly longer delays on Windows
        })
    elif platform_info.is_macos:
        # macOS-specific defaults
        defaults.update({
            'git_retry_delay': 0.8,   # Faster retries on macOS
        })
    elif platform_info.is_linux:
        # Linux-specific defaults
        defaults.update({
            'git_retry_delay': 0.5,   # Fastest retries on Linux
        })
    
    return defaults


def create_secure_temp_file(directory: Path, suffix: str = '.tmp') -> tuple[int, Path]:
    """
    Create a secure temporary file in a cross-platform way.
    
    Args:
        directory: Directory to create the temp file in
        suffix: File suffix
        
    Returns:
        Tuple of (file_descriptor, file_path)
    """
    # Ensure directory exists
    directory.mkdir(parents=True, exist_ok=True)
    
    # Create secure temporary file
    fd, temp_path = tempfile.mkstemp(dir=str(directory), suffix=suffix)
    return fd, Path(temp_path)


def get_git_executable() -> str:
    """
    Get the Git executable name for the current platform.
    
    Returns:
        Git executable name
    """
    platform_info = get_platform_info()
    
    if platform_info.is_windows:
        # On Windows, try common Git executable names
        return "git.exe"
    else:
        # On Unix-like systems
        return "git"


def validate_git_availability() -> tuple[bool, Optional[str]]:
    """
    Validate that Git is available on the current platform.
    
    Returns:
        Tuple of (is_available, error_message)
    """
    import subprocess
    
    git_cmd = get_git_executable()
    
    try:
        result = subprocess.run(
            [git_cmd, "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            return True, None
        else:
            return False, f"Git command failed: {result.stderr}"
            
    except FileNotFoundError:
        return False, f"Git executable '{git_cmd}' not found"
    except subprocess.TimeoutExpired:
        return False, "Git command timed out"
    except Exception as e:
        return False, f"Error checking Git availability: {e}"


def get_platform_specific_git_config() -> Dict[str, str]:
    """
    Get platform-specific Git configuration.
    
    Returns:
        Dictionary of Git configuration options
    """
    platform_info = get_platform_info()
    
    config = {
        'core.autocrlf': 'false',  # Default for all platforms
        'init.defaultBranch': 'main'
    }
    
    if platform_info.is_windows:
        # Windows-specific Git configuration
        config.update({
            'core.autocrlf': 'true',  # Handle line endings on Windows
            'core.filemode': 'false'  # Ignore file mode changes on Windows
        })
    elif platform_info.is_unix:
        # Unix-specific Git configuration
        config.update({
            'core.autocrlf': 'input',  # Convert CRLF to LF on commit
            'core.filemode': 'true'    # Track file mode changes on Unix
        })
    
    return config