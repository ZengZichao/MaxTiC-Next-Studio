"""Studio 对话框与 i18n ``_`` 解包守卫。

覆盖的不变量：

* **文件对话框可用**：``path, _ = QFileDialog.get…(self, _("标题"), …)`` 这种写法将 i18n
  函数 ``_`` 当成元组解包目标。Python 把 ``_`` 视为整个函数的局部变量，而实参 ``_(...)``
  在赋值**之前**求值 → 一点击"保存/打开"就 ``UnboundLocalError``。
  本文件同时静态扫描 11 个对话框方法，确保该写法不再出现。
* **对话框在 offscreen 下真的可调用**（覆盖 ``main_window.py``、``input_panel``）。

静态守卫扫的是 Studio 包自己的源码树 ``src/maxtic_studio``。
"""

import os
import re
import sys
from pathlib import Path

import pytest

# --------------------------------------------------------------------------- #
# Studio 只依赖**已安装**的核心包 maxtic_next；本地开发时核心没装，
# 因此这里兜底探测一个已克隆但尚未安装的核心仓库 ``src``（可用 ``MAXTIC_STUDIO_CORE_SRC``
# 显式覆盖）。核心真的 pip 安装时探测为空操作，不影响任何行为。
# --------------------------------------------------------------------------- #
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


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


_add_to_path(SRC)
CORE_SRC = _core_src()
_add_to_path(CORE_SRC)


STUDIO_PKG = SRC / "maxtic_studio"

# Qt 相关的用例需要 offscreen（必须在任何 Qt import 之前设置）
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    import PySide6.QtWidgets  # noqa: F401

    _HAS_QT = True
except ImportError:  # pragma: no cover - 取决于装了哪些 extras
    _HAS_QT = False

requires_qt = pytest.mark.skipif(
    not _HAS_QT,
    reason='PySide6 未安装（pip install -e ".[dev]" 或 pip install PySide6 matplotlib）',
)


def _gui_files():
    return sorted(STUDIO_PKG.rglob("*.py"))


# --------------------------------------------------------------------------- #
# 静态守卫 —— 绝不允许再把 i18n 的 `_` 用作 QFileDialog 的解包目标
# --------------------------------------------------------------------------- #
_SHOULD_NOT_APPEAR = re.compile(r"\b\w+\s*,\s*_\s*=\s*QFileDialog")


@pytest.mark.parametrize("path", _gui_files(), ids=lambda p: p.name)
def test_gui_never_shadows_gettext_underscore(path) -> None:
    """修前 11 处 ``path, _ = QFileDialog.get…(self, _("标题"), …)`` 点击即崩溃。

    Python 把 ``_`` 当作整个函数的局部变量，而实参 ``_(...)`` 在赋值之前求值
    → ``UnboundLocalError``。这里用最小的静态守卫挡住回归，真正的行为验证见下面
    三个 offscreen 用例（改前它们全部直接崩溃）。
    """
    text = path.read_text(encoding="utf-8")
    hits = [i + 1 for i, line in enumerate(text.splitlines()) if _SHOULD_NOT_APPEAR.search(line)]
    assert not hits, f"{path.name}:{hits} 又把 `_` 用作了解包目标"


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication(sys.argv)


# --------------------------------------------------------------------------- #
# / 对话框在 offscreen 下真的能点开
# --------------------------------------------------------------------------- #
@requires_qt
def test_save_config_dialog_cancels_cleanly(qapp, monkeypatch, tmp_path) -> None:
    """修前：`_("dialog_save_config_title")` 在解包目标 `_` 的同一作用域里求值 → 崩溃。"""
    from PySide6.QtWidgets import QFileDialog
    from maxtic_studio.main_window import MainWindow

    win = MainWindow()
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: ("", "")))
    win._save_config()  # 取消路径：静默返回
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: (str(tmp_path / "cfg.json"), "")),
    )
    win._save_config()  # 确认路径：真的写出配置
    assert (tmp_path / "cfg.json").is_file()


@requires_qt
def test_input_panel_browse_tree_cancels_cleanly(qapp, monkeypatch) -> None:
    from PySide6.QtWidgets import QFileDialog
    from maxtic_studio.main_window import MainWindow

    win = MainWindow()
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: ("", "")))
    win.input_panel._browse_tree()


@requires_qt
def test_result_panel_exports_cancel_cleanly(qapp, monkeypatch) -> None:
    from PySide6.QtWidgets import QFileDialog
    from maxtic_studio.main_window import MainWindow

    win = MainWindow()
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: ("", "")))
    win.result_panel._export_csv()
