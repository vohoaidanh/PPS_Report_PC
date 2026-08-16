from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = collect_data_files('pyvista')
hiddenimports = collect_submodules('pyvista')