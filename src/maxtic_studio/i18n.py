"""轻量 dict 式国际化（i18n）。

采用简单 dict 映射，而非 Qt Linguist（``.ts``/``.qm``）全工具链——
对小体量 GUI 更简单、无需额外构建步骤。所有控件文案通过 ``_(key)`` 获取，
按当前语言返回 zh / en 文案。语言偏好存入 ``QSettings``，重启保留。

用法::

    from maxtic_studio.i18n import _, set_language, get_language

    set_language("zh")        # 切换为中文
    print(_("species_tree"))  # "物种树"
    set_language("en")        # 切换为英文
    print(_("species_tree"))  # "Species Tree"
"""

from __future__ import annotations

from typing import Dict

# ---------------------------------------------------------------------------
# 当前语言状态
# ---------------------------------------------------------------------------
_current: str = "zh"

# ---------------------------------------------------------------------------
# 翻译表
# ---------------------------------------------------------------------------
# 两个 dict 的 key 完全一致；遗漏的 key 回退到 key 本身。

_ZH: Dict[str, str] = {
    # ---- 窗口标题 / 菜单 ----
    "app_title": "MaxTiC-Next Studio",
    "menu_file": "文件",
    "menu_run": "运行",
    "menu_view": "视图",
    "menu_settings": "设置",
    "menu_help": "帮助",
    "action_open_config": "打开配置(JSON)…",
    "action_save_config": "保存配置(JSON)…",
    "action_exit": "退出",
    "action_start": "开始",
    "action_cancel": "取消",
    "action_demo": "用示例数据演示",
    "action_toggle_log": "切换日志可见",
    "action_reset_layout": "重置布局",
    "action_language": "语言",
    "action_about": "关于",
    "action_cli_docs": "打开 CLI 文档",
    "action_check_update": "检查更新",
    # ---- 输入面板 ----
    "group_input": "输入",
    "species_tree": "物种树",
    "species_tree_filter": "Newick 树文件 (*.tree *.nwk *.newick *.tre);;所有文件 (*)",
    "constraints": "约束",
    "constraints_filter": "约束文件 (*.tsv *.txt *.csv);;所有文件 (*)",
    "button_browse": "浏览…",
    "button_add": "+ 添加",
    "button_remove": "- 删除",
    "button_clear": "清空",
    # ---- 核心参数 ----
    "group_core_params": "核心参数",
    "seed": "随机种子",
    "local_search": "局部搜索时长 (秒)",
    "temperature": "Metropolis 温度",
    "random_type": "随机化类型",
    "min_transfer_distance": "最小转移距离",
    "threshold_constraints": "约束权重阈值",
    "random_trees": "随机树采样数",
    # ---- 主窗口标签页 / 工具条 ----
    "tab_basic": "基本设置",
    "preset": "预设",
    "preset_quick": "快速",
    "preset_standard": "标准",
    "preset_strict": "严谨",
    "preset_placeholder": "选择预设…",
    "button_reset_default": "重置默认",
    "cli_preview": "实时 CLI 命令",
    "cli_preview_hint": "边填边预览可复现的命令（只读）…",
    "action_dark_theme": "深色主题",
    # ---- 工具条上的语言 / 主题切换控件 ----
    "lang_display_zh": "中文",
    "lang_display_en": "English",
    "tooltip_language": "界面语言：在中文 / English 之间切换",
    "theme_mode_light": "浅色",
    "theme_mode_dark": "深色",
    "tooltip_theme": "界面主题：在亮色 / 暗色之间切换",
    # ---- 高级参数 ----
    "group_advanced": "高级参数",
    "tab_adapters": "上游适配器",
    "adapter_tool_none": "无（按 MaxTiC 原生格式读约束）",
    "adapter_tool_auto": "自动检测",
    "adapter_tool_ale": "ALE",
    "adapter_tool_ranger": "RANGER-DTLx",
    "adapter_tool_eccetera": "ecceTERA",
    "adapter_tool_artra": "ARTra",
    "adapter_tool_alerax": "AleRax",
    "adapter_hint_none": ("未启用适配器：约束按 MaxTiC 原生 TSV 解析，下方参数没有适用对象。"),
    "adapter_hint_auto": (
        "自动检测：按内容/扩展名识别上游工具并分发；混合输入会额外做端点口径与权重量纲一致性检查。"
    ),
    "adapter_hint_ale": (
        "ALE：把 .uml_rec 调和文件经基因树家族推导为约束。"
        "该适配器不读端点命中率阈值，故不显示该项。"
    ),
    "adapter_hint_ranger": "RANGER-DTLx：解析其 DTL 输出为约束。",
    "adapter_hint_eccetera": "ecceTERA：解析其事件列表为约束。",
    "adapter_hint_artra": "ARTra：解析其转移列表为约束，可限定统计的转移类别。",
    "adapter_hint_alerax": "AleRax：解析其基因树 / 调度输出为约束。",
    "adapter_min_endpoint_hit_rate": "最小端点命中率",
    "adapter_quiet": "静默适配器诊断",
    "tab_pruning": "剪裁",
    "tab_run_mode": "运行模式",
    "tab_mcmc": "MCMC",
    "tab_checkpoint": "检查点",
    "tab_output": "输出",
    "ale_min_support": "最小支持度",
    "ale_min_family_size": "最小家族规模",
    "ale_cache_dir": "缓存目录",
    "ale_source": "约束来源口径",
    "ale_parallel": "并行模式",
    "from_tool": "上游工具适配器",
    "from_tool_none": "无",
    "artra_transfer_kind": "ARTra 转移类别",
    "target_clade": "目标类群根节点",
    "target_clade_ancestor_map": "外部祖先映射到根",
    "dry_run": "仅预检不运行",
    "generate_html_report": "生成交互式 HTML 报告",
    "mcmc": "开启 MCMC 采样",
    "mcmc_iters": "MCMC 迭代次数",
    "mcmc_temperature": "MCMC 温度",
    "mcmc_temperature_auto": "auto（按实例能量尺度推导）",
    "incremental": "启用增量 scoring",
    "checkpoint_path": "检查点文件路径",
    "checkpoint_interval": "检查点保存间隔 (秒)",
    "constraints_out": "约束输出路径（两阶段）",
    "output_prefix": "输出前缀",
    "output_prefix_hint": "留空 = 自动取约束文件名",
    "output_style": "输出文件命名风格",
    # ---- 运行控制 ----
    "button_run": "运行 ▶",
    "button_cancel_run": "取消 ■",
    "status_ready": "就绪",
    "status_running": "运行中…",
    "status_done": "完成",
    "status_error": "出错",
    "status_cancelled": "已取消",
    "stage_loading_tree": "加载物种树…",
    "stage_ranking": "排名中…",
    "stage_running": "运行中…",
    "stage_render": "渲染结果…",
    "error_card_hint": "详情见底部日志。可尝试修正红色标记的输入。",
    # ---- 日志面板 ----
    "group_log": "日志",
    "log_copy": "复制",
    "log_clear": "清空",
    "log_save": "保存",
    # ---- 结果面板 ----
    "group_results": "结果",
    "tab_table": "排名表",
    "tab_chart": "排名图",
    "col_rank": "排名",
    "col_node": "节点标签",
    # ：这不是"MTC 分数"，而是"把该节点移到序首 / 序尾时目标函数的变化量"
    "col_value": "Δ目标值（移序首/移序尾）",
    "col_informative": "信息性",
    "button_open_report": "在外部浏览器打开 HTML 报告",
    "button_export_csv": "导出 CSV",
    "button_export_png": "导出 PNG",
    "button_export_pdf": "导出 PDF",
    "no_results": "尚无结果。运行排序后此处显示排名表与图。",
    "empty_guide_title": "还没有结果",
    "empty_guide_steps": "\n① 选择物种树文件\n② 添加约束文件\n③ 点击「运行」开始排序",
    "metric_ranked": "排名节点数",
    "metric_informative": "信息性节点",
    "metric_conflicts": "冲突数",
    "metric_time": "用时",
    "error_card_text": "运行失败，请查看底部日志。",
    "chart_unavailable": "图表组件不可用：未安装 matplotlib。\n排名表仍可正常查看与导出。",
    "chart_title": "节点位置敏感性（移到序首/序尾的目标值变化幅度）",
    "chart_axis_score": "目标值变化幅度（非 MTC 分数）",
    # ：逐节点量的 tooltip（明确它不是 MTC 分数）
    "tooltip_node_impact": (
        "目标值变化：把本节点移到「序首 / 序尾」后被违反的"
        "信息性约束权重和的变化量\n"
        "（负值 = 更一致；MaxTiC 未定义逐节点 MTC 分数）"
    ),
    "tooltip_impact_front": "移到序首",
    "tooltip_impact_back": "移到序尾",
    "tooltip_impact_degenerate": "节点数 < 3：移到序首与序尾是同一操作",
    "legend_informative": "信息性",
    "legend_non_informative": "非信息性",
    # ---- 校验消息 ----
    "err_no_species_tree": "请选择物种树文件",
    "err_no_constraints": "请添加至少一个约束文件",
    "err_file_not_found": "文件不存在: {}",
    "err_seed_negative": "随机种子不能为负数",
    "err_temperature_zero": "温度必须大于 0",
    # ：与 CLI 同口径的参数域校验
    "err_random_type": "随机化类型只能取 0 / 1 / 2",
    "err_threshold_constraints": "阈值比例 threshold-constraints 必须落在 [0, 1]",
    "err_local_search_negative": "局部搜索时长 local-search 不能为负数",
    "err_near_optimal_top_k": (
        "近优解收集容量 near-optimal-top-k 必须是 >= 1 的整数"
        "（0 个近优排序无法构成稳健性/敏感性摘要）"
    ),
    "err_mcmc_iters": "MCMC 步数 mcmc-iters 必须是正整数",
    "err_mcmc_thin": "MCMC 抽稀间隔 mcmc-thin 必须 >= 1",
    "err_ale_source": "ALE 约束来源只能是 rec 或 trf",
    "err_min_endpoint_hit_rate": ("上游端点命中率阈值 min-endpoint-hit-rate 必须落在 [0, 1]"),
    "err_output_style": "输出命名风格只能是 short 或 legacy",
    "err_invalid_number": "无效的数值: {}",
    "err_config_read": "配置文件读取失败：{}",
    "err_config_write": "配置文件保存失败：{}",
    "err_demo_missing": "示例文件未找到:\n{}\n{}",
    "log_cancel_requested": "已请求取消：将在局部搜索的下一次迭代边界停止。",
    "log_cancel_unsupported": (
        "当前内核版本不接受取消回调，取消只能在阶段边界生效"
        "（长 local-search 任务会跑完当前阶段后丢弃结果）。"
    ),
    "log_stdout_contended": (
        "stdout 捕获已被另一个任务占用：本任务改为在结束后"
        "直接渲染结果摘要，避免两个任务的日志互相串台。"
    ),
    "task_still_running": "任务仍在运行中",
    "task_still_running_hint": "等待 5 秒后任务仍未完成。是否强制关闭窗口？强制关闭可能丢失数据。",
    "yes": "是",
    "no": "否",
    # ---- 对话框 ----
    "dialog_about_title": "关于 MaxTiC-Next Studio",
    "dialog_about_text": (
        "<h3>MaxTiC-Next Studio</h3>"
        "<p>MaxTiC 的 Python 3 重写版图形化桌面端。</p>"
        "<p>版本: {} / 核心算法 {}</p>"
        "<p>许可证: CeCILL 2.1 / PySide6 (LGPL)</p>"
        "<p>核心算法: maxtic_next.api.rank</p>"
    ),
    "dialog_save_config_title": "保存配置",
    "dialog_open_config_title": "打开配置",
    "dialog_export_csv_title": "导出排名表为 CSV",
    "dialog_export_image_title": "导出排名图",
    # ---- 其他 ----
    "confirm_cancel": "确定要取消当前运行吗？",
    "demo_loaded": "已加载示例数据：{} + {}",
}

