"""主窗口：整合所有面板 + 菜单栏 + 运行控制 + QSettings。

布局：
```
┌──────────────────────────────────────────────────────────┐
│ 菜单：文件 | 运行 | 视图 | 设置 | 帮助                     │
├──────────────────────────────┬───────────────────────────┤
│  左侧：输入 + 核心参数        │  右侧：结果                │
│  [输入区]                     │  [排名表格]                │
│  [核心参数]                   │  [排名条形图]              │
│  [高级 ▸]（标签页折叠）       │  [报告按钮]                │
│  [输出前缀]                   │                           │
├──────────────────────────────┴───────────────────────────┤
│  [运行 ▶] [取消 ■]   状态：就绪                           │
│  ── 日志面板 ────────────────────────────────────────────│
└──────────────────────────────────────────────────────────┘
```
"""

from __future__ import annotations

import json
import os
import sys
from typing import Optional

from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStatusBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QTabWidget,
)

from . import metrics as M
from .i18n import _, get_language, set_language, available_languages
from maxtic_next.config import MCMC_TEMPERATURE_AUTO
from .params import (
    collect_params,
    params_to_json,
    json_to_params,
    params_to_cli_command,
    ValidationError,
)
from .run_engine import RunEngine
from .widgets.input_panel import InputPanel
from .widgets.advanced_panel import AdvancedPanel
from .widgets.log_panel import LogPanel
from .widgets.result_panel import ResultPanel


# 示例数据路径：源码运行时相对本文件向上 3 级到仓库根；
# 冻结为 .app（PyInstaller）时取随包内置的 examples/ 资源目录（见 packaging/maxtic_studio.spec）。
# PyInstaller 6.x 的 macOS bundle 里 _MEIPASS 指向 Contents/Frameworks，
# 而 datas 落在 Contents/Resources（实测 6.22），故两处连同可执行目录一起探测。
if getattr(sys, "frozen", False):
    _exe_dir = os.path.dirname(sys.executable)
    _frozen_bases = [
        getattr(sys, "_MEIPASS", ""),  # PyInstaller toplevel
        os.path.join(_exe_dir, os.pardir, "Resources"),  # .app 的 Contents/Resources
        _exe_dir,  # 无 bundle 的 onedir 兜底
    ]
    _PROJECT_ROOT = next(
        (
            os.path.normpath(base)
            for base in _frozen_bases
            if base and os.path.isdir(os.path.join(base, "examples"))
        ),
        os.path.normpath(getattr(sys, "_MEIPASS", "") or _exe_dir),
    )
else:
    # 源码运行：…/src/maxtic_studio/main_window.py → 上两级即仓库根
    _PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_EXAMPLE_TREE = os.path.join(_PROJECT_ROOT, "examples", "minitree.tree")
_EXAMPLE_CONSTRAINTS = os.path.join(_PROJECT_ROOT, "examples", "Cyano_CUTConstraints.tsv")

# 高级面板独占参数（预设注入时避免脏写输入面板键）
_ADV_ONLY_KEYS = {"mcmc", "mcmc_iters", "mcmc_temperature", "html_report"}

# 运行阶段文案 key（用于 i18n 即时刷新阶段标签）
_STAGE_KEYS = {"stage_running", "stage_render", "stage_loading_tree", "stage_ranking"}


def _language_label(code: str) -> str:
    """语言代码 → 按钮/菜单上显示的母语自称（不随界面语言变化）。"""
    return {"zh": "中文", "en": "English"}.get(code, code.upper())


def _scroll_area(inner: QWidget) -> QScrollArea:
    """把面板包进滚动区：内容高于视口时出滚动条，而不是让控件互相压字。"""
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    area.setWidget(inner)
    return area


