"""Configuration management for AIAML server."""

import os
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List

from .platform import get_platform_specific_defaults, get_platform_info

try:
    from dotenv import load_dotenv
    load_dotenv()  # Load .env file if it exists
except ImportError:
    # python-dotenv not available, continue without it
    pass


@dataclass
class Config:
    """Configuration class for AIAML server with validation and defaults."""
    
    # Git synchronization
    enable_git_sync: bool = True
    git_remote_url: Optional[str] = None
    git_retry_attempts: int = 3
    git_retry_delay: float = 1.0
    
    # Storage
    memory_dir: Path = field(default_factory=lambda: Path.home() / ".aiaml")  # Base directory for all AIAML data
    
    # Logging
    log_level: str = "INFO"
    
    # Performance
    max_search_results: int = 25
    
    # Note: Network-related fields (host, port, api_key) have been removed for local-only server
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        # Convert string path to Path object and normalize (expand ~ and resolve)
        if isinstance(self.memory_dir, str):
            self.memory_dir = Path(self.memory_dir)
        
        # Normalize the memory directory path to properly handle ~ expansion
        from .platform import normalize_path
        self.memory_dir = normalize_path(self.memory_dir)
        
        # Validate log level
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.log_level.upper() not in valid_log_levels:
            raise ValueError(f"Invalid log level: {self.log_level}. Must be one of {valid_log_levels}")
        
        # Validate retry attempts
        if self.git_retry_attempts < 0:
            raise ValueError("git_retry_attempts must be non-negative")
        
        # Validate retry delay
        if self.git_retry_delay < 0:
            raise ValueError("git_retry_delay must be non-negative")
        
        # Validate max search results
        if self.max_search_results <= 0:
            raise ValueError("max_search_results must be positive")
    
    @property
    def files_dir(self) -> Path:
        """Directory where memory files are stored."""
        return self.memory_dir / "files"
    
    @property
    def backup_dir(self) -> Path:
        """Directory where backup files are stored."""
        return self.memory_dir / "backups"
    
    @property
    def temp_dir(self) -> Path:
        """Directory for temporary files."""
        return self.memory_dir / "temp"
    
    @property
    def lock_dir(self) -> Path:
        """Directory for file locks."""
        return self.memory_dir / "locks"
    
    @property
    def git_repo_dir(self) -> Path:
        """Git repository directory (same as memory_dir base)."""
        return self.memory_dir


def load_configuration() -> Config:
    """Load configuration from environment variables with platform-specific defaults."""
    try:
        # Get platform-specific defaults
        platform_defaults = get_platform_specific_defaults()
        platform_info = get_platform_info()
        
        # Network environment variables are ignored for local-only server
        # AIAML_API_KEY, AIAML_HOST, AIAML_PORT are explicitly ignored
        if os.getenv("AIAML_API_KEY") or os.getenv("AIAML_HOST") or os.getenv("AIAML_PORT"):
            logging.getLogger('aiaml.config').info(
                "Network-related environment variables (AIAML_API_KEY, AIAML_HOST, AIAML_PORT) "
                "are ignored in local-only server mode"
            )
        
        return Config(
            enable_git_sync=os.getenv("AIAML_ENABLE_SYNC", "true").lower() == "true",
            git_remote_url=os.getenv("AIAML_GITHUB_REMOTE"),
            memory_dir=Path(os.getenv("AIAML_MEMORY_DIR", str(platform_defaults['memory_dir']))),
            log_level=os.getenv("AIAML_LOG_LEVEL", platform_defaults['log_level']).upper(),
            max_search_results=int(os.getenv("AIAML_MAX_SEARCH_RESULTS", str(platform_defaults['max_search_results']))),
            git_retry_attempts=int(os.getenv("AIAML_GIT_RETRY_ATTEMPTS", str(platform_defaults['git_retry_attempts']))),
            git_retry_delay=float(os.getenv("AIAML_GIT_RETRY_DELAY", str(platform_defaults['git_retry_delay'])))
        )
    except (ValueError, TypeError) as e:
        raise ValueError(f"Configuration error: {e}")


def validate_configuration(config: Config) -> List[str]:
    """Validate configuration and return any errors or warnings with comprehensive validation."""
    from .memory.validation import validate_configuration_input
    
    errors = []
    
    # Use comprehensive configuration validation (network validation removed for local-only server)
    config_dict = {
        'memory_dir': str(config.memory_dir),
        'git_remote_url': config.git_remote_url,
        'log_level': config.log_level
        # Network-related fields (host, port, api_key) removed for local-only server
    }
    
    # Get validation errors from the comprehensive validator
    validation_errors = validate_configuration_input(config_dict)
    for error in validation_errors:
        errors.append(f"ERROR: {error}")
    
    # Check memory files directory permissions
    try:
        config.files_dir.mkdir(parents=True, exist_ok=True)
        # Test write permissions
        test_file = config.files_dir / ".test_write"
        test_file.write_text("test")
        test_file.unlink()
    except PermissionError:
        errors.append(f"ERROR: No write permission for memory files directory: {config.files_dir}")
    except Exception as e:
        errors.append(f"ERROR: Cannot access memory files directory {config.files_dir}: {e}")
    
    # Validate Git configuration
    if config.enable_git_sync:
        if config.git_remote_url and not config.git_remote_url.startswith(("http://", "https://", "git@")):
            errors.append(f"WARNING: Git remote URL may be invalid: {config.git_remote_url}")
    
    # Validate file limits and performance settings
    if config.max_search_results > 100:
        errors.append("WARNING: High max_search_results may impact performance")
    
    return errors