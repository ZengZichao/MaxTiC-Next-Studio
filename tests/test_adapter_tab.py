#!/usr/bin/env python3
"""上游适配器单页化 + 按工具动态显隐参数的回归测试。

背景：原来 ALE 独占一页、其余 4 个工具挤在「多工具」页的下拉里，
看上去像"只支持 ALE"。现在合成一页，参数按所选工具显隐。

显隐矩阵不是拍脑袋：它按核心层各 ``convert_from_*`` 的真实签名推导
（``registry._public_kwargs`` 会把适配器不吃的参数丢掉），
所以界面也不该展示"能填但没作用"的字段。
"""

import os
import re
import sys
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

from PySide6.QtWidgets import QApplication, QTabBar, QWidget  # noqa: E402

from maxtic_studio.params import collect_params, params_to_cli_command  # noqa: E402
from maxtic_studio.widgets.advanced_panel import AdvancedPanel  # noqa: E402

TREE = str(ROOT / "tests" / "data" / "minitree.tree")
CONS = str(ROOT / "tests" / "data" / "Cyano_CUTConstraints.tsv")

_COMMON = {"min_support", "min_family", "cache", "parallel", "quiet"}

# 工具 → 应当可见的参数键（与 AdvancedPanel._ADAPTER_FIELDS 一致，
# 这里独立重述一遍：两处都写错成同一个样子的概率远低于一处写错）
EXPECTED = {
    "none": set(),
    "auto": _COMMON | {"hit_rate", "transfer_kind"},
    "ale": _COMMON | {"source"},
    "ranger": _COMMON | {"hit_rate"},
    "eccetera": _COMMON | {"hit_rate"},
    "artra": _COMMON | {"hit_rate", "transfer_kind"},
    "alerax": _COMMON | {"hit_rate"},
}


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication(sys.argv)


@pytest.fixture()
def panel(qapp):
    p = AdvancedPanel()
    p.resize(560, 620)
    p.show()
    qapp.processEvents()
    yield p
    p.close()


def _visible_fields(p):
    return {key for key, widgets in p._adapter_rows.items() if all(w.isVisible() for w in widgets)}


@pytest.mark.parametrize("tool", sorted(EXPECTED))
def test_only_the_selected_tools_fields_show_up(panel, tool):
    panel._select_adapter_tool(tool)
    panel._apply_adapter_visibility()
    assert _visible_fields(panel) == EXPECTED[tool], f"工具 {tool} 的参数显隐不符"


def test_five_adapters_share_one_page(panel):
    """5 个适配器 + 无 + 自动检测 全在一页的同一个下拉里。"""
    values = [panel.adapter_tool_combo.itemData(i) for i in range(panel.adapter_tool_combo.count())]
    assert values == ["none", "auto", "ale", "ranger", "eccetera", "artra", "alerax"]
    # 原来的两页（ALE 适配器 / 多工具）已合并为一页
    assert panel.tabs.count() == 6
    assert panel.tabs.tabText(0) == "上游适配器"


def test_hint_explains_the_selected_tool(panel):
    panel._select_adapter_tool("ale")
    assert "端点命中率" in panel.adapter_hint.text()
    panel._select_adapter_tool("none")
    assert "原生 TSV" in panel.adapter_hint.text()


def test_ale_hides_hit_rate_but_artra_shows_it(panel):
    """convert_from_ale 的签名里没有 min_endpoint_hit_rate，界面就不该给。"""
    panel._select_adapter_tool("ale")
    assert not panel.adapter_hit_spin.isVisible()
    panel._select_adapter_tool("artra")
    assert panel.adapter_hit_spin.isVisible()
    assert panel.artra_kind_combo.isVisible()
    panel._select_adapter_tool("eccetera")
    assert not panel.artra_kind_combo.isVisible()


# --------------------------------------------------------------------------- #
# CLI 命令生成
# --------------------------------------------------------------------------- #
def _params(**kw):
    """collect_params 只覆盖用到的项，其余走默认值。"""
    base = dict(species_tree=TREE, constraints=[CONS])
    base.update(kw)
    return collect_params(**base)


def test_adapter_tuning_is_dropped_when_no_adapter_is_active():
    """没选适配器时，--ale-* 没有消费方，不该出现在"可复现命令"里。"""
    cmd = params_to_cli_command(
        _params(
            ale_min_support=0.3, ale_min_family_size=9, ale_parallel="thread", adapter_quiet=True
        )
    )
    assert "--from" not in cmd and "--from-ale" not in cmd
    for flag in (
        "--ale-min-support",
        "--ale-min-family-size",
        "--ale-parallel",
        "--quiet-adapters",
    ):
        assert flag not in cmd, f"{flag} 在无适配器时仍被输出"


def test_adapter_tuning_survives_when_an_adapter_is_active():
    cmd = params_to_cli_command(
        _params(from_tool="ranger", ale_min_support=0.3, adapter_min_endpoint_hit_rate=0.8)
    )
    assert "--from ranger" in cmd
    assert "--ale-min-support 0.3" in cmd
    assert "--min-endpoint-hit-rate 0.8" in cmd


