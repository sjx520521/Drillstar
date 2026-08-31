# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules


project_root = Path.cwd()

datas = [
    (str(project_root / "icon"), "icon"),
    (str(project_root / "style.qss"), "."),
    (str(project_root / "graph.json"), "."),
]
binaries = []
hiddenimports = []

for package_name in [
    "pyqtgraph",
    "matplotlib",
    "numpy",
    "pandas",
    "scipy",
    "sklearn",
    "openpyxl",
    "xlrd",
    "nidaqmx",
    "pymysql",
    "cryptography",
    "cffi",
    "requests",
    "tzlocal",
]:
    pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(package_name)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hiddenimports

hiddenimports += [
    "matplotlib.backends.backend_qt5agg",
    "matplotlib.backends.backend_qtagg",
    "mpl_toolkits.mplot3d",
]

datas += collect_data_files("dataanalysis", include_py_files=False)
hiddenimports += collect_submodules("dataanalysis")


a = Analysis(
    ["main.py"],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DrillStar",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="DrillStar",
)
