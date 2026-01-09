"""Runtime hook to set up openhands namespace package."""

import sys
import os
import pkgutil

# Create the openhands namespace package
# This is needed because openhands is a PEP 420 namespace package
# without an __init__.py file

# Get the base path where PyInstaller extracts files
if getattr(sys, 'frozen', False):
    # Running in a PyInstaller bundle
    base_path = sys._MEIPASS
    
    # Create a namespace package for openhands
    import types
    
    # Check if openhands is already in sys.modules
    if 'openhands' not in sys.modules:
        # Create a namespace package
        openhands = types.ModuleType('openhands')
        openhands.__path__ = pkgutil.extend_path([], 'openhands')
        openhands.__file__ = None
        openhands.__package__ = 'openhands'
        sys.modules['openhands'] = openhands
