"""MaxTiC-Next Studio 入口点。

``maxtic-studio`` 控制台脚本指向 ``main:main``。
创建 ``QApplication`` 并显示主窗口。
"""

from __future__ import annotations

import sys
from typing import List, Optional


def main(argv: Optional[List[str]] = None) -> None:
    """启动 MaxTiC-Next Studio 桌面端。"""
    if argv is None:
        argv = sys.argv

    # ：入口点在 pyproject 里无条件注册，未装 GUI 依赖时
    # 直接抛 ModuleNotFoundError 回溯对用户毫无帮助，故先给出安装指引。
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import Qt
    except ImportError:
        sys.stderr.write(
            "MaxTiC-Next Studio 需要 GUI 依赖 PySide6（以及 matplotlib）。\n"
            '安装：pip install "git+https://github.com/ZengZichao/MaxTiC-Next-Studio.git"\n'
            "命令行功能不受影响：请使用核心仓库 MaxTiC-Next 的 maxtic-next。\n"
        )
        raise SystemExit(3) from None

    # 高 DPI 支持（Qt 6 默认启用，此处显式设置确保兼容）
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(argv)
    app.setApplicationName("MaxTiC-Next Studio")
    app.setOrganizationName("MaxTiC")

    # 应用图标（SVG 母版，见 appicon.py）：窗口标题栏与各对话框继承同一份；
    # macOS 下源码运行时它也负责 Dock 图块。
    from maxtic_studio.appicon import window_icon

    _icon = window_icon()
    if _icon is not None:
        app.setWindowIcon(_icon)

    # 应用统一浅/深主题（偏好持久化在 QSettings，默认浅色）
    from PySide6.QtCore import QSettings
    from maxtic_studio.theme import apply_theme

    _settings = QSettings("MaxTiC", "MaxTiC-Next-Studio")
    _dark = bool(_settings.value("theme_dark", False, type=bool))
    apply_theme(app, _dark)
    # 让主窗口可读到当前深浅主题
    app.setProperty("maxTic-dark", _dark)

    from maxtic_studio.main_window import MainWindow

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
