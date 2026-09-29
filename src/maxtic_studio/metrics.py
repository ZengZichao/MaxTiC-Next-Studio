"""统一布局度量：控件尺寸 / 字号令牌 + 落地工具。

为什么需要这个模块
------------------
QSS 的 ``font-size`` / ``min-height`` 只影响**绘制**，不保证进入控件的
``sizeHint()`` / ``minimumSizeHint()``。于是出现两类可见故障：

1. 按钮按 13px 量宽、按 14px 画字 → 文字被边框裁掉；
2. 控件按 QSS 画得比布局预留的高 → 相邻行互相压字。

这里把字号与高度收敛成一组常量，**在代码里** setFont / setMinimumHeight，
QSS 只保留颜色、圆角与内边距。两侧共用一份数字，不会再漂移。
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabBar,
    QToolButton,
    QWidget,
)

# ---- 控件高度 ----
CONTROL_H = 32  # 输入类：QLineEdit / QComboBox / QSpinBox / QToolButton
BUTTON_H = 34  # 普通按钮
SMALL_BUTTON_H = 28  # btn_small（浏览 / 日志工具条 / 演示）
PRIMARY_BUTTON_H = 44  # 运行 / 取消

# ---- 间距 ----
GROUP_SPACING = 10  # 分组框之间
FORM_SPACING = 8  # 表单行距
FIELD_SPACING = 8  # 同一行内控件间距

# ---- 面板自然高度 ----
CONSTRAINT_LIST_H = 84  # 约束文件列表默认可见高度
CLI_PREVIEW_H = 76  # CLI 实时预览高度
METRIC_CARD_H = 60  # 指标卡高度

# ---- 字号（pt）。全部在代码里 setFont，QSS 不写 font-size ----
FONT_BASE_PT = 13
FONT_SMALL_PT = 11  # btn_small
FONT_PRIMARY_PT = 14  # 运行按钮 / 空状态引导
FONT_METRIC_VALUE_PT = 20
FONT_METRIC_TITLE_PT = 11
FONT_HINT_PT = 11  # 表单内说明文字
FONT_MONO_PT = 10

MONO_FAMILIES = ["JetBrains Mono", "Cascadia Code", "Menlo", "Consolas", "SF Mono"]


def font(pt_size: int, bold: bool = False, mono: bool = False):
    """按字号构造字体（可选粗体 / 等宽），供控件 ``setFont`` 使用。"""
    from PySide6.QtGui import QFont

    f = QFont()
    if mono:
        f.setStyleHint(QFont.StyleHint.Monospace)
        f.setFamilies(MONO_FAMILIES)
    f.setPointSize(pt_size)
    if bold:
        f.setBold(True)
        f.setWeight(QFont.Weight.Bold)
    return f


def _min_height(widget: QWidget, value: int) -> None:
    """只在需要时抬高最小高度，绝不压低调用方显式设过的值。"""
    if widget.minimumHeight() < value:
        widget.setMinimumHeight(value)


def enforce_metrics(root: QWidget) -> QWidget:
    """把本模块的字号 / 高度令牌落到 root 及其所有子控件上。

    必须在 UI 全部构建完成、且 QSS 已应用之后调用；否则新建的控件不受约束。
    切换语言后需再调一次：文案变了，控件的最小高度也要跟着重算。

    刻意**不设最小宽度**：QSS 的 padding 会进入 sizeHint，控件自身的
    sizeHint 已经够宽，再抬宽度只会让窄窗口更容易排不下。
    """
    from PySide6.QtWidgets import QLabel

    for w in root.findChildren(QWidget) + [root]:
        name = w.objectName()
        if isinstance(w, (QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QToolButton)):
            _min_height(w, CONTROL_H)
        elif isinstance(w, QPushButton):
            if name == "btn_run":
                w.setFont(font(FONT_PRIMARY_PT, bold=True))
                _min_height(w, PRIMARY_BUTTON_H)
            elif name == "btn_cancel":
                _min_height(w, PRIMARY_BUTTON_H)
            elif name == "btn_small":
                w.setFont(font(FONT_SMALL_PT))
                _min_height(w, SMALL_BUTTON_H)
            else:
                _min_height(w, BUTTON_H)
        elif isinstance(w, QLabel):
            if name == "metricValue":
                w.setFont(font(FONT_METRIC_VALUE_PT, bold=True))
            elif name == "metricTitle":
                w.setFont(font(FONT_METRIC_TITLE_PT))
            elif name == "emptyGuide":
                w.setFont(font(FONT_PRIMARY_PT))
            elif name == "fieldHint":
                w.setFont(font(FONT_HINT_PT))
        elif isinstance(w, QTabBar):
            # 标签页随文字长度伸展时不应把相邻标签压扁
            w.setExpanding(False)
    return root
