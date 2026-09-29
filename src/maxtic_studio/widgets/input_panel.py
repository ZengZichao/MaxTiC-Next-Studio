"""输入面板：文件选择（物种树 + 约束多文件）+ 核心参数表单。

提供：
- 文件校验（存在性、扩展名）、约束多文件增删；
- 非法值即时红框态：``seed < 0`` / ``temperature <= 0`` / 树文件缺失；
- 文件拖拽与目录记忆；
- 语言切换即时刷新（``retranslate``）。
"""

from __future__ import annotations

import os
from typing import List, Optional

from PySide6.QtCore import Qt, QSettings, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSpinBox,
    QDoubleSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..i18n import _
from .. import metrics as M


class _DropLineEdit(QLineEdit):
    """支持把文件或文件夹拖进来设值的 QLineEdit。"""

    def __init__(self, parent=None, is_dir: bool = False):
        super().__init__(parent)
        self._is_dir = is_dir
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if self._is_dir:
                if os.path.isdir(path):
                    self.setText(path)
            elif os.path.isfile(path):
                self.setText(path)
            event.acceptProposedAction()


def _set_error(widget, on: bool, tooltip: str = ""):
    """开关控件的 error 红框态。"""
    widget.setProperty("error", on)
    widget.setToolTip(tooltip if on else "")
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)


