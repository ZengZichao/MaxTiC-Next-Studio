"""应用图标：定位 SVG 母版并构造 ``QIcon``。

SVG 是唯一母版（``maxtic_studio/assets/maxtic-studio.svg``）：
运行时窗口/Dock 图标由 Qt 直接渲染它，macOS 打包用的 ``.icns``
也由 ``packaging/make_app_icon.py`` 从同一个文件生成，不会两处各画一遍。

查找顺序覆盖三种运行形态：源码运行 / 已安装的 wheel / PyInstaller 冻结的 .app。
"""

from __future__ import annotations

import os
import sys
from typing import Optional

ASSET_NAME = os.path.join("assets", "maxtic-studio.svg")


def icon_path() -> Optional[str]:
    """返回 SVG 母版路径；找不到时返回 ``None``（图标缺失不该让程序起不来）。"""
    candidates = []
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        # PyInstaller 6.x 的 macOS bundle：_MEIPASS 指向 Contents/Frameworks，
        # datas 落在 Contents/Resources（与 main_window 里示例数据的处理保持一致）
        candidates += [
            os.path.join(getattr(sys, "_MEIPASS", ""), ASSET_NAME),
            os.path.join(exe_dir, os.pardir, "Resources", ASSET_NAME),
            os.path.join(exe_dir, ASSET_NAME),
        ]
    pkg_dir = os.path.dirname(os.path.abspath(__file__))
    candidates += [
        os.path.join(pkg_dir, ASSET_NAME),  # 安装态 / 源码态
        os.path.join(os.path.dirname(os.path.dirname(pkg_dir)), ASSET_NAME),
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            return os.path.normpath(path)
    return None


def window_icon():
    """构造窗口图标；QtSvg 不可用或资源缺失时返回 ``None``。"""
    path = icon_path()
    if not path:
        return None
    try:
        from PySide6.QtGui import QIcon

        icon = QIcon(path)
        return None if icon.isNull() else icon
    except Exception:
        return None
