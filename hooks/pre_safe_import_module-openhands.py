"""Pre-safe-import-module hook for openhands namespace package.

This hook is needed because openhands is a PEP 420 namespace package
without an __init__.py file.
"""

def pre_safe_import_module(api):
    """Set up the openhands namespace package."""
    # Tell PyInstaller that openhands is a namespace package
    api.add_runtime_package_path('openhands', api.module_graph.find_module('openhands.sdk').__file__)
