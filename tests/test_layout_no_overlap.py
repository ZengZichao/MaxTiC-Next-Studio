#!/usr/bin/env python3
"""布局回归测试：界面元素不得互相挤压 / 重叠 / 被裁字。

回归背景：``release/MaxTiC-Next-Studio.app`` 的截图里，「核心参数」的标签压在
数值框上、物种树输入框与「浏览…」按钮被裁掉一半。根因是两件事：

1. QSS 的 ``font-size`` / ``min-height`` 只改绘制、不进 ``sizeHint``，
   控件画得比布局预留的高 → 相邻行重叠；
2. 面板内容高于视口时，Qt 会把每个控件保持在自己的最小尺寸上、
   却按更小的行距摆放 → 直接互相压字。

修法见 ``metrics.py``（字号/高度在代码里落地）与 ``main_window._scroll_area``
（两栏各包一层滚动区）。本文件把"不许重叠"变成可执行的断言。
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false;qt.qpa.fonts=false")

ROOT = Path(__file__).resolve().parents[1]


def _add_to_path(path):
    path = str(path)
    if path and os.path.isdir(path) and path not in sys.path:
        sys.path.insert(0, path)


def _core_src():
    override = os.environ.get("MAXTIC_STUDIO_CORE_SRC")
    if override:
        return override
    for sibling in sorted(ROOT.parent.iterdir()):
        if (sibling / "src" / "maxtic_next" / "__init__.py").is_file():
            return str(sibling / "src")
    return ""


_add_to_path(ROOT / "src")
_add_to_path(_core_src())

pytest.importorskip("PySide6", reason="PySide6 未安装")

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QWidget  # noqa: E402

# 把 QSettings 指到临时目录：本文件会反复改写语言/主题偏好，
# 不能污染用户真实的 ~/Library/Preferences/MaxTiC/MaxTiC-Next-Studio.ini
_SETTINGS_DIR = tempfile.mkdtemp(prefix="maxtic-studio-settings-")
QSettings.setDefaultFormat(QSettings.Format.IniFormat)
QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, _SETTINGS_DIR)

_TOLERANCE = 2  # 允许的像素级误差（分割条、1px 边框）


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def _make_window(app, lang, dark, size):
    from maxtic_studio.i18n import set_language
    from maxtic_studio.theme import apply_theme
    from maxtic_studio.main_window import MainWindow

    settings = QSettings("MaxTiC", "MaxTiC-Next-Studio")
    settings.setValue("language", lang)
    settings.setValue("theme_dark", dark)
    settings.remove("geometry")
    settings.remove("windowState")
    settings.sync()
    set_language(lang)
    apply_theme(app, dark)
    app.setProperty("maxTic-dark", dark)

    win = MainWindow()
    win.resize(*size)
    win.show()
    for _ in range(6):
        app.processEvents()
    return win


def _rect(widget, origin):
    top_left = widget.mapTo(origin, widget.rect().topLeft())
    return (
        top_left.x(),
        top_left.y(),
        top_left.x() + widget.width(),
        top_left.y() + widget.height(),
    )


def _overlapping_siblings(win):
    """返回同一父容器下互相压住的可感知控件对（>2px 双向重叠）。"""
    from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QLineEdit, QSpinBox

    checked = (QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPushButton, QLabel)
    bad = []
    for parent in win.findChildren(QWidget):
        kids = [
            k
            for k in parent.children()
            if isinstance(k, checked) and k.isVisible() and k.parentWidget() is parent
        ]
        for i in range(len(kids)):
            for j in range(i + 1, len(kids)):
                a, b = _rect(kids[i], win), _rect(kids[j], win)
                ox = min(a[2], b[2]) - max(a[0], b[0])
                oy = min(a[3], b[3]) - max(a[1], b[1])
                if ox > _TOLERANCE and oy > _TOLERANCE:
                    bad.append((kids[i], kids[j], ox, oy))
    return bad


def _clipped_buttons(win):
    """按钮文字被自身边框裁掉的检测（QSS 字号不进 sizeHint 的典型后果）。"""
    bad = []
    for b in win.findChildren(QPushButton):
        if not b.isVisible() or not b.text():
            continue
        need = b.fontMetrics().horizontalAdvance(b.text())
        if need > b.width() + _TOLERANCE:
            bad.append((b.text(), need, b.width()))
    return bad


# 覆盖：中英 × 亮暗 × 最小/常见/宽屏尺寸。窄而矮的那档正是回归截图的情形。
_CASES = [
    (lang, theme, size)
    for lang in ("zh", "en")
    for theme in (False, True)
    for size in ((960, 620), (1250, 760), (1500, 950))
]


@pytest.mark.parametrize(
    "lang,dark,size",
    _CASES,
    ids=[f"{lang_code}-{'dark' if d else 'light'}-{w}x{h}" for lang_code, d, (w, h) in _CASES],
)
def test_no_element_squeezing(qapp, lang, dark, size):
    win = _make_window(qapp, lang, dark, size)
    try:
        overlaps = _overlapping_siblings(win)
        assert not overlaps, "控件互相压字：\n" + "\n".join(
            f"  {a.__class__.__name__}{a.text()[:16]!r} × "
            f"{b.__class__.__name__}{b.text()[:16]!r} 重叠 {ox}x{oy}px"
            for a, b, ox, oy in overlaps[:12]
        )
        clipped = _clipped_buttons(win)
        assert not clipped, "按钮文字被裁：\n" + "\n".join(
            f"  {t!r} 需要 {need}px，只有 {have}px" for t, need, have in clipped[:12]
        )
    finally:
        win.close()
        win.deleteLater()


def test_language_switch_is_instant_and_relayouts(qapp):
    """切语言必须即时刷新文案，并且重算后仍不重叠。"""
    win = _make_window(qapp, "zh", False, (1250, 760))
    try:
        assert "运行" in win.btn_run.text()
        assert "中文" in win.btn_language.text()
        win._switch_language("en")
        for _ in range(4):
            qapp.processEvents()
        assert win.btn_run.text().lower().startswith("run")
        assert "English" in win.btn_language.text()
        assert not _overlapping_siblings(win)
    finally:
        win.close()
        win.deleteLater()


def test_theme_switch_repaints_and_keeps_layout(qapp):
    """切主题要落到 QApplication 令牌上，且图表/布局跟着更新。"""
    win = _make_window(qapp, "zh", False, (1250, 760))
    try:
        assert "浅色" in win.btn_theme.text()
        assert qapp.property("maxTic-dark") is False
        win._set_dark_theme(True)
        for _ in range(4):
            qapp.processEvents()
        assert qapp.property("maxTic-dark") is True
        assert "深色" in win.btn_theme.text()
        assert not _overlapping_siblings(win)
    finally:
        win._set_dark_theme(False)
        win.close()
        win.deleteLater()


def test_preferences_round_trip(qapp):
    """语言与主题偏好写入 QSettings，重启后保持。"""
    win = _make_window(qapp, "zh", False, (1250, 760))
    try:
        win._switch_language("en")
        win._set_dark_theme(True)
        settings = QSettings("MaxTiC", "MaxTiC-Next-Studio")
        assert settings.value("language") == "en"
        assert bool(settings.value("theme_dark", False, type=bool)) is True
    finally:
        win.close()
        win.deleteLater()
