#!/usr/bin/env python3
"""
Test that Task 11 requirements are fully implemented.

Task 11: Implement comprehensive input validation
- Add parameter validation for all MCP tools
- Implement sanitization for user inputs  
- Add validation for memory IDs and file names
- Create validation error responses
- Requirements: 3.5, 7.4
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
from aiaml.errors import ErrorResponse, error_handler


def test_requirement_parameter_validation_all_tools():
    """Test parameter validation for all MCP tools (remember, think, recall, performance_stats)."""
    print("Testing Parameter Validation for All MCP Tools")
    print("-" * 50)
    
    # Test remember tool validation
    params = {
        'agent': 'claude',
        'user': 'user1', 
        'topics': ['python', 'programming'],
        'content': 'Valid content'
    }
    error = validate_tool_parameters("remember", params)
    if error is None:
        print("  ✓ Remember tool parameter validation works")
    else:
        print(f"  ✗ Remember tool parameter validation failed: {error.message}")
        return False
    
    # Test think tool validation
    params = {'keywords': ['python', 'programming']}
    error = validate_tool_parameters("think", params)
    if error is None:
        print("  ✓ Think tool parameter validation works")
    else:
        print(f"  ✗ Think tool parameter validation failed: {error.message}")
        return False
    
    # Test recall tool validation
    params = {'memory_ids': ['abc12345', 'def67890']}
    error = validate_tool_parameters("recall", params)
    if error is None:
        print("  ✓ Recall tool parameter validation works")
    else:
        print(f"  ✗ Recall tool parameter validation failed: {error.message}")
        return False
    
    # Test performance_stats tool validation (no parameters)
    error = validate_tool_parameters("performance_stats", {})
    if error is None:
        print("  ✓ Performance stats tool parameter validation works")
    else:
        print(f"  ✗ Performance stats tool parameter validation failed: {error.message}")
        return False
    
    # Test parameter validation catches missing parameters
    params = {'agent': 'claude', 'user': 'user1'}  # Missing topics and content
    error = validate_tool_parameters("remember", params)
    if error and error.error_code.startswith("VALIDATION"):
        print("  ✓ Missing parameter detection works")
    else:
        print("  ✗ Missing parameter detection failed")
        return False
    
    return True


def test_requirement_input_sanitization():
    """Test sanitization for user inputs to prevent XSS and injection attacks."""
    print("\nTesting Input Sanitization for User Inputs")
    print("-" * 50)
    
    # Test HTML escaping
    try:
        result = sanitize_string_input("Content with <b>bold</b> tags", "test")
        if "&lt;b&gt;bold&lt;/b&gt;" in result:
            print("  ✓ HTML tags are properly escaped")
        else:
            print(f"  ✗ HTML tags not escaped properly: {result}")
            return False
    except Exception as e:
        print(f"  ✗ HTML escaping failed: {e}")
        return False
    
    # Test dangerous script rejection
    try:
        sanitize_string_input("<script>alert('xss')</script>", "test")
        print("  ✗ Dangerous script was not rejected")
        return False
    except ValueError:
        print("  ✓ Dangerous script content is rejected")
    except Exception as e:
        print(f"  ✗ Unexpected error with dangerous script: {e}")
        return False
    
    # Test JavaScript URL rejection
    try:
        sanitize_string_input("javascript:alert('xss')", "test")
        print("  ✗ JavaScript URL was not rejected")
        return False
    except ValueError:
        print("  ✓ JavaScript URL content is rejected")
    except Exception as e:
        print(f"  ✗ Unexpected error with JavaScript URL: {e}")
        return False
    
    # Test event handler rejection
    try:
        sanitize_string_input("onclick=alert('xss')", "test")
        print("  ✗ Event handler was not rejected")
        return False
    except ValueError:
        print("  ✓ Event handler content is rejected")
    except Exception as e:
        print(f"  ✗ Unexpected error with event handler: {e}")
        return False
    
    # Test unicode normalization
    try:
        result = sanitize_string_input("Café", "test")
        if "Café" in result:
            print("  ✓ Unicode normalization works")
        else:
            print(f"  ✗ Unicode normalization failed: {result}")
            return False
    except Exception as e:
        print(f"  ✗ Unicode normalization error: {e}")
        return False
    
    return True


def test_requirement_memory_id_validation():
    """Test validation for memory IDs with proper format checking."""
    print("\nTesting Memory ID Validation")
    print("-" * 50)
    
    # Test valid memory ID formats
    valid_ids = ["abc12345", "def67890", "12345678", "abcdef01", "00000000", "ffffffff"]
    for memory_id in valid_ids:
        if validate_memory_id_format(memory_id):
            print(f"  ✓ Valid memory ID accepted: {memory_id}")
        else:
            print(f"  ✗ Valid memory ID rejected: {memory_id}")
            return False
    
    # Test invalid memory ID formats
    invalid_ids = [
        "ABC12345",    # Uppercase
        "abc1234",     # Too short
        "abc123456",   # Too long
        "xyz!@#$%",    # Invalid characters
        "",            # Empty
        "abc 1234",    # Space
        "abcdefgh",    # Non-hex characters
        123456789      # Not a string
    ]
    for memory_id in invalid_ids:
        if not validate_memory_id_format(memory_id):
            print(f"  ✓ Invalid memory ID rejected: {memory_id}")
        else:
            print(f"  ✗ Invalid memory ID accepted: {memory_id}")
            return False
    
    # Test memory ID validation in recall function
    error = validate_recall_input(["abc12345", "def67890"])
    if error is None:
        print("  ✓ Valid memory IDs pass recall validation")
    else:
        print(f"  ✗ Valid memory IDs fail recall validation: {error.message}")
        return False
    
    error = validate_recall_input(["invalid_id"])
    if error and "invalid format" in error.message:
        print("  ✓ Invalid memory ID format caught in recall validation")
    else:
        print("  ✗ Invalid memory ID format not caught in recall validation")
        return False
    
    return True


def test_requirement_filename_validation():
    """Test validation for file names with security checks."""
    print("\nTesting Filename Validation")
    print("-" * 50)
    
    # Test safe filenames
    safe_filenames = [
        "memory.md",
        "20240115_103000_abc12345.md",
        "test-file_123.txt",
        "simple.log",
        "data_2024.json"
    ]
    for filename in safe_filenames:
        if validate_filename_safety(filename):
            print(f"  ✓ Safe filename accepted: {filename}")
        else:
            print(f"  ✗ Safe filename rejected: {filename}")
            return False
    
    # Test dangerous filenames
    dangerous_filenames = [
        "../../../etc/passwd",     # Path traversal
        "file<script>.md",         # HTML injection
        "CON.md",                  # Windows reserved name
        "file|pipe.md",            # Pipe character
        "file:stream.md",          # Colon character
        'file"quote.md',           # Quote character
        "file?query.md",           # Question mark
        "file*wildcard.md",        # Asterisk
        "",                        # Empty filename
        "a" * 300,                 # Too long filename
        "file with spaces.md",     # Spaces (not allowed in our strict validation)
        "file\x00null.md"          # Null byte
    ]
    for filename in dangerous_filenames:
        if not validate_filename_safety(filename):
            print(f"  ✓ Dangerous filename rejected: {filename}")
        else:
            print(f"  ✗ Dangerous filename accepted: {filename}")
            return False
    
    return True


def test_requirement_validation_error_responses():
    """Test that validation error responses are properly structured and informative."""
    print("\nTesting Validation Error Responses")
    print("-" * 50)
    
    # Test memory input validation error response
    error = validate_memory_input("", "user1", ["topic"], "content")
    if error and isinstance(error, ErrorResponse):
        print("  ✓ Memory validation returns ErrorResponse object")
        
        # Check required fields
        error_dict = error.to_dict()
        required_fields = ['error', 'error_code', 'message', 'timestamp', 'category']
        for field in required_fields:
            if field in error_dict:
                print(f"    ✓ Error response has {field}: {error_dict[field]}")
            else:
                print(f"    ✗ Error response missing {field}")
                return False
        
        # Check error categorization
        if error.category == "validation":
            print("  ✓ Error properly categorized as validation")
        else:
            print(f"  ✗ Error incorrectly categorized: {error.category}")
            return False
        
        # Check error code format
        if error.error_code.startswith("VALIDATION"):
            print("  ✓ Error code follows proper format")
        else:
            print(f"  ✗ Error code format incorrect: {error.error_code}")
            return False
            
    else:
        print("  ✗ Memory validation does not return ErrorResponse")
        return False
    
    # Test search input validation error response
    error = validate_search_input([])
    if error and isinstance(error, ErrorResponse):
        print("  ✓ Search validation returns ErrorResponse object")
        if error.error_code.startswith("VALIDATION"):
            print("  ✓ Search error code follows proper format")
        else:
            print(f"  ✗ Search error code format incorrect: {error.error_code}")
            return False
    else:
        print("  ✗ Search validation does not return ErrorResponse")
        return False
    
    # Test recall input validation error response
    error = validate_recall_input(["invalid"])
    if error and isinstance(error, ErrorResponse):
        print("  ✓ Recall validation returns ErrorResponse object")
        if error.error_code.startswith("VALIDATION"):
            print("  ✓ Recall error code follows proper format")
        else:
            print(f"  ✗ Recall error code format incorrect: {error.error_code}")
            return False
    else:
        print("  ✗ Recall validation does not return ErrorResponse")
        return False
    
    return True


def test_requirement_comprehensive_coverage():
    """Test that validation covers all input vectors comprehensively."""
    print("\nTesting Comprehensive Validation Coverage")
    print("-" * 50)
    
    # Test type validation
    error = validate_memory_input(123, "user", ["topic"], "content")
    if error and "string" in error.message:
        print("  ✓ Type validation works (non-string agent)")
    else:
        print("  ✗ Type validation failed for non-string agent")
        return False
    
    # Test length validation
    error = validate_memory_input("a" * 100, "user", ["topic"], "content")
    if error and "50 characters" in error.message:
        print("  ✓ Length validation works (agent too long)")
    else:
        print("  ✗ Length validation failed for long agent")
        return False
    
    # Test list validation
    error = validate_memory_input("agent", "user", "not_a_list", "content")
    if error and ("list" in error.message or "topics" in error.message):
        print("  ✓ List validation works (topics not a list)")
    else:
        print("  ✗ List validation failed for non-list topics")
        return False
    
    # Test empty validation
    error = validate_memory_input("agent", "user", [], "content")
    if error and "At least one topic" in error.message:
        print("  ✓ Empty validation works (empty topics)")
    else:
        print("  ✗ Empty validation failed for empty topics")
        return False
    
    # Test content size validation
    error = validate_memory_input("agent", "user", ["topic"], "x" * 100001)
    if error and ("100,000 characters" in error.message or "100000 characters" in error.message):
        print("  ✓ Content size validation works")
    else:
        print(f"  ✗ Content size validation failed - Error: {error.message if error else 'None'}")
        return False
    
    return True


def test_integration_with_server():
    """Test that validation is properly integrated with the server tools."""
    print("\nTesting Integration with Server Tools")
    print("-" * 50)
    
    # Import server functions to test integration
    try:
        from aiaml.memory import (
            validate_memory_input,
            validate_search_input, 
            validate_recall_input
        )
        print("  ✓ Validation functions are properly exported from memory module")
    except ImportError as e:
        print(f"  ✗ Validation functions not properly exported: {e}")
        return False
    
    # Test that validation functions are used in server.py
    try:
        with open("aiaml/server.py", "r") as f:
            server_content = f.read()
            
        if "validate_memory_input" in server_content:
            print("  ✓ Memory input validation is used in server")
        else:
            print("  ✗ Memory input validation not used in server")
            return False
            
        if "validate_search_input" in server_content:
            print("  ✓ Search input validation is used in server")
        else:
            print("  ✗ Search input validation not used in server")
            return False
            
        if "validate_recall_input" in server_content:
            print("  ✓ Recall input validation is used in server")
        else:
            print("  ✗ Recall input validation not used in server")
            return False
            
    except Exception as e:
        print(f"  ✗ Error checking server integration: {e}")
        return False
    
    return True


def main():
    """Run all task requirement tests."""
    print("Task 11: Comprehensive Input Validation - Requirements Test")
    print("=" * 70)
    
    tests = [
        ("Parameter validation for all MCP tools", test_requirement_parameter_validation_all_tools),
        ("Input sanitization for user inputs", test_requirement_input_sanitization),
        ("Memory ID validation", test_requirement_memory_id_validation),
        ("Filename validation", test_requirement_filename_validation),
        ("Validation error responses", test_requirement_validation_error_responses),
        ("Comprehensive validation coverage", test_requirement_comprehensive_coverage),
        ("Integration with server", test_integration_with_server)
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"\n✅ REQUIREMENT SATISFIED: {test_name}")
            else:
                failed += 1
                print(f"\n❌ REQUIREMENT NOT SATISFIED: {test_name}")
        except Exception as e:
            failed += 1
            print(f"\n❌ REQUIREMENT TEST FAILED: {test_name} - {e}")
    
    print("\n" + "=" * 70)
    print(f"Task 11 Requirements Test Results: {passed} satisfied, {failed} not satisfied")
    
    if failed == 0:
        print("\n🎉 ALL TASK 11 REQUIREMENTS SATISFIED!")
        print("\n✅ Parameter validation for all MCP tools - IMPLEMENTED")
        print("✅ Input sanitization for user inputs - IMPLEMENTED")
        print("✅ Memory ID and filename validation - IMPLEMENTED")
        print("✅ Validation error responses - IMPLEMENTED")
        print("✅ Requirements 3.5 and 7.4 - SATISFIED")
        return True
    else:
        print(f"\n❌ {failed} TASK 11 REQUIREMENTS NOT SATISFIED!")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)