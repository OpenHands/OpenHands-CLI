# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for OpenHands CLI.

This spec file configures PyInstaller to create a standalone executable
for the OpenHands CLI application.
"""

from pathlib import Path
import os
import sys
from PyInstaller.utils.hooks import (
    collect_submodules,
    collect_data_files,
    copy_metadata
)



# Get the project root directory (current working directory when running PyInstaller)
project_root = Path.cwd()

# Get the site-packages directory for the virtual environment
# This is needed to find namespace packages like openhands.sdk and openhands.tools
import site
site_packages = site.getsitepackages()[0] if site.getsitepackages() else None

# Build pathex list
pathex_list = [str(project_root)]
if site_packages:
    pathex_list.append(site_packages)
    # Also add the openhands namespace package directory explicitly
    openhands_path = os.path.join(site_packages, 'openhands')
    if os.path.exists(openhands_path):
        pathex_list.append(openhands_path)

# Create a temporary __init__.py for the openhands namespace package
# This is needed because openhands is a PEP 420 namespace package without __init__.py
# and PyInstaller doesn't automatically handle namespace packages
openhands_init_created = False
if site_packages:
    openhands_init_path = os.path.join(site_packages, 'openhands', '__init__.py')
    if not os.path.exists(openhands_init_path):
        try:
            with open(openhands_init_path, 'w') as f:
                f.write('# Namespace package init created by PyInstaller spec\n')
                f.write('__path__ = __import__("pkgutil").extend_path(__path__, __name__)\n')
            openhands_init_created = True
            print(f"Created temporary __init__.py at {openhands_init_path}")
        except Exception as e:
            print(f"Warning: Could not create __init__.py for openhands namespace: {e}")

a = Analysis(
    ['openhands_cli/entrypoint.py'],
    pathex=pathex_list,
    binaries=[],
    datas=[
        # Include any data files that might be needed
        # Add more data files here if needed in the future
        *collect_data_files('tiktoken'),
        *collect_data_files('tiktoken_ext'),
        *collect_data_files('litellm'),
        *collect_data_files('fastmcp'),
        *collect_data_files('mcp'),
        # Include all data files from openhands.sdk (templates, configs, etc.)
        *collect_data_files('openhands.sdk'),
        # Include all data files from openhands_cli package
        *collect_data_files('openhands_cli'),
        # Include package metadata for importlib.metadata
        *copy_metadata('fastmcp'),
        *copy_metadata('agent-client-protocol'),
    ],
    hiddenimports=[
        # Explicitly include modules that might not be detected automatically
        *collect_submodules('openhands_cli'),
        *collect_submodules('prompt_toolkit'),
        # Include OpenHands SDK submodules explicitly to avoid resolution issues
        # Note: openhands is a namespace package (PEP 420) without __init__.py
        # We need to explicitly include the submodules
        *collect_submodules('openhands.sdk'),
        *collect_submodules('openhands.tools'),
        # Explicitly include commonly used SDK modules to ensure they're bundled
        'openhands.sdk.llm',
        'openhands.sdk.agent',
        'openhands.sdk.conversation',
        'openhands.sdk.event',
        'openhands.sdk.tool',
        'openhands.sdk.context',
        'openhands.sdk.mcp',
        'openhands.sdk.io',
        'openhands.sdk.workspace',
        'openhands.sdk.logger',
        *collect_submodules('tiktoken'),
        *collect_submodules('tiktoken_ext'),
        *collect_submodules('litellm'),
        *collect_submodules('fastmcp'),
        # Include Agent Client Protocol (ACP) for 'openhands acp' command
        *collect_submodules('acp'),
        # Include mcp but exclude CLI parts that require typer
        'mcp.types',
        'mcp.client',
        'mcp.server',
        'mcp.shared',
        'openhands.tools.terminal',
        'openhands.tools.str_replace_editor',
        'openhands.tools.task_tracker',
        # Include textual internal modules that might not be auto-detected
        'textual.widgets._tab_pane',
        'textual.widgets._select',
        'textual.widgets._tabbed_content',
    ],
    hookspath=[str(project_root / "hooks")],
    hooksconfig={},
    runtime_hooks=[str(project_root / "hooks" / "rthook_openhands.py")],
    excludes=[
        # Exclude unnecessary modules to reduce binary size
        'tkinter',
        'matplotlib',
        'numpy',
        'scipy',
        'pandas',
        'IPython',
        'jupyter',
        'notebook',
        # Exclude mcp CLI parts that cause issues
        'mcp.cli',
        'prompt_toolkit.contrib.ssh',
        'fastmcp.cli',
        'boto3',
        'botocore',
        'posthog',
        'browser-use',
        'openhands.tools.browser_use'
    ],
    noarchive=False,
    # IMPORTANT: do not use optimize=2 (-OO) because it strips docstrings used by PLY/bashlex grammar
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='openhands',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,  # Strip debug symbols to reduce size
    upx=True,    # Use UPX compression if available
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # CLI application needs console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon path here if you have one
)
