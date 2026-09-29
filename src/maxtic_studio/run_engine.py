"""运行引擎：QThread 封装 ``api.rank`` + 每任务独立日志流 + 协作式取消。

点击「运行」→ 启动 ``QThread`` 工作线程执行 ``api.rank``，避免界面卡死。
非 Qt 的机制（取消令牌、每任务流、全局 stdout 独占锁）都在
:mod:`maxtic_studio.cancellation`，可在无 PySide6 的环境下单测。

（两条修正）
------------------------------------------------------------------------------
1. **每任务独立的输出流**：旧实现对 ``contextlib.redirect_stdout`` 是**进程级**替换 ——
   同进程内其他线程/其他任务的 ``print`` 会被劫持进同一个日志面板。现在：

   * 每个 :class:`RunEngine` 持有自己的 :class:`~cancellation.TaskStdout`，永不共享；
   * 重定向前必须取得进程级 ``STDOUT_LOCK``；拿不到锁时**不**抢占全局 stdout
     （抢占正是串台的根因），而是以 ``print_summary=False`` 运行，结束后用
     ``io.output.format_summary(result)`` 在本任务自己的流里渲染摘要，
     并推送一条可见说明（``log_stdout_contended``）。

2. **异常路径不再有 ``UnboundLocalError``**：旧代码在 ``redirector`` 尚未绑定时于
   ``except`` 分支引用它，并靠内层 ``except Exception: pass`` 吞掉真正的错误上下文。
   现在流对象在进入 ``try`` 之前创建，清理统一放在 ``finally``。

（协作式取消）
------------------------------------------------------------------------------
"取消"过去只是"等跑完再丢弃结果"：``_cancel_flag`` 只在 ``api.rank`` 前后三处检查，
长 ``--ls`` 任务无法真正中断。现在：

* :class:`~cancellation.StopToken` 被注入 ``api.rank`` 的 **``stop_check``** 形参
  （``cancellation_hook`` 探测形参名后注入 ``token.should_stop`` 谓词），该谓词一路
  传到 ``Ranker.run`` → ``optimisation_locale``（搜索主循环体的**第一条**语句）与
  ``MCMCSampler.sample``（每次链步之间），故长任务在**迭代边界**真正停下，
  返回"截至取消点"的历史最优；
* 取消发生时本模块推送一条可见说明（``log_cancel_applied``），并照旧发出
  ``cancelled`` 信号（结果不提交到界面）；
* 若安装的内核版本过旧、不接受任何取消回调，仍按阶段边界取消并在日志里如实说明
  （``log_cancel_unsupported``），而不是假装能中断。
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from PySide6.QtCore import QThread, Signal

from .cancellation import (
    CancelledError,
    StopToken,
    TaskStdout,
    cancellation_hook,
    guard_global_stdout,
)
from .i18n import _


def _format_summary_safe(result) -> str:
    """尽力把 ``Result`` 渲染成摘要文本（输出层不可用时退回占位说明）。"""
    try:
        from maxtic_next.io.output import format_summary

        return format_summary(result)
    except Exception:  # pragma: no cover - 输出层不可用
        return "(summary unavailable)"


class RunEngine(QThread):
    """在后台线程执行 ``api.rank``，流式推送 stdout 与结果。

    Signals:
        log_message(str): 一行日志文本（已含换行）。
        finished_ok(object, float): ``Result`` 对象与耗时秒数（成功时）。
        finished_err(str): 错误消息（失败时）。
        cancelled(): 取消完成。
    """

    log_message = Signal(str)
    finished_ok = Signal(object, float)
    finished_err = Signal(str)
    cancelled = Signal()
    stage_changed = Signal(str)

    def __init__(self, params: dict, parent=None):
        super().__init__(parent)
        self._params: Dict[str, Any] = dict(params)
        self._token = StopToken()

    def cancel(self) -> None:
        """请求取消：置位令牌；下层若接受取消回调会在迭代边界真正停止。"""
        self._token.cancel()

    @property
    def is_cancelled(self) -> bool:
        return self._token.cancelled

    @property
    def stop_token(self) -> StopToken:
        return self._token

    # ------------------------------------------------------------------
    def _emit(self, text: str) -> None:
        """把一行日志安全地推给面板（面板已销毁也不影响计算线程）。"""
        try:
            self.log_message.emit(text)
        except Exception:  # pragma: no cover
            pass

    def run(self) -> None:  # noqa: C901 - QThread.run 约定
        """线程入口：执行 ``api.rank``，捕获本任务输出与异常。"""
        from maxtic_next import api

        # 流对象在 try **之前**创建：异常分支不再引用未绑定的局部名
        stream = TaskStdout(self._emit)
        hook = cancellation_hook(api.rank, self._token)
        kwargs = dict(self._params)
        kwargs.update(hook)
        result = None
        started = time.monotonic()
        try:
            if self._token.should_stop():
                self.cancelled.emit()
                return

            self.stage_changed.emit("stage_running")
            if not hook:
                # 下层不接受取消回调：如实说明取消只能在阶段边界生效
                self._emit(_("log_cancel_unsupported") + "\n")

            with guard_global_stdout(stream) as owns_stdout:
                call_kwargs = dict(kwargs)
                if not owns_stdout:
                    call_kwargs["print_summary"] = False
                result = api.rank(**call_kwargs)
                stream.flush()
                if not owns_stdout:
                    self._emit(_("log_stdout_contended") + "\n")
                    stream.write(_format_summary_safe(result) + "\n")
                    stream.flush()
            elapsed = time.monotonic() - started

            if self._token.should_stop():
                self.cancelled.emit()
                return

            self.stage_changed.emit("stage_render")
            self.finished_ok.emit(result, elapsed)

        except CancelledError:
            stream.flush()
            self.cancelled.emit()
        except Exception as exc:  # noqa: BLE001 - 面向用户日志面板
            try:
                stream.flush()
            except Exception:  # pragma: no cover
                pass
            if self._token.should_stop():
                self.cancelled.emit()
                return
            self.finished_err.emit(f"{type(exc).__name__}: {exc}")


def engine_supports_cancellation(api_rank=None) -> bool:
    """当前安装的内核是否接受取消回调（供界面提示"取消语义"时查询）。"""
    if api_rank is None:
        from maxtic_next import api

        api_rank = api.rank
    return bool(cancellation_hook(api_rank, StopToken()))


def build_params_with_cancellation(
    params: Dict[str, Any], token: StopToken, func: Optional[Any] = None
) -> Dict[str, Any]:
    """把取消回调注入参数字典（供不走 QThread 的同步/测试调用路径复用）。"""
    if func is None:
        from maxtic_next import api

        func = api.rank
    out = dict(params)
    out.update(cancellation_hook(func, token))
    return out
