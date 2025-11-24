"""
PyInstaller runtime hook to filter sys.path.

This hook removes /openhands/code from sys.path to avoid namespace conflicts
between the OpenHands main repository package and the openhands-sdk/openhands-tools
packages that are properly installed via pip/uv.

The /openhands/code path is added by the Docker environment but causes issues
with PyInstaller's module collection.
"""

import sys

# Filter out /openhands/code from sys.path to avoid namespace conflicts
sys.path = [p for p in sys.path if '/openhands/code' not in p]
