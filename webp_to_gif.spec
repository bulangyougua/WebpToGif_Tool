# -*- mode: python ; coding: utf-8 -*-
import os
import tkinterdnd2

_tkdnd_dir = os.path.dirname(tkinterdnd2.__file__)

a = Analysis(
    ['webp_to_gif.py'],
    pathex=[],
    binaries=[],
    datas=[
        (os.path.join(_tkdnd_dir, 'tkdnd'), os.path.join('tkinterdnd2', 'tkdnd')),
        (os.path.join(_tkdnd_dir, 'TkinterDnD.py'), 'tkinterdnd2'),
        (os.path.join(_tkdnd_dir, '__init__.py'), 'tkinterdnd2'),
        ('webp_converter_icon.ico', '.'),
    ],
    hiddenimports=['tkinterdnd2'],
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
    name='webp转换工具',
    icon='webp_converter_icon.ico',
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