class InputPanel(QWidget):
    """输入面板：物种树 + 约束文件列表 + 输出前缀 + 核心参数。"""

    data_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._settings = QSettings("MaxTiC", "MaxTiC-Next-Studio")
        self._build_ui()
        self._connect_validation()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # ---- 物种树 ----
        self.group_input = QGroupBox(_("group_input"))
        tree_layout = QFormLayout(self.group_input)
        # 跨平台一致：macOS 默认字段列不扩展（FieldsStayAtSizeHint）会把
        # 输入框压成一条缝，显式让字段列随面板拉伸
        tree_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        tree_layout.setVerticalSpacing(M.FORM_SPACING)

        self.tree_edit = _DropLineEdit()
        self.tree_edit.setObjectName("treeEdit")
        self.tree_edit.setPlaceholderText(_("species_tree"))
        self.btn_browse_tree = QPushButton(_("button_browse"))
        self.btn_browse_tree.setObjectName("btn_small")
        self.btn_browse_tree.clicked.connect(self._browse_tree)
        tree_row = QHBoxLayout()
        tree_row.addWidget(self.tree_edit, 1)
        tree_row.addWidget(self.btn_browse_tree)
        tree_row_w = QWidget()
        tree_row_w.setLayout(tree_row)
        self.lbl_species_tree = QLabel(_("species_tree") + ":")
        # 建立 label → field buddy 关联，读屏软件可读出字段名
        self.lbl_species_tree.setBuddy(self.tree_edit)
        tree_layout.addRow(self.lbl_species_tree, tree_row_w)

        # ---- 约束文件列表 ----
        self.cons_list = QListWidget()
        self.cons_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.cons_list.setMinimumHeight(M.CONSTRAINT_LIST_H)
        self.btn_cons_add = QPushButton(_("button_add"))
        self.btn_cons_add.setObjectName("btn_small")
        self.btn_cons_remove = QPushButton(_("button_remove"))
        self.btn_cons_remove.setObjectName("btn_small")
        self.btn_cons_clear = QPushButton(_("button_clear"))
        self.btn_cons_clear.setObjectName("btn_small")
        self.btn_cons_add.clicked.connect(self._add_constraints)
        self.btn_cons_remove.clicked.connect(self._remove_constraints)
        self.btn_cons_clear.clicked.connect(self._clear_constraints)
        cons_buttons = QHBoxLayout()
        cons_buttons.addWidget(self.btn_cons_add)
        cons_buttons.addWidget(self.btn_cons_remove)
        cons_buttons.addWidget(self.btn_cons_clear)
        cons_buttons.addStretch()
        cons_buttons_w = QWidget()
        cons_buttons_w.setLayout(cons_buttons)
        self.lbl_constraints = QLabel(_("constraints") + ":")
        # buddy 关联
        self.lbl_constraints.setBuddy(self.cons_list)
        tree_layout.addRow(self.lbl_constraints, cons_buttons_w)
        tree_layout.addRow("", self.cons_list)

        # ---- 输出前缀 ----
        self.output_prefix_edit = QLineEdit()
        self.output_prefix_edit.setPlaceholderText(_("output_prefix_hint"))
        self.lbl_output_prefix = QLabel(_("output_prefix") + ":")
        # buddy 关联
        self.lbl_output_prefix.setBuddy(self.output_prefix_edit)
        tree_layout.addRow(self.lbl_output_prefix, self.output_prefix_edit)

        layout.addWidget(self.group_input)

        # ---- 核心参数 ----
        self.group_core = QGroupBox(_("group_core_params"))
        core_form = QFormLayout(self.group_core)
        core_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        core_form.setVerticalSpacing(M.FORM_SPACING)

        self.lbl_seed = QLabel(_("seed") + ":")
        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(0, 2**31 - 1)
        self.seed_spin.setValue(42)
        # buddy 关联
        self.lbl_seed.setBuddy(self.seed_spin)
        core_form.addRow(self.lbl_seed, self.seed_spin)

        self.lbl_local_search = QLabel(_("local_search") + ":")
        self.ls_spin = QDoubleSpinBox()
        self.ls_spin.setRange(0.0, 1e9)
        self.ls_spin.setDecimals(2)
        self.ls_spin.setSingleStep(0.5)
        self.ls_spin.setValue(0.0)
        self.ls_spin.setSuffix(" s")
        # buddy 关联
        self.lbl_local_search.setBuddy(self.ls_spin)
        core_form.addRow(self.lbl_local_search, self.ls_spin)

        self.lbl_temperature = QLabel(_("temperature") + ":")
        self.temp_spin = QDoubleSpinBox()
        self.temp_spin.setRange(0.0001, 1e6)
        self.temp_spin.setDecimals(6)
        self.temp_spin.setSingleStep(0.001)
        self.temp_spin.setValue(0.001)
        # buddy 关联
        self.lbl_temperature.setBuddy(self.temp_spin)
        core_form.addRow(self.lbl_temperature, self.temp_spin)

        self.lbl_random_type = QLabel(_("random_type") + ":")
        self.rtype_spin = QSpinBox()
        self.rtype_spin.setRange(0, 2)
        self.rtype_spin.setValue(0)
        # buddy 关联
        self.lbl_random_type.setBuddy(self.rtype_spin)
        core_form.addRow(self.lbl_random_type, self.rtype_spin)

        self.lbl_min_transfer_distance = QLabel(_("min_transfer_distance") + ":")
        self.dist_spin = QDoubleSpinBox()
        self.dist_spin.setRange(0.0, 1e9)
        self.dist_spin.setDecimals(2)
        self.dist_spin.setSingleStep(0.5)
        self.dist_spin.setValue(0.0)
        # buddy 关联
        self.lbl_min_transfer_distance.setBuddy(self.dist_spin)
        core_form.addRow(self.lbl_min_transfer_distance, self.dist_spin)

        self.lbl_threshold = QLabel(_("threshold_constraints") + ":")
        self.ts_spin = QDoubleSpinBox()
        self.ts_spin.setRange(0.0, 1.0)
        self.ts_spin.setDecimals(4)
        self.ts_spin.setSingleStep(0.05)
        self.ts_spin.setValue(0.0)
        # buddy 关联
        self.lbl_threshold.setBuddy(self.ts_spin)
        core_form.addRow(self.lbl_threshold, self.ts_spin)

        self.lbl_random_trees = QLabel(_("random_trees") + ":")
        self.rd_spin = QSpinBox()
        self.rd_spin.setRange(0, 2**31 - 1)
        self.rd_spin.setValue(0)
        # buddy 关联
        self.lbl_random_trees.setBuddy(self.rd_spin)
        core_form.addRow(self.lbl_random_trees, self.rd_spin)

        # 统一尺寸：高度取 metrics 令牌，和 QSS 绘制高度同源，
        # 布局会真正预留出这么多空间；统一宽度消除右侧参差感
        for spin in (
            self.seed_spin,
            self.ls_spin,
            self.temp_spin,
            self.rtype_spin,
            self.dist_spin,
            self.ts_spin,
            self.rd_spin,
        ):
            spin.setMinimumHeight(M.CONTROL_H)
            spin.setFixedWidth(180)

        layout.addWidget(self.group_core)
        layout.addStretch()

        # ---- 数据变更信号 ----
        for w in [self.tree_edit, self.output_prefix_edit]:
            w.textChanged.connect(self._on_changed)
        for w in [
            self.seed_spin,
            self.ls_spin,
            self.temp_spin,
            self.rtype_spin,
            self.dist_spin,
            self.ts_spin,
            self.rd_spin,
        ]:
            w.valueChanged.connect(self._on_changed)
        self.cons_list.model().rowsInserted.connect(self._on_changed)
        self.cons_list.model().rowsRemoved.connect(self._on_changed)

    def _connect_validation(self):
        # 移除永不可达的校验分支（QSpinBox 已钳制范围）
        # 保留 tree_edit 的文件存在性校验
        self.tree_edit.textChanged.connect(self._validate_tree)

    # ------------------------------------------------------------------
    # 即时校验
    # ------------------------------------------------------------------
    # 移除 _validate_temperature 和 _validate_seed
    # QSpinBox/QDoubleSpinBox 的 setRange 已钳制输入，这些校验永不可达
    def _validate_tree(self):
        v = self.tree_edit.text().strip()
        if not v:
            _set_error(self.tree_edit, True, _("err_no_species_tree"))
        elif not os.path.isfile(v):
            _set_error(self.tree_edit, True, _("err_file_not_found").format(v))
        else:
            _set_error(self.tree_edit, False)

    def validate(self) -> Optional[str]:
        """返回第一条错误文案（无错误返回 ``None``）。用于运行前即时反馈。"""
        # 移除永不可达的 temperature/seed 校验
        self._validate_tree()
        if self.tree_edit.property("error"):
            return self.tree_edit.toolTip()
        return None

    # ------------------------------------------------------------------
    # 文件选择（带目录记忆）
    # ------------------------------------------------------------------
    def _last_dir(self) -> str:
        return self._settings.value("last_dir", "", type=str) or ""

    def _remember_dir(self, path: str):
        d = os.path.dirname(path)
        if d:
            self._settings.setValue("last_dir", d)

    def _browse_tree(self):
        path, _selected_filter = QFileDialog.getOpenFileName(
            self, _("species_tree"), self._last_dir(), _("species_tree_filter")
        )
        if path:
            self.tree_edit.setText(path)
            self._remember_dir(path)

    def _add_constraints(self):
        paths, _selected_filter = QFileDialog.getOpenFileNames(
            self, _("constraints"), self._last_dir(), _("constraints_filter")
        )
        for p in paths:
            # 注意：findItems 返回列表，须用 len() 判空（.count 是方法对象，恒真值）
            if not self.cons_list.findItems(p, Qt.MatchExactly):
                self.cons_list.addItem(p)
            self._remember_dir(p)

    def _remove_constraints(self):
        for item in self.cons_list.selectedItems():
            self.cons_list.takeItem(self.cons_list.row(item))

    def _clear_constraints(self):
        self.cons_list.clear()

    def _on_changed(self, *args):
        self.data_changed.emit()

    # ------------------------------------------------------------------
    # 语言刷新
    # ------------------------------------------------------------------
    def retranslate(self):
        self.group_input.setTitle(_("group_input"))
        self.group_core.setTitle(_("group_core_params"))
        self.lbl_species_tree.setText(_("species_tree") + ":")
        self.lbl_constraints.setText(_("constraints") + ":")
        self.lbl_output_prefix.setText(_("output_prefix") + ":")
        self.lbl_seed.setText(_("seed") + ":")
        self.lbl_local_search.setText(_("local_search") + ":")
        self.lbl_temperature.setText(_("temperature") + ":")
        self.lbl_random_type.setText(_("random_type") + ":")
        self.lbl_min_transfer_distance.setText(_("min_transfer_distance") + ":")
        self.lbl_threshold.setText(_("threshold_constraints") + ":")
        self.lbl_random_trees.setText(_("random_trees") + ":")
        # 按钮 + 占位符同样纳入 retranslate，否则切语言后残留旧文案
        self.btn_browse_tree.setText(_("button_browse"))
        self.btn_cons_add.setText(_("button_add"))
        self.btn_cons_remove.setText(_("button_remove"))
        self.btn_cons_clear.setText(_("button_clear"))
        self.tree_edit.setPlaceholderText(_("species_tree"))
        self.output_prefix_edit.setPlaceholderText(_("output_prefix_hint"))

    # ------------------------------------------------------------------
    # 取值
    # ------------------------------------------------------------------
    @property
    def species_tree(self) -> str:
        return self.tree_edit.text().strip()

    @property
    def constraints(self) -> List[str]:
        return [self.cons_list.item(i).text() for i in range(self.cons_list.count())]

    @property
    def output_prefix(self) -> str:
        return self.output_prefix_edit.text()

    @property
    def seed(self) -> int:
        return self.seed_spin.value()

    @property
    def local_search(self) -> float:
        return self.ls_spin.value()

    @property
    def temperature(self) -> float:
        return self.temp_spin.value()

    @property
    def random_type(self) -> int:
        return self.rtype_spin.value()

    @property
    def min_transfer_distance(self) -> float:
        return self.dist_spin.value()

    @property
    def threshold_constraints(self) -> float:
        return self.ts_spin.value()

    @property
    def random_trees(self) -> int:
        return self.rd_spin.value()

    # ---- 赋值（加载配置 / 预设用） ----
    def set_values(self, values: dict):
        if "species_tree_path" in values:
            self.tree_edit.setText(values["species_tree_path"])
        if "constraints_path" in values:
            self.cons_list.clear()
            cons = values["constraints_path"]
            if isinstance(cons, str):
                cons = [cons]
            for c in cons:
                self.cons_list.addItem(c)
        if "output_prefix" in values:
            # 显式支持清空（重置默认 / 加载不含此前缀的配置时须能覆盖旧值）
            self.output_prefix_edit.setText(values["output_prefix"] or "")
        if "seed" in values:
            self.seed_spin.setValue(values["seed"])
        if "local_search" in values:
            self.ls_spin.setValue(values["local_search"])
        if "temperature" in values:
            self.temp_spin.setValue(values["temperature"])
        if "random_type" in values:
            self.rtype_spin.setValue(values["random_type"])
        if "min_transfer_distance" in values:
            self.dist_spin.setValue(values["min_transfer_distance"])
        if "threshold_constraints" in values:
            self.ts_spin.setValue(values["threshold_constraints"])
        if "random_trees" in values:
            self.rd_spin.setValue(values["random_trees"])
