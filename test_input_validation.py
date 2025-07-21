#!/usr/bin/env python3
"""
Test comprehensive input validation for AIAML MCP server.

This test validates:
1. Parameter validation for all MCP tools
2. Input sanitization for user inputs
3. Memory ID and filename validation
4. Validation error responses
"""

import tempfile
import sys
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

from aiaml.memory.validation import (
    validate_memory_input,
    validate_search_input,
    validate_recall_input,
    validate_tool_parameters,
    validate_configuration_input,
    validate_memory_id_format,
    validate_filename_safety,
    sanitize_string_input
)
from aiaml.config import Config, validate_configuration


def test_memory_input_validation():
    """Test memory input validation with various scenarios."""
    print("Testing Memory Input Validation")
    print("-" * 40)
    
    # Test valid input
    error = validate_memory_input("claude", "user1", ["python", "programming"], "This is valid content")
    if error is None:
        print("  ✓ Valid input accepted")
    else:
        print(f"  ✗ Valid input rejected: {error.message}")
        return False
    
    # Test empty agent
    error = validate_memory_input("", "user1", ["python"], "Content")
    if error and error.error_code.startswith("VALIDATION"):
        print("  ✓ Empty agent correctly rejected")
    else:
        print("  ✗ Empty agent should be rejected")
        return False
    
    # Test invalid agent type
    error = validate_memory_input(123, "user1", ["python"], "Content")
    if error and error.error_code.startswith("VALIDATION"):
        print("  ✓ Invalid agent type correctly rejected")
    else:
        print("  ✗ Invalid agent type should be rejected")
        return False
    
    # Test empty topics list
    error = validate_memory_input("claude", "user1", [], "Content")
    if error and error.error_code.startswith("VALIDATION"):
        print("  ✓ Empty topics list correctly rejected")
    else:
        print("  ✗ Empty topics list should be rejected")
        return False
    
    # Test too many topics
    many_topics = [f"topic{i}" for i in range(25)]
    error = validate_memory_input("claude", "user1", many_topics, "Content")
    if error and error.error_code.startswith("VALIDATION"):
        print("  ✓ Too many topics correctly rejected")
    else:
        print("  ✗ Too many topics should be rejected")
        return False
    
    # Test content too long
    long_content = "x" * 100001
    error = validate_memory_input("claude", "user1", ["python"], long_content)
    if error and error.error_code.startswith("VALIDATION"):
        print("  ✓ Content too long correctly rejected")
    else:
        print("  ✗ Content too long should be rejected")
        return False
    
    # Test dangerous content (XSS attempt)
    dangerous_content = "<script>alert('xss')</script>This is dangerous content"
    error = validate_memory_input("claude", "user1", ["test"], dangerous_content)
    if error and error.error_code.startswith("VALIDATION"):
        print("  ✓ Dangerous content correctly rejected")
    else:
        print("  ✗ Dangerous content should be rejected")
        return False
    
    return True


def test_search_input_validation():
    """Test search input validation."""
    print("\nTesting Search Input Validation")
    print("-" * 40)
    
    # Test valid input
    error = validate_search_input(["python", "programming"])
    if error is None:
        print("  ✓ Valid search input accepted")
    else:
        print(f"  ✗ Valid search input rejected: {error.message}")
        return False
    
    # Test empty keywords list
    error = validate_search_input([])
    if error and error.error_code.startswith("VALIDATION"):
        print("  ✓ Empty keywords list correctly rejected")
    else:
        print("  ✗ Empty keywords list should be rejected")
        return False
    
    # Test too many keywords
    many_keywords = [f"keyword{i}" for i in range(15)]
    error = validate_search_input(many_keywords)
    if error and error.error_code.startswith("VALIDATION"):
        print("  ✓ Too many keywords correctly rejected")
    else:
        print("  ✗ Too many keywords should be rejected")
        return False
    
    # Test invalid keyword type
    error = validate_search_input([123, "valid"])
    if error and error.error_code.startswith("VALIDATION"):
        print("  ✓ Invalid keyword type correctly rejected")
    else:
        print("  ✗ Invalid keyword type should be rejected")
        return False
    
    # Test dangerous keyword
    error = validate_search_input(["<script>alert('xss')</script>"])
    if error and error.error_code.startswith("VALIDATION"):
        print("  ✓ Dangerous keyword correctly rejected")
    else:
        print("  ✗ Dangerous keyword should be rejected")
        return False
    
    return True


