"""
Runtime hook to fix openhands namespace package imports.

This hook ensures that the openhands namespace package properly resolves
to include both openhands.sdk and openhands.tools from the PyPI packages.
"""

import os
import sys


# When PyInstaller extracts the application, it sets sys._MEIPASS
# We need to ensure that openhands namespace resolution works correctly
if hasattr(sys, "_MEIPASS"):
    # PyInstaller extracts files to this directory
    base_path = sys._MEIPASS  # type: ignore[attr-defined]

    # Add the extracted location to the openhands package path if it exists
    try:
        import openhands

        if hasattr(openhands, "__path__"):
            # Ensure the extracted path is in the namespace package path
            extracted_openhands = os.path.join(base_path, "openhands")
            if extracted_openhands not in openhands.__path__:
                openhands.__path__.insert(0, extracted_openhands)
    except ImportError:
        pass
