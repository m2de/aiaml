# Design Document

## Overview

This design enhances AIAML's Git synchronization system to seamlessly work with existing GitHub repositories. The current implementation assumes new repositories and hard-codes branch names, causing failures when connecting to existing repositories. The enhanced system will dynamically detect repository state, handle various branch naming conventions, and properly synchronize with existing content.

## Architecture

### Current Architecture Issues

The existing Git sync architecture has several limitations:
- Hard-coded "main" branch assumption in `GitSyncManager.sync_memory_with_retry()`
- No detection of existing repository state or default branch
- Missing upstream tracking configuration
- No synchronization with existing remote content
- Limited error handling for existing repository scenarios

### Enhanced Architecture

The enhanced architecture introduces a new `RepositoryStateManager` component and modifies existing components:

```
GitSyncManager
├── RepositoryStateManager (NEW)
│   ├── detectRepositoryState()
│   ├── getDefaultBranch()
│   ├── setupUpstreamTracking()
│   └── synchronizeWithRemote()
├── Enhanced GitSyncManager
│   ├── _initialize_repository() (MODIFIED)
│   ├── _configure_git_remote() (MODIFIED)
│   └── sync_memory_with_retry() (MODIFIED)
└── GitOperations (ENHANCED)
    ├── cloneExistingRepository() (NEW)
    ├── detectRemoteDefaultBranch() (NEW)
    └── setupBranchTracking() (NEW)
```

## Components and Interfaces

### 1. RepositoryStateManager

**Purpose:** Manages repository state detection and synchronization with existing repositories.

**Interface:**
```python
class RepositoryStateManager:
    def __init__(self, config: Config, git_repo_dir: Path)
    
    def detect_repository_state(self) -> RepositoryState
    def get_default_branch(self) -> str
    def setup_upstream_tracking(self, branch_name: str) -> GitSyncResult
    def synchronize_with_remote(self) -> GitSyncResult
    def clone_existing_repository(self) -> GitSyncResult
```

**Key Methods:**

- `detect_repository_state()`: Determines if repository is new, existing local, or existing remote
- `get_default_branch()`: Dynamically detects remote default branch name
- `setup_upstream_tracking()`: Configures local branch to track remote branch
- `synchronize_with_remote()`: Pulls existing content and resolves conflicts

### 2. Enhanced GitSyncManager

**Modifications to existing class:**

```python
class GitSyncManager:
    def __init__(self, config: Config):
        # Add repository state manager
        self.repo_state_manager = RepositoryStateManager(config, self.git_repo_dir)
        self.default_branch = "main"  # Will be dynamically determined
    
    def _initialize_repository(self) -> GitSyncResult:
        # Enhanced to handle existing repositories
        
    def sync_memory_with_retry(self, memory_id: str, filename: str) -> GitSyncResult:
        # Use dynamic branch name instead of hard-coded "main"
```

### 3. Repository State Detection

**RepositoryState Enum:**
```python
class RepositoryState(Enum):
    NEW_LOCAL = "new_local"           # No local .git, no remote configured
    EXISTING_LOCAL = "existing_local" # Local .git exists, may have remote
    EXISTING_REMOTE = "existing_remote" # Remote exists, needs cloning
    SYNCHRONIZED = "synchronized"     # Local and remote in sync
```

**Detection Logic:**
1. Check if local `.git` directory exists
2. Check if remote URL is configured
3. Check if remote repository exists and is accessible
4. Determine appropriate initialization strategy

### 4. Branch Detection and Management

**Default Branch Detection:**
```python
def detect_remote_default_branch(self, remote_url: str) -> str:
    """
    Detect the default branch of a remote repository.
    
    Strategy:
    1. Use `git ls-remote --symref origin HEAD` to get symbolic ref
    2. Parse the symbolic reference to extract branch name
    3. Fall back to common branch names (main, master, develop)
    4. Default to "main" if detection fails
    """
```

**Branch Synchronization:**
```python
def setup_branch_tracking(self, local_branch: str, remote_branch: str) -> GitSyncResult:
    """
    Set up tracking between local and remote branches.
    
    Operations:
    1. Create local branch if it doesn't exist
    2. Set upstream tracking: git branch --set-upstream-to=origin/branch
    3. Verify tracking configuration
    """
```

## Data Models

### RepositoryState

