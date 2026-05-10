# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all


def _include_kivy_submodule(name: str) -> bool:
    return name != "kivy.garden" and not name.startswith("kivy.garden.")

datas = [('database.db', '.'), ('kivy_ui', './kivy_ui'), ('app', './app')]
binaries = []
hiddenimports = ['kivy', 'kivy.uix.screenmanager', 'kivy.core.window']
tmp_ret = collect_all('kivy', filter_submodules=_include_kivy_submodule)
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['main.py'],
    pathex=[],
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
    a.binaries,
    a.datas,
    [],
    name='LaTiburona',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
