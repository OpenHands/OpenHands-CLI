"""PyInstaller hook for openhands.sdk namespace package."""

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# Collect all submodules from openhands.sdk
hiddenimports = collect_submodules('openhands.sdk')

# Collect data files
datas = collect_data_files('openhands.sdk')
