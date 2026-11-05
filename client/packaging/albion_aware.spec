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
        ("../data/avalon", "data/avalon"),
    ],
    hiddenimports=["pystray._win32", "PIL._tkinter_finder"],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="AlbionAware",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon="albion.ico",
)
# 目录模式：图标等静态资源直接随目录拷贝，不需要每次启动解包到临时目录
coll = COLLECT(
    exe, a.binaries, a.datas,
    strip=False,
    upx=False,
    name="AlbionAware",
)