# 一键填充预设。
# 预设里的 mcmc_temperature 统一取 0.0 = auto（按实例能量尺度推导，与 CLI 默认一致）：
# 0.01 / 0.001 正是链冻结、样本不构成后验采样的温度区间。
# 需要手动指定时，用户仍可在高级面板里填数值。
_PRESETS = {
    "quick": {
        "seed": 1,
        "local_search": 0.0,
        "temperature": 0.01,
        "random_type": 0,
        "min_transfer_distance": 0,
        "threshold_constraints": 0.0,
        "random_trees": 0,
        "mcmc": False,
        "mcmc_iters": 1000,
        "mcmc_temperature": MCMC_TEMPERATURE_AUTO,
        "html_report": True,
    },
    "standard": {
        "seed": 42,
        "local_search": 60.0,
        "temperature": 0.001,
        "random_type": 0,
        "min_transfer_distance": 0,
        "threshold_constraints": 0.0,
        "random_trees": 0,
        "mcmc": False,
        "mcmc_iters": 100000,
        "mcmc_temperature": MCMC_TEMPERATURE_AUTO,
        "html_report": True,
    },
    "strict": {
        "seed": 12345,
        "local_search": 300.0,
        "temperature": 0.0001,
        "random_type": 0,
        "min_transfer_distance": 1,
        "threshold_constraints": 0.1,
        "random_trees": 0,
        "mcmc": True,
        "mcmc_iters": 1000000,
        "mcmc_temperature": MCMC_TEMPERATURE_AUTO,
        "html_report": True,
    },
}


