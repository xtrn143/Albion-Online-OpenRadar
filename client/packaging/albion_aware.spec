# client/packaging/albion_aware.spec
# -*- mode: python ; coding: utf-8 -*-
a = Analysis(
    ["../albion_aware/main.py"],
    pathex=[".."],
    binaries=[],
    datas=[
        ("../albion_aware/lang", "albion_aware/lang"),
        ("../data/items.min.json", "data"),
        ("../data/icons", "data/icons"),
    ],
    hiddenimports=["pystray._win32", "PIL._tkinter_finder"],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="AlbionAware",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon="albion.ico",
)
