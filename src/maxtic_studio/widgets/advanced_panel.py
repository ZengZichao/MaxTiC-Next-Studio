"""高级参数面板：输入适配 / 多工具 / 剪裁 / 运行模式 / MCMC / 检查点 / 输出。

默认所有参数与 CLI 完全一致。本面板作为主窗口「高级参数」页的内容直接展开，
不再被外层 QTabWidget 二次包裹（消除"Tab 套 Tab"）。
运行模式（dry-run / HTML 报告）与 MCMC 分成两个语义清晰的 tab。
"""

from __future__ import annotations

from typing import Dict, List, Optional, TypeVar, Union

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractSpinBox,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..i18n import _
from ..params import ADAPTER_FIELDS
from .. import metrics as M
from maxtic_next.config import DEFAULT_MIN_ENDPOINT_HIT_RATE, MCMC_TEMPERATURE_AUTO


# `_spin` 只做外观设置并原样返回传入的控件；调用方需要拿回**具体类型**
# （QDoubleSpinBox / QSpinBox 才有 setDecimals / setRange / setValue …）。
# 旧标注把返回类型写成 QAbstractSpinBox，于是 mypy 在 27 个调用点上报
# "has no attribute setRange"。用参数化 TypeVar 精化签名，零行为改动。
SpinBox = Union[QDoubleSpinBox, QSpinBox]
SpinBoxT = TypeVar("SpinBoxT", QDoubleSpinBox, QSpinBox)


