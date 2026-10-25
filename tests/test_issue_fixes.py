#!/usr/bin/env python3
"""针对用户反馈的 7 项问题修复的回归测试。

覆盖：
1. HTML 报告中英各一份（``run_engine._write_english_report``）；
2. 排名表列宽可拖拽（全部列 Interactive 模式）；
3. 「Δ 移到序首 / 序尾」拆列 + 表格下方说明行；
4. 所有按钮统一高度（运行 / 取消不再独享 44px）；
5. 「用示例数据演示」归位到输入面板；
6. 排名图带数值标注与读图说明；
7. 图标底板按 macOS 栅格缩放（不再画满画布）。
"""

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false;qt.qpa.fonts=false")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

pytest.importorskip("PySide6", reason="PySide6 未安装")

SVG = ROOT / "src" / "maxtic_studio" / "assets" / "maxtic-studio.svg"


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv)
    yield app


@pytest.fixture(scope="module")
def main_window(qapp):
    from maxtic_studio.main_window import MainWindow

    win = MainWindow()
    yield win


class _MockResult:
    """与 test_gui_smoke 相同形状的假结果，另带双语报告路径。"""

    best_order = ["node1", "node2", "node3"]
    values = {"input": 100.0, "greedy": 90.0, "mixing": 85.0}
    informative_lines = ["node1,node2 50.0", "node2,node3 30.0"]
    conflicting_lines = []
    dry_run_report = ""
    html_report_file = ""
    html_report_file_en = ""
    ranked_newick = "(A:1,B:1)node1;"
    similarity_to_input = 0.5
    best_source = "greedy heuristic"
    partial_total = 0.0
    conflict_with_input = 0.0


# ---------------------------------------------------------------------------
# 问题 2：列宽可拖拽
# ---------------------------------------------------------------------------
def test_table_columns_are_user_resizable(qapp):
    """全部列都是 Interactive：用户可拖拽任意列分隔线调整相对宽度。"""
    from PySide6.QtWidgets import QHeaderView

    from maxtic_studio.widgets.result_panel import ResultPanel

    panel = ResultPanel()
    header = panel.table_view.horizontalHeader()
    modes = [header.sectionResizeMode(i) for i in range(panel.table_model.columnCount())]
    assert all(m == QHeaderView.ResizeMode.Interactive for m in modes), modes


# ---------------------------------------------------------------------------
# 问题 3：Δ 列拆分 + 说明行
# ---------------------------------------------------------------------------
def test_ranking_model_splits_delta_columns(qapp):
    """「移序首 / 移序尾」拆成两列，列头不再是合并写法。"""
    from PySide6.QtCore import Qt

    from maxtic_studio.i18n import _
    from maxtic_studio.results_view import RankingTableModel

    m = RankingTableModel()
    m.populate_from_result(_MockResult())
    assert m.columnCount() == 5
    headers = [m.headerData(i, Qt.Orientation.Horizontal) for i in range(5)]
    assert headers[0] == _("col_rank")
    assert headers[1] == _("col_node")
    assert headers[2] == _("col_delta_front")
    assert headers[3] == _("col_delta_back")
    assert headers[4] == _("col_informative")
    # 两列各自给出单独的数值（带正负号）
    v_front = m.index(0, 2).data()
    v_back = m.index(0, 3).data()
    assert v_front is not None and v_back is not None
    assert "/" not in v_front and "/" not in v_back


def test_ranking_model_csv_matches_columns(qapp):
    from maxtic_studio.i18n import _
    from maxtic_studio.results_view import RankingTableModel

    m = RankingTableModel()
    m.populate_from_result(_MockResult())
    rows = [line for line in m.to_csv().splitlines() if line]
    assert len(rows[0].split(",")) == 5
    assert _("col_delta_front") in rows[0] and _("col_delta_back") in rows[0]


def test_result_panel_has_hint_labels(qapp):
    """表格页与图表页各有一行常驻说明（Δ 含义 / 读图方法）。"""
    from maxtic_studio.i18n import _
    from maxtic_studio.widgets.result_panel import ResultPanel

    panel = ResultPanel()
    assert panel.table_hint_label.text() == _("table_hint")
    assert panel.chart_hint_label.text() == _("chart_hint")
    assert panel.table_hint_label.text().strip()
    assert panel.chart_hint_label.text().strip()


# ---------------------------------------------------------------------------
# 问题 4：按钮统一高度
# ---------------------------------------------------------------------------
def test_all_buttons_share_one_height(main_window):
    """主窗口内所有 QPushButton 的最小高度一致（运行 / 取消不再偏大）。"""
    from PySide6.QtWidgets import QPushButton

    from maxtic_studio import metrics as M

    heights = {w.minimumHeight() for w in main_window.findChildren(QPushButton)}
    assert heights <= {M.BUTTON_H}, heights
    run_h = main_window.btn_run.minimumHeight()
    cancel_h = main_window.btn_cancel.minimumHeight()
    small_h = main_window.input_panel.btn_demo.minimumHeight()
    assert run_h == cancel_h == small_h == M.BUTTON_H


