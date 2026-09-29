"""统一样式系统：浅 / 深双主题令牌 + QPalette + QSS。

核心思路：
- 一套设计令牌（颜色 / 圆角 / 间距），浅色与深色仅替换令牌值，结构不变。
- 统一用 Fusion 风格 + 全局 QSS + 令牌化 QPalette 落地：
  QPalette 负责原生绘制的子控件（旋转框箭头 / 下拉箭头 / 复选框指示器 /
  滚动条 / 禁用态文字），QSS 负责容器与状态外观，两者同源，避免深色主题下
  出现"深底黑箭头"的观感割裂。
- 提供 :func:`theme_tokens` 供非 QSS 层（表格、图表、日志）复用同一颜色，
  避免 matplotlib 图 / 表格高亮与主体"两张皮"。
"""

from __future__ import annotations

from typing import Dict

from . import metrics as M

# ---------------------------------------------------------------------------
# 设计令牌（Design Token）
# ---------------------------------------------------------------------------
LIGHT: Dict[str, str] = {
    # 品牌主色：深青绿，呼应系统发育 / 进化生物学语境
    "primary": "#0F6E56",
    "primary_hover": "#0D5E49",
    "primary_pressed": "#0B5040",
    "primary_disabled": "#9FE1CB",
    "primary_100": "#9FE1CB",
    "primary_soft": "#E6F5F0",
    # 主色上的文字色（浅色主题用白字，对比度 6.20:1 PASS）
    "on_primary": "#FFFFFF",
    # 背景 / 表面 / 边框
    "bg": "#F7F8FA",
    "surface": "#FFFFFF",
    "surface_alt": "#F1F5F9",
    "border": "#E5E7EB",
    # 强边框（需被看见的边界用 border_strong，对白底 ≈3:1）
    "border_strong": "#A9B0BB",
    # 文本
    "text_1": "#2C2C2A",
    "text_2": "#6B7280",
    # 语义
    "success": "#3B6D11",
    "success_soft": "#EAF5E0",
    "warning": "#BA7517",
    "warning_soft": "#FBF1E0",
    "danger": "#A32D2D",
    "danger_soft": "#FDECEC",
    "info": "#185FA5",
    "info_soft": "#E7EFF8",
    # 日志区（保持深色底，双主题一致）
    "log_bg": "#0F172A",
    "log_fg": "#E2E8F0",
    "log_err": "#F87171",
    "log_warn": "#FACC15",
    # 表格
    "row_alt": "#F8FAFC",
    "row_info": "#E6F5F0",
}

DARK: Dict[str, str] = {
    "primary": "#34C39A",
    "primary_hover": "#3FD0A6",
    "primary_pressed": "#2AB287",
    "primary_disabled": "#1E5B4A",
    "primary_100": "#9FE1CB",
    "primary_soft": "#12302A",
    # 主色上的文字色（深色主题用深色文字，对比度 8.01:1 PASS）
    "on_primary": "#06281F",
    "bg": "#0F172A",
    "surface": "#1E293B",
    "surface_alt": "#334155",
    # border 不再与 surface_alt 同值，使用独立色值
    "border": "#475569",
    # 强边框（深色主题需被看见的边界）
    "border_strong": "#64748B",
    "text_1": "#E2E8F0",
    "text_2": "#94A3B8",
    "success": "#4ADE80",
    "success_soft": "#14361F",
    "warning": "#FBBF24",
    "warning_soft": "#3A2C0E",
    "danger": "#F87171",
    "danger_soft": "#3D1C1C",
    "info": "#38BDF8",
    "info_soft": "#123142",
    "log_bg": "#050B14",
    "log_fg": "#E2E8F0",
    "log_err": "#F87171",
    "log_warn": "#FACC15",
    "row_alt": "#182235",
    "row_info": "#12302A",
}


def theme_tokens(dark: bool) -> Dict[str, str]:
    """返回当前主题的令牌字典表。"""
    return DARK if dark else LIGHT


