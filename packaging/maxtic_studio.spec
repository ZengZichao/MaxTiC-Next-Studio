# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec —— 将 MaxTiC-Next Studio 冻结为 macOS .app。

用法（仓库根目录执行，需已安装 PySide6 / matplotlib / PyInstaller / MaxTiC-Next）：

    pyinstaller packaging/maxtic_studio.spec --noconfirm

或一键脚本（自动把产物归位到 release/）：

    bash packaging/build_studio_app.sh

产物：``dist/MaxTiC-Next-Studio.app``（目录式 bundle，非 one-file）。
"""
import os
import sys
from pathlib import Path

# 打包脚本承诺支持的解释器与 pyproject 的 requires-python 一致（>=3.9），
# 而 tomllib 是 3.11 才进标准库的；缺它时 PyInstaller 读 spec 就直接 ImportError。
try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# SPECPATH 由 PyInstaller 注入，指向本 spec 所在目录（packaging/）
ROOT = Path(SPECPATH).resolve().parent
VERSION = tomllib.loads(
    (ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]

datas = collect_data_files("maxtic_next")            # report/templates/*.j2 等核心包内数据
datas.append((str(ROOT / "examples"), "examples"))   # 演示菜单加载的示例数据随包内置
datas.append((str(ROOT / "src" / "maxtic_studio" / "assets"), "assets"))  # 图标母版

# 应用图标：icns 由 SVG 母版现场渲染（Qt + iconutil），
# 因此仓库里不需要维护第二份"手画的"图标文件。
ICON_NAME = None
sys.path.insert(0, str(ROOT / "packaging"))
try:
    from make_app_icon import build_icns
    _icon_built = build_icns(str(ROOT / "build" / "maxtic-studio.icns"))
    if _icon_built.endswith(".icns"):
        # 不走 BUNDLE(icon=...)：PyInstaller 会把传入的 icns 重新编码一遍，
        # 实测丢掉 512/1024 两档，Retina 下的 Dock 图标因此发虚。
        # 这里把我们自己 iconutil 出来的 icns 原样放进 Resources，
        # 再用 CFBundleIconFile 指过去，尺寸集完全由 make_app_icon 说了算。
        ICON_NAME = os.path.basename(_icon_built)
        datas.append((_icon_built, "."))   # 目标写 "."：否则 PyInstaller 会把它当成子目录
except Exception as exc:                                  # 无 iconutil / 无 Qt：出无图标包而不是失败
    print(f"[spec] 未能生成 .icns，改用默认图标：{exc}")

a = Analysis(
    [str(ROOT / "packaging" / "studio_entry.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=(collect_submodules("maxtic_next")
                   + collect_submodules("maxtic_studio")),
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MaxTiC-Next-Studio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,          # 桌面应用：不弹终端
    icon=None,              # 图标改由 Resources + CFBundleIconFile 提供，见上
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="MaxTiC-Next-Studio",
)
app = BUNDLE(
    coll,
    name="MaxTiC-Next-Studio.app",
    bundle_identifier="org.maxtic.next.studio",
    info_plist={
        "CFBundleName": "MaxTiC-Next-Studio",
        "CFBundleDisplayName": "MaxTiC-Next Studio",
        "CFBundleShortVersionString": VERSION,
        "CFBundleVersion": VERSION,
        "NSHighResolutionCapable": True,
        **({"CFBundleIconFile": os.path.splitext(ICON_NAME)[0]} if ICON_NAME else {}),
    },
)
