#!/usr/bin/env bash
# 一键打包 MaxTiC-Next Studio 为 macOS .app。
#
# 前置（在用于打包的 Python 环境里执行一次）：
#   pip install "git+https://github.com/ZengZichao/MaxTiC-Next.git"   # 核心算法
#   pip install -e .                   # 本 Studio 包（含 PySide6 / matplotlib）
#   pip install PyInstaller
#
# 用法（仓库根目录或任意位置均可）：
#   bash packaging/build_studio_app.sh
#   PYTHON=/path/to/venv/bin/python bash packaging/build_studio_app.sh
#
# 产物：release/MaxTiC-Next-Studio.app
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PY="${PYTHON:-python3}"

# 每次从干净目录出发：spec 会在 build/ 下现算 .icns（由 SVG 母版渲染），
# 若沿用上一轮的 build/ 产物，可能把旧图标打进新包里。
# Finder 会在并发写 .DS_Store 时让单次 rm 失败，所以重试几次而不是直接放弃。
for _ in 1 2 3; do
    rm -rf build 2>/dev/null && break
    sleep 1
done
[ -d build ] && rm -rf build

"$PY" -m PyInstaller packaging/maxtic_studio.spec \
    --noconfirm --distpath build/pyinstaller --workpath build/pyinstaller-work

rm -rf release
mkdir -p release
mv build/pyinstaller/MaxTiC-Next-Studio.app release/

echo
echo "已生成：release/MaxTiC-Next-Studio.app"
echo "首次打开若被 Gatekeeper 拦截：xattr -cr release/MaxTiC-Next-Studio.app"
