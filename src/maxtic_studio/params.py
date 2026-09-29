"""参数映射与校验：GUI 控件值 ↔ ``api.rank`` 参数字典。

本模块是参数的**单一事实来源**（在 GUI 侧），负责：
* 从 GUI 控件收集值，组装为 ``api.rank(**params)`` 可接受的字典；
* 从字典反向填充 GUI 控件（加载配置 / 恢复上次状态）；
* 校验参数合法性（文件存在性、数值范围等）。

：参数域校验与 CLI（由另一位同事同步加固）保持同口径 ——
``random_type ∈ {0,1,2}``、``threshold_constraints ∈ [0,1]``、``local_search ≥ 0``、
``temperature > 0``、``mcmc_iters > 0``、``ale_source ∈ {rec,trf}``、
``output_style ∈ {short,legacy}``、``top_k``（近优解收集容量）``≥ 1``。
GUI 过去只校验 ``seed`` 与 ``temperature``，
于是 ``--r 3`` 这类拼错在 GUI 路径同样会静默按"未随机化"跑完（ 传染）。

注意 ``--no-html`` 的反向语义：UI 用正向勾选框「生成 HTML 报告」，
默认选中；取消勾选 = ``html_report=False``。
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

from maxtic_next.config import (
    DEFAULT_MIN_ENDPOINT_HIT_RATE,
    DEFAULT_NEAR_OPTIMAL_TOP_K,
    MCMC_TEMPERATURE_AUTO,
    RANDOM_TYPE_CHOICES,
    THRESHOLD_CONSTRAINTS_MAX,
    THRESHOLD_CONSTRAINTS_MIN,
    OUTPUT_SUFFIXES,
)


class ValidationError(ValueError):
    """参数校验失败异常，``message`` 中含中文/英文（取决于 i18n）错误描述。"""


def validate_params(params: Dict[str, Any]) -> None:
    """校验一个 ``api.rank`` 参数字典；不合法时抛 :class:`ValidationError`。

    与 :func:`collect_params` 内联校验同口径，单独暴露以便测试与"加载配置"路径复用。
    """
    seed = params.get("seed", 42)
    if seed is None or seed < 0:
        raise ValidationError("err_seed_negative")
    temperature = params.get("temperature", 0.001)
    if temperature is None or temperature <= 0:
        raise ValidationError("err_temperature_zero")
    random_type = params.get("random_type", 0)
    if random_type not in RANDOM_TYPE_CHOICES:
        raise ValidationError("err_random_type")
    threshold = params.get("threshold_constraints", 0.0)
    if threshold is None or not (
        THRESHOLD_CONSTRAINTS_MIN <= threshold <= THRESHOLD_CONSTRAINTS_MAX
    ):
        raise ValidationError("err_threshold_constraints")
    local_search = params.get("local_search", 0.0)
    if local_search is None or local_search < 0:
        raise ValidationError("err_local_search_negative")
    # ：近优解收集容量（api.rank 的 top_k）与 CLI 同口径 —— >= 1 的整数
    top_k = params.get("top_k", DEFAULT_NEAR_OPTIMAL_TOP_K)
    if top_k is None or isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
        raise ValidationError("err_near_optimal_top_k")
    if params.get("random_trees", 0) < 0:
        raise ValidationError("err_local_search_negative")
    if params.get("min_transfer_distance", 0) < 0:
        raise ValidationError("err_local_search_negative")
    if params.get("mcmc"):
        iters = params.get("mcmc_iters", 0)
        if not iters or iters <= 0:
            raise ValidationError("err_mcmc_iters")
        thin = params.get("mcmc_thin")
        if thin is not None and thin < 1:
            raise ValidationError("err_mcmc_thin")
        temp = params.get("mcmc_temperature")
        if temp is not None and temp < 0:
            raise ValidationError("err_temperature_zero")
    ale_source = params.get("ale_source")
    if ale_source is not None and ale_source not in ("rec", "trf"):
        raise ValidationError("err_ale_source")
    hit_rate = params.get("adapter_min_endpoint_hit_rate")
    if hit_rate is not None:
        if (
            isinstance(hit_rate, bool)
            or not isinstance(hit_rate, (int, float))
            or not (0.0 <= hit_rate <= 1.0)
        ):
            raise ValidationError("err_min_endpoint_hit_rate")
    style = params.get("output_style")
    if style is not None and style not in OUTPUT_SUFFIXES:
        raise ValidationError("err_output_style")


def collect_params(
    species_tree: str,
    constraints: List[str],
    *,
    seed: int = 42,
    local_search: float = 0.0,
    temperature: float = 0.001,
    random_type: int = 0,
    min_transfer_distance: float = 0,
    threshold_constraints: float = 0.0,
    random_trees: int = 0,
    near_optimal_top_k: int = DEFAULT_NEAR_OPTIMAL_TOP_K,
    output_prefix: str = "",
    # ALE
    from_ale: bool = False,
    ale_min_support: float = 0.05,
    ale_min_family_size: int = 5,
    ale_cache_dir: str = "",
    ale_source: str = "trf",
    ale_parallel: str = "process",
    adapter_min_endpoint_hit_rate: float = DEFAULT_MIN_ENDPOINT_HIT_RATE,
    adapter_quiet: bool = False,
    # multi-tool
    from_tool: Optional[str] = None,
    artra_transfer_kind: str = "all",
    # pruning
    target_clade: str = "",
    target_clade_ancestor_map: bool = False,
    # run mode
    dry_run: bool = False,
    generate_html_report: bool = True,
    # mcmc
    mcmc: bool = False,
    mcmc_iters: int = 1000,
    mcmc_temperature: float = MCMC_TEMPERATURE_AUTO,
    mcmc_burn_in: Optional[int] = None,
    mcmc_thin: Optional[int] = None,
    # performance
    incremental: bool = True,
    checkpoint_path: str = "",
    checkpoint_interval: float = 60.0,
    # two-phase
    constraints_out: str = "",
    # output
    output_style: str = "short",
) -> Dict[str, Any]:
    """从 GUI 控件值组装 ``api.rank`` 参数字典。

    返回的字典可直接 ``api.rank(**params)`` 调用。
    会执行校验（func:`validate_params`，与 CLI 同口径），不合法时抛
    ``ValidationError``。

    ：``mcmc_temperature`` 默认改为 ``0.0``（= auto，按总权重自适应）。
    旧默认 0.01 在能量尺度（总权重常为 1e3）下会让 MH 链实际冻结，
    产出的"样本"几乎全是同一个序。
    """
    # ---- 校验 ----
    if not species_tree:
        raise ValidationError("err_no_species_tree")
    if not os.path.isfile(species_tree):
        raise ValidationError("err_file_not_found:species_tree")
    if not constraints:
        raise ValidationError("err_no_constraints")
    for c in constraints:
        if not os.path.isfile(c):
            raise ValidationError(f"err_file_not_found:{c}")

    # ---- 组装 ----
    params: Dict[str, Any] = {
        "species_tree_path": species_tree,
        "constraints_path": constraints if len(constraints) > 1 else constraints[0],
        "seed": seed,
        "local_search": local_search,
        "temperature": temperature,
        "random_type": random_type,
        "min_transfer_distance": min_transfer_distance,
        "threshold_constraints": threshold_constraints,
        "random_trees": random_trees,
        # ：近优解收集容量。**键名必须与 api.rank 的形参 top_k 一致**
        # （这个字典最终被 ``api.rank(**params)`` 直接展开）
        "top_k": near_optimal_top_k,
    }
    # ：数值域校验统一走 validate_params（与 CLI 同口径），在补齐全部
    # 字段后再做一次整体校验（见下方 MCMC 段之后）。

    # 输出前缀：空字符串 → None（让 api.rank 取约束文件名）
    params["output_prefix"] = output_prefix.strip() if output_prefix.strip() else None

    # ALE
    params["from_ale"] = from_ale
    params["ale_min_support"] = ale_min_support
    params["ale_min_family_size"] = ale_min_family_size
    params["ale_cache_dir"] = ale_cache_dir.strip() if ale_cache_dir.strip() else None
    params["ale_source"] = ale_source
    params["ale_parallel"] = ale_parallel
    # 适配器可观测性：与 CLI 同名选项一一对应
    params["adapter_min_endpoint_hit_rate"] = adapter_min_endpoint_hit_rate
    params["adapter_quiet"] = adapter_quiet

    # 多工具：from_tool 优先于 from_ale
    effective_tool = from_tool
    if effective_tool and effective_tool != "none":
        params["from_tool"] = effective_tool
    else:
        params["from_tool"] = None

    params["artra_transfer_kind"] = artra_transfer_kind

    # 剪裁
    params["target_clade"] = target_clade.strip() if target_clade.strip() else None
    params["ancestor_map"] = target_clade_ancestor_map

    # 运行模式
    params["dry_run"] = dry_run
    params["html_report"] = generate_html_report  # 正向语义

    # MCMC
    params["mcmc"] = mcmc
    params["mcmc_iters"] = mcmc_iters
    params["mcmc_temperature"] = mcmc_temperature
    params["mcmc_burn_in"] = mcmc_burn_in
    params["mcmc_thin"] = mcmc_thin
    validate_params(params)

    # 性能
    params["incremental"] = incremental
    params["checkpoint_path"] = checkpoint_path.strip() if checkpoint_path.strip() else None
    params["checkpoint_interval"] = checkpoint_interval

    # 两阶段
    params["constraints_out"] = constraints_out.strip() if constraints_out.strip() else None

    # 输出
    params["output_style"] = output_style

    return params


# ---------------------------------------------------------------------------
# 上游适配器：哪个工具真正消费哪个参数
# ---------------------------------------------------------------------------
# 依据核心层各 convert_from_* 的真实签名（registry._public_kwargs 会把适配器
# 不吃的参数直接丢掉）。界面按它决定显隐，命令生成按它决定输出，
# 二者共用一份事实，不会出现"字段看不见但值仍被写进可复现命令"的漏网。
_ADAPTER_COMMON = ("min_support", "min_family", "cache", "parallel", "quiet")
ADAPTER_FIELDS: Dict[str, Tuple[str, ...]] = {
    "auto": _ADAPTER_COMMON + ("hit_rate", "transfer_kind"),
    "ale": _ADAPTER_COMMON + ("source",),
    "ranger": _ADAPTER_COMMON + ("hit_rate",),
    "eccetera": _ADAPTER_COMMON + ("hit_rate",),
    "artra": _ADAPTER_COMMON + ("hit_rate", "transfer_kind"),
    "alerax": _ADAPTER_COMMON + ("hit_rate",),
}


def adapter_tool_of(params: Dict[str, Any]) -> Optional[str]:
    """解析生效的上游适配器名；``from_ale`` 是 ``from_tool="ale"`` 的兼容别名。"""
    tool = params.get("from_tool")
    if tool:
        return tool
    return "ale" if params.get("from_ale") else None


def adapter_fields_for(tool: Optional[str]) -> Tuple[str, ...]:
    """该工具会消费的参数键；未启用适配器时为空。"""
    return ADAPTER_FIELDS.get(tool or "", ())


def params_to_json(params: Dict[str, Any]) -> Dict[str, Any]:
    """将参数字典序列化为 JSON 可存储的纯字典（去掉 None 值）。

    保留所有非 None 值，以便加载后可完整复现一次运行。
    """
    return {k: v for k, v in params.items() if v is not None}


def json_to_params(data: Dict[str, Any]) -> Dict[str, Any]:
    """从 JSON 字典恢复参数字典（补全缺失键为默认值）。"""
    defaults = _default_params()
    defaults.update(data)
    return defaults


def _default_params() -> Dict[str, Any]:
    """返回 ``collect_params`` 的全默认参数字典。"""
    return {
        "species_tree_path": "",
        "constraints_path": [],
        "seed": 42,
        "local_search": 0.0,
        "temperature": 0.001,
        "random_type": 0,
        "min_transfer_distance": 0,
        "threshold_constraints": 0.0,
        "random_trees": 0,
        "top_k": DEFAULT_NEAR_OPTIMAL_TOP_K,
        "output_prefix": None,
        "from_ale": False,
        "ale_min_support": 0.05,
        "ale_min_family_size": 5,
        "ale_cache_dir": None,
        "ale_source": "trf",
        "ale_parallel": "process",
        "adapter_min_endpoint_hit_rate": DEFAULT_MIN_ENDPOINT_HIT_RATE,
        "adapter_quiet": False,
        "from_tool": None,
        "artra_transfer_kind": "all",
        "target_clade": None,
        "ancestor_map": False,
        "dry_run": False,
        "html_report": True,
        "mcmc": False,
        "mcmc_iters": 1000,
        "mcmc_temperature": MCMC_TEMPERATURE_AUTO,
        "mcmc_burn_in": None,
        "mcmc_thin": None,
        "incremental": True,
        "checkpoint_path": None,
        "checkpoint_interval": 60.0,
        "constraints_out": None,
        "output_style": "short",
    }


def params_to_cli_command(params: Dict[str, Any]) -> str:
    """将参数字典转换为等效的 CLI 命令字符串，便于复现/分享。

    不含 ``print_summary``（CLI 默认打印）。
    """
    parts: List[str] = ["maxtic-next"]

    # 位置参数
    parts.append(f'"{params["species_tree_path"]}"')
    cons = params["constraints_path"]
    if isinstance(cons, list):
        for c in cons:
            parts.append(f'"{c}"')
    else:
        parts.append(f'"{cons}"')

    # 核心参数
    if params.get("seed") != 42:
        parts.append(f"--seed {params['seed']}")
    if params.get("local_search"):
        parts.append(f"--ls {params['local_search']}")
    if params.get("temperature") and params["temperature"] != 0.001:
        parts.append(f"--t {params['temperature']}")
    if params.get("random_type"):
        parts.append(f"--r {params['random_type']}")
    if params.get("min_transfer_distance"):
        parts.append(f"--d {params['min_transfer_distance']}")
    if params.get("threshold_constraints"):
        parts.append(f"--ts {params['threshold_constraints']}")
    if params.get("random_trees"):
        parts.append(f"--rd {params['random_trees']}")
    # ：近优解收集容量 —— 只在偏离默认（50）时出现在命令预览里
    top_k = params.get("top_k", DEFAULT_NEAR_OPTIMAL_TOP_K)
    if top_k is not None and top_k != DEFAULT_NEAR_OPTIMAL_TOP_K:
        parts.append(f"--near-optimal-top-k {top_k}")
    # 上游适配器：--from 是唯一的工具开关；--from-ale 只在没有 --from 时
    # 作为向后兼容路径出现，避免预览里同时冒出两个语义重复的旗标。
    tool = adapter_tool_of(params)
    if params.get("from_tool"):
        parts.append(f"--from {params['from_tool']}")
    elif params.get("from_ale"):
        parts.append("--from-ale")
    # 每个参数只在"当前工具真的消费它"时才输出：未启用适配器时整段消失，
    # 启用 ALE 时也不该带上它并不读的 --min-endpoint-hit-rate。
    fields = set(adapter_fields_for(tool))
    if "transfer_kind" in fields and tool == "artra" and params.get("artra_transfer_kind") != "all":
        parts.append(f"--artra-transfer-kind {params['artra_transfer_kind']}")
    if "min_support" in fields and params.get("ale_min_support") != 0.05:
        parts.append(f"--ale-min-support {params['ale_min_support']}")
    if "min_family" in fields and params.get("ale_min_family_size") != 5:
        parts.append(f"--ale-min-family-size {params['ale_min_family_size']}")
    if "cache" in fields and params.get("ale_cache_dir"):
        parts.append(f'--ale-cache-dir "{params["ale_cache_dir"]}"')
    if "source" in fields and params.get("ale_source") != "trf":
        parts.append(f"--ale-source {params['ale_source']}")
    if "parallel" in fields and params.get("ale_parallel") != "process":
        parts.append(f"--ale-parallel {params['ale_parallel']}")
    if (
        "hit_rate" in fields
        and params.get("adapter_min_endpoint_hit_rate") is not None
        and params.get("adapter_min_endpoint_hit_rate") != DEFAULT_MIN_ENDPOINT_HIT_RATE
    ):
        parts.append(f"--min-endpoint-hit-rate {params['adapter_min_endpoint_hit_rate']}")
    if "quiet" in fields and params.get("adapter_quiet"):
        parts.append("--quiet-adapters")

    # 剪裁
    if params.get("target_clade"):
        parts.append(f'--target-clade "{params["target_clade"]}"')
    if params.get("ancestor_map"):
        parts.append("--target-clade-ancestor-map")

    # 运行模式
    if params.get("dry_run"):
        parts.append("--dry-run")
    if not params.get("html_report", True):
        parts.append("--no-html")

    # MCMC（温度默认 0.0 == auto；预览须能原样复现，含 burn-in / thin）
    if params.get("mcmc"):
        parts.append("--mcmc")
        if params.get("mcmc_iters") != 1000:
            parts.append(f"--mcmc-iters {params['mcmc_iters']}")
        temp = params.get("mcmc_temperature", MCMC_TEMPERATURE_AUTO)
        if temp != MCMC_TEMPERATURE_AUTO:
            parts.append(f"--mcmc-temperature {temp}")
        if params.get("mcmc_burn_in") is not None:
            parts.append(f"--mcmc-burn-in {params['mcmc_burn_in']}")
        if params.get("mcmc_thin") is not None:
            parts.append(f"--mcmc-thin {params['mcmc_thin']}")

    # 性能
    if not params.get("incremental"):
        parts.append("--no-incremental")
    if params.get("checkpoint_path"):
        parts.append(f'--checkpoint "{params["checkpoint_path"]}"')
    if params.get("checkpoint_interval") != 60.0:
        parts.append(f"--checkpoint-interval {params['checkpoint_interval']}")

    # 两阶段
    if params.get("constraints_out"):
        parts.append(f'-o "{params["constraints_out"]}"')

    # 输出前缀（GUI 与 CLI 预览一致性）
    if params.get("output_prefix"):
        parts.append(f'-p "{params["output_prefix"]}"')

    # 输出风格
    if params.get("output_style") != "short":
        parts.append(f"--output-style {params['output_style']}")

    return " ".join(parts)
