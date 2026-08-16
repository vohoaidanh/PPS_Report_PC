# build.spec
from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.', 'src'],
    binaries=[],
    datas=[
        ('src/pps_report/gui', 'gui'),
        ('src/pps_report/core', 'core'),
        ('src/pps_report/report', 'report'),
        ('src/pps_report/utils', 'utils'),
        ('sample', 'sample'),
        ('assets', 'assets'),
    ],
    hiddenimports=[
        'shiboken6',
        'PySide6.QtPrintSupport',
        'PySide6.QtPdf',
        'PySide6.QtPdfWidgets',
        'vtkmodules',
        'vtkmodules.all',
        'vtkmodules.util.misc',
        'vtkmodules.util.numpy_support',
        'pyvista',
        'pyvistaqt',
        'open3d',
        'pdfkit',
        'jinja2',
    ],
    hookspath=['.'],
    runtime_hooks=[],
    excludes=[
        # The build machine's global site-packages carries other Qt
        # bindings and unrelated ML frameworks; PyInstaller refuses to
        # freeze an app that pulls in more than one Qt binding, and none
        # of these are dependencies of this application.
        'PyQt5', 'PyQt6', 'PySide2',
        'torch', 'tensorflow', 'transformers', 'IPython',
    ],
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name='Jacon PPS Report Generator',
    debug=False,
    console=True,
    icon='assets/icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='Jacon PPS Report Generator',
)