def build_palette(t: Dict[str, str]):
    """从令牌构建 QPalette，供 Fusion 原生子控件（箭头 / 指示器 / 滚动条）使用。"""
    from PySide6.QtGui import QColor, QPalette

    def c(key: str) -> QColor:
        return QColor(t.get(key, "#000000"))

    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, c("bg"))
    pal.setColor(QPalette.ColorRole.WindowText, c("text_1"))
    pal.setColor(QPalette.ColorRole.Base, c("surface"))
    pal.setColor(QPalette.ColorRole.AlternateBase, c("row_alt"))
    pal.setColor(QPalette.ColorRole.Text, c("text_1"))
    pal.setColor(QPalette.ColorRole.Button, c("surface"))
    pal.setColor(QPalette.ColorRole.ButtonText, c("text_1"))
    pal.setColor(QPalette.ColorRole.PlaceholderText, c("text_2"))
    pal.setColor(QPalette.ColorRole.Highlight, c("primary"))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    pal.setColor(QPalette.ColorRole.Light, c("surface_alt"))
    pal.setColor(QPalette.ColorRole.Midlight, c("surface_alt"))
    pal.setColor(QPalette.ColorRole.Dark, c("border"))
    pal.setColor(QPalette.ColorRole.Mid, c("border"))
    pal.setColor(QPalette.ColorRole.Shadow, c("border"))
    pal.setColor(QPalette.ColorRole.ToolTipBase, c("surface"))
    pal.setColor(QPalette.ColorRole.ToolTipText, c("text_1"))
    pal.setColor(QPalette.ColorRole.Link, c("info"))
    # 禁用态：文字统一降为次级色，保证可读但不抢眼
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        pal.setColor(QPalette.ColorGroup.Disabled, role, c("text_2"))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Base, c("surface_alt"))
    return pal


