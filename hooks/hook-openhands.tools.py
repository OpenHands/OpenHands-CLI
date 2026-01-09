"""PyInstaller hook for openhands.tools namespace package."""

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# Collect all submodules from openhands.tools
hiddenimports = collect_submodules('openhands.tools')

# Collect data files
datas = collect_data_files('openhands.tools')