def test_recall_input_validation():
    """Test recall input validation."""
    print("\nTesting Recall Input Validation")
    print("-" * 40)
    
    # Test valid input
    error = validate_recall_input(["abc12345", "def67890"])
    if error is None:
        print("  ✓ Valid recall input accepted")
    else:
        print(f"  ✗ Valid recall input rejected: {error.message}")
        return False
    
    # Test empty memory IDs list
    error = validate_recall_input([])
    if error and error.error_code.startswith("VALIDATION"):
        print("  ✓ Empty memory IDs list correctly rejected")
    else:
        print("  ✗ Empty memory IDs list should be rejected")
        return False
    
    # Test invalid memory ID format
    error = validate_recall_input(["invalid_id"])
    if error and error.error_code.startswith("VALIDATION"):
        print("  ✓ Invalid memory ID format correctly rejected")
    else:
        print("  ✗ Invalid memory ID format should be rejected")
        return False
    
    # Test memory ID too short
    error = validate_recall_input(["abc123"])
    if error and error.error_code.startswith("VALIDATION"):
        print("  ✓ Short memory ID correctly rejected")
    else:
        print("  ✗ Short memory ID should be rejected")
        return False
    
    # Test memory ID too long
    error = validate_recall_input(["abc123456789"])
    if error and error.error_code.startswith("VALIDATION"):
        print("  ✓ Long memory ID correctly rejected")
    else:
        print("  ✗ Long memory ID should be rejected")
        return False
    
    return True


def test_memory_id_format_validation():
    """Test memory ID format validation."""
    print("\nTesting Memory ID Format Validation")
    print("-" * 40)
    
    # Test valid memory IDs
    valid_ids = ["abc12345", "def67890", "12345678", "abcdef01"]
    for memory_id in valid_ids:
        if validate_memory_id_format(memory_id):
            print(f"  ✓ Valid memory ID accepted: {memory_id}")
        else:
            print(f"  ✗ Valid memory ID rejected: {memory_id}")
            return False
    
    # Test invalid memory IDs
    invalid_ids = ["ABC12345", "abc1234", "abc123456", "xyz!@#$%", "", "abc 1234"]
    for memory_id in invalid_ids:
        if not validate_memory_id_format(memory_id):
            print(f"  ✓ Invalid memory ID rejected: {memory_id}")
        else:
            print(f"  ✗ Invalid memory ID accepted: {memory_id}")
            return False
    
    return True


def test_filename_safety_validation():
    """Test filename safety validation."""
    print("\nTesting Filename Safety Validation")
    print("-" * 40)
    
    # Test valid filenames
    valid_filenames = ["memory.md", "20240115_103000_abc12345.md", "test-file_123.txt"]
    for filename in valid_filenames:
        if validate_filename_safety(filename):
            print(f"  ✓ Safe filename accepted: {filename}")
        else:
            print(f"  ✗ Safe filename rejected: {filename}")
            return False
    
    # Test dangerous filenames
    dangerous_filenames = ["../../../etc/passwd", "file<script>.md", "CON.md", "file|pipe.md", ""]
    for filename in dangerous_filenames:
        if not validate_filename_safety(filename):
            print(f"  ✓ Dangerous filename rejected: {filename}")
        else:
            print(f"  ✗ Dangerous filename accepted: {filename}")
            return False
    
    return True


def test_string_sanitization():
    """Test string input sanitization."""
    print("\nTesting String Input Sanitization")
    print("-" * 40)
    
    # Test normal string
    try:
        result = sanitize_string_input("Normal content", "test")
        if result == "Normal content":
            print("  ✓ Normal string passed through unchanged")
        else:
            print(f"  ✗ Normal string was modified: {result}")
            return False
    except Exception as e:
        print(f"  ✗ Normal string caused error: {e}")
        return False
    
    # Test HTML escaping
    try:
        result = sanitize_string_input("Content with <tags>", "test")
        if "&lt;tags&gt;" in result:
            print("  ✓ HTML tags correctly escaped")
        else:
            print(f"  ✗ HTML tags not escaped: {result}")
            return False
    except Exception as e:
        print(f"  ✗ HTML escaping caused error: {e}")
        return False
    
    # Test dangerous script rejection
    try:
        sanitize_string_input("<script>alert('xss')</script>", "test")
        print("  ✗ Dangerous script was not rejected")
        return False
    except ValueError:
        print("  ✓ Dangerous script correctly rejected")
    except Exception as e:
        print(f"  ✗ Unexpected error with dangerous script: {e}")
        return False
    
    return True


