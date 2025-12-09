"""Tests for MCP visualization fix.

This module tests the fix for the issue where Linear MCP server returns JSON lists
causing 'list' object has no attribute 'items' error in the SDK's display_dict function.
"""

import json
import pytest

from openhands_cli.utils import apply_mcp_visualization_fix, display_json_data


class TestMCPVisualizationFix:
    """Test cases for the MCP visualization fix."""

    def test_display_json_data_with_dict(self):
        """Test display_json_data with dictionary input (original working case)."""
        data = {
            "id": "123",
            "title": "Test Issue",
            "description": "Multi-line\ndescription",
            "status": "open",
        }
        result = display_json_data(data)
        
        # Check that all fields are present in the output
        output = result.plain
        assert "id:" in output
        assert "title:" in output
        assert "description:" in output
        assert "status:" in output
        assert '"123"' in output
        assert '"Test Issue"' in output

    def test_display_json_data_with_list(self):
        """Test display_json_data with list input (the problematic case)."""
        data = [
            {"id": "1", "name": "Item 1"},
            {"id": "2", "name": "Item 2"},
            "Simple string",
            42,
        ]
        result = display_json_data(data)
        
        # Check that list items are formatted correctly
        output = result.plain
        assert "[0]:" in output
        assert "[1]:" in output
        assert "[2]:" in output
        assert "[3]:" in output
        assert "Simple string" in output
        assert "42" in output

    def test_display_json_data_with_string(self):
        """Test display_json_data with string input."""
        data = "Simple string response"
        result = display_json_data(data)
        
        output = result.plain
        assert output == "Simple string response"

    def test_display_json_data_with_number(self):
        """Test display_json_data with number input."""
        data = 42
        result = display_json_data(data)
        
        output = result.plain
        assert output == "42"

    def test_display_json_data_with_boolean(self):
        """Test display_json_data with boolean input."""
        data = True
        result = display_json_data(data)
        
        output = result.plain
        assert output == "True"

    def test_display_json_data_with_none(self):
        """Test display_json_data with None input."""
        data = None
        result = display_json_data(data)
        
        output = result.plain
        assert output == "None"

    def test_monkey_patch_application(self):
        """Test that the monkey patch is applied correctly."""
        # Apply the fix
        apply_mcp_visualization_fix()
        
        # Import the SDK module
        import openhands.sdk.utils.visualize
        
        # Test with a list (the problematic case)
        test_list = [{"key": "value"}, "string", 123]
        
        # This should not raise an AttributeError
        result = openhands.sdk.utils.visualize.display_dict(test_list)
        
        # Verify the result is correct
        output = result.plain
        assert "[0]:" in output
        assert "[1]:" in output
        assert "[2]:" in output

    def test_mcp_observation_simulation(self):
        """Test the full MCP observation scenario that was causing the error."""
        # Apply the fix first
        apply_mcp_visualization_fix()
        
        # Simulate Linear MCP server response (JSON list)
        json_response = '''[
            {
                "id": "issue-123",
                "title": "Fix MCP visualization bug",
                "status": "in_progress"
            },
            {
                "id": "issue-124", 
                "title": "Update documentation",
                "status": "open"
            }
        ]'''
        
        # Parse the JSON (this is what happens in MCPToolObservation.visualize)
        parsed = json.loads(json_response)
        
        # Import the patched function
        from openhands.sdk.utils.visualize import display_dict
        
        # This should work without error
        result = display_dict(parsed)
        
        # Verify the output contains expected content
        output = result.plain
        assert "issue-123" in output
        assert "issue-124" in output
        assert "Fix MCP visualization bug" in output
        assert "Update documentation" in output

    def test_nested_data_structures(self):
        """Test display_json_data with nested data structures."""
        data = {
            "issues": [
                {"id": "1", "title": "First issue"},
                {"id": "2", "title": "Second issue"},
            ],
            "metadata": {
                "total": 2,
                "page": 1,
            },
        }
        result = display_json_data(data)
        
        output = result.plain
        assert "issues:" in output
        assert "metadata:" in output
        # Nested structures should be converted to string representation
        assert "First issue" in output or "id" in output

    def test_empty_list(self):
        """Test display_json_data with empty list."""
        data = []
        result = display_json_data(data)
        
        # Should handle empty list gracefully
        output = result.plain
        assert output.strip() == ""

    def test_empty_dict(self):
        """Test display_json_data with empty dictionary."""
        data = {}
        result = display_json_data(data)
        
        # Should handle empty dict gracefully
        output = result.plain
        assert output.strip() == ""