"""Studio 的逐节点目标值量（``maxtic_studio/node_scores.py``）。

覆盖 ``node_scores.py``：逐节点"移到序首 / 序尾的目标值变化量"，
纯 Python（**无需 PySide6**）；只作为受体出现的节点不得被标成 0.0 信息性。

目标值仍由核心 ``maxtic_next.ranking.value`` 全量计算，故本模块需要核心
仓库的 ``src`` 在 ``sys.path`` 上（见下方探测）。
"""

import os
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


from maxtic_studio import node_scores as ns  # noqa: E402


# =========================================================================
# ：GUI 逐节点量（无 PySide6 依赖）
# =========================================================================
class _FakeResult:
    def __init__(self, best_order, informative_lines):
        self.best_order = best_order
        self.informative_lines = informative_lines


def test_node_objective_impacts_are_defensible():
    # 交付序 [a, b, c]，约束 a→b（1.0）与 a→c（2.0）：a 在最前正是最优
    lines = ["a,b 1.0", "a,c 2.0"]
    imp = ns.node_objective_impacts(["a", "b", "c"], informative_lines=lines)
    assert imp["a"].delta_front == 0.0 and imp["a"].delta_back == -3.0 * 0 + 3.0
    assert imp["a"].amplitude == 3.0
    # c 已在末端：移到序尾不变；移到序首会违反 a→c（+2.0）与 a→b? 不违反
    assert imp["c"].delta_back == 0.0
    assert imp["c"].delta_front == pytest.approx(2.0)
    # 每个节点的 informative 判定基于"是否参与任一信息性约束"（供体或受体）
    assert imp["b"].informative and imp["c"].informative
    assert imp["b"].donor_weight == 0.0 and imp["b"].receptor_weight == 1.0


def test_receptor_only_node_is_not_shown_as_zero_informative():
    # 节点 r 只作为受体出现：旧口径给它 0.0 却标 informative=True（自相矛盾）
    lines = ["d,r 4.0"]
    imp = ns.node_objective_impacts(["d", "r", "x"], informative_lines=lines)
    r = imp["r"]
    assert r.informative is True
    assert r.donor_weight == 0.0 and r.receptor_weight == 4.0
    # 新口径给出的是**目标函数变化量**，非零且可解释
    assert r.delta_front == pytest.approx(4.0)
    assert r.amplitude > 0.0
    assert "不是 MTC 分数" in r.tooltip()


def test_impacts_match_direct_value_recomputation():
    from maxtic_next.ranking.value import value as _value

    lines = ["1,2 1.5", "2,3 0.5", "1,3 2.0"]
    order = ["1", "2", "3"]
    edge, keys = ns.parse_informative_edges(lines)
    base = _value(order, edge, keys)
    imp = ns.node_objective_impacts(order, informative_lines=lines)
    for node in order:
        moved = [node] + [x for x in order if x != node]
        assert imp[node].delta_front == pytest.approx(_value(moved, edge, keys) - base)
