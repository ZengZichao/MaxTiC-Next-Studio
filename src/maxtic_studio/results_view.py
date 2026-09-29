"""结果解析与渲染：从 ``Result`` 内存数据构建表格模型 + matplotlib 条形图。

排名表**优先用内存 ``Result.best_order`` + ``Result.informative_lines``** 直接构建，
无需解析 TSV；``<prefix>.mt.informative.tsv`` 作为导出/兜底来源。

口径说明：MaxTiC 的目标函数是**整个排序**被违反的约束权重和
（``maxtic_next.ranking.value``），**不存在**逐节点 MTC 分数——donor 出度权重只描述
输入约束集、与排名结果几乎无关，且只作为受体出现的节点会以 0.0 被标成"信息性"
（自相矛盾）。因此本表交付**可辩护**的逐节点量
"把该节点移到序首 / 序尾时目标函数的变化量"，其计算在 :mod:`maxtic_studio.node_scores`
（纯 Python、无 PySide6 依赖，可独立单测）。
"""

from __future__ import annotations

import csv
import os
from typing import List, Optional, Tuple

from PySide6.QtCore import Qt, QAbstractTableModel
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from .i18n import _
from .node_scores import impacts_from_result, ranked_impacts

__all__ = ["RankingTableModel"]


def _info_row_color() -> QColor:
    """informative 行高亮色，读取主题令牌，避免深浅主题下硬编码突兀。"""
    app = QApplication.instance()
    tokens = app.property("maxTic-tokens") if app is not None else None
    hexc = tokens.get("row_info") if isinstance(tokens, dict) else None
    if hexc:
        c = QColor(hexc)
        if c.isValid():
            return c
    return QColor(230, 245, 240)  # 兜底浅青绿


class RankingTableModel(QAbstractTableModel):
    """排名表数据模型（基于内存 ``Result.best_order`` + 逐节点目标值影响）。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        # (rank, node, delta_front, delta_back, amplitude, is_informative,
        #  is_degenerate)
        self._rows: List[Tuple[int, str, float, float, float, bool, bool]] = []

    # ------------------------------------------------------------------
    # 填充
    # ------------------------------------------------------------------
    def populate_from_result(self, result) -> None:
        """从 ``Result`` 对象填充表格。

        - ``best_order``: 已交付的排序（第 0 位 = 最古老 / 最高排名）。
        - ``informative_lines``: ``"donor,receptor weight"`` 行，用于构造目标函数的
          可变部分（已剔除树种系哨兵边与零权重边）。
        - ``values``: 整体启发式 value（**不是**逐节点量，故不用于此列）。

        每个节点给出两个变化量：把它单独移到序首、移到序尾时目标函数（被违反的信息性
        约束权重和）的变化量。负值 = 更一致。条形图用两者的极差（位置敏感性幅度）。
        """
        self.beginResetModel()
        self._rows.clear()

        order = list(result.best_order or [])
        impacts = impacts_from_result(result)
        for rank, imp in enumerate(ranked_impacts(impacts, order)):
            self._rows.append(
                (
                    rank + 1,
                    imp.node,
                    imp.delta_front,
                    imp.delta_back,
                    imp.amplitude,
                    imp.informative,
                    imp.degenerate,
                )
            )

        self.endResetModel()

    def populate_from_tsv(self, tsv_path: str) -> None:
        """从 ``<prefix>.mt.informative.tsv`` 文件填充表格（兜底/导出用）。

        TSV 格式: ``donor,receptor weight``。没有交付排序时，按"供体先出现、受体后
        出现"的启发式伪序计算变化量（兜底口径，仅供浏览）。
        """
        self.beginResetModel()
        self._rows.clear()

        lines: List[str] = []
        order: List[str] = []
        if os.path.isfile(tsv_path):
            with open(tsv_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split()
                    if len(parts) < 2:
                        continue
                    lines.append(line)
                    key = parts[0]
                    donor = key.split(",")[0]
                    receptor = key.split(",")[1] if "," in key else ""
                    for node in (donor, receptor):
                        if node and node not in order:
                            order.append(node)

        from .node_scores import node_objective_impacts

        impacts = node_objective_impacts(order, informative_lines=lines)
        for rank, imp in enumerate(ranked_impacts(impacts, order)):
            self._rows.append(
                (
                    rank + 1,
                    imp.node,
                    imp.delta_front,
                    imp.delta_back,
                    imp.amplitude,
                    imp.informative,
                    imp.degenerate,
                )
            )

        self.endResetModel()

    # ------------------------------------------------------------------
    # Qt 模型接口
    # ------------------------------------------------------------------
    def rowCount(self, parent=None) -> int:
        return len(self._rows)

    def columnCount(self, parent=None) -> int:
        return 4

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        col = index.column()
        _rank, node, d_front, d_back, _amp, is_info, degen = row

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return str(_rank)
            elif col == 1:
                return node
            elif col == 2:
                return f"{d_front:+g} / {d_back:+g}"
            elif col == 3:
                return "✓" if is_info else ""
        elif role == Qt.ItemDataRole.ToolTipRole:
            return (
                _("tooltip_node_impact")
                + f"\n  {_('tooltip_impact_front')}: {d_front:+g}"
                + f"\n  {_('tooltip_impact_back')}: {d_back:+g}"
                + (("\n" + _("tooltip_impact_degenerate")) if degen else "")
            )
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if col in (0, 2, 3):
                return Qt.AlignmentFlag.AlignCenter
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        elif role == Qt.ItemDataRole.BackgroundRole:
            if is_info:
                return _info_row_color()
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            headers = [_("col_rank"), _("col_node"), _("col_value"), _("col_informative")]
            return headers[section] if section < len(headers) else ""
        return str(section + 1)

    def to_csv(self) -> str:
        """导出为 CSV 字符串（使用 csv.writer 正确转义字段）。"""
        import io

        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow([_("col_rank"), _("col_node"), _("col_value"), _("col_informative")])
        for rank, node, d_front, d_back, _amp, info, _degen in self._rows:
            w.writerow([rank, node, f"{d_front:+g} / {d_back:+g}", _("yes") if info else _("no")])
        return buf.getvalue()

    def get_node_scores(self) -> List[Tuple[str, float, bool]]:
        """返回 ``(node_label, amplitude, is_informative)`` 列表，按排名顺序。用于绘图。

        ``amplitude`` = "移到序首" 与 "移到序尾" 两个目标值变化量的极差：非负，越大表示
        该节点的位置对目标函数越敏感（不是 MTC 分数）。
        """
        return [(row[1], row[4], row[5]) for row in self._rows]

    def node_impacts(self) -> List[Tuple[str, float, float, float, bool]]:
        """返回 ``(node, delta_front, delta_back, amplitude, is_informative)`` 全量。"""
        return [(r[1], r[2], r[3], r[4], r[5]) for r in self._rows]

    def label_at(self, row: int) -> Optional[str]:
        """返回指定行的节点标签；越界返回 ``None``。供表↔图联动使用。"""
        if 0 <= row < len(self._rows):
            return self._rows[row][1]
        return None

    def ranked_count(self) -> int:
        """排名节点总数。"""
        return len(self._rows)

    def informative_count(self) -> int:
        """信息性节点数（作为**供体或受体**出现在任一信息性约束中）。"""
        return sum(1 for r in self._rows if r[5])
