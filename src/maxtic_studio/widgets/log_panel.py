"""日志面板：等宽字体（跨平台回退）、可滚动、可复制、自动滚到底。

错误行以红色高亮（包含 ``Error`` / ``Traceback`` / ``WARNING`` / ``警告`` 的行）。
前景色走主题令牌（深色日志底），避免深色主题下黑字不可见。
增加工具条：复制 / 清空 / 保存。
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QGroupBox,
)

from ..i18n import _
from .. import metrics as M


def _log_colors():
    """从主题令牌读取日志区配色（深色日志底的双主题稳定前景）。"""
    app = QApplication.instance()
    tokens = app.property("maxTic-tokens") if app is not None else None
    if isinstance(tokens, dict):
        return (
            QColor(tokens.get("log_fg", "#E2E8F0")),
            QColor(tokens.get("log_err", "#F87171")),
            QColor(tokens.get("log_warn", "#FACC15")),
        )
    return QColor("#E2E8F0"), QColor("#F87171"), QColor("#FACC15")


def _mono_font() -> QFont:
    """构造跨平台等宽字体（回退序列 + StyleHint，而非单一 'Monaco'）。"""
    return M.font(M.FONT_MONO_PT, mono=True)


class LogPanel(QWidget):
    """实时日志面板。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        # 缓存 QColor 对象，避免每行重建
        self._cached_colors = None
        self._build_ui()
        # 限制日志行数，防止 MCMC 长跑内存无限增长
        self.text_edit.setMaximumBlockCount(5000)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._group = QGroupBox(_("group_log"))
        glayout = QVBoxLayout(self._group)

        # 工具条：复制 / 清空 / 保存（接已有 API）
        toolbar = QHBoxLayout()
        self.btn_copy = QPushButton(_("log_copy"))
        self.btn_copy.setObjectName("btn_small")
        self.btn_copy.clicked.connect(self._copy_log)
        self.btn_clear = QPushButton(_("log_clear"))
        self.btn_clear.setObjectName("btn_small")
        self.btn_clear.clicked.connect(self.clear_log)
        self.btn_save = QPushButton(_("log_save"))
        self.btn_save.setObjectName("btn_small")
        self.btn_save.clicked.connect(self._save_log)
        toolbar.addWidget(self.btn_copy)
        toolbar.addWidget(self.btn_clear)
        toolbar.addWidget(self.btn_save)
        toolbar.addStretch()
        toolbar_w = QWidget()
        toolbar_w.setLayout(toolbar)
        glayout.addWidget(toolbar_w)

        self.text_edit = QPlainTextEdit()
        self.text_edit.setObjectName("log")
        self.text_edit.setReadOnly(True)
        self.text_edit.setFont(_mono_font())
        glayout.addWidget(self.text_edit)

        layout.addWidget(self._group)

    def retranslate(self):
        """语言切换时刷新文案。"""
        self._group.setTitle(_("group_log"))
        self.btn_copy.setText(_("log_copy"))
        self.btn_clear.setText(_("log_clear"))
        self.btn_save.setText(_("log_save"))
        # 主题切换后清除缓存，下次 append 时重建
        self._cached_colors = None

    def append_line(self, text: str) -> None:
        """追加一行日志。根据内容自动着色，前景色随主题令牌。"""
        # 缓存 QColor，仅在主题切换时重建
        if self._cached_colors is None:
            self._cached_colors = _log_colors()
        fg, err, warn = self._cached_colors
        cursor = self.text_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        fmt = QTextCharFormat()
        lower = text.lower()
        if any(kw in lower for kw in ["error", "traceback", "exception"]):
            fmt.setForeground(err)
            fmt.setFontWeight(QFont.Weight.Bold)
        elif any(kw in lower for kw in ["warning", "警告", "warn"]):
            fmt.setForeground(warn)
            fmt.setFontWeight(QFont.Weight.Bold)
        else:
            fmt.setForeground(fg)

        cursor.setCharFormat(fmt)
        cursor.insertText(text if text.endswith("\n") else text + "\n")

        # 只在用户已在底部时才自动滚动，避免翻阅时被拽回
        scrollbar = self.text_edit.verticalScrollBar()
        at_bottom = scrollbar.value() >= scrollbar.maximum() - 4
        if at_bottom:
            self.text_edit.setTextCursor(cursor)
            self.text_edit.ensureCursorVisible()

    def clear_log(self) -> None:
        self.text_edit.clear()

    def _copy_log(self):
        self.text_edit.selectAll()
        QApplication.clipboard().setText(self.text_edit.toPlainText())
        # 复位光标到末尾，不打扰阅读
        move = self.text_edit.textCursor()
        move.movePosition(QTextCursor.MoveOperation.End)
        self.text_edit.setTextCursor(move)

    def _save_log(self):
        path, _selected_filter = QFileDialog.getSaveFileName(
            self, _("log_save"), "maxtic-studio.log", "Text (*.log *.txt)"
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.text_edit.toPlainText())
