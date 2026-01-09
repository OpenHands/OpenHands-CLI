"""PyInstaller hook for openhands namespace package."""

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# Collect all submodules from the openhands namespace package
hiddenimports = collect_submodules('openhands.sdk') + collect_submodules('openhands.tools')

# Collect data files
datas = collect_data_files('openhands.sdk') + collect_data_files('openhands.tools')