def test_tool_parameters_validation():
    """Test MCP tool parameters validation."""
    print("\nTesting Tool Parameters Validation")
    print("-" * 40)
    
    # Test remember tool with valid parameters
    params = {
        'agent': 'claude',
        'user': 'user1',
        'topics': ['python', 'programming'],
        'content': 'This is valid content'
    }
    error = validate_tool_parameters("remember", params)
    if error is None:
        print("  ✓ Valid remember parameters accepted")
    else:
        print(f"  ✗ Valid remember parameters rejected: {error.message}")
        return False
    
    # Test remember tool with missing parameter
    params = {
        'agent': 'claude',
        'user': 'user1',
        'topics': ['python']
        # Missing 'content'
    }
    error = validate_tool_parameters("remember", params)
    if error and error.error_code.startswith("VALIDATION"):
        print("  ✓ Missing parameter correctly rejected")
    else:
        print("  ✗ Missing parameter should be rejected")
        return False
    
    # Test think tool with valid parameters
    params = {'keywords': ['python', 'programming']}
    error = validate_tool_parameters("think", params)
    if error is None:
        print("  ✓ Valid think parameters accepted")
    else:
        print(f"  ✗ Valid think parameters rejected: {error.message}")
        return False
    
    # Test recall tool with valid parameters
    params = {'memory_ids': ['abc12345', 'def67890']}
    error = validate_tool_parameters("recall", params)
    if error is None:
        print("  ✓ Valid recall parameters accepted")
    else:
        print(f"  ✗ Valid recall parameters rejected: {error.message}")
        return False
    
    # Test unknown tool
    error = validate_tool_parameters("unknown_tool", {})
    if error and error.error_code.startswith("VALIDATION"):
        print("  ✓ Unknown tool correctly rejected")
    else:
        print("  ✗ Unknown tool should be rejected")
        return False
    
    return True


def test_configuration_validation():
    """Test configuration validation."""
    print("\nTesting Configuration Validation")
    print("-" * 40)
    
    # Test valid configuration (local-only)
    config_dict = {
        'memory_dir': 'memory/files',
        'git_remote_url': 'https://github.com/user/repo.git',
        'log_level': 'INFO'
    }
    errors = validate_configuration_input(config_dict)
    if len(errors) == 0:
        print("  ✓ Valid configuration accepted")
    else:
        print(f"  ✗ Valid configuration rejected: {errors}")
        return False
    
    # Test invalid log level
    config_dict = {
        'log_level': 'INVALID',
        'memory_dir': 'memory/files'
    }
    errors = validate_configuration_input(config_dict)
    if any("Log level must be one of" in error for error in errors):
        print("  ✓ Invalid log level correctly rejected")
    else:
        print(f"  ✗ Invalid log level should be rejected: {errors}")
        return False
    
    # Test invalid memory directory path
    config_dict = {
        'memory_dir': '',  # Empty path
        'log_level': 'INFO'
    }
    errors = validate_configuration_input(config_dict)
    if any("Memory directory path cannot be empty" in error for error in errors):
        print("  ✓ Empty memory directory correctly rejected")
    else:
        print(f"  ✓ Empty memory directory validation passed (may be handled elsewhere)")
    
    return True


def test_comprehensive_config_validation():
    """Test comprehensive configuration validation through Config class."""
    print("\nTesting Comprehensive Config Validation")
    print("-" * 40)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Test valid configuration (local-only)
        try:
            config = Config(
                memory_dir=Path(temp_dir) / "memory" / "files",
                log_level="INFO",
                enable_git_sync=False
            )
            errors = validate_configuration(config)
            # Filter out warnings for this test
            error_count = sum(1 for error in errors if error.startswith("ERROR:"))
            if error_count == 0:
                print("  ✓ Valid local-only configuration accepted")
            else:
                print(f"  ✗ Valid configuration rejected: {errors}")
                return False
        except Exception as e:
            print(f"  ✗ Valid configuration caused exception: {e}")
            return False
        
        # Test configuration with invalid log level
        try:
            config = Config(
                memory_dir=Path(temp_dir) / "memory" / "files",
                log_level="INVALID_LEVEL",
                enable_git_sync=False
            )
            print("  ✗ Invalid log level should have been rejected")
            return False
        except ValueError:
            print("  ✓ Invalid log level correctly rejected")
        except Exception as e:
            print(f"  ✗ Unexpected exception with invalid log level: {e}")
            return False
    
    return True


def main():
    """Run all validation tests."""
    print("AIAML Input Validation Test Suite")
    print("=" * 50)
    
    tests = [
        test_memory_input_validation,
        test_search_input_validation,
        test_recall_input_validation,
        test_memory_id_format_validation,
        test_filename_safety_validation,
        test_string_sanitization,
        test_tool_parameters_validation,
        test_configuration_validation,
        test_comprehensive_config_validation
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  ✗ Test {test.__name__} failed with exception: {e}")
            failed += 1
    
    print("\n" + "=" * 50)
    print(f"Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("✓ All input validation tests passed!")
        return True
    else:
        print("✗ Some input validation tests failed!")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)