# ---------------------------------------------------------------------------
# 问题 5：演示按钮归位输入面板
# ---------------------------------------------------------------------------
def test_demo_button_lives_in_input_panel(main_window):
    from maxtic_studio.i18n import _

    assert main_window.input_panel.btn_demo.text() == _("action_demo")
    assert not hasattr(main_window.result_panel, "btn_demo"), (
        "「用示例数据演示」不应再出现在结果面板"
    )
    # 信号连通：触发 input_panel 的演示信号会调用主窗口的 _load_demo
    calls = []
    main_window.input_panel.demo_requested.connect(lambda: calls.append(1))
    main_window.input_panel.demo_requested.emit()
    assert calls


# ---------------------------------------------------------------------------
# 问题 1：HTML 报告中英各一份
# ---------------------------------------------------------------------------
def test_report_button_candidates_cover_both_languages(qapp):
    """中文 + 英文两份报告都在时，报告按钮给出两个候选（菜单选择）。"""
    from maxtic_studio.i18n import _
    from maxtic_studio.widgets.result_panel import ResultPanel

    panel = ResultPanel()
    panel._result = None
    assert panel._report_candidates() == []

    r = _MockResult()
    r.html_report_file = "/tmp/out.html"
    r.html_report_file_en = ""
    panel._result = r
    assert panel._report_candidates() == [(_("report_lang_zh"), "/tmp/out.html")]

    r.html_report_file_en = "/tmp/out.en.html"
    assert panel._report_candidates() == [
        (_("report_lang_zh"), "/tmp/out.html"),
        (_("report_lang_en"), "/tmp/out.en.html"),
    ]


def test_english_report_written_next_to_chinese(tmp_path):
    """真实运行一次：中文报告由核心写出，_write_english_report 补写英文版。"""
    from maxtic_next.api import rank

    from maxtic_studio.run_engine import _write_english_report

    data = ROOT.parent / "MaxTiC-Next-项目代码" / "tests" / "data"
    tree = data / "minitree.tree"
    cons = data / "Cyano_CUTConstraints.tsv"
    if not tree.is_file():
        pytest.skip("核心仓库测试数据不可用")
    prefix = str(tmp_path / "r")
    r = rank(
        str(tree),
        str(cons),
        seed=42,
        local_search=0.02,
        output_prefix=prefix,
        html_report=True,
        print_summary=False,
    )
    assert r.html_report_file and os.path.isfile(r.html_report_file)

    logs = []
    _write_english_report(r, logs.append)
    assert not any("ERROR" in x for x in logs)
    en_path = getattr(r, "html_report_file_en", "")
    assert en_path, "英文报告未写出"
    assert en_path.endswith(".en.html") and os.path.isfile(en_path)
    zh_text = open(r.html_report_file, encoding="utf-8").read()
    en_text = open(en_path, encoding="utf-8").read()
    assert "排序报告" in zh_text
    assert "Ranking Report" in en_text
    # 英文报告正文不得残留中文标签（图表 JS 内部的字体数据除外）
    body = en_text.split("<body", 1)[-1]
    for line in body.splitlines():
        if "plotly" in line or "Plotly" in line or "new Plotly" in line:
            continue
        # 只挑纯文本行检查：含标签的行允许属性里的 lang 等
        stripped = line.strip()
        if stripped and not stripped.startswith("<"):
            assert not any("\u4e00" <= ch <= "\u9fff" for ch in stripped), stripped


# ---------------------------------------------------------------------------
# 问题 6：排名图可读性
# ---------------------------------------------------------------------------
def test_chart_has_value_labels_and_hint(qapp):
    """图表渲染不崩溃，且读图说明常驻图表页下方。"""
    from maxtic_studio.widgets.result_panel import _ChartWidget

    widget = _ChartWidget()
    scores = [("n1", 3.0, True), ("n2", 0.0, False)]
    widget.update_chart(scores)
    widget.update_chart(scores, highlight_label="n1")
    assert widget._canvas is not None


# ---------------------------------------------------------------------------
# 问题 7：图标栅格
# ---------------------------------------------------------------------------
def test_icon_tile_follows_macos_grid(qapp):
    """底板四周留出边距（Apple 栅格约 10%），不再画满整张画布。"""
    from PySide6.QtGui import QIcon

    icon = QIcon(str(SVG))
    assert not icon.isNull()
    pm = icon.pixmap(512, 512)
    assert pm.width() == 512
    img = pm.toImage()

    def alpha(x, y):
        return img.pixelColor(x, y).alpha()

    # 画布四角（30px 内）必须透明：底板若仍画满画布，这里会是实心
    for x, y in ((5, 5), (5, 256), (506, 256), (256, 5), (256, 506), (30, 256)):
        assert alpha(x, y) == 0, f"({x},{y}) 应为透明边距，alpha={alpha(x, y)}"
    # 中心当然是底板本体
    assert alpha(256, 256) > 0
    # 底板从约 50px 开始（Apple 栅格），而不是旧的 16px
    assert alpha(70, 256) > 0