def _qss(t: Dict[str, str]) -> str:
    """根据令牌生成全局 QSS（浅 / 深通用）。

    注意：这里**不写控件的 min-height**。QSS 的 min-height 属于绘制层，
    不保证进入布局的 sizeHint；一旦"画出来的高度 > 布局预留的高度"，相邻行
    就会互相压字。控件高度统一由 :mod:`maxtic_studio.metrics` 通过
    ``setMinimumHeight()`` 决定，QSS 只负责配色、圆角与内边距。
    """
    return f"""
/* 全局基座 */
/* 字体（族与字号）由 apply_theme() 用 QApplication.setFont 统一设置，
   QSS 里不写 font-* —— 否则 sizeHint 按默认字体量、绘制按 QSS 字体画，
   文字就会被控件裁掉 */
QWidget {{
    background: {t["bg"]};
    color: {t["text_1"]};
}}
/* 文字类控件必须融入所在容器（卡片 / 分组框），避免出现色块矩形 */
QLabel, QCheckBox, QRadioButton, QToolButton, QAbstractScrollArea {{ background: transparent; }}
QMainWindow, QDialog {{ background: {t["bg"]}; }}
QToolTip {{
    background: {t["surface"]}; color: {t["text_1"]};
    border: 1px solid {t["border"]}; padding: 4px 8px; border-radius: 4px;
}}

/* 分组框（卡片感） */
QGroupBox {{
    border: 1px solid {t["border"]};
    border-radius: 8px;
    margin-top: {M.GROUP_SPACING}px;
    padding-top: 6px;
    background: {t["surface"]};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px; top: 2px; padding: 0 4px;
    color: {t["text_2"]};
}}

/* ---- 按钮体系 ---- */
QPushButton {{
    background: {t["surface"]};
    color: {t["text_1"]};
    border: 1px solid {t["border"]};
    border-radius: 6px;
    padding: 4px 14px;
}}
QPushButton:hover {{ border-color: {t["primary"]}; color: {t["primary"]}; }}
QPushButton:pressed {{ background: {t["surface_alt"]}; }}
QPushButton:focus {{ border-color: {t["primary"]}; }}
QPushButton:disabled {{ color: {t["text_2"]}; border-color: {t["border"]}; background: {t["surface_alt"]}; }}

/* 主操作（运行）。字号不写在 QSS 里：QSS 字体不进 sizeHint，
   按钮会按 13px 量宽、按 14px 画字，结果就是文字被边框裁掉。
   统一由 metrics.primary_font() 设到控件字体上。 */
QPushButton#btn_run {{
    background: {t["primary"]}; color: {t["on_primary"]};
    border: none; border-radius: 6px;
    padding: 6px 26px;
}}
QPushButton#btn_run:hover {{ background: {t["primary_hover"]}; }}
QPushButton#btn_run:pressed {{ background: {t["primary_pressed"]}; }}
QPushButton#btn_run:disabled {{ background: {t["primary_disabled"]}; color: {t["text_2"]}; }}
/* 主按钮焦点环（ID 规则 + :focus 伪态，特异度足够覆盖） */
QPushButton#btn_run:focus {{
    border: 2px solid {t["text_1"]};
    outline: 2px solid {t["primary"]};
    outline-offset: 2px;
}}

/* 取消（危险描边） */
QPushButton#btn_cancel {{
    background: {t["surface"]}; color: {t["danger"]};
    border: 1px solid {t["danger"]}; border-radius: 6px;
    padding: 6px 18px;
}}
QPushButton#btn_cancel:hover {{ background: {t["danger_soft"]}; }}
QPushButton#btn_cancel:disabled {{ color: {t["text_2"]}; border-color: {t["border"]}; background: {t["surface_alt"]}; }}
/* 取消按钮焦点环 */
QPushButton#btn_cancel:focus {{
    border: 2px solid {t["text_1"]};
    outline: 2px solid {t["primary"]};
    outline-offset: 2px;
}}

/* 小工具按钮（日志工具条 / 浏览） */
QPushButton#btn_small {{
    padding: 2px 10px; border-radius: 4px;
}}

/* 工具条上的语言 / 主题切换按钮 */
QToolButton {{
    background: {t["surface"]};
    color: {t["text_1"]};
    border: 1px solid {t["border"]};
    border-radius: 6px;
    padding: 2px 10px;
}}
QToolButton:hover {{ border-color: {t["primary"]}; color: {t["primary"]}; }}
QToolButton::menu-indicator {{ image: none; width: 0; }}

/* ---- 输入控件的 focus / error 态 ---- */
QLineEdit, QComboBox {{
    background: {t["surface"]};
    border: 1px solid {t["border"]};
    border-radius: 6px;
    padding: 2px 8px;
    selection-background-color: {t["primary"]};
    selection-color: #FFFFFF;
}}
/* 旋钮类：不设垂直 padding，避免数值被裁切；高度统一由 metrics 落地 */
QSpinBox, QDoubleSpinBox {{
    background: {t["surface"]};
    border: 1px solid {t["border"]};
    border-radius: 6px;
    padding: 0px 12px 0px 8px;
    selection-background-color: {t["primary"]};
    selection-color: #FFFFFF;
}}
QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-origin: border; subcontrol-position: top right;
    width: 18px; border: none; background: transparent;
}}
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border; subcontrol-position: bottom right;
    width: 18px; border: none; background: transparent;
}}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background: {t["surface_alt"]};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border: 1px solid {t["primary"]};
}}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {{
    background: {t["surface_alt"]}; color: {t["text_2"]};
}}
QLineEdit[error="true"], QSpinBox[error="true"], QDoubleSpinBox[error="true"] {{
    /* 常态和 error 态都保持 1px 边框宽度，避免布局跳动 */
    border: 1px solid {t["danger"]};
    background: {t["danger_soft"]};
}}

/* 下拉框弹层（深色主题下若不显式着色会回退白底） */
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {t["surface"]}; color: {t["text_1"]};
    border: 1px solid {t["border"]};
    border-radius: 6px;
    selection-background-color: {t["primary_soft"]};
    selection-color: {t["text_1"]};
    padding: 4px;
    outline: none;
}}

/* ---- 列表（约束文件列表） ---- */
QListWidget {{
    background: {t["surface"]}; color: {t["text_1"]};
    border: 1px solid {t["border"]}; border-radius: 6px;
    padding: 2px;
    outline: none;
}}
QListWidget::item {{ padding: 4px 6px; border-radius: 4px; }}
QListWidget::item:hover {{ background: {t["surface_alt"]}; }}
QListWidget::item:selected {{
    background: {t["primary_soft"]}; color: {t["text_1"]};
}}

/* ---- Tab ---- */
QTabWidget::pane {{
    border: 1px solid {t["border"]};
    border-radius: 6px;
    top: -1px;
    background: {t["surface"]};
}}
QTabBar::tab {{
    background: {t["surface_alt"]}; color: {t["text_2"]};
    padding: 6px 16px;
    border: 1px solid {t["border"]};
    border-bottom: none;
    border-top-left-radius: 6px; border-top-right-radius: 6px;
}}
QTabBar::tab:selected {{
    background: {t["surface"]}; color: {t["primary"]};
}}
QTabBar::tab:hover:!selected {{ color: {t["primary"]}; }}

/* ---- 表格 ---- */
QTableView {{
    background: {t["surface"]};
    alternate-background-color: {t["row_alt"]};
    gridline-color: {t["border"]};
    border: 1px solid {t["border"]};
    border-radius: 6px;
    selection-background-color: {t["primary_soft"]};
    selection-color: {t["text_1"]};
}}
QTableView::item {{
    padding: 4px 6px; color: {t["text_1"]};
}}
QTableView::item:selected {{
    background: {t["primary_soft"]}; color: {t["text_1"]};
}}
QHeaderView::section {{
    background: {t["surface_alt"]}; color: {t["text_2"]};
    border: none; border-right: 1px solid {t["border"]};
    border-bottom: 1px solid {t["border"]};
    padding: 6px;
}}

/* ---- 概览指标卡 ---- */
QFrame#metricCard {{
    background: {t["surface"]};
    border: 1px solid {t["border"]};
    border-radius: 8px;
}}
QLabel#metricTitle {{ color: {t["text_2"]}; background: transparent; }}
QLabel#metricValue {{ background: transparent; }}

/* ---- 结果区空状态 / 错误卡 / 阶段提示 ---- */
QLabel#emptyGuide {{
    color: {t["text_2"]};
    background: transparent; padding: 16px;
}}
QLabel#errorBanner {{
    color: {t["danger"]};
    background: {t["danger_soft"]};
    border: 1px solid {t["danger"]};
    border-radius: 8px; padding: 16px;
}}
/* 表单内的说明文字（如上游适配器的口径提示） */
QLabel#fieldHint {{ color: {t["text_2"]}; background: transparent; }}
QLabel#stageLabel {{ color: {t["info"]}; background: transparent; }}
QLabel#statusLabel {{ color: {t["text_2"]}; background: transparent; }}

/* ---- CLI 命令预览（等宽） ---- */
QPlainTextEdit#cliPreview {{
    background: {t["surface_alt"]}; color: {t["text_1"]};
    border: 1px solid {t["border"]}; border-radius: 6px;
    selection-background-color: {t["primary"]};
    selection-color: #FFFFFF;
}}

/* ---- 日志（等宽，深色底，双主题稳定） ---- */
QPlainTextEdit#log {{
    background: {t["log_bg"]}; color: {t["log_fg"]};
    border: 1px solid {t["border"]}; border-radius: 6px;
    selection-background-color: {t["primary"]};
    selection-color: #FFFFFF;
}}

/* ---- 菜单 ---- */
QMenuBar {{ background: {t["bg"]}; color: {t["text_1"]}; }}
QMenuBar::item:selected {{ background: {t["primary_soft"]}; color: {t["primary"]}; }}
QMenu {{ background: {t["surface"]}; color: {t["text_1"]}; border: 1px solid {t["border"]}; }}
QMenu::item:selected {{ background: {t["primary_soft"]}; color: {t["primary"]}; }}
QMenu::item:disabled {{ color: {t["text_2"]}; }}
QMenu::separator {{ height: 1px; background: {t["border"]}; margin: 4px 8px; }}

/* ---- 状态栏 / 进度 / 分割线 ---- */
QStatusBar {{ background: {t["surface"]}; color: {t["text_2"]}; }}
QProgressBar {{
    background: {t["surface_alt"]}; border: 1px solid {t["border"]}; border-radius: 4px;
    text-align: center; color: {t["text_2"]}; height: 8px;
}}
QProgressBar::chunk {{ background: {t["primary"]}; border-radius: 4px; }}
QSplitter::handle {{ background: {t["border"]}; }}
QSplitter::handle:horizontal {{ width: 5px; }}
QSplitter::handle:vertical {{ height: 5px; }}
QSplitter::handle:hover {{ background: {t["primary"]}; }}

/* ---- 滚动条（纤细、融入主题） ---- */
QScrollBar:vertical {{
    background: transparent; width: 10px; margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {t["text_2"]}; border-radius: 4px; min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: {t["text_1"]}; }}
QScrollBar:horizontal {{
    background: transparent; height: 10px; margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: {t["text_2"]}; border-radius: 4px; min-width: 24px;
}}
QScrollBar::handle:horizontal:hover {{ background: {t["text_1"]}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
"""