class AdvancedPanel(QWidget):
    """高级参数面板（分组标签页，直接铺开）。"""

    data_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._label_keys = {}  # QLabel -> i18n key（用于 retranslate）
        self._adapter_rows: Dict[str, List[QWidget]] = {}  # 参数键 -> 需联动显隐的控件
        self._tab_keys = {}  # index -> i18n key（用于 retranslate）
        self._check_keys = {}  # QCheckBox -> i18n key（用于 retranslate）
        self._browse_buttons = []  # 浏览按钮（用于 retranslate）
        self._build_ui()
        self._wire_data_signals()

    def _wire_data_signals(self):
        """把各字段变更汇聚为 ``data_changed``，供 CLI 实时预览等使用。"""
        for w in self.findChildren(QAbstractSpinBox):
            w.valueChanged.connect(lambda *_: self.data_changed.emit())
        for w in self.findChildren(QComboBox):
            w.currentIndexChanged.connect(lambda *_: self.data_changed.emit())
        for w in self.findChildren(QLineEdit):
            w.textChanged.connect(lambda *_: self.data_changed.emit())
        for w in self.findChildren(QAbstractButton):
            w.toggled.connect(lambda *_: self.data_changed.emit())

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()
        self._tab_keys = {
            self._add_tab(self._build_adapter_tab(), "tab_adapters"): "tab_adapters",
            self._add_tab(self._build_pruning_tab(), "tab_pruning"): "tab_pruning",
            self._add_tab(self._build_run_mode_tab(), "tab_run_mode"): "tab_run_mode",
            self._add_tab(self._build_mcmc_tab(), "tab_mcmc"): "tab_mcmc",
            self._add_tab(self._build_checkpoint_tab(), "tab_checkpoint"): "tab_checkpoint",
            self._add_tab(self._build_output_tab(), "tab_output"): "tab_output",
        }

        layout.addWidget(self.tabs)

    def _add_tab(self, w: QWidget, key: str) -> int:
        return self.tabs.addTab(w, _(key))

    # ---- 工具：建表单 ----
    def _form(self, w: QWidget) -> QFormLayout:
        form = QFormLayout(w)
        # 跨平台一致：macOS 默认字段列不扩展，会把输入框压成一条缝
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setContentsMargins(8, 8, 8, 8)
        form.setVerticalSpacing(M.FORM_SPACING)
        return form

    def _browse_button(self, key: str) -> QPushButton:
        """创建并注册一个「浏览…」小按钮（语言切换时统一刷新）。"""
        btn = QPushButton(_("button_browse"))
        btn.setObjectName("btn_small")
        self._browse_buttons.append(btn)
        return btn

    def _spin(self, spin: SpinBoxT, width: int = 180) -> SpinBoxT:
        """统一旋钮类控件的尺寸：高度取 metrics 令牌（与 QSS 绘制高度同源，
        布局会真正预留）；统一宽度消除表单右侧参差感。"""
        spin.setMinimumHeight(M.CONTROL_H)
        spin.setFixedWidth(width)
        return spin

    def _checkbox(self, key: str) -> QCheckBox:
        """创建并注册一个带 i18n key 的复选框（语言切换时统一刷新）。"""
        check = QCheckBox(_(key))
        self._check_keys[check] = key
        return check

    # ---- 上游适配器：5 个工具收进同一页，按所选工具动态显示专属参数 ----
    #
    # 显隐矩阵来自 ..params.ADAPTER_FIELDS（它按核心层各 convert_from_* 的真实
    # 签名推导）：界面与 CLI 命令生成共用同一份事实，不会出现"字段看不见但值
    # 仍被写进可复现命令"的情况。
    _ADAPTER_TOOLS = (
        ("none", "adapter_tool_none"),
        ("auto", "adapter_tool_auto"),
        ("ale", "adapter_tool_ale"),
        ("ranger", "adapter_tool_ranger"),
        ("eccetera", "adapter_tool_eccetera"),
        ("artra", "adapter_tool_artra"),
        ("alerax", "adapter_tool_alerax"),
    )

    def _build_adapter_tab(self) -> QWidget:
        w = QWidget()
        form = self._form(w)

        self.adapter_tool_combo = QComboBox()
        for value, key in self._ADAPTER_TOOLS:
            self.adapter_tool_combo.addItem(_(key), value)
        self.adapter_tool_combo.currentIndexChanged.connect(self._apply_adapter_visibility)
        tool_label = _keyed_label(form, "from_tool")
        tool_label.setBuddy(self.adapter_tool_combo)
        form.addRow(tool_label, self.adapter_tool_combo)

        self.adapter_hint = QLabel()
        self.adapter_hint.setObjectName("fieldHint")
        self.adapter_hint.setWordWrap(True)
        self.adapter_hint.setTextFormat(Qt.TextFormat.PlainText)
        form.addRow("", self.adapter_hint)

        self.ale_min_support = self._spin(QDoubleSpinBox())
        self.ale_min_support.setRange(0.0, 1.0)
        self.ale_min_support.setDecimals(4)
        self.ale_min_support.setSingleStep(0.01)
        self.ale_min_support.setValue(0.05)
        self._add_adapter_row(form, "min_support", "ale_min_support", self.ale_min_support)

        self.ale_min_fam = self._spin(QSpinBox())
        self.ale_min_fam.setRange(1, 100000)
        self.ale_min_fam.setValue(5)
        self._add_adapter_row(form, "min_family", "ale_min_family_size", self.ale_min_fam)

        self.ale_cache_edit = QLineEdit()
        ale_cache_browse = self._browse_button("button_browse")
        ale_cache_browse.clicked.connect(self._browse_ale_cache)
        ale_cache_row = QHBoxLayout()
        ale_cache_row.setSpacing(M.FIELD_SPACING)
        ale_cache_row.addWidget(self.ale_cache_edit, 1)
        ale_cache_row.addWidget(ale_cache_browse)
        ale_cache_w = QWidget()
        ale_cache_w.setLayout(ale_cache_row)
        self._add_adapter_row(form, "cache", "ale_cache_dir", ale_cache_w)

        self.ale_source_combo = QComboBox()
        # trf 在前 = 默认口径（ALE 官方 MaxTiC 集成用 constraints_from_transfers）
        self.ale_source_combo.addItems(["trf", "rec"])
        self._add_adapter_row(form, "source", "ale_source", self.ale_source_combo)

        self.artra_kind_combo = QComboBox()
        self.artra_kind_combo.addItems(["all", "replacing", "additive"])
        self._add_adapter_row(form, "transfer_kind", "artra_transfer_kind", self.artra_kind_combo)

        self.adapter_hit_spin = self._spin(QDoubleSpinBox())
        self.adapter_hit_spin.setRange(0.0, 1.0)
        self.adapter_hit_spin.setDecimals(2)
        self.adapter_hit_spin.setSingleStep(0.05)
        self.adapter_hit_spin.setValue(DEFAULT_MIN_ENDPOINT_HIT_RATE)
        self._add_adapter_row(
            form, "hit_rate", "adapter_min_endpoint_hit_rate", self.adapter_hit_spin
        )

        self.ale_parallel_combo = QComboBox()
        self.ale_parallel_combo.addItems(["process", "thread"])
        self._add_adapter_row(form, "parallel", "ale_parallel", self.ale_parallel_combo)

        self.adapter_quiet_check = self._checkbox("adapter_quiet")
        self._add_adapter_row(form, "quiet", None, self.adapter_quiet_check)

        self._apply_adapter_visibility()
        return w

    def _add_adapter_row(self, form, field_key: str, label_key: Optional[str], widget: QWidget):
        """加一行并登记到可见性表：隐藏时标签与字段一起消失。"""
        if label_key is None:
            form.addRow(widget)
            self._adapter_rows.setdefault(field_key, []).append(widget)
            return
        lbl = _keyed_label(form, label_key)
        lbl.setBuddy(widget)
        form.addRow(lbl, widget)
        self._adapter_rows.setdefault(field_key, []).extend([lbl, widget])

    def _adapter_tool(self) -> str:
        data = self.adapter_tool_combo.currentData()
        return data if data else "none"

    def _select_adapter_tool(self, tool: str):
        idx = self.adapter_tool_combo.findData(tool or "none")
        self.adapter_tool_combo.setCurrentIndex(max(idx, 0))

    def _apply_adapter_visibility(self):
        """按当前工具显隐参数行，并刷新该工具的说明。"""
        tool = self._adapter_tool()
        visible = set(ADAPTER_FIELDS.get(tool, ()))
        for field_key, widgets in self._adapter_rows.items():
            for widget in widgets:
                widget.setVisible(field_key in visible)
        self.adapter_hint.setText(_("adapter_hint_" + tool))
        # 行数变了：让外层滚动区重新量内容高度，避免留下空白或压出重叠
        if self.layout() is not None:
            self.layout().invalidate()

    def _browse_ale_cache(self):
        path = QFileDialog.getExistingDirectory(self, _("ale_cache_dir"))
        if path:
            self.ale_cache_edit.setText(path)

    # ---- 剪裁标签页 ----
    def _build_pruning_tab(self) -> QWidget:
        w = QWidget()
        form = self._form(w)

        self.target_clade_edit = QLineEdit()
        form.addRow(_keyed_label(form, "target_clade"), self.target_clade_edit)

        self.ancestor_map_check = self._checkbox("target_clade_ancestor_map")
        form.addRow(self.ancestor_map_check)

        return w

    # ---- 运行模式标签页（仅 dry-run + HTML 报告） ----
    def _build_run_mode_tab(self) -> QWidget:
        w = QWidget()
        form = self._form(w)

        self.dry_run_check = self._checkbox("dry_run")
        form.addRow(self.dry_run_check)

        self.html_report_check = self._checkbox("generate_html_report")
        self.html_report_check.setChecked(True)
        form.addRow(self.html_report_check)

        form.addRow(QLabel(""))  # 底部留白

        return w

    # ---- MCMC 标签页 ----
    def _build_mcmc_tab(self) -> QWidget:
        w = QWidget()
        form = self._form(w)

        self.mcmc_check = self._checkbox("mcmc")
        form.addRow(self.mcmc_check)

        self.mcmc_iters_spin = self._spin(QSpinBox())
        self.mcmc_iters_spin.setRange(1, 10**9)
        self.mcmc_iters_spin.setValue(1000)
        form.addRow(_keyed_label(form, "mcmc_iters"), self.mcmc_iters_spin)

        self.mcmc_temp_spin = self._spin(QDoubleSpinBox())
        # ：温度下限曾为 1e-6，"auto"（哨兵 0.0）在选择器里根本
        # 选不到，而 0.01 恰是链冻结的默认档 —— GUI 因此仍会产出"不是后验样本"的
        # 输出。现以 0.0 = auto 为默认值与下限，并给出可读的 specialValueText。
        self.mcmc_temp_spin.setRange(MCMC_TEMPERATURE_AUTO, 1e6)
        self.mcmc_temp_spin.setDecimals(6)
        self.mcmc_temp_spin.setSingleStep(0.01)
        self.mcmc_temp_spin.setSpecialValueText(_("mcmc_temperature_auto"))
        self.mcmc_temp_spin.setValue(MCMC_TEMPERATURE_AUTO)
        form.addRow(_keyed_label(form, "mcmc_temperature"), self.mcmc_temp_spin)

        return w

    # ---- 检查点 / 性能标签页 ----
    def _build_checkpoint_tab(self) -> QWidget:
        w = QWidget()
        form = self._form(w)

        self.incremental_check = self._checkbox("incremental")
        form.addRow(self.incremental_check)

        self.checkpoint_edit = QLineEdit()
        ckpt_browse = self._browse_button("button_browse")
        ckpt_browse.clicked.connect(self._browse_checkpoint)
        ckpt_row = QHBoxLayout()
        ckpt_row.addWidget(self.checkpoint_edit, 1)
        ckpt_row.addWidget(ckpt_browse)
        ckpt_w = QWidget()
        ckpt_w.setLayout(ckpt_row)
        form.addRow(_keyed_label(form, "checkpoint_path"), ckpt_w)

        self.ckpt_interval_spin = self._spin(QDoubleSpinBox())
        self.ckpt_interval_spin.setRange(0.1, 1e6)
        self.ckpt_interval_spin.setDecimals(1)
        self.ckpt_interval_spin.setSingleStep(10)
        self.ckpt_interval_spin.setValue(60.0)
        self.ckpt_interval_spin.setSuffix(" s")
        form.addRow(_keyed_label(form, "checkpoint_interval"), self.ckpt_interval_spin)

        return w

    def _browse_checkpoint(self):
        path, _selected_filter = QFileDialog.getOpenFileName(self, _("checkpoint_path"))
        if path:
            self.checkpoint_edit.setText(path)

    # ---- 输出标签页 ----
    def _build_output_tab(self) -> QWidget:
        w = QWidget()
        form = self._form(w)

        self.constraints_out_edit = QLineEdit()
        cons_out_browse = self._browse_button("button_browse")
        cons_out_browse.clicked.connect(self._browse_constraints_out)
        cons_out_row = QHBoxLayout()
        cons_out_row.addWidget(self.constraints_out_edit, 1)
        cons_out_row.addWidget(cons_out_browse)
        cons_out_w = QWidget()
        cons_out_w.setLayout(cons_out_row)
        form.addRow(_keyed_label(form, "constraints_out"), cons_out_w)

        self.output_style_combo = QComboBox()
        self.output_style_combo.addItems(["short", "legacy"])
        form.addRow(_keyed_label(form, "output_style"), self.output_style_combo)

        return w

    def _browse_constraints_out(self):
        path, _selected_filter = QFileDialog.getSaveFileName(self, _("constraints_out"))
        if path:
            self.constraints_out_edit.setText(path)

    # ------------------------------------------------------------------
    # 取值
    # ------------------------------------------------------------------
    @property
    def from_ale(self) -> bool:
        """恒为 ``False``：单一工具选择器已覆盖 ``--from-ale`` 的语义。

        核心层文档写明 ``from_ale`` 只是 ``from_tool="ale"`` 的向后兼容开关
        （``api.rank`` 里 ``tool = from_tool if from_tool else ("ale" if from_ale)``），
        所以这里不再产生第二个开关，实时 CLI 预览也不会同时出现两个旗标。
        """
        return False

    @property
    def ale_min_support_val(self) -> float:
        return self.ale_min_support.value()

    @property
    def ale_min_family_size_val(self) -> int:
        return self.ale_min_fam.value()

    @property
    def ale_cache_dir_val(self) -> str:
        return self.ale_cache_edit.text()

    @property
    def ale_source_val(self) -> str:
        return self.ale_source_combo.currentText()

    @property
    def ale_parallel_val(self) -> str:
        return self.ale_parallel_combo.currentText()

    @property
    def from_tool_val(self) -> Optional[str]:
        tool = self._adapter_tool()
        return None if tool == "none" else tool

    @property
    def adapter_min_endpoint_hit_rate_val(self) -> float:
        return self.adapter_hit_spin.value()

    @property
    def adapter_quiet_val(self) -> bool:
        return self.adapter_quiet_check.isChecked()

    @property
    def artra_transfer_kind_val(self) -> str:
        return self.artra_kind_combo.currentText()

    @property
    def target_clade_val(self) -> str:
        return self.target_clade_edit.text()

    @property
    def ancestor_map_val(self) -> bool:
        return self.ancestor_map_check.isChecked()

    @property
    def dry_run_val(self) -> bool:
        return self.dry_run_check.isChecked()

    @property
    def generate_html_report_val(self) -> bool:
        return self.html_report_check.isChecked()

    @property
    def mcmc_val(self) -> bool:
        return self.mcmc_check.isChecked()

    @property
    def mcmc_iters_val(self) -> int:
        return self.mcmc_iters_spin.value()

    @property
    def mcmc_temperature_val(self) -> float:
        return self.mcmc_temp_spin.value()

    @property
    def incremental_val(self) -> bool:
        return self.incremental_check.isChecked()

    @property
    def checkpoint_path_val(self) -> str:
        return self.checkpoint_edit.text()

    @property
    def checkpoint_interval_val(self) -> float:
        return self.ckpt_interval_spin.value()

    @property
    def constraints_out_val(self) -> str:
        return self.constraints_out_edit.text()

    @property
    def output_style_val(self) -> str:
        return self.output_style_combo.currentText()

    # ------------------------------------------------------------------
    # 赋值
    # ------------------------------------------------------------------
    def set_values(self, values: dict):
        # 路径 / 文本类字段显式支持清空（None / 空串 → 覆盖为空），
        # 否则「重置默认」与加载精简配置时无法覆盖旧值
        # 旧配置里的 from_ale=true 等价于选中 ALE：统一收敛到工具选择器
        tool = values.get("from_tool")
        if not tool and values.get("from_ale"):
            tool = "ale"
        if "from_tool" in values or "from_ale" in values:
            self._select_adapter_tool(tool or "none")
        if "ale_min_support" in values:
            self.ale_min_support.setValue(values["ale_min_support"])
        if "ale_min_family_size" in values:
            self.ale_min_fam.setValue(values["ale_min_family_size"])
        if "ale_cache_dir" in values:
            self.ale_cache_edit.setText(values["ale_cache_dir"] or "")
        if "ale_source" in values:
            self.ale_source_combo.setCurrentText(values["ale_source"])
        if "ale_parallel" in values:
            self.ale_parallel_combo.setCurrentText(values["ale_parallel"])
        if "artra_transfer_kind" in values:
            self.artra_kind_combo.setCurrentText(values["artra_transfer_kind"])
        if "target_clade" in values:
            self.target_clade_edit.setText(values["target_clade"] or "")
        if "ancestor_map" in values:
            self.ancestor_map_check.setChecked(bool(values["ancestor_map"]))
        if "dry_run" in values:
            self.dry_run_check.setChecked(bool(values["dry_run"]))
        if "html_report" in values:
            self.html_report_check.setChecked(bool(values["html_report"]))
        if "mcmc" in values:
            self.mcmc_check.setChecked(bool(values["mcmc"]))
        if "mcmc_iters" in values:
            self.mcmc_iters_spin.setValue(values["mcmc_iters"])
        if "mcmc_temperature" in values:
            self.mcmc_temp_spin.setValue(values["mcmc_temperature"])
        if "incremental" in values:
            self.incremental_check.setChecked(bool(values["incremental"]))
        if "checkpoint_path" in values:
            self.checkpoint_edit.setText(values["checkpoint_path"] or "")
        if "checkpoint_interval" in values:
            self.ckpt_interval_spin.setValue(values["checkpoint_interval"])
        if "constraints_out" in values:
            self.constraints_out_edit.setText(values["constraints_out"] or "")
        if "adapter_min_endpoint_hit_rate" in values:
            self.adapter_hit_spin.setValue(float(values["adapter_min_endpoint_hit_rate"]))
        if "adapter_quiet" in values:
            self.adapter_quiet_check.setChecked(bool(values["adapter_quiet"]))
        if "output_style" in values:
            self.output_style_combo.setCurrentText(values["output_style"])

    # ------------------------------------------------------------------
    # 语言刷新
    # ------------------------------------------------------------------
    def retranslate(self):
        # 刷新标签页标题
        for idx, key in self._tab_keys.items():
            self.tabs.setTabText(idx, _(key))
        # 刷新字段标签
        for lbl, key in self._label_keys.items():
            lbl.setText(_(key) + ":")
        # 复选框与浏览按钮也要纳入 retranslate，否则切语言后残留旧文案
        for check, key in self._check_keys.items():
            check.setText(_(key))
        for btn in self._browse_buttons:
            btn.setText(_("button_browse"))
        # 适配器工具名与说明：前两项是短语（无 / 自动检测），需随语言刷新；
        # 其余是工具专名，_() 里中英同形，走同一套逻辑也无害。
        for i, (_value, key) in enumerate(self._ADAPTER_TOOLS):
            self.adapter_tool_combo.setItemText(i, _(key))
        self.adapter_quiet_check.setText(_("adapter_quiet"))
        self._apply_adapter_visibility()


def _keyed_label(form, key: str) -> QLabel:
    """创建一个带 i18n key 的 QLabel，并挂到所属 AdvancedPanel 的注册表。

    从 ``form.parentWidget()`` 向上回溯到 ``AdvancedPanel`` 实例，
    把 ``label -> key`` 记入 ``_label_keys``，供 ``retranslate`` 刷新。
    """
    lbl = QLabel(_(key) + ":")
    panel = form.parentWidget()
    while panel is not None and not isinstance(panel, AdvancedPanel):
        panel = panel.parentWidget()
    if panel is not None:
        panel._label_keys[lbl] = key
        # 如果有对应字段控件，建立 buddy 关联
        # _keyed_label 在 addRow 之前调用，无法直接拿到字段控件
        # 但 AdvancedPanel 中的字段控件在 _keyed_label 返回后由 addRow 添加
        # 因此 buddy 关联在 AdvancedPanel 的各 _build_*_tab 方法中手动补充
    return lbl
