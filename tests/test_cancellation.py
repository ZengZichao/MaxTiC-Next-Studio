"""Studio 的协作式取消与每任务 stdout（``maxtic_studio/cancellation.py``）。

覆盖 ``maxtic_studio/cancellation.py``：StopToken / 取消回调注入 / 每任务 stdout 流。

纯 Python，不依赖 Qt，也不依赖核心包。
"""

import pytest

from maxtic_studio.cancellation import (
    CancelledError,
    StopToken,
    TaskStdout,
    cancellation_hook,
    guard_global_stdout,
)


# =========================================================================
# 协作式取消 + 每任务流（纯 Python 部分）
# =========================================================================
def test_stop_token_is_a_predicate_and_callback():
    token = StopToken()
    assert token.should_stop() is False
    token.cancel()
    assert token.should_stop() is True and token.cancelled is True
    assert token() is True  # 实例可直接当谓词
    with pytest.raises(CancelledError):
        token.check()


def test_cancellation_hook_only_injects_supported_kwargs():
    token = StopToken()

    def accepts_stop_check(a, b=1, stop_check=None):
        pass

    def accepts_should_stop(should_stop=None):
        pass

    def accepts_none(x, y=2):
        pass

    assert cancellation_hook(accepts_stop_check, token) == {"stop_check": token.should_stop}
    assert cancellation_hook(accepts_should_stop, token) == {"should_stop": token.should_stop}
    assert cancellation_hook(accepts_none, token) == {}


def test_cooperative_cancellation_actually_stops_a_loop():
    """模拟局部搜索循环：注入 stop_check 后，取消能在迭代边界真正停下。"""
    token = StopToken()
    iterations = {"n": 0}

    def local_search_like(stop_check=None, duration=10**9):
        import time

        t0 = time.perf_counter()
        while time.perf_counter() - t0 < duration:
            iterations["n"] += 1
            if stop_check is not None and stop_check():
                return "cancelled"
            if iterations["n"] == 50:
                token.cancel()
        return "finished"

    assert local_search_like(stop_check=token.should_stop) == "cancelled"
    assert 50 <= iterations["n"] <= 1000, "取消确实中断，而不是跑完再丢弃"


def test_task_stdout_buffers_partial_lines_and_is_per_task():
    a, b = [], []
    s1, s2 = TaskStdout(a.append), TaskStdout(b.append)
    s1.write("half")
    assert a == []  # 不再把残行当成一条日志
    s1.write("-line\n")
    s1.write("tail")
    s1.flush()
    s2.write("other\n")
    assert a == ["half-line\n", "tail\n"]
    assert b == ["other\n"]


def test_global_stdout_guard_is_not_preempted():
    import sys

    original = sys.stdout  # pytest 捕获下 __stdout__ 与 stdout 不同，先存基准
    lines = []
    with guard_global_stdout(TaskStdout(lines.append)) as owns:
        assert owns is True
        assert sys.stdout is not original
        # 第二个任务不得抢占全局 stdout
        with guard_global_stdout(TaskStdout(lines.append), timeout=0.05) as owns2:
            assert owns2 is False
            assert sys.stdout is not original  # 第二个上下文未替换它
    assert sys.stdout is original
