"""协作式取消与每任务日志流（纯 Python，可在**无 PySide6** 环境下导入与单测）。

，使 :mod:`maxtic_studio.run_engine`
只剩 Qt 胶水，逻辑本身可测：

* :class:`StopToken` —— 取消令牌。下层（``api.rank`` → ``Ranker.run`` →
  ``optimisation_locale`` / ``MCMCSampler.sample``）**已经**接受 ``stop_check``
  谓词形参，因此取消请求会在**迭代边界**真正打断计算；
  :func:`cancellation_hook` 负责探测形参名并注入正确约定的回调。
* :class:`TaskStdout` —— 每任务独立的输出流：按**完整行**推送，不把未换行的部分
  输出拆成假日志（旧实现的行为），也不与任何其他任务共享。
* :func:`guard_global_stdout` —— 进程级 ``redirect_stdout`` 的"独占权"上下文：
  拿不到锁的任务**不抢占**全局 stdout（抢占正是并发任务日志串台的原因），
  而是走 ``print_summary=False`` + 事后自行渲染摘要的旁路。
"""

from __future__ import annotations

import contextlib
import inspect
import io
import threading
from typing import Any, Callable, Dict, Iterator, Optional, Set

__all__ = [
    "CancelledError",
    "StopToken",
    "cancellation_hook",
    "TaskStdout",
    "STDOUT_LOCK",
    "guard_global_stdout",
    "build_call_kwargs",
]


class CancelledError(RuntimeError):
    """用户请求取消后，在协作点上抛出的可控异常。"""


class StopToken:
    """协作式取消令牌（线程安全，可重复 ``cancel()``）。

    约定：``should_stop()`` 是**谓词**（返回 bool），供下层的
    ``stop_check`` / ``should_stop`` 形参使用（循环里 ``if stop_check(): break``）；
    ``check()`` 在已取消时抛 :class:`CancelledError`，供 ``cancel_callback`` /
    ``on_cancel`` 这类"回调即中止"约定使用。选谓词作默认约定，是为了即便接收方
    把回调用在"是否继续"的判断上也不会崩。
    """

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        """请求取消。"""
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def should_stop(self) -> bool:
        """谓词：是否已请求取消。"""
        return self._event.is_set()

    def check(self) -> None:
        """已取消则抛 :class:`CancelledError`。"""
        if self._event.is_set():
            raise CancelledError("用户已取消本次运行")

    def __call__(self) -> bool:
        """令牌实例本身即可当谓词用（``stop_check=token``）。"""
        return self.should_stop()


#: 下层可能使用的取消回调形参名 -> 从令牌构造出相应约定的可调用对象。
#: ：内核一侧已经接受 **``stop_check``** ——
#: ``api.rank(stop_check=)`` → ``Ranker.run(stop_check=)`` →
#: ``ranking.local_search.optimisation_locale``（搜索主循环体第一条语句）与
#: ``robustness.mcmc.MCMCSampler.sample``（每次链步之间）。dict 的插入顺序即探测
#: 顺序，故 ``stop_check`` 优先命中；其余别名只为兼容其它/后续内核写法，
#: 全部映射到同一个"谓词返回真值即停止"的约定。
_STOP_KWARGS: Dict[str, Callable[[StopToken], Any]] = {
    "stop_check": lambda t: t.should_stop,
    "should_stop": lambda t: t.should_stop,
    "stop_predicate": lambda t: t.should_stop,
    "should_cancel": lambda t: t.should_stop,
    "cancel_callback": lambda t: t.check,
    "on_cancel": lambda t: t.check,
}


def accepted_kwargs(func: Callable) -> Set[str]:
    """探测可调用对象接受的形参名（无法内省 / ``**kwargs`` 时给出宽容答案）。"""
    try:
        sig = inspect.signature(func)
    except (TypeError, ValueError):  # pragma: no cover - 内置函数等
        return set()
    names = {
        p.name
        for p in sig.parameters.values()
        if p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)
    }
    if any(p.kind is p.VAR_KEYWORD for p in sig.parameters.values()):
        names.add("**kwargs")
    return names


def cancellation_hook(func: Callable, token: StopToken) -> Dict[str, Any]:
    """``func`` 接受取消回调形参时返回要注入的关键字参数；否则返回空字典。"""
    names = accepted_kwargs(func)
    for kwarg, maker in _STOP_KWARGS.items():
        if kwarg in names or "**kwargs" in names:
            return {kwarg: maker(token)}
    return {}


def build_call_kwargs(
    params: Dict[str, Any],
    func: Callable,
    token: Optional[StopToken] = None,
    print_summary: Optional[bool] = None,
) -> Dict[str, Any]:
    """组装实际调用参数：原参数 + 取消回调（若下层支持）+ 可选的 ``print_summary``。

    Returns:
        ``(kwargs, supports_cancellation)`` —— 这里只返回 kwargs；是否支持取消由
        :func:`cancellation_hook` 是否为空判断。
    """
    kwargs = dict(params)
    if token is not None:
        kwargs.update(cancellation_hook(func, token))
    if print_summary is not None:
        kwargs["print_summary"] = print_summary
    return kwargs


class TaskStdout(io.TextIOBase):
    """每任务独立的输出流：按完整行推送文本到 ``callback``。

    与旧的写法相比：(a) 流对象属于单个任务，绝不跨任务共享；(b) 未以换行结尾的
    部分输出**留在缓冲区**（旧实现会立即当成一条日志推送，导致进度式输出被拆碎）。
    """

    def __init__(self, callback: Callable[[str], None]) -> None:
        super().__init__()
        self._callback = callback
        self._buffer = ""

    def writable(self) -> bool:
        return True

    def write(self, text: str) -> int:
        if not text:
            return 0
        self._buffer += text
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            if line:
                self._callback(line + "\n")
        return len(text)

    def flush(self) -> None:
        if self._buffer:
            pending, self._buffer = self._buffer, ""
            if pending.strip():
                self._callback(pending if pending.endswith("\n") else pending + "\n")


#: 进程级"全局 stdout 捕获权"：同一时刻只允许一个任务重定向 ``sys.stdout``
STDOUT_LOCK = threading.Lock()


@contextlib.contextmanager
def guard_global_stdout(stream: TaskStdout, timeout: Optional[float] = None) -> Iterator[bool]:
    """尝试独占全局 stdout 并把 ``stream`` 装上去；失败则 yield ``False``（不抢占）。

    用法::

        with guard_global_stdout(stream) as owns:
            if owns:
                result = api.rank(**kwargs)              # 日志进本任务流
            else:
                result = api.rank(**kwargs, print_summary=False)
    """
    acquired = (
        STDOUT_LOCK.acquire(timeout=timeout)
        if timeout is not None
        else STDOUT_LOCK.acquire(blocking=False)
    )
    if not acquired:
        yield False
        return
    try:
        with contextlib.redirect_stdout(stream):
            yield True
    finally:
        STDOUT_LOCK.release()