_EN: Dict[str, str] = {
    # ---- window title / menus ----
    "app_title": "MaxTiC-Next Studio",
    "menu_file": "File",
    "menu_run": "Run",
    "menu_view": "View",
    "menu_settings": "Settings",
    "menu_help": "Help",
    "action_open_config": "Open Config (JSON)…",
    "action_save_config": "Save Config (JSON)…",
    "action_exit": "Exit",
    "action_start": "Start",
    "action_cancel": "Cancel",
    "action_demo": "Run Demo",
    "action_toggle_log": "Toggle Log Visibility",
    "action_reset_layout": "Reset Layout",
    "action_language": "Language",
    "action_about": "About",
    "action_cli_docs": "Open CLI Documentation",
    "action_check_update": "Check for Updates",
    # ---- input panel ----
    "group_input": "Input",
    "species_tree": "Species Tree",
    "species_tree_filter": "Newick tree files (*.tree *.nwk *.newick *.tre);;All files (*)",
    "constraints": "Constraints",
    "constraints_filter": "Constraint files (*.tsv *.txt *.csv);;All files (*)",
    "button_browse": "Browse…",
    "button_add": "+ Add",
    "button_remove": "- Remove",
    "button_clear": "Clear",
    # ---- core parameters ----
    "group_core_params": "Core Parameters",
    "seed": "Random Seed",
    "local_search": "Local Search Time (s)",
    "temperature": "Metropolis Temperature",
    "random_type": "Randomization Type",
    "min_transfer_distance": "Min Transfer Distance",
    "threshold_constraints": "Constraint Weight Threshold",
    "random_trees": "Random Tree Samples",
    # ---- main window tabs / toolbar ----
    "tab_basic": "Basic Settings",
    "preset": "Preset",
    "preset_quick": "Quick",
    "preset_standard": "Standard",
    "preset_strict": "Strict",
    "preset_placeholder": "Select preset…",
    "button_reset_default": "Reset Defaults",
    "cli_preview": "Live CLI Command",
    "cli_preview_hint": "Live reproducible command (read-only)…",
    "action_dark_theme": "Dark Theme",
    # ---- toolbar language / theme switch ----
    "lang_display_zh": "中文",
    "lang_display_en": "English",
    "tooltip_language": "Interface language: switch between Chinese and English",
    "theme_mode_light": "Light",
    "theme_mode_dark": "Dark",
    "tooltip_theme": "Interface theme: switch between light and dark",
    # ---- advanced parameters ----
    "group_advanced": "Advanced Parameters",
    "tab_adapters": "Upstream Adapters",
    "adapter_tool_none": "None (native MaxTiC constraint format)",
    "adapter_tool_auto": "Auto-detect",
    "adapter_tool_ale": "ALE",
    "adapter_tool_ranger": "RANGER-DTLx",
    "adapter_tool_eccetera": "ecceTERA",
    "adapter_tool_artra": "ARTra",
    "adapter_tool_alerax": "AleRax",
    "adapter_hint_none": (
        "No adapter: constraints are parsed as native MaxTiC TSV, "
        "so the options below have nothing to apply to."
    ),
    "adapter_hint_auto": (
        "Auto-detect: the upstream tool is inferred from content / "
        "extension; mixed inputs also get endpoint-convention and "
        "weight-unit consistency checks."
    ),
    "adapter_hint_ale": (
        "ALE: derives constraints from .uml_rec reconciliations via "
        "gene-tree families. This adapter ignores the endpoint hit-rate "
        "threshold, so that field is hidden."
    ),
    "adapter_hint_ranger": "RANGER-DTLx: parses its DTL output into constraints.",
    "adapter_hint_eccetera": "ecceTERA: parses its event list into constraints.",
    "adapter_hint_artra": (
        "ARTra: parses its transfer list into constraints and can "
        "restrict which transfer kinds are counted."
    ),
    "adapter_hint_alerax": "AleRax: parses its gene tree / scheduling output into constraints.",
    "adapter_min_endpoint_hit_rate": "Min Endpoint Hit Rate",
    "adapter_quiet": "Silence Adapter Diagnostics",
    "tab_pruning": "Pruning",
    "tab_run_mode": "Run Mode",
    "tab_mcmc": "MCMC",
    "tab_checkpoint": "Checkpoint",
    "tab_output": "Output",
    "ale_min_support": "Min Support",
    "ale_min_family_size": "Min Family Size",
    "ale_cache_dir": "Cache Directory",
    "ale_source": "Constraint Source",
    "ale_parallel": "Parallel Mode",
    "from_tool": "Upstream Tool Adapter",
    "from_tool_none": "None",
    "artra_transfer_kind": "ARTra Transfer Kind",
    "target_clade": "Target Clade Root Node",
    "target_clade_ancestor_map": "Map external ancestors to root",
    "dry_run": "Dry-run only (no actual ranking)",
    "generate_html_report": "Generate interactive HTML report",
    "mcmc": "Enable MCMC sampling",
    "mcmc_iters": "MCMC Iterations",
    "mcmc_temperature": "MCMC Temperature",
    "mcmc_temperature_auto": "auto (derived from the instance energy scale)",
    "incremental": "Enable incremental scoring",
    "checkpoint_path": "Checkpoint file path",
    "checkpoint_interval": "Checkpoint save interval (s)",
    "constraints_out": "Constraints output path (two-phase)",
    "output_prefix": "Output Prefix",
    "output_prefix_hint": "Leave empty = auto from constraint filename",
    "output_style": "Output filename style",
    # ---- run controls ----
    "button_run": "Run ▶",
    "button_cancel_run": "Cancel ■",
    "status_ready": "Ready",
    "status_running": "Running…",
    "status_done": "Done",
    "status_error": "Error",
    "status_cancelled": "Cancelled",
    "stage_loading_tree": "Loading species tree…",
    "stage_ranking": "Ranking…",
    "stage_running": "Running…",
    "stage_render": "Rendering results…",
    "error_card_hint": "See the log below. Fix the highlighted inputs.",
    # ---- log panel ----
    "group_log": "Log",
    "log_copy": "Copy",
    "log_clear": "Clear",
    "log_save": "Save",
    # ---- result panel ----
    "group_results": "Results",
    "tab_table": "Ranking Table",
    "tab_chart": "Ranking Chart",
    "col_rank": "Rank",
    "col_node": "Node Label",
    "col_value": "Δ objective (move to front/back)",
    "col_informative": "Informative",
    "button_open_report": "Open HTML Report",
    "button_export_csv": "Export CSV",
    "button_export_png": "Export PNG",
    "button_export_pdf": "Export PDF",
    "no_results": "No results yet. Run ranking to see the table and chart here.",
    "empty_guide_title": "No results yet",
    "empty_guide_steps": '\n① Choose a species tree file\n② Add constraint files\n③ Click "Run" to start ranking',
    "metric_ranked": "Ranked Nodes",
    "metric_informative": "Informative Nodes",
    "metric_conflicts": "Conflicts",
    "metric_time": "Time",
    "error_card_text": "Run failed. See the log below.",
    "chart_unavailable": "Chart unavailable: matplotlib is not installed.\nThe ranking table remains available.",
    "chart_title": "Node position sensitivity (Δ objective: front vs back)",
    "chart_axis_score": "Objective change amplitude (not an MTC score)",
    "tooltip_node_impact": (
        "Objective delta: change of the violated informative-"
        "constraint weight when this node is moved to the "
        "front / back of the delivered order\n"
        "(negative = more consistent; MaxTiC defines no "
        "per-node MTC score)"
    ),
    "tooltip_impact_front": "moved to front",
    "tooltip_impact_back": "moved to back",
    "tooltip_impact_degenerate": (
        "Fewer than 3 nodes: moving to front and to back is the same operation"
    ),
    "legend_informative": "Informative",
    "legend_non_informative": "Non-informative",
    # ---- validation messages ----
    "err_no_species_tree": "Please select a species tree file",
    "err_no_constraints": "Please add at least one constraint file",
    "err_file_not_found": "File not found: {}",
    "err_seed_negative": "Random seed cannot be negative",
    "err_temperature_zero": "Temperature must be greater than 0",
    "err_random_type": "random-type must be one of 0 / 1 / 2",
    "err_threshold_constraints": ("threshold-constraints must lie in the closed interval [0, 1]"),
    "err_local_search_negative": "local-search duration cannot be negative",
    "err_near_optimal_top_k": (
        "near-optimal-top-k must be an integer >= 1 "
        "(0 near-optimal orders cannot form a "
        "robustness/sensitivity summary)"
    ),
    "err_mcmc_iters": "mcmc-iters must be a positive integer",
    "err_mcmc_thin": "mcmc-thin must be >= 1",
    "err_ale_source": "ALE constraint source must be rec or trf",
    "err_min_endpoint_hit_rate": ("min-endpoint-hit-rate must lie in the closed interval [0, 1]"),
    "err_output_style": "Output naming style must be short or legacy",
    "err_invalid_number": "Invalid number: {}",
    "err_config_read": "Failed to read configuration file: {}",
    "err_config_write": "Failed to save configuration file: {}",
    "err_demo_missing": "Example files not found:\n{}\n{}",
    "log_cancel_requested": (
        "Cancellation requested: stopping at the next local-search iteration boundary."
    ),
    "log_cancel_unsupported": (
        "The installed kernel does not accept a cancellation "
        "callback, so cancellation only takes effect at stage "
        "boundaries (a long local-search run finishes first "
        "and its result is discarded)."
    ),
    "log_stdout_contended": (
        "stdout capture is held by another task: this task "
        "renders the summary from the Result object instead, "
        "so the two tasks' logs cannot interleave."
    ),
    "task_still_running": "Task is still running",
    "task_still_running_hint": "The task did not finish within 5 seconds. Force close the window? Data may be lost.",
    "yes": "Yes",
    "no": "No",
    # ---- dialogs ----
    "dialog_about_title": "About MaxTiC-Next Studio",
    "dialog_about_text": (
        "<h3>MaxTiC-Next Studio</h3>"
        "<p>Python 3 rewrite of MaxTiC — native desktop GUI.</p>"
        "<p>Version: {} / core algorithm {}</p>"
        "<p>License: CeCILL 2.1 / PySide6 (LGPL)</p>"
        "<p>Core algorithm: maxtic_next.api.rank</p>"
    ),
    "dialog_save_config_title": "Save Configuration",
    "dialog_open_config_title": "Open Configuration",
    "dialog_export_csv_title": "Export ranking table as CSV",
    "dialog_export_image_title": "Export ranking chart",
    # ---- misc ----
    "confirm_cancel": "Cancel the current run?",
    "demo_loaded": "Loaded example data: {} + {}",
}

_TABLES: Dict[str, Dict[str, str]] = {"zh": _ZH, "en": _EN}


def get_language() -> str:
    """返回当前语言代码（``"zh"`` 或 ``"en"``）。"""
    return _current


def set_language(lang: str) -> None:
    """设置当前语言代码（``"zh"`` 或 ``"en"``）。无效值静默忽略。"""
    global _current
    if lang in _TABLES:
        _current = lang


def _(key: str) -> str:
    """翻译查询：按当前语言返回文案。未找到时回退到 key 本身。"""
    table = _TABLES.get(_current, _ZH)
    return table.get(key, key)


def available_languages() -> list:
    """返回支持的语言代码列表。"""
    return list(_TABLES.keys())
