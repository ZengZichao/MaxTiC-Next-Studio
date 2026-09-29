"""Studio 参数域校验 + "科学逻辑不依赖 Qt" 的回归测试。

覆盖的不变量：

* ``maxtic_studio/params.py``：与 CLI 同口径的参数域校验。
* ``node_scores`` / ``params`` 必须在**屏蔽 PySide6 的子进程**里可导入。
* ``maxtic-studio`` 在未装 GUI 依赖时给出安装指引而非裸回溯。
* ``--incremental`` 的默认值在 CLI / ``api.rank`` / ``Ranker`` / GUI 四处一致。

``maxtic_studio.params`` 从核心 ``maxtic_next.config`` 取常量，故需要核心仓库
的 ``src`` 在 ``sys.path`` 上（见下方探测）。
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

# --------------------------------------------------------------------------- #
# Studio 只依赖**已安装**的核心包 maxtic_next；本地开发时核心没装，
# 因此这里兜底探测一个已克隆但尚未安装的核心仓库 ``src``（可用 ``MAXTIC_STUDIO_CORE_SRC``
# 显式覆盖）。核心真的 pip 安装时探测为空操作，不影响任何行为。
# --------------------------------------------------------------------------- #
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def _add_to_path(path):
    path = str(path)
    if path and os.path.isdir(path) and path not in sys.path:
        sys.path.insert(0, path)


def _core_src():
    override = os.environ.get("MAXTIC_STUDIO_CORE_SRC")
    if override:
        return override
    for sibling in sorted(ROOT.parent.iterdir()):
        if (sibling / "src" / "maxtic_next" / "__init__.py").is_file():
            return str(sibling / "src")
    return ""


_add_to_path(SRC)
CORE_SRC = _core_src()
_add_to_path(CORE_SRC)


from maxtic_studio import node_scores as ns  # noqa: E402
from maxtic_studio import params as gui_params  # noqa: E402

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
TREE = os.path.join(DATA_DIR, "minitree.tree")
CONS = os.path.join(DATA_DIR, "Cyano_CUTConstraints.tsv")


_BLOCK_QT_CHILD = """
import sys
class _NoQt:
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] == "PySide6":
            raise ImportError("PySide6 blocked by test")
        return None
sys.meta_path.insert(0, _NoQt())
for _p in {paths!r}:
    if _p not in sys.path:
        sys.path.insert(0, _p)
