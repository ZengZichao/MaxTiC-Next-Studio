#!/usr/bin/env python3
"""应用图标回归测试：SVG 母版必须存在、可被 Qt 渲染、并被打包配置引用。

图标只有 ``src/maxtic_studio/assets/maxtic-studio.svg`` 一份母版：
运行时 QIcon 与 macOS 的 .icns 都从它派生，所以这里同时盯住
"文件在不在包里" 与 "渲染出来是不是空图"。
"""

import os
import re
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

pytest.importorskip("PySide6", reason="PySide6 未安装")

SVG = ROOT / "src" / "maxtic_studio" / "assets" / "maxtic-studio.svg"


def test_svg_master_exists_and_is_well_formed():
    assert SVG.is_file(), f"缺少 SVG 图标母版：{SVG}"
    text = SVG.read_text(encoding="utf-8")
    assert text.lstrip().startswith("<?xml") and "<svg" in text
    assert text.rstrip().endswith("</svg>")
    m = re.search(r'viewBox="0 0 (\d+) (\d+)"', text)
    assert m and m.group(1) == m.group(2), "viewBox 应为正方形，否则图标会被拉扁"
    # 不引用外部资源：冻结到 .app 后没有网络与相对路径可依赖
    assert "http://" not in text.replace("http://www.w3.org", "")
    assert "<image" not in text and "xlink:href" not in text


def test_qicon_renders_non_empty_pixmap_at_small_size():
    from PySide6.QtWidgets import QApplication
    from maxtic_studio.appicon import icon_path, window_icon

    assert icon_path() == str(SVG), "appicon 没解析到包内母版"
    app = QApplication.instance() or QApplication(sys.argv)
    icon = window_icon()
    assert icon is not None and not icon.isNull()
    app.setWindowIcon(icon)
    assert not app.windowIcon().isNull()
    # 16px 是 macOS 标题栏/Dock 缩略的下限，画不出来就等于没有图标
    pixmap = icon.pixmap(16, 16)
    assert not pixmap.isNull() and pixmap.width() == 16
    image = pixmap.toImage()
    opaque = sum(
        1 for x in range(0, 16, 2) for y in range(0, 16, 2) if image.pixelColor(x, y).alpha() > 0
    )
    assert opaque > 20, "16px 渲染结果几乎是透明的"


def test_packaging_declares_icon_sources():
    """spec 必须自己放 icns 并指 CFBundleIconFile。

    不能用 BUNDLE(icon=...)：PyInstaller 会把传入的 icns 重新编码，
    实测丢掉 512/1024 两档，Retina 下的 Dock 图标就发虚了。
    """
    spec = (ROOT / "packaging" / "maxtic_studio.spec").read_text(encoding="utf-8")
    assert "make_app_icon" in spec
    assert "CFBundleIconFile" in spec, "icns 放进去了但没人指向它"
    assert "icon=None" in spec, "仍在用 BUNDLE(icon=)，会被 PyInstaller 重编码"
    assert 'datas.append((_icon_built, "."))' in spec
    assert '"assets"' in spec, "SVG 母版没有随 .app 一起打包"
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "assets/*.svg" in pyproject, "wheel 里不会带上图标母版"


def test_icns_is_generated_from_the_svg_master(tmp_path):
    """.icns 由 SVG 现算，不入库；没有 iconutil 的环境退化为 PNG 也算通过。"""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "make_app_icon", ROOT / "packaging" / "make_app_icon.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    out = mod.build_icns(str(tmp_path / "studio.icns"))
    assert Path(out).is_file() and Path(out).stat().st_size > 0


def test_icns_carries_the_retina_sizes(tmp_path):
    """iconutil 会静默丢掉非规范命名的尺寸，Dock 在 Retina 上就发虚。

    这里把它真正收进去的条目反解出来核对，而不是只信生成脚本的返回值。
    """
    import shutil as sh
    import subprocess

    iconutil = sh.which("iconutil")
    if not iconutil:
        pytest.skip("本机没有 iconutil（非 macOS）")
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "make_app_icon", ROOT / "packaging" / "make_app_icon.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    icns = mod.build_icns(str(tmp_path / "studio.icns"))
    assert icns.endswith(".icns")
    out_set = tmp_path / "back.iconset"
    subprocess.run([iconutil, "-c", "iconset", icns, "-o", str(out_set)], check=True)
    names = {p.name for p in out_set.iterdir()}
    for required in ("icon_512x512.png", "icon_512x512@2x.png", "icon_16x16.png"):
        assert required in names, f".icns 缺少 {required}，实际为 {sorted(names)}"


# --------------------------------------------------------------------------- #
# 文档一致性：仓库之间的依赖必须用 GitHub 仓库地址表达，不能用本地相对路径
# --------------------------------------------------------------------------- #
_LOCAL_PATH_MARKERS = (
    "../MaxTiC",
    "MaxTiC-Next-项目代码",
    "MaxTiC-Next-Studio-项目代码",
    "同级目录",
    "同级仓库",
    "sibling directory",
    "sibling repository",
)
_DOC_FILES = (
    "README.md",
    "README.zh.md",
    "requirements.txt",
    "pyproject.toml",
    "docs/studio.md",
    "docs/studio.en.md",
    "packaging/build_studio_app.sh",
    ".github/workflows/ci.yml",
    "src/maxtic_studio/__init__.py",
    "src/maxtic_studio/main.py",
)


@pytest.mark.parametrize("rel", _DOC_FILES)
def test_docs_never_describe_the_dependency_by_local_path(rel):
    text = (ROOT / rel).read_text(encoding="utf-8")
    hits = [m for m in _LOCAL_PATH_MARKERS if m in text]
    assert not hits, f"{rel} 用本地路径/本地目录名描述了对 MaxTiC-Next 的依赖：{hits}"


@pytest.mark.parametrize(
    "rel",
    (
        "README.md",
        "README.zh.md",
        "requirements.txt",
        "pyproject.toml",
        "docs/studio.md",
        "docs/studio.en.md",
    ),
)
def test_docs_point_the_dependency_at_the_core_repository(rel):
    text = (ROOT / rel).read_text(encoding="utf-8")
    assert "github.com/ZengZichao/MaxTiC-Next" in text, f"{rel} 没给出核心仓库地址"