def apply_theme(app, dark: bool) -> None:
    """将给定的浅 / 深主题应用到 QApplication。

    Args:
        app: ``QApplication`` 实例。
        dark: 是否为深色主题。
    """
    # 始终使用 Fusion 基座，保证三平台观感一致
    try:
        from PySide6.QtWidgets import QStyleFactory

        app.setStyle(QStyleFactory.create("Fusion"))
    except Exception:
        app.setStyle("Fusion")

    tokens = theme_tokens(dark)
    # QPalette 先行：让 Fusion 原生绘制的箭头 / 指示器 / 滚动条与令牌同源
    app.setPalette(build_palette(tokens))
    app.setStyleSheet(_qss(tokens))
    # 字体族与字号在这里设，QSS 里不写 font-*：QSS 字体只改绘制、不进
    # sizeHint，会让按钮/标签按小字号量宽、按大字号画字，文字被裁掉。
    ui_font = app.font()
    ui_font.setPointSize(M.FONT_BASE_PT)
    # 只钉字号，不覆盖字体族：macOS 系统字体（San Francisco）负责拉丁字形，
    # 中文由 Qt 的逐字回退落到 PingFang SC。把 PingFang SC 放在最前面会让
    # 英文界面也用它那套拉丁字形（"R" 的斜笔被削平），观感明显变差。
    app.setFont(ui_font)
    # 存储当前主题标记，供子模块读取
    app.setProperty("maxTic-dark", dark)
    app.setProperty("maxTic-tokens", tokens)