def test_from_and_from_ale_never_both_appear():
    """--from 优先；兼容路径只在没有 --from 时出现，二者不同时出现。"""
    both = params_to_cli_command(_params(from_tool="ale", from_ale=True))
    assert "--from ale" in both and "--from-ale" not in both
    legacy = params_to_cli_command(_params(from_ale=True))
    assert "--from-ale" in legacy and "--from " not in legacy


def test_hidden_field_value_never_leaks_into_the_command():
    """字段因不适用于当前工具而隐藏后，它的值也不该被写进命令。

    ``--min-endpoint-hit-rate`` 这类旗标在 ALE 下不被核心层读取：若无条件输出，
    预览里就会出现一条 ALE 根本不读的旗标，"可复现命令"因此名不副实。
    """
    ale = params_to_cli_command(
        _params(from_tool="ale", adapter_min_endpoint_hit_rate=0.9, artra_transfer_kind="additive")
    )
    assert "--min-endpoint-hit-rate" not in ale
    assert "--artra-transfer-kind" not in ale
    assert "--ale-min-support" not in ale  # 默认值本就不输出
    artra = params_to_cli_command(
        _params(
            from_tool="artra", adapter_min_endpoint_hit_rate=0.9, artra_transfer_kind="additive"
        )
    )
    assert "--min-endpoint-hit-rate 0.9" in artra
    assert "--artra-transfer-kind additive" in artra


def test_ui_visibility_and_cli_emission_share_one_matrix():
    """界面显隐与命令输出必须来自同一份 ADAPTER_FIELDS。"""
    from maxtic_studio.params import ADAPTER_FIELDS
    from maxtic_studio.widgets.advanced_panel import AdvancedPanel as AP

    assert not hasattr(AP, "_ADAPTER_FIELDS"), "面板又私自复制了一份矩阵"
    assert set(ADAPTER_FIELDS) == set(EXPECTED) - {"none"}
    for tool, fields in ADAPTER_FIELDS.items():
        assert set(fields) == EXPECTED[tool], f"{tool} 的矩阵与预期不符"


def test_artra_kind_only_emitted_for_artra():
    cmd = params_to_cli_command(_params(from_tool="artra", artra_transfer_kind="additive"))
    assert "--artra-transfer-kind additive" in cmd
    other = params_to_cli_command(_params(from_tool="ranger", artra_transfer_kind="additive"))
    assert "--artra-transfer-kind" not in other


# --------------------------------------------------------------------------- #
# 配置往返
# --------------------------------------------------------------------------- #
def test_legacy_from_ale_config_maps_to_the_selector(panel):
    """旧 JSON 里只有 from_ale=true：应还原成选中 ALE。"""
    panel.set_values({"from_ale": True})
    assert panel._adapter_tool() == "ale"
    assert panel.from_tool_val == "ale"
    assert panel.from_ale is False


def test_tool_round_trips_through_the_selector(panel):
    for tool in ("auto", "ale", "ranger", "eccetera", "artra", "alerax"):
        panel.set_values(
            {
                "from_tool": tool,
                "artra_transfer_kind": "replacing",
                "adapter_min_endpoint_hit_rate": 0.42,
                "adapter_quiet": True,
            }
        )
        assert panel.from_tool_val == tool
        assert panel.artra_transfer_kind_val == "replacing"
        assert panel.adapter_min_endpoint_hit_rate_val == pytest.approx(0.42)
        assert panel.adapter_quiet_val is True
    panel.set_values({"from_tool": None})
    assert panel.from_tool_val is None


def test_language_switch_relabels_without_losing_the_selection(panel, qapp):
    from maxtic_studio.i18n import set_language

    panel._select_adapter_tool("artra")
    set_language("en")
    panel.retranslate()
    qapp.processEvents()
    try:
        assert panel._adapter_tool() == "artra"
        assert panel.tabs.tabText(0) == "Upstream Adapters"
        assert _visible_fields(panel) == EXPECTED["artra"]
    finally:
        set_language("zh")
        panel.retranslate()


# --------------------------------------------------------------------------- #
# 翻译表覆盖：漏键会把内部 key 直接印到界面上
# --------------------------------------------------------------------------- #
_KEY_LIKE = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)+$")


@pytest.mark.parametrize("lang", ["zh", "en"])
def test_no_untranslated_key_leaks_into_the_ui(qapp, lang):
    from maxtic_studio.i18n import set_language
    from maxtic_studio.main_window import MainWindow

    set_language(lang)
    win = MainWindow()
    win.left_tabs.setCurrentIndex(1)
    win.show()
    qapp.processEvents()
    try:
        texts = []
        for w in win.findChildren(QWidget) + [win]:
            if isinstance(w, (QTabBar,)):
                texts += [w.tabText(i) for i in range(w.count())]
            if not w.isVisible():
                continue
            getter = getattr(w, "text", None)
            if callable(getter):
                texts.append(getter())
        for act in win.menuBar().actions():
            texts.append(act.text())
        leaked = sorted({t for t in texts if t and _KEY_LIKE.match(t.strip())})
        assert not leaked, f"{lang} 界面上出现了未翻译的内部 key：{leaked}"
    finally:
        win.close()
        set_language("zh")
