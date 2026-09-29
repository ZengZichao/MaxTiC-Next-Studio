#!/usr/bin/env python3
"""由 SVG 母版生成应用图标（macOS .icns / 预览 PNG）。

SVG 是唯一母版：``assets/maxtic-studio.svg`` 改一次，运行时图标（Qt 直接吃 SVG）
与 macOS 打包图标（.icns）都从这里派生，避免"改了 SVG 忘了改 icns"的漂移。

渲染用 Qt 自己的 SVG 模块，因此不引入 rsvg / cairosvg / Inkscape 之类外部依赖
——PySide6 本来就是 Studio 的硬依赖。

用法：

    python packaging/make_app_icon.py --png /tmp/icon.png          # 预览
    python packaging/make_app_icon.py --icns release/maxtic.icns   # 打包用
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SVG = os.path.join(REPO_ROOT, "src", "maxtic_studio", "assets", "maxtic-studio.svg")

# iconutil 只认这套规范命名（16/32/128/256/512 及其 @2x）；
# 写成 64 或 1024 会被它静默丢掉，Dock 在 Retina 上就会发虚。
ICNS_BASE = (16, 32, 128, 256, 512)


def _qt_offscreen_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QGuiApplication

    app = QGuiApplication.instance() or QGuiApplication(sys.argv)
    return app


def render(png_path: str, size: int = 512, svg_path: str = SVG) -> None:
    """把 SVG 按 ``size`` 渲染成 PNG（含 alpha）。"""
    from PySide6.QtGui import QIcon, QPixmap
    import PySide6.QtSvg  # 触发可用性检查：缺 QtSvg 时这里就报错，而不是静默出空图标

    del PySide6

    _qt_offscreen_app()
    icon = QIcon(svg_path)
    if icon.isNull():
        raise SystemExit(f"Qt 无法加载 SVG 图标：{svg_path}（检查 PySide6 的 QtSvg 模块）")
    pixmap: QPixmap = icon.pixmap(size, size)
    if pixmap.isNull():
        raise SystemExit(f"SVG 渲染失败：{svg_path} @ {size}px")
    if not pixmap.save(png_path):
        raise SystemExit(f"PNG 写入失败：{png_path}")


def build_icns(icns_path: str, svg_path: str = SVG) -> str:
    """生成 .icns。非 macOS 或无 iconutil 时退化为一份 1024px PNG。"""
    iconutil = shutil.which("iconutil")
    if not iconutil:
        fallback = os.path.splitext(icns_path)[0] + ".png"
        render(fallback, 1024, svg_path)
        print(f"未找到 iconutil，已退化为 PNG：{fallback}")
        return fallback

    workdir = tempfile.mkdtemp(prefix="maxtic-iconset-")
    try:
        set_dir = os.path.join(workdir, "icon.iconset")
        os.makedirs(set_dir)
        for px in ICNS_BASE:
            render(os.path.join(set_dir, f"icon_{px}x{px}.png"), px, svg_path)
            render(os.path.join(set_dir, f"icon_{px}x{px}@2x.png"), px * 2, svg_path)
        os.makedirs(os.path.dirname(os.path.abspath(icns_path)), exist_ok=True)
        subprocess.run([iconutil, "-c", "icns", set_dir, "-o", icns_path], check=True)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    return icns_path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--png", help="渲染一张预览 PNG")
    ap.add_argument("--icns", help="生成 .icns 到该路径")
    ap.add_argument("--size", type=int, default=512)
    ap.add_argument("--svg", default=SVG)
    a = ap.parse_args()
    if a.png:
        render(a.png, a.size, a.svg)
        print(f"已生成 {a.png}")
    if a.icns:
        print(f"已生成 {build_icns(a.icns, a.svg)}")
    if not (a.png or a.icns):
        ap.error("需要 --png 或 --icns")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
