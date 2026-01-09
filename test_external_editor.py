#!/usr/bin/env python3
"""Simple test script for external editor functionality."""

import os
import tempfile
from pathlib import Path

# Add the project root to Python path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from openhands_cli.tui.widgets.input_field import get_external_editor


def test_editor_detection():
    """Test that editor detection works correctly."""
    print("Testing external editor detection...")
    
    # Save original environment
    original_visual = os.environ.get("VISUAL")
    original_editor = os.environ.get("EDITOR")
    
    try:
        # Test 1: VISUAL takes precedence
        os.environ["VISUAL"] = "vim"
        os.environ["EDITOR"] = "nano"
        editor = get_external_editor()
        print(f"✓ VISUAL precedence test: {editor} (expected: vim)")
        assert "vim" in editor
        
        # Test 2: EDITOR fallback
        del os.environ["VISUAL"]
        os.environ["EDITOR"] = "nano"
        editor = get_external_editor()
        print(f"✓ EDITOR fallback test: {editor} (expected: nano)")
        assert "nano" in editor
        
        # Test 3: System fallback
        del os.environ["EDITOR"]
        editor = get_external_editor()
        print(f"✓ System fallback test: {editor}")
        assert editor in ["vim", "nano", "emacs", "vi"]
        
        print("All tests passed! ✓")
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        
    finally:
        # Restore original environment
        if original_visual is not None:
            os.environ["VISUAL"] = original_visual
        elif "VISUAL" in os.environ:
            del os.environ["VISUAL"]
            
        if original_editor is not None:
            os.environ["EDITOR"] = original_editor
        elif "EDITOR" in os.environ:
            del os.environ["EDITOR"]


if __name__ == "__main__":
    test_editor_detection()