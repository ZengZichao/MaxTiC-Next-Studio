"""结果面板：指标卡概览层 + 排名表 + matplotlib 条形图 + 空/错误态 + 报告按钮。

面板结构：
- 顶部 4 张指标卡（排名数 / 信息性 / 冲突 / 用时）——概览层；
- 四态：空状态引导 / 加载 / 成功 / 错误卡；
- 图表主题化（rcParams）+ 色盲友好（深青绿=信息性 / 浅青绿=非信息性）+ 图例 + 排名标注；
- 表↔图联动：点击表行高亮图中对应条。

排名表优先用内存 ``Result.best_order`` + informative 信息；报告走系统浏览器。
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
    QGroupBox,
    QHeaderView,
)

from ..i18n import _
from .. import metrics as M
from ..results_view import RankingTableModel

# matplotlib QtAgg 后端（延迟 import 避免无 matplotlib 时 GUI 无法启动）
_MplCanvas = None
_FigureCanvas = None


def _mono_font() -> QFont:
    """跨平台等宽字体（dry-run 预检文本用）。"""
    return M.font(M.FONT_MONO_PT, mono=True)


def _ensure_matplotlib():
    """延迟初始化 matplotlib QtAgg 后端。"""
    global _MplCanvas, _FigureCanvas
    if _MplCanvas is not None:
        return
    import matplotlib

    matplotlib.use("QtAgg")
    import matplotlib as mpl

    # 图表字体对齐 UI 字体且具备 CJK 能力。
    mpl.rcParams["font.family"] = "sans-serif"
    mpl.rcParams["font.sans-serif"] = [
        "PingFang SC",
        "Microsoft YaHei",
        "Noto Sans CJK SC",
        "Hiragino Sans GB",
        "Arial Unicode MS",
        "Heiti SC",
        "DejaVu Sans",
    ]
    mpl.rcParams["axes.unicode_minus"] = False
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure

    _FigureCanvas = FigureCanvas
    _MplCanvas = Figure


def _chart_theme():
    """从主题令牌取图表配色，避免图与主体"两张皮"。"""
    app = QApplication.instance()
    tokens = app.property("maxTic-tokens") if app is not None else None
    if not isinstance(tokens, dict):
        tokens = {}
    return {
        "info": tokens.get("primary", "#0F6E56"),
        "plain": tokens.get("primary_100", "#9FE1CB"),
        "surface": tokens.get("surface", "#FFFFFF"),
        "text": tokens.get("text_1", "#2C2C2A"),
        "muted": tokens.get("text_2", "#6B7280"),
        "border": tokens.get("border", "#E5E7EB"),
        "bg": tokens.get("bg", "#F7F8FA"),
    }


class _MetricCard(QFrame):
    """单张指标卡：大数值 + 小标题（配色统一走 QSS #metricCard/#metricTitle）。"""

    def __init__(self, title_key: str, value: QLabel, parent=None):
        super().__init__(parent)
        self.setObjectName("metricCard")
        self.title_key = title_key
        self.value_label = value
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(2)
        self.title_label = QLabel(_(title_key))
        self.title_label.setObjectName("metricTitle")
        lay.addWidget(self.value_label, 0, Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.title_label, 0, Qt.AlignmentFlag.AlignCenter)

    def retranslate(self):
        self.title_label.setText(_(self.title_key))