```python
@dataclass
class RepositoryInfo:
    state: RepositoryState
    local_exists: bool
    remote_exists: bool
    remote_url: Optional[str]
    default_branch: str
    local_branch: Optional[str]
    tracking_configured: bool
    needs_sync: bool
```

### Enhanced GitSyncResult

```python
@dataclass
class GitSyncResult:
    success: bool
    message: str
    operation: str
    attempts: int = 1
    error_code: Optional[str] = None
    repository_info: Optional[RepositoryInfo] = None  # NEW
    branch_used: Optional[str] = None  # NEW
```

## Error Handling

### Error Categories

1. **Repository Access Errors**
   - Network connectivity issues
   - Authentication failures
   - Repository not found
   - Permission denied

2. **Branch Detection Errors**
   - Remote branch detection failure
   - Ambiguous default branch
   - Branch creation failures

3. **Synchronization Errors**
   - Merge conflicts
   - Divergent histories
   - Push/pull failures

### Error Recovery Strategies

```python
class ErrorRecoveryStrategy:
    def handle_repository_access_error(self, error: GitSyncResult) -> GitSyncResult:
        """
        Recovery for repository access issues:
        1. Retry with exponential backoff
        2. Fall back to local-only mode
        3. Provide detailed error messages
        """
    
    def handle_branch_detection_error(self, error: GitSyncResult) -> GitSyncResult:
        """
        Recovery for branch detection issues:
        1. Try common branch names (main, master)
        2. Use configured default branch
        3. Create new branch if needed
        """
    
    def handle_sync_conflict(self, error: GitSyncResult) -> GitSyncResult:
        """
        Recovery for synchronization conflicts:
        1. Prioritize remote content
        2. Log conflicts for user review
        3. Continue with local operation
        """
```

## Testing Strategy

### Unit Tests

1. **RepositoryStateManager Tests**
   - Repository state detection accuracy
   - Default branch detection with various Git hosting services
   - Upstream tracking configuration
   - Error handling for network failures

2. **Enhanced GitSyncManager Tests**
   - Initialization with existing repositories
   - Dynamic branch name usage
   - Backward compatibility with existing configurations

3. **Integration Tests**
   - End-to-end sync with existing GitHub repositories
   - Conflict resolution scenarios
   - Multiple branch naming conventions

### Test Scenarios

```python
def test_existing_repository_scenarios():
    """
    Test scenarios:
    1. Empty existing repository
    2. Repository with existing memory files
    3. Repository with conflicting content
    4. Repository with different default branch (master, develop)
    5. Private repository requiring authentication
    6. Repository with no default branch set
    """
```

### Performance Testing

- Repository state detection performance
- Large repository cloning efficiency
- Sync performance with existing content
- Memory usage during synchronization

## Implementation Phases

### Phase 1: Repository State Detection
- Implement `RepositoryStateManager`
- Add repository state detection logic
- Create comprehensive test suite

### Phase 2: Branch Detection and Management
- Implement dynamic branch detection
- Add upstream tracking configuration
- Modify existing sync operations to use dynamic branch names

### Phase 3: Existing Repository Synchronization
- Implement repository cloning for existing remotes
- Add conflict resolution logic
- Enhance error handling and recovery

### Phase 4: Integration and Testing
- Integrate all components
- Comprehensive testing with various repository configurations
- Performance optimization and validation

## Backward Compatibility

The enhanced Git sync maintains full backward compatibility:

1. **Existing Configurations**: All current environment variables and configuration options continue to work
2. **New Repository Behavior**: When no remote is configured, behavior remains identical to current implementation
3. **Graceful Degradation**: If enhanced features fail, the system falls back to current behavior
4. **API Compatibility**: All existing public methods maintain their signatures and behavior

## Security Considerations

1. **Authentication**: Existing Git credential handling remains unchanged
2. **Repository Validation**: Validate remote URLs to prevent malicious repositories
3. **Content Validation**: Validate existing memory files before integration
4. **Error Information**: Avoid exposing sensitive information in error messages

## Monitoring and Logging

Enhanced logging for troubleshooting:

```python
# Repository state detection
logger.info(f"Detected repository state: {repo_state}")
logger.debug(f"Default branch detected: {default_branch}")

# Synchronization operations
logger.info(f"Synchronizing with existing repository: {remote_url}")
logger.warning(f"Conflict detected in file: {filename}")

# Error scenarios
logger.error(f"Failed to detect default branch, using fallback: {fallback_branch}")
```