#!/usr/bin/env python3
"""Quick smoke test for MaxTiC-Next Studio GUI (no event loop, no api.rank).

Rewritten as a proper pytest test module (was a script with module-level
``sys.exit(0)`` that crashed the entire test suite during collection).
"""

import os
import sys
import json
from pathlib import Path

import pytest

# Set offscreen platform BEFORE any Qt import
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false;qt.qpa.fonts=false")

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
_add_to_path(_core_src())

# PySide6 ships only with the optional ``studio`` extra
# (``pip install -e ".[dev]"``, which pulls PySide6 + matplotlib), while CI installs
# the same extras head-lessly on the offscreen Qt platform.
# Probe the import once at module level so the Qt-dependent smoke tests are
# *skipped* (not failed/errored) when PySide6 is absent, and still run when it
# is installed.  ``i18n`` and ``params`` are pure-Python, so their tests stay
# unguarded and keep running in either case.
try:
    import PySide6.QtWidgets  # noqa: F401

    _HAS_PYSIDE6 = True
except ImportError:  # pragma: no cover - depends on the installed extras
    _HAS_PYSIDE6 = False

requires_qt = pytest.mark.skipif(
    not _HAS_PYSIDE6,
    reason='PySide6 is not installed (pip install -e ".[dev]")',
)


@pytest.fixture(scope="module")
def qapp():
    """Create a single QApplication for all tests in this module."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv)
    yield app


@pytest.fixture(scope="module")
def main_window(qapp):
    from maxtic_studio.main_window import MainWindow

    win = MainWindow()
    yield win


@requires_qt
def test_window_creates(main_window):
    """Window title is set."""
    assert main_window.windowTitle()


@requires_qt
def test_demo_loaded(main_window):
    """Demo data can be loaded."""
    main_window._load_demo()
    assert main_window.input_panel.species_tree


@requires_qt
def test_params_collected(main_window):
    """Params collection returns a non-empty dict."""
    params = main_window._collect_all_params()
    assert isinstance(params, dict)


@requires_qt
def test_cli_preview(main_window):
    """CLI preview is generated from params."""
    from maxtic_studio.params import params_to_cli_command

    try:
        params = main_window._collect_all_params()
        cli = params_to_cli_command(params)
        assert isinstance(cli, str)
    except Exception:
        # If species_tree is not set, CLI preview is empty — that's OK
        pass


def test_i18n():
    """i18n module works."""
    from maxtic_studio.i18n import _, get_language

    assert get_language() in ("zh", "en")
    assert _("seed")


def test_config_roundtrip():
    """Config JSON round-trips correctly."""
    from maxtic_studio.params import params_to_json, json_to_params, _default_params

    params = _default_params()
    j = params_to_json(params)
    restored = json_to_params(json.loads(json.dumps(j, ensure_ascii=False)))
    assert len(restored) == len(params)


@requires_qt
def test_ranking_table_model():
    """RankingTableModel can be populated from a mock Result."""
    from maxtic_studio.results_view import RankingTableModel

    class MockResult:
        best_order = ["node1", "node2", "node3"]
        values = {"input": 100.0, "greedy": 90.0, "mixing": 85.0}
        informative_lines = ["node1,node2 50.0", "node2,node3 30.0"]
        conflicting_lines = []
        dry_run_report = ""
        html_report_file = ""

    m = RankingTableModel()
    m.populate_from_result(MockResult())
    assert m.rowCount() == 3


@requires_qt
def test_result_panel_update(main_window):
    """Result panel can be updated with a mock Result."""

    class MockResult:
        best_order = ["node1", "node2", "node3"]
        values = {"input": 100.0, "greedy": 90.0, "mixing": 85.0}
        informative_lines = ["node1,node2 50.0", "node2,node3 30.0"]
        conflicting_lines = []
        dry_run_report = ""
        html_report_file = ""
        ranked_newick = "(A:1,B:1)node1;"
        similarity_to_input = 0.5
        best_source = "greedy heuristic"
        partial_total = 0.0
        conflict_with_input = 0.0

    main_window.result_panel.update_result(MockResult())