class MainWindow(QMainWindow):
    """MaxTiC-Next Studio 主窗口。"""

    def __init__(self):
        super().__init__()
        self._engine: Optional[RunEngine] = None

        self._load_settings()
        self._build_ui()
        self._build_menus()
        self._build_statusbar()
        self._refresh_pref_buttons()
        self._build_shortcuts()
        self._restore_geometry()

    def _build_shortcuts(self):
        """全局快捷键：Ctrl+Shift+L 切语言，Ctrl+Shift+D 切亮暗。"""
        from PySide6.QtGui import QShortcut

        QShortcut(QKeySequence("Ctrl+Shift+L"), self, self._toggle_language)
        QShortcut(
            QKeySequence("Ctrl+Shift+D"),
            self,
            lambda: self._set_dark_theme(not bool(QApplication.instance().property("maxTic-dark"))),
        )

    # ------------------------------------------------------------------
    # 设置
    # ------------------------------------------------------------------
    def _load_settings(self):
        self._settings = QSettings("MaxTiC", "MaxTiC-Next-Studio")
        lang = self._settings.value("language", "zh", type=str)
        set_language(lang)

    def _save_settings(self):
        self._settings.setValue("language", get_language())
        self._settings.setValue("geometry", self.saveGeometry())
        self._settings.setValue("windowState", self.saveState())

    def _restore_geometry(self):
        geom = self._settings.value("geometry")
        if geom:
            self.restoreGeometry(geom)
        state = self._settings.value("windowState")
        if state:
            self.restoreState(state)

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------
    def _build_ui(self):
        self.setWindowTitle(_("app_title"))
        # 左右两栏内容都包在 QScrollArea 里，窗口再矮也只会出滚动条，
        # 不会把控件压到彼此重叠，所以最小尺寸只需保证三层结构可交互。
        self.setMinimumSize(960, 620)

        central = QWidget()
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        # ---- 顶部：主操作 + 预设 + 语言 / 主题 + 进度/阶段 ----
        main_layout.addWidget(self._build_toolbar())

        # 上下分割：上面板区 + 日志区
        self.main_splitter = QSplitter(Qt.Orientation.Vertical)

        # 上半部分：左右分割
        top_splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧：单层 QTabWidget「基本设置 | 高级参数」，消除 Tab 套 Tab
        self.left_tabs = QTabWidget()
        self.left_tabs.setObjectName("leftTabs")
        self.left_tabs.setMinimumHeight(280)
        self.left_tabs.setMinimumWidth(420)

        # 基本设置页 = 输入面板 + CLI 实时预览
        basic_page = QWidget()
        basic_layout = QVBoxLayout(basic_page)
        basic_layout.setContentsMargins(8, 8, 8, 8)
        basic_layout.setSpacing(M.GROUP_SPACING)
        self.input_panel = InputPanel()
        basic_layout.addWidget(self.input_panel)
        basic_layout.addWidget(self._build_cli_preview())
        basic_layout.addStretch(1)
        self.left_tabs.addTab(_scroll_area(basic_page), _("tab_basic"))

        # 高级参数页（内部 7 个语义 tab 正常展开）
        self.advanced_panel = AdvancedPanel()
        self.left_tabs.addTab(_scroll_area(self.advanced_panel), _("group_advanced"))
        self._left_tab_keys = {0: "tab_basic", 1: "group_advanced"}

        top_splitter.addWidget(self.left_tabs)

        # 右侧：结果面板
        self.result_panel = ResultPanel()
        self.result_panel.setMinimumHeight(280)
        self.result_panel.setMinimumWidth(470)
        top_splitter.addWidget(self.result_panel)

        top_splitter.setStretchFactor(0, 2)
        top_splitter.setStretchFactor(1, 3)
        top_splitter.setSizes([480, 720])
        self.top_splitter = top_splitter
        self.main_splitter.addWidget(top_splitter)

        # 下半部分：日志（保留在底部，宽度回收给结果区）
        self.log_panel = LogPanel()
        self.log_panel.setMinimumHeight(120)
        self.main_splitter.addWidget(self.log_panel)

        # 按比例分配而非写死像素值，Qt 会按 stretch 归一化
        self.main_splitter.setStretchFactor(0, 3)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setSizes([600, 200])

        main_layout.addWidget(self.main_splitter)
        self.setCentralWidget(central)

        # 把 QSS 的绘制高度同步写成布局最小高度，避免"画得比预留的高"而重叠
        M.enforce_metrics(self)

        # 参数变更 → CLI 即时预览
        self.input_panel.data_changed.connect(self._update_cli_preview)
        self.advanced_panel.data_changed.connect(self._update_cli_preview)
        self._update_cli_preview()
        # 结果区空状态「用示例数据演示」按钮
        self.result_panel.demo_requested.connect(self._load_demo)

    def _build_toolbar(self) -> QWidget:
        """顶部工具条：运行 / 取消 / 预设 / 语言 / 主题 / 进度 / 状态。"""
        tool = QWidget()
        tl = QHBoxLayout(tool)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(M.FIELD_SPACING)

        self.btn_run = QPushButton(_("button_run"))
        self.btn_run.setObjectName("btn_run")
        self.btn_run.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_run.clicked.connect(self._on_run)
        self.btn_cancel = QPushButton(_("button_cancel_run"))
        self.btn_cancel.setObjectName("btn_cancel")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._on_cancel)

        # 预设
        self.lbl_preset = QLabel(_("preset") + ":")
        self.preset_combo = QComboBox()
        self.preset_combo.addItem(_("preset_placeholder"))
        self.preset_combo.addItem(_("preset_quick"))
        self.preset_combo.addItem(_("preset_standard"))
        self.preset_combo.addItem(_("preset_strict"))
        self.preset_combo.currentIndexChanged.connect(self._apply_preset)
        self.btn_reset = QPushButton(_("button_reset_default"))
        self.btn_reset.setObjectName("btn_small")
        self.btn_reset.clicked.connect(self._reset_defaults)

        # 语言 / 主题：常驻工具条的可见切换入口（菜单里同时保留，快捷键也在这里）
        self.btn_language = self._build_language_button()
        self.btn_theme = self._build_theme_button()

        # 阶段 / 进度 / 状态
        self.stage_label = QLabel("")
        self.stage_label.setObjectName("stageLabel")
        self.stage_label.setVisible(False)
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedWidth(180)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        self.status_label = QLabel(_("status_ready"))
        self.status_label.setObjectName("statusLabel")
        # 状态文案只放短词；长消息（示例数据路径等）走底部状态栏，
        # 否则它会把整条工具条挤成一团
        self.status_label.setMaximumWidth(160)

        tl.addWidget(self.btn_run)
        tl.addWidget(self.btn_cancel)
        tl.addSpacing(12)
        tl.addWidget(self.lbl_preset)
        tl.addWidget(self.preset_combo)
        tl.addWidget(self.btn_reset)
        tl.addStretch()
        tl.addWidget(self.btn_language)
        tl.addWidget(self.btn_theme)
        tl.addSpacing(12)
        tl.addWidget(self.stage_label)
        tl.addWidget(self.progress_bar)
        tl.addWidget(self.status_label)
        return tool

    def _build_language_button(self) -> QToolButton:
        btn = QToolButton()
        btn.setObjectName("btn_pref")
        btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        btn.setToolTip(_("tooltip_language"))
        menu = QMenu(btn)
        self._lang_actions = {}
        for lang in available_languages():
            act = QAction(_language_label(lang), self)
            act.setCheckable(True)
            act.triggered.connect(lambda checked, lang_=lang: self._switch_language(lang_))
            menu.addAction(act)
            self._lang_actions[lang] = act
        btn.setMenu(menu)
        return btn

    def _build_theme_button(self) -> QToolButton:
        btn = QToolButton()
        btn.setObjectName("btn_pref")
        btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        btn.setToolTip(_("tooltip_theme"))
        menu = QMenu(btn)
        self._theme_actions = {
            False: menu.addAction(_("theme_mode_light")),
            True: menu.addAction(_("theme_mode_dark")),
        }
        for is_dark, act in self._theme_actions.items():
            act.setCheckable(True)
            act.triggered.connect(lambda checked, dark_=is_dark: self._set_dark_theme(dark_))
        btn.setMenu(menu)
        return btn

    def _refresh_pref_buttons(self):
        """同步语言 / 主题按钮的文案与勾选态。"""
        lang = get_language()
        self.btn_language.setText(_language_label(lang))
        for code, act in self._lang_actions.items():
            act.setText(_language_label(code))
            act.setChecked(code == lang)

        app = QApplication.instance()
        dark = bool(app.property("maxTic-dark")) if app is not None else False
        self.btn_theme.setText(
            ("☾ " if dark else "☀ ") + (_("theme_mode_dark") if dark else _("theme_mode_light"))
        )
        for is_dark, act in self._theme_actions.items():
            act.setChecked(is_dark == dark)

    def _build_cli_preview(self) -> QWidget:
        """CLI 命令实时预览框（只读，便于复现）。"""
        box = QGroupBox(_("cli_preview"))
        bl = QVBoxLayout(box)
        bl.setContentsMargins(8, 8, 8, 8)
        self.cli_preview_edit = QPlainTextEdit()
        self.cli_preview_edit.setObjectName("cliPreview")
        self.cli_preview_edit.setReadOnly(True)
        self.cli_preview_edit.setMinimumHeight(M.CLI_PREVIEW_H)
        self.cli_preview_edit.setMaximumHeight(M.CLI_PREVIEW_H)
        self.cli_preview_edit.setPlaceholderText(_("cli_preview_hint"))
        self.cli_preview_edit.setFont(M.font(M.FONT_MONO_PT, mono=True))
        bl.addWidget(self.cli_preview_edit)
        return box

    def _update_cli_preview(self):
        params = self._collect_all_params_unsafe()
        # 尚未选择物种树时显示占位提示，避免出现 maxtic-next "" 的半成品命令
        if not params.get("species_tree_path"):
            self.cli_preview_edit.setPlainText("")
            return
        try:
            cmd = params_to_cli_command(params)
        except Exception:
            cmd = ""
        self.cli_preview_edit.setPlainText(cmd)

    # ------------------------------------------------------------------
    # 预设 / 重置默认
    # ------------------------------------------------------------------
    def _apply_preset(self, idx: int):
        if idx < 1 or idx > 3:
            return
        # 按索引映射，避免依赖随语言变化的下拉项文案
        key = {1: "quick", 2: "standard", 3: "strict"}[idx]
        vals = _PRESETS[key]
        self.input_panel.set_values(vals)
        self.advanced_panel.set_values({k: v for k, v in vals.items() if k in _ADV_ONLY_KEYS})
        self._update_cli_preview()
        # 回到占位，避免二次误触
        self.preset_combo.blockSignals(True)
        self.preset_combo.setCurrentIndex(0)
        self.preset_combo.blockSignals(False)

    def _reset_defaults(self):
        from .params import _default_params

        d = _default_params()
        self.input_panel.set_values(d)
        self.advanced_panel.set_values(d)
        self._update_cli_preview()

    def _build_menus(self):
        menubar = self.menuBar()

        # ---- 文件 ----
        file_menu = menubar.addMenu(_("menu_file"))
        self.action_open_config = QAction(_("action_open_config"), self)
        self.action_open_config.setShortcut(QKeySequence("Ctrl+O"))
        self.action_open_config.triggered.connect(self._open_config)
        file_menu.addAction(self.action_open_config)

        self.action_save_config = QAction(_("action_save_config"), self)
        self.action_save_config.setShortcut(QKeySequence("Ctrl+S"))
        self.action_save_config.triggered.connect(self._save_config)
        file_menu.addAction(self.action_save_config)

        file_menu.addSeparator()
        action_exit = QAction(_("action_exit"), self)
        action_exit.setShortcut(QKeySequence("Ctrl+Q"))
        action_exit.triggered.connect(self.close)
        file_menu.addAction(action_exit)

        # ---- 运行 ----
        run_menu = menubar.addMenu(_("menu_run"))
        self.action_start = QAction(_("action_start"), self)
        self.action_start.setShortcut(QKeySequence("Ctrl+R"))
        self.action_start.triggered.connect(self._on_run)
        run_menu.addAction(self.action_start)

        self.action_cancel = QAction(_("action_cancel"), self)
        self.action_cancel.triggered.connect(self._on_cancel)
        run_menu.addAction(self.action_cancel)

        run_menu.addSeparator()
        self.action_demo = QAction(_("action_demo"), self)
        self.action_demo.triggered.connect(self._load_demo)
        run_menu.addAction(self.action_demo)

        # ---- 视图 ----
        view_menu = menubar.addMenu(_("menu_view"))
        self.action_toggle_log = QAction(_("action_toggle_log"), self)
        self.action_toggle_log.setCheckable(True)
        self.action_toggle_log.setChecked(True)
        self.action_toggle_log.toggled.connect(self._toggle_log)
        view_menu.addAction(self.action_toggle_log)

        action_reset_layout = QAction(_("action_reset_layout"), self)
        action_reset_layout.triggered.connect(self._reset_layout)
        view_menu.addAction(action_reset_layout)

        # ---- 设置 ----
        settings_menu = menubar.addMenu(_("menu_settings"))
        lang_menu = settings_menu.addMenu(_("action_language"))
        for lang in available_languages():
            action = QAction(_language_label(lang), self)
            action.setCheckable(True)
            action.setChecked(get_language() == lang)
            action.triggered.connect(lambda checked, lang_=lang: self._switch_language(lang_))
            lang_menu.addAction(action)

        # 深色主题切换
        theme_action = QAction(_("action_dark_theme"), self)
        theme_action.setCheckable(True)
        app = QApplication.instance()
        theme_action.setChecked(bool(app.property("maxTic-dark")) if app else False)
        theme_action.toggled.connect(self._toggle_dark_theme)
        settings_menu.addAction(theme_action)
        self.theme_action = theme_action

        # ---- 帮助 ----
        help_menu = menubar.addMenu(_("menu_help"))
        action_about = QAction(_("action_about"), self)
        action_about.triggered.connect(self._show_about)
        help_menu.addAction(action_about)

        action_cli_docs = QAction(_("action_cli_docs"), self)
        action_cli_docs.triggered.connect(self._open_cli_docs)
        help_menu.addAction(action_cli_docs)

        action_check_update = QAction(_("action_check_update"), self)
        action_check_update.triggered.connect(self._check_update)
        help_menu.addAction(action_check_update)

    def _build_statusbar(self):
        self.setStatusBar(QStatusBar())

    # ------------------------------------------------------------------
    # 运行控制
    # ------------------------------------------------------------------
    def _collect_all_params(self) -> dict:
        """从所有面板收集参数。"""
        ip = self.input_panel
        ap = self.advanced_panel
        return collect_params(
            species_tree=ip.species_tree,
            constraints=ip.constraints,
            seed=ip.seed,
            local_search=ip.local_search,
            temperature=ip.temperature,
            random_type=ip.random_type,
            min_transfer_distance=ip.min_transfer_distance,
            threshold_constraints=ip.threshold_constraints,
            random_trees=ip.random_trees,
            output_prefix=ip.output_prefix,
            # ALE
            from_ale=ap.from_ale,
            ale_min_support=ap.ale_min_support_val,
            ale_min_family_size=ap.ale_min_family_size_val,
            ale_cache_dir=ap.ale_cache_dir_val,
            ale_source=ap.ale_source_val,
            ale_parallel=ap.ale_parallel_val,
            # 上游适配器（工具选择 + 诊断阈值）
            from_tool=ap.from_tool_val,
            artra_transfer_kind=ap.artra_transfer_kind_val,
            adapter_min_endpoint_hit_rate=ap.adapter_min_endpoint_hit_rate_val,
            adapter_quiet=ap.adapter_quiet_val,
            # pruning
            target_clade=ap.target_clade_val,
            target_clade_ancestor_map=ap.ancestor_map_val,
            # run mode
            dry_run=ap.dry_run_val,
            generate_html_report=ap.generate_html_report_val,
            # mcmc
            mcmc=ap.mcmc_val,
            mcmc_iters=ap.mcmc_iters_val,
            mcmc_temperature=ap.mcmc_temperature_val,
            # performance
            incremental=ap.incremental_val,
            checkpoint_path=ap.checkpoint_path_val,
            checkpoint_interval=ap.checkpoint_interval_val,
            # two-phase
            constraints_out=ap.constraints_out_val,
            # output
            output_style=ap.output_style_val,
        )

    def _on_run(self):
        """点击运行。"""
        # 先刷新红框态，让错误输入在弹窗之外也有视觉定位
        self.input_panel.validate()
        try:
            params = self._collect_all_params()
        except ValidationError as e:
            # 错误消息可能是 i18n key（如 "err_no_species_tree"）或 "key:arg" 格式
            parts = str(e).split(":", 1)
            if len(parts) == 2:
                msg = _(parts[0]).format(parts[1])
            else:
                msg = _(parts[0])
            QMessageBox.warning(self, _("app_title"), msg)
            return

        # 切换 UI 状态
        self._set_running(True)
        self.log_panel.clear_log()
        self.result_panel.clear_results()

        # 启动线程
        self._engine = RunEngine(params, parent=self)
        self._engine.log_message.connect(self.log_panel.append_line)
        self._engine.stage_changed.connect(self._update_stage)
        self._engine.finished_ok.connect(self._on_finished_ok)
        self._engine.finished_err.connect(self._on_finished_err)
        self._engine.cancelled.connect(self._on_cancelled)
        self._engine.start()

    def _update_stage(self, key: str):
        text = _(key) if key in _STAGE_KEYS else key
        self.stage_label.setText(text)
        self.stage_label.setVisible(bool(key))

    def _on_cancel(self):
        if self._engine and self._engine.isRunning():
            reply = QMessageBox.question(
                self,
                _("app_title"),
                _("confirm_cancel"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._engine.cancel()
                self.status_label.setText(_("status_running") + " → " + _("status_cancelled"))

    def _on_finished_ok(self, result, elapsed: float):
        self._set_running(False)
        self.status_label.setText(_("status_done"))
        self.result_panel.update_result(result, elapsed=elapsed)

    def _on_finished_err(self, msg):
        self._set_running(False)
        self.status_label.setText(_("status_error"))
        self.result_panel.show_error(_("error_card_text"))
        self.log_panel.append_line(f"ERROR: {msg}")
        QMessageBox.critical(self, _("app_title"), msg)

    def _on_cancelled(self):
        self._set_running(False)
        self.status_label.setText(_("status_cancelled"))

    def _set_running(self, running: bool):
        self.btn_run.setEnabled(not running)
        self.btn_cancel.setEnabled(running)
        self.action_start.setEnabled(not running)
        # 无确定进度 → 用 indeterminate 动画（进度条转圈）
        self.progress_bar.setRange(0, 0 if running else 100)
        self.progress_bar.setVisible(running)
        if not running:
            self.progress_bar.setValue(0)
            self.stage_label.setVisible(False)
        if not running:
            self.status_label.setText(_("status_ready"))

    # ------------------------------------------------------------------
    # 配置导入导出
    # ------------------------------------------------------------------
    def _save_config(self):
        try:
            params = self._collect_all_params()
        except ValidationError:
            params = self._collect_all_params_unsafe()

        path, _selected_filter = QFileDialog.getSaveFileName(
            self, _("dialog_save_config_title"), "maxtic-config.json", "JSON (*.json)"
        )
        if not path:
            return
        # 配置文件写入加异常兜底
        try:
            data = params_to_json(params)
            data["_cli_command"] = params_to_cli_command(params)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except (OSError, TypeError, ValueError) as exc:
            QMessageBox.critical(self, _("app_title"), _("err_config_write").format(exc))

    def _collect_all_params_unsafe(self) -> dict:
        """与 ``_collect_all_params`` 类似但不校验（用于保存半成品配置）。"""
        ip = self.input_panel
        ap = self.advanced_panel
        params = {
            "species_tree_path": ip.species_tree,
            "constraints_path": ip.constraints if ip.constraints else [],
            "seed": ip.seed,
            "local_search": ip.local_search,
            "temperature": ip.temperature,
            "random_type": ip.random_type,
            "min_transfer_distance": ip.min_transfer_distance,
            "threshold_constraints": ip.threshold_constraints,
            "random_trees": ip.random_trees,
            "output_prefix": ip.output_prefix.strip() or None,
            "from_ale": ap.from_ale,
            "ale_min_support": ap.ale_min_support_val,
            "ale_min_family_size": ap.ale_min_family_size_val,
            "ale_cache_dir": ap.ale_cache_dir_val.strip() or None,
            "ale_source": ap.ale_source_val,
            "ale_parallel": ap.ale_parallel_val,
            "from_tool": ap.from_tool_val,
            "artra_transfer_kind": ap.artra_transfer_kind_val,
            "adapter_min_endpoint_hit_rate": ap.adapter_min_endpoint_hit_rate_val,
            "adapter_quiet": ap.adapter_quiet_val,
            "target_clade": ap.target_clade_val.strip() or None,
            "ancestor_map": ap.ancestor_map_val,
            "dry_run": ap.dry_run_val,
            "html_report": ap.generate_html_report_val,
            "mcmc": ap.mcmc_val,
            "mcmc_iters": ap.mcmc_iters_val,
            "mcmc_temperature": ap.mcmc_temperature_val,
            "incremental": ap.incremental_val,
            "checkpoint_path": ap.checkpoint_path_val.strip() or None,
            "checkpoint_interval": ap.checkpoint_interval_val,
            "constraints_out": ap.constraints_out_val.strip() or None,
            "output_style": ap.output_style_val,
        }
        return params

    def _open_config(self):
        path, _selected_filter = QFileDialog.getOpenFileName(
            self, _("dialog_open_config_title"), "", "JSON (*.json)"
        )
        if not path:
            return
        # 配置文件读取加异常兜底
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            QMessageBox.critical(self, _("app_title"), _("err_config_read").format(exc))
            return
        data.pop("_cli_command", None)
        try:
            params = json_to_params(data)
        except Exception as exc:
            QMessageBox.critical(self, _("app_title"), _("err_config_read").format(exc))
            return
        self.input_panel.set_values(params)
        self.advanced_panel.set_values(params)

    # ------------------------------------------------------------------
    # 演示数据
    # ------------------------------------------------------------------
    def _load_demo(self):
        """加载 examples/ 示例数据。"""
        tree = _EXAMPLE_TREE
        cons = _EXAMPLE_CONSTRAINTS
        if not os.path.isfile(tree) or not os.path.isfile(cons):
            # 使用 i18n key 替代硬编码英文
            QMessageBox.warning(self, _("app_title"), _("err_demo_missing").format(tree, cons))
            return
        self.input_panel.tree_edit.setText(tree)
        self.input_panel.cons_list.clear()
        self.input_panel.cons_list.addItem(cons)
        # 长文案进底部状态栏：工具条状态标签只放短词，避免把工具条挤变形
        self.statusBar().showMessage(_("demo_loaded").format(tree, cons), 10000)
        self.status_label.setText(_("status_ready"))

    # ------------------------------------------------------------------
    # 视图
    # ------------------------------------------------------------------
    def _toggle_log(self, visible: bool):
        self.log_panel.setVisible(visible)

    def _reset_layout(self):
        # 与初始分割比例保持一致（上面板区 / 日志区，左栏 / 右栏）
        self.main_splitter.setSizes([600, 200])
        self.top_splitter.setSizes([480, 720])

    # ------------------------------------------------------------------
    # 语言切换（即时刷新）
    # ------------------------------------------------------------------
    def _switch_language(self, lang: str):
        if lang == get_language():
            return
        set_language(lang)
        self._settings.setValue("language", lang)
        self._apply_language()

    def _toggle_language(self):
        """在已支持的语言间循环（快捷键用）。"""
        langs = available_languages()
        if len(langs) < 2:
            return
        nxt = langs[(langs.index(get_language()) + 1) % len(langs)]
        self._switch_language(nxt)

    def _apply_language(self):
        """切语言后即时刷新全部控件与菜单，不弹「请重启」对话框。"""
        self.setWindowTitle(_("app_title"))
        # 工具条
        self.btn_run.setText(_("button_run"))
        self.btn_cancel.setText(_("button_cancel_run"))
        self.lbl_preset.setText(_("preset") + ":")
        for i, key in enumerate(
            ["preset_placeholder", "preset_quick", "preset_standard", "preset_strict"]
        ):
            self.preset_combo.setItemText(i, _(key))
        self.btn_reset.setText(_("button_reset_default"))
        self.btn_language.setToolTip(_("tooltip_language"))
        self.btn_theme.setToolTip(_("tooltip_theme"))
        self.status_label.setText(_("status_ready"))
        # CLI 预览组标题
        box = self.cli_preview_edit.parentWidget()
        while box is not None and not isinstance(box, QGroupBox):
            box = box.parentWidget()
        if box is not None:
            box.setTitle(_("cli_preview"))
            self.cli_preview_edit.setPlaceholderText(_("cli_preview_hint"))
        # 左侧单 Tab 标题
        for idx, key in self._left_tab_keys.items():
            self.left_tabs.setTabText(idx, _(key))
        # 各面板
        self.input_panel.retranslate()
        self.advanced_panel.retranslate()
        self.log_panel.retranslate()
        self.result_panel.retranslate()
        # 重建菜单（含语言动作勾选状态）
        self.menuBar().clear()
        self._build_menus()
        self._refresh_pref_buttons()
        # 文案长度随语言变化，重新量一次最小高度，避免换语言后又挤上
        M.enforce_metrics(self)
        self._update_cli_preview()

    # ------------------------------------------------------------------
    # 亮 / 暗主题切换
    # ------------------------------------------------------------------
    def _set_dark_theme(self, dark: bool):
        from .theme import apply_theme

        app = QApplication.instance()
        if app is None:
            return
        if bool(app.property("maxTic-dark")) == dark:
            return
        apply_theme(app, dark)
        self._settings.setValue("theme_dark", dark)
        if getattr(self, "theme_action", None) is not None:
            self.theme_action.setChecked(dark)
        self._refresh_pref_buttons()
        # 图表配色取自主题令牌，切换后需重绘才能跟上新主题
        self.result_panel.on_theme_changed()

    def _toggle_dark_theme(self, dark: bool):
        """菜单项（checkable）入口。"""
        self._set_dark_theme(dark)

    # ------------------------------------------------------------------
    # 帮助
    # ------------------------------------------------------------------
    def _show_about(self):
        from maxtic_next import __version__ as core_version
        from . import __version__ as studio_version

        msg = _("dialog_about_text").format(studio_version, core_version)
        QMessageBox.about(self, _("dialog_about_title"), msg)

    def _open_cli_docs(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        QDesktopServices.openUrl(QUrl("https://github.com/ZengZichao/MaxTiC-Next"))

    def _check_update(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        QDesktopServices.openUrl(QUrl("https://github.com/ZengZichao/MaxTiC-Next/releases"))

    # ------------------------------------------------------------------
    # 关闭事件
    # ------------------------------------------------------------------
    def closeEvent(self, event):
        self._save_settings()
        if self._engine and self._engine.isRunning():
            # 请求中断 + 取消标志，等待后仍在运行时给用户选择
            self._engine.requestInterruption()
            self._engine.cancel()
            if not self._engine.wait(5000):
                box = QMessageBox(self)
                box.setWindowTitle(_("app_title"))
                box.setText(_("task_still_running"))
                box.setInformativeText(_("task_still_running_hint"))
                box.setStandardButtons(
                    QMessageBox.StandardButton.Close | QMessageBox.StandardButton.Cancel
                )
                if box.exec() != QMessageBox.StandardButton.Close:
                    event.ignore()
                    return
                # 最后手段：强制终止线程
                self._engine.terminate()
                self._engine.wait()
        event.accept()