import maxtic_studio.node_scores as ns
import maxtic_studio.params as gp
assert callable(ns.node_objective_impacts), "node_scores 科学逻辑不可导入"
assert callable(gp.collect_params), "params 不可导入"
print("OK")
"""


def test_node_scores_module_imports_without_pyside6():
    """的真实主张是"节点打分与参数校验不依赖 Qt"，所以必须在**屏蔽 PySide6 的子进程**里验证。

    原实现写作 ``with pytest.raises(ImportError): import PySide6``，即把"本机恰好没装 Qt"
    当成前提 —— 在装了本仓库 GUI 依赖的环境（普通用户、以及 CI 的 studio 作业）里必然失败。
    这与：**测试依赖环境假设而不是自己构造环境**。
    """
    child = subprocess.run(
        [
            sys.executable,
            "-c",
            _BLOCK_QT_CHILD.format(paths=[p for p in (str(SRC), CORE_SRC) if p]),
        ],
        capture_output=True,
        text=True,
    )
    assert "OK" in child.stdout, child.stdout + child.stderr
    # 当前进程（无论是否装了 Qt）都必须能用同一份科学逻辑
    assert callable(ns.node_objective_impacts)
    assert callable(gui_params.collect_params)


# =========================================================================
# ：GUI 参数域校验与 CLI 同口径
# =========================================================================
def _collect(**kw):
    base = dict(species_tree=TREE, constraints=[CONS])
    base.update(kw)
    return gui_params.collect_params(**base)


def test_gui_validates_random_type_threshold_local_search_temperature():
    _collect()  # 默认值必须通过
    for bad in (3, -1, 99):
        with pytest.raises(gui_params.ValidationError):
            _collect(random_type=bad)
    for bad in (-0.1, 1.5, 3):
        with pytest.raises(gui_params.ValidationError):
            _collect(threshold_constraints=bad)
    with pytest.raises(gui_params.ValidationError):
        _collect(local_search=-5)
    with pytest.raises(gui_params.ValidationError):
        _collect(temperature=-1.0)
    with pytest.raises(gui_params.ValidationError):
        _collect(temperature=0.0)
    with pytest.raises(gui_params.ValidationError):
        _collect(seed=-1)
    with pytest.raises(gui_params.ValidationError):
        _collect(mcmc=True, mcmc_iters=0)
    with pytest.raises(gui_params.ValidationError):
        _collect(mcmc=True, mcmc_iters=100, mcmc_thin=0)


def test_gui_mcmc_temperature_default_is_auto():
    p = _collect(mcmc=True)
    assert p["mcmc_temperature"] == 0.0  # 0.0 == auto

    cmd = gui_params.params_to_cli_command(p)
    assert "--mcmc" in cmd and "--mcmc-temperature" not in cmd
    p2 = _collect(mcmc=True, mcmc_burn_in=200, mcmc_thin=10, mcmc_temperature=1.25)
    cmd2 = gui_params.params_to_cli_command(p2)
    assert "--mcmc-burn-in 200" in cmd2 and "--mcmc-thin 10" in cmd2
    assert "--mcmc-temperature 1.25" in cmd2


def test_validate_params_is_reusable():
    gui_params.validate_params(
        {
            "seed": 1,
            "temperature": 0.001,
            "random_type": 2,
            "threshold_constraints": 1.0,
            "local_search": 0.0,
        }
    )
    with pytest.raises(gui_params.ValidationError):
        gui_params.validate_params({"random_type": 7})
    with pytest.raises(gui_params.ValidationError):
        gui_params.validate_params({"output_style": "weird"})


# ----------------------------------------------------------------------
# n5：未装 extras 的 Studio 给出安装指引而非裸回溯
# ----------------------------------------------------------------------
def test_studio_without_pyside6_prints_install_hint(tmp_path, capsys):
    # 注：此处刻意不用 importorskip —— 本用例要验证的正是"没装 PySide6"的降级路径，
    # 装了 Qt 的环境（CI 的 studio 作业）改由下面的显式 skip 让路。
    try:
        import PySide6  # noqa: F401

        pytest.skip("本机已安装 PySide6，无法验证降级提示路径")
    except ImportError:
        pass
    from maxtic_studio.main import main as studio_main

    with pytest.raises(SystemExit) as exc:
        studio_main(["maxtic-studio"])
    assert exc.value.code == 3
    err = capsys.readouterr().err
    assert "PySide6" in err and "pip install" in err
    # 提示里的安装途径必须是对外可用的仓库地址，而不是本地相对路径
    assert "github.com/ZengZichao/MaxTiC-Next-Studio" in err
    assert "../" not in err


# --------------------------------------------------------------------------- #
# `--incremental` 默认开启：GUI 与 CLI / api.rank / Ranker 三处默认一致
# （CLI 解析器一侧的守卫仍留在核心仓库 tests/test_delivery_guards.py）
# --------------------------------------------------------------------------- #
def test_api_and_ranker_defaults_match_cli() -> None:
    """三处默认值必须一致，否则"CLI 说默认开、库调用却走全量"会重新制造分叉。"""
    import inspect

    from maxtic_next.api import rank as api_rank
    from maxtic_next.ranking.ranker import Ranker

    assert inspect.signature(api_rank).parameters["incremental"].default is True
    assert inspect.signature(Ranker.__init__).parameters["incremental"].default is True
    from maxtic_studio import params as gui_params

    defaults = gui_params.collect_params(species_tree=TREE, constraints=[CONS])
    assert defaults["incremental"] is True
    # CLI 命令回显：只有关闭时才需要打印 --no-incremental
    assert "--no-incremental" not in gui_params.params_to_cli_command(defaults)
    off = dict(defaults, incremental=False)
    assert "--no-incremental" in gui_params.params_to_cli_command(off)
