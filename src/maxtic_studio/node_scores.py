"""逐节点"目标值影响"计算——纯 Python，可在无 PySide6 环境下导入与测试。

为什么需要这个模块
------------------------------------------------------------------------------
旧 ``gui/results_view.py`` 把"该节点作为 donor 出现的信息性约束权重之和"当作
``mtc_score`` 与排名并排展示（代码自己承认"作为 MTC 分数近似"）。但 MaxTiC 的目标函数
是**整个排序被违反的约束权重之和**（``ranking/value.py`` 的 ``value()``），
不存在"逐节点 MTC 分数"这一量：donor 出度权重只描述**输入约束集**，与排序结果几乎无关，
而且只作为 receptor 出现的节点会拿到 0.0 却被标成 informative（口径自相矛盾）。

本模块改为交付一个**可辩护**的逐节点量：在**已交付的排序**上，把某个节点分别移到

* 序首（最古老端）与
* 序尾（最年轻端）

时，目标函数（被违反的信息性约束权重和）的**变化量**::

    delta_front(x) = value(order_with_x_at_front) - value(order)
    delta_back(x)  = value(order_with_x_at_back)  - value(order)

负值 = "把该节点放到那一端会更一致（目标更小）"，正值 = "当前位置已比该端更一致"，
0 = 该节点与其余节点之间没有方向性约束信息。两者之和/差给出该节点的**位置敏感性幅度**
``amplitude = max(delta_front, delta_back) - min(delta_front, delta_back)``，
适合画条形图。

实现说明：目标值直接用 ``maxtic_next.ranking.value.value`` 全量计算（``n`` 个节点 ⇒
``2n`` 次调用，代价 ``O(n·|E|)``，对排序规模完全可接受）。**没有**改用
``IncrementalValueComputer``：它的移动语义是"把位置 ``a`` 的元素区间旋转到 ``b``
（要求 ``a < b``，其余元素左移）"，无法表达"移到序首"这类跨越性移动，因此直接调用
``value()`` 才是与核心目标函数零漂移的做法（其 ``full_recompute`` 也走同一函数）。

能量口径：只使用**信息性约束**（``Result.informative_lines``，即已剔除树种系哨兵边与
零权重边的集合）。这些正是"排序可以影响其是否被违反"的约束，也是 ``conflicts.tsv``
的来源，故 delta 完全落在目标函数的可变部分内。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


@dataclass
class NodeObjectiveImpact:
    """一个节点的目标值影响。"""

    node: str
    delta_front: float = 0.0
    delta_back: float = 0.0
    donor_weight: float = 0.0
    receptor_weight: float = 0.0
    n_constraints: int = 0
    #: 交付序中该节点的位置（0 = 序首）
    position: int = 0
    #: 是否出现在**任一**信息性约束里（donor 或 receptor 端点均算，修正旧口径）
    informative: bool = False
    #: 排序规模不足以移动（节点数 < 3 时移到序首/序尾是同一操作或空操作）
    degenerate: bool = False

    @property
    def amplitude(self) -> float:
        """位置敏感性幅度 = 两个方向变化量的极差（非负，供条形图使用）。"""
        return max(self.delta_front, self.delta_back) - min(self.delta_front, self.delta_back)

    @property
    def best_move_gain(self) -> float:
        """把该节点移到序首或序尾所能获得的**最大**目标值改进（>= 0 才有改进）。"""
        return -min(self.delta_front, self.delta_back)

    def tooltip(self) -> str:
        """表格 tooltip / 说明文本（明确它**不是** MTC 分数）。"""
        return (
            f"节点 {self.node}（交付序第 {self.position + 1} 位）\n"
            "目标值影响（不是 MTC 分数，MaxTiC 未定义逐节点分数）：\n"
            f"  移到序首：{self.delta_front:+g}\n"
            f"  移到序尾：{self.delta_back:+g}\n"
            "（数值 = 把该节点移到该端后，被违反的信息性约束权重和的变化；"
            "负值表示更一致。）\n"
            f"信息性约束：作为供体 {self.donor_weight:g}、"
            f"作为受体 {self.receptor_weight:g}，共 {self.n_constraints} 条"
            + ("\n（节点数 < 3：移到序首与序尾为同一操作）" if self.degenerate else "")
        )


def parse_informative_edges(lines: Optional[Iterable[str]]) -> Tuple[Dict[str, float], List[str]]:
    """解析 ``"donor,receptor weight"`` 行为 ``(edge, edge_keys)``（保序、按键去重）。"""
    edge: Dict[str, float] = {}
    keys: List[str] = []
    for line in lines or []:
        parts = str(line).split()
        if len(parts) < 2:
            continue
        key = parts[0]
        try:
            weight = float(parts[1])
        except ValueError:
            continue
        if key not in edge:
            edge[key] = weight
            keys.append(key)
    return edge, keys


def _move_to(order: Sequence[str], node: str, position: int) -> List[str]:
    """返回把 ``node`` 移到 ``position``（0 或末尾）后的**新**列表。"""
    rest = [x for x in order if x != node]
    if position <= 0:
        return [node] + rest
    return rest + [node]


def node_objective_impacts(
    order: Sequence[str],
    informative_lines: Optional[Iterable[str]] = None,
    edge: Optional[Dict[str, float]] = None,
    edge_keys: Optional[Sequence[str]] = None,
) -> Dict[str, NodeObjectiveImpact]:
    """计算 ``order``（交付序）中每个节点的"移到序首/序尾"目标值变化量。

    Args:
        order: 已交付的排序（内部节点 bootstrap 标签，第 0 位 = 最古老）。
        informative_lines: ``Result.informative_lines``（``"donor,receptor weight"``）。
            与 ``edge`` 二选一；给了 ``edge`` 时以 ``edge`` 为准。
        edge: 直接给出的边权字典。
        edge_keys: ``edge`` 的键顺序（``None`` 时取 ``list(edge)``）。

    Returns:
        ``{节点标签: NodeObjectiveImpact}``；``order`` 为空时返回空字典。
    """
    from maxtic_next.ranking.value import value as _value

    nodes = list(order)
    if edge is None:
        edge, keys = parse_informative_edges(informative_lines)
    else:
        keys = list(edge_keys) if edge_keys is not None else list(edge.keys())
    keys = [k for k in keys if k in edge]

    base = _value(nodes, edge, keys)
    donor_w: Dict[str, float] = {}
    receptor_w: Dict[str, float] = {}
    counts: Dict[str, int] = {}
    for key in keys:
        parts = key.split(",", 1)
        if len(parts) != 2:
            continue
        donor, receptor = parts
        w = float(edge[key])
        donor_w[donor] = donor_w.get(donor, 0.0) + w
        receptor_w[receptor] = receptor_w.get(receptor, 0.0) + w
        counts[donor] = counts.get(donor, 0) + 1
        counts[receptor] = counts.get(receptor, 0) + 1

    degenerate = len(nodes) < 3
    out: Dict[str, NodeObjectiveImpact] = {}
    for pos, node in enumerate(nodes):
        delta_front = _value(_move_to(nodes, node, 0), edge, keys) - base
        delta_back = _value(_move_to(nodes, node, len(nodes)), edge, keys) - base
        out[node] = NodeObjectiveImpact(
            node=node,
            delta_front=delta_front,
            delta_back=delta_back,
            donor_weight=donor_w.get(node, 0.0),
            receptor_weight=receptor_w.get(node, 0.0),
            n_constraints=counts.get(node, 0),
            position=pos,
            informative=counts.get(node, 0) > 0,
            degenerate=degenerate,
        )
    return out


def impacts_from_result(result) -> Dict[str, NodeObjectiveImpact]:
    """从 ``Result`` 组装逐节点目标值影响（供 ``results_view`` 调用）。"""
    return node_objective_impacts(
        getattr(result, "best_order", []) or [],
        informative_lines=getattr(result, "informative_lines", []) or [],
    )


def ranked_impacts(
    impacts: Dict[str, NodeObjectiveImpact], order: Sequence[str]
) -> List[NodeObjectiveImpact]:
    """按交付顺序排出 impacts 列表；``order`` 中未出现在字典里的节点补零值。"""
    rows: List[NodeObjectiveImpact] = []
    for pos, node in enumerate(order):
        item = impacts.get(node)
        if item is None:
            item = NodeObjectiveImpact(
                node=node, position=pos, informative=False, degenerate=len(order) < 3
            )
        rows.append(item)
    return rows


def trivial_pairs_from_impacts(impacts: Dict[str, NodeObjectiveImpact]) -> List[Tuple[str, str]]:
    """列出"移到任一端都不改变目标值"的节点对（辅助信息，供报告标注无信息节点）。"""
    return [(n, n) for n, imp in impacts.items() if imp.amplitude == 0.0]


__all__ = [
    "NodeObjectiveImpact",
    "node_objective_impacts",
    "impacts_from_result",
    "ranked_impacts",
    "parse_informative_edges",
    "trivial_pairs_from_impacts",
]