class _ChartWidget(QWidget):
    """matplotlib 条形图容器（延迟初始化 + 主题化 + 表图联动点亮）。

    matplotlib 缺失时优雅降级为文字提示，不影响表格查看与导出。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._canvas = None
        self._unavailable = False

    def ensure_canvas(self) -> bool:
        """初始化画布；matplotlib 不可用时返回 False 并显示提示。"""
        if self._unavailable:
            return False
        if self._canvas is not None:
            return True
        try:
            _ensure_matplotlib()
        except Exception as exc:  # ImportError 或后端初始化失败
            self._unavailable = True
            hint = QLabel(_("chart_unavailable") + f"\n({type(exc).__name__})")
            hint.setObjectName("emptyGuide")
            hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hint.setWordWrap(True)
            layout = self.layout()
            if layout is not None:  # 未装布局时不该在渲染图表的路上崩掉
                layout.addWidget(hint)
            return False
        # _ensure_matplotlib() 成功即注入两个类；这里显式取局部变量让类型收窄可见
        canvas_cls, figure_cls = _MplCanvas, _FigureCanvas
        if canvas_cls is None or figure_cls is None:  # 理论不可达，防御式处理
            self._unavailable = True
            return False
        fig = canvas_cls(figsize=(6, 4))
        self._canvas = figure_cls(fig)
        layout = self.layout()
        if layout is not None:
            layout.addWidget(self._canvas)
        return True

    def update_chart(self, node_scores=None, highlight_label: Optional[str] = None):
        """更新条形图。

        Args:
            node_scores: ``(node_label, score, is_informative)`` 列表，按排名顺序。
            highlight_label: 需要点亮的节点标签（来自表格当前选中行）。
        """
        if not self.ensure_canvas():
            return
        fig = self._canvas.figure
        fig.clear()
        ax = fig.add_subplot(111)
        theme = _chart_theme()
        fig.set_facecolor(theme["surface"])

        if not node_scores:
            ax.text(0.5, 0.5, _("no_results"), ha="center", va="center", transform=ax.transAxes)
            self._canvas.draw()
            return

        labels = []
        scores = []
        infos = []
        for i, (label, score, info) in enumerate(node_scores):
            labels.append(f"{i + 1}  {label}")  # 排名标注
            scores.append(score)
            infos.append(info)

        colors = [theme["info"] if info else theme["plain"] for info in infos]
        alphas = [
            0.35 if (highlight_label is not None and node_scores[i][0] != highlight_label) else 1.0
            for i in range(len(node_scores))
        ]
        bars = ax.barh(range(len(labels)), scores, color=colors, edgecolor="none")

        # 联动：选中条加粗描边
        for i, bar in enumerate(bars):
            bar.set_alpha(alphas[i])
            if highlight_label is not None and node_scores[i][0] == highlight_label:
                bar.set_edgecolor(theme["info"])
                bar.set_linewidth(2.0)

        ax.set_yticks(range(len(labels)))
        ax.set_yticklabels(labels)
        ax.invert_yaxis()  # 第 0 位在顶部
        ax.set_xlabel(_("chart_axis_score"))
        ax.set_title(_("chart_title"))
        ax.set_facecolor(theme["bg"])
        ax.tick_params(colors=theme["muted"])
        for spine in ax.spines.values():
            spine.set_color(theme["border"])
        ax.title.set_color(theme["text"])
        ax.xaxis.label.set_color(theme["text"])

        # 色盲友好图例（深青绿 / 浅青绿 + 文字）
        from matplotlib.patches import Patch

        handles = [
            Patch(facecolor=theme["info"], label=_("legend_informative")),
            Patch(facecolor=theme["plain"], label=_("legend_non_informative")),
        ]
        ax.legend(
            handles=handles, loc="lower right", frameon=False, fontsize=9, labelcolor=theme["muted"]
        )

        fig.tight_layout()
        self._canvas.draw()

    def save_figure(self, path: str) -> bool:
        """保存图表到文件（PNG / PDF 等，按扩展名）。"""
        if self._canvas is None:
            return False
        self._canvas.figure.savefig(path, dpi=150)
        return True


class ResultPanel(QWidget):
    """结果面板：指标卡 + 表格 + 图 + 报告按钮 + 空/错误态。"""

    demo_requested = Signal()

    # 面板状态：empty（运行前引导）/ results（结果）/ dry（预检报告）/ error（错误卡）
    _MODE_EMPTY, _MODE_RESULTS, _MODE_DRY, _MODE_ERROR = "empty", "results", "dry", "error"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._result = None
        self._elapsed = None
        self._mode = self._MODE_EMPTY
        self._error_text = ""
        self._build_ui()
        self._wire_links()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        group = QGroupBox(_("group_results"))
        glayout = QVBoxLayout(group)
        glayout.setSpacing(6)

        # ---- 概览层：4 张指标卡 ----
        self._metric_cards = {}
        metrics_row = QHBoxLayout()
        self.metrics_row = metrics_row
        metrics_row.setSpacing(8)
        for key in ("metric_ranked", "metric_informative", "metric_conflicts", "metric_time"):
            value = QLabel("–")
            value.setObjectName("metricValue")
            card = _MetricCard(key, value)
            card.setMinimumHeight(M.METRIC_CARD_H)
            self._metric_cards[key] = card
            metrics_row.addWidget(card, 1)
        metrics_w = QWidget()
        metrics_w.setLayout(metrics_row)
        glayout.addWidget(metrics_w)

        # ---- 空状态引导 ----
        self.placeholder = QLabel("")
        self.placeholder.setObjectName("emptyGuide")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder.setWordWrap(True)
        self._set_empty_guide()
        glayout.addWidget(self.placeholder, 1)

        # ---- 错误卡 ----
        self.error_label = QLabel("")
        self.error_label.setObjectName("errorBanner")
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        glayout.addWidget(self.error_label)

        # ---- 标签页：表格 + 图 ----
        self.tabs = QTabWidget()
        self.table_view = QTableView()
        self.table_model = RankingTableModel()
        self.table_view.setModel(self.table_model)
        self.table_view.setSortingEnabled(False)  # 保持模型顺序与图一致
        self.table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table_view.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.table_view.setAlternatingRowColors(True)
        # 行号表头与「排名」列重复；列宽自适应并让节点标签列吃掉剩余宽度，
        # 消除表格右侧的整段空白
        self.table_view.verticalHeader().setVisible(False)
        header = self.table_view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.tabs.addTab(self.table_view, _("tab_table"))

        self.chart_widget = _ChartWidget()
        self.tabs.addTab(self.chart_widget, _("tab_chart"))
        self.tabs.setVisible(False)
        glayout.addWidget(self.tabs, 1)

        # ---- 按钮行：报告 / 演示 一行，导出 一行 ----
        # 单行排 5 个按钮时，窄窗口下这一行的最小宽度超过结果区可用宽度，
        # 按钮会互相压字；拆两行后每行都能在自己的空间里放下。
        self.btn_report = QPushButton(_("button_open_report"))
        self.btn_report.setEnabled(False)
        self.btn_report.clicked.connect(self._open_report)
        self.btn_csv = QPushButton(_("button_export_csv"))
        self.btn_csv.setEnabled(False)
        self.btn_csv.clicked.connect(self._export_csv)
        self.btn_png = QPushButton(_("button_export_png"))
        self.btn_png.setEnabled(False)
        self.btn_png.clicked.connect(self._export_png)
        self.btn_pdf = QPushButton(_("button_export_pdf"))
        self.btn_pdf.setEnabled(False)
        self.btn_pdf.clicked.connect(self._export_pdf)
        self.btn_demo = QPushButton(_("action_demo"))
        self.btn_demo.setObjectName("btn_small")
        self.btn_demo.clicked.connect(self.demo_requested.emit)

        primary_row = QHBoxLayout()
        primary_row.setSpacing(M.FIELD_SPACING)
        primary_row.addWidget(self.btn_report)
        primary_row.addStretch()
        primary_row.addWidget(self.btn_demo)
        export_row = QHBoxLayout()
        export_row.setSpacing(M.FIELD_SPACING)
        export_row.addWidget(self.btn_csv)
        export_row.addWidget(self.btn_png)
        export_row.addWidget(self.btn_pdf)
        export_row.addStretch()
        for row in (primary_row, export_row):
            holder = QWidget()
            holder.setLayout(row)
            glayout.addWidget(holder)

        layout.addWidget(group)

    def _wire_links(self):
        # 表↔图联动：选中行 → 高亮图中对应条
        self.table_view.selectionModel().selectionChanged.connect(self._on_table_selected)

    def _on_table_selected(self, *_):
        selection = self.table_view.selectionModel().selectedRows()
        if not selection:
            return
        row = selection[0].row()
        label = self.table_model.label_at(row)
        # 只更新图表数据，不强制切换到图表页
        # 用户可用键盘方向键在表格中自由浏览，不会被弹到图表页
        self.chart_widget.update_chart(self.table_model.get_node_scores(), highlight_label=label)

    def _set_empty_guide(self):
        self.placeholder.setText(_("empty_guide_title") + " " + _("empty_guide_steps"))

    def retranslate(self):
        group = self.placeholder.parentWidget()
        while group is not None and not isinstance(group, QGroupBox):
            group = group.parentWidget()
        if isinstance(group, QGroupBox):
            group.setTitle(_("group_results"))
        for card in self._metric_cards.values():
            card.retranslate()
        self.tabs.setTabText(0, _("tab_table"))
        self.tabs.setTabText(1, _("tab_chart"))
        self.btn_report.setText(_("button_open_report"))
        self.btn_csv.setText(_("button_export_csv"))
        self.btn_png.setText(_("button_export_png"))
        self.btn_pdf.setText(_("button_export_pdf"))
        self.btn_demo.setText(_("action_demo"))
        # 图表标题/图例语言刷新
        if self._mode == self._MODE_RESULTS:
            self.chart_widget.update_chart(self.table_model.get_node_scores())
        elif self._mode == self._MODE_EMPTY:
            self._set_empty_guide()
        elif self._mode == self._MODE_ERROR:
            self.error_label.setText(self._error_text + "\n" + _("error_card_hint"))
        # dry 模式下占位区显示的是预检报告原文，无需翻译，保持不动

    def on_theme_changed(self):
        """主题切换后重绘图表，使配色与新令牌一致。"""
        if self._mode == self._MODE_RESULTS:
            self.chart_widget.update_chart(self.table_model.get_node_scores())

    # ------------------------------------------------------------------
    # 状态切换
    # ------------------------------------------------------------------
    def show_empty(self):
        self._result = None
        self._mode = self._MODE_EMPTY
        self.tabs.setVisible(False)
        self.error_label.setVisible(False)
        self._set_empty_guide()
        self.placeholder.setVisible(True)
        self._reset_metrics()
        self._set_buttons(False)

    def show_error(self, text: str):
        self._result = None
        self._mode = self._MODE_ERROR
        self._error_text = text
        self.tabs.setVisible(False)
        self.placeholder.setVisible(False)
        # 配色统一走 QSS #errorBanner，随主题自动切换
        self.error_label.setText(text + "\n" + _("error_card_hint"))
        self.error_label.setVisible(True)
        self._reset_metrics()
        self._set_buttons(False)

    def clear_results(self) -> None:
        """清空结果面板（回到空状态）。"""
        self.table_model.beginResetModel()
        self.table_model._rows.clear()
        self.table_model.endResetModel()
        self.chart_widget.update_chart([])
        self.show_empty()

    def update_result(self, result, elapsed: Optional[float] = None) -> None:
        """用 ``Result`` 对象更新面板。

        Args:
            result: ``api.rank`` 返回的 ``Result``；
            elapsed: 运行耗时（秒），用于「用时」指标卡。
        """
        self._result = result
        self._elapsed = elapsed
        self.error_label.setVisible(False)
        self.placeholder.setVisible(False)
        self.tabs.setVisible(True)

        # dry-run 模式：显示预检报告文本（等宽字体便于阅读对齐）
        if getattr(result, "dry_run_report", None):
            self._mode = self._MODE_DRY
            self.placeholder.setFont(_mono_font())
            self.placeholder.setText(result.dry_run_report)
            self.placeholder.setVisible(True)
            self.tabs.setVisible(False)
            self._reset_metrics()
            self._set_buttons(False, report=False)
            return

        self._mode = self._MODE_RESULTS

        # 先填充表格模型，指标卡再从模型读取统计（顺序颠倒会把 0 写进卡片）
        self.table_model.populate_from_result(result)
        self._update_metrics(result)

        # 表格 + 图
        self.chart_widget.update_chart(self.table_model.get_node_scores())

        # 按钮
        self._set_buttons(True)
        has_report = bool(getattr(result, "html_report_file", ""))
        self.btn_report.setEnabled(has_report)

    def _update_metrics(self, result):
        ranked = self.table_model.ranked_count()
        infos = self.table_model.informative_count()
        # 「冲突数」对应 Result.conflicting_lines，不是 informative_lines
        conflicts = len(getattr(result, "conflicting_lines", []) or [])
        elapsed = self._elapsed if self._elapsed is not None else 0.0
        self._metric_cards["metric_ranked"].value_label.setText(str(ranked))
        self._metric_cards["metric_informative"].value_label.setText(str(infos))
        self._metric_cards["metric_conflicts"].value_label.setText(str(conflicts))
        self._metric_cards["metric_time"].value_label.setText(f"{elapsed:.1f} s")

    def _reset_metrics(self):
        for card in self._metric_cards.values():
            card.value_label.setText("–")

    def _set_buttons(self, enabled: bool, report: bool = True):
        self.btn_csv.setEnabled(enabled)
        self.btn_png.setEnabled(enabled)
        self.btn_pdf.setEnabled(enabled)
        self.btn_report.setEnabled(enabled and report)

    # ------------------------------------------------------------------
    # 导出 / 打开
    # ------------------------------------------------------------------
    def _open_report(self):
        if self._result and self._result.html_report_file:
            url = QUrl.fromLocalFile(self._result.html_report_file)
            QDesktopServices.openUrl(url)

    def _export_csv(self):
        path, _selected_filter = QFileDialog.getSaveFileName(
            self, _("dialog_export_csv_title"), "ranking.csv", "CSV (*.csv)"
        )
        if path:
            # 使用 utf-8-sig 编码（带 BOM），Windows Excel 可正确显示中文
            try:
                csv_data = self.table_model.to_csv()
                with open(path, "w", encoding="utf-8-sig", newline="") as f:
                    f.write(csv_data)
            except OSError as exc:
                QMessageBox.critical(self, _("app_title"), str(exc))

    def _export_png(self):
        path, _selected_filter = QFileDialog.getSaveFileName(
            self, _("dialog_export_image_title"), "ranking_chart.png", "PNG (*.png)"
        )
        if path:
            # 导出加异常兜底
            try:
                self.chart_widget.save_figure(path)
            except Exception as exc:
                QMessageBox.critical(self, _("app_title"), str(exc))

    def _export_pdf(self):
        path, _selected_filter = QFileDialog.getSaveFileName(
            self, _("dialog_export_image_title"), "ranking_chart.pdf", "PDF (*.pdf)"
        )
        if path:
            # 导出加异常兜底
            try:
                self.chart_widget.save_figure(path)
            except Exception as exc:
                QMessageBox.critical(self, _("app_title"), str(exc))
