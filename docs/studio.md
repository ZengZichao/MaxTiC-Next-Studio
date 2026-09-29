# MaxTiC-Next Studio —— 原生桌面端使用说明

> 🌐 English version: [studio.en.md](studio.en.md)

MaxTiC-Next Studio 是 MaxTiC-Next 的**原生图形化桌面端**（PySide6 / Qt 6）。
它与命令行核心共享同一算法（`maxtic_next.api.rank`），但作为**独立仓库、独立发行物**
维护：本仓库只依赖已安装的 `MaxTiC-Next` 包，核心包不再包含任何 GUI 代码。

## 安装

Studio 依赖独立仓库 [`MaxTiC-Next`](https://github.com/ZengZichao/MaxTiC-Next)，先装核心、再装 Studio：

```bash
# 1) 核心算法（CLI + Python API）
pip install "git+https://github.com/ZengZichao/MaxTiC-Next.git"

# 2) Studio 桌面端（会一并拉起 PySide6 / matplotlib）
pip install "git+https://github.com/ZengZichao/MaxTiC-Next-Studio.git"
```

已把仓库克隆到本地时，改用可编辑安装即可：`pip install -e /path/to/MaxTiC-Next`，
再在 Studio 仓库根目录 `pip install -e .`。`MaxTiC-Next` 发布到 PyPI 之后，
第 1 步直接写 `pip install MaxTiC-Next`，甚至省略——pip 会替本仓库解析该依赖。

安装后获得一个命令：
- `maxtic-studio`：GUI 入口

（`maxtic-next` CLI 入口由核心仓库提供，与本仓库无关。）

> **没装 PySide6 时的行为**：`maxtic-studio` 入口点是无条件注册的，直接抛
> `ModuleNotFoundError` 回溯对用户毫无帮助，因此它先给出安装指引、再**以退出码 3 退出**：
>
> ```
> $ maxtic-studio
> MaxTiC-Next Studio 需要 GUI 依赖 PySide6（以及 matplotlib）。
> 安装：pip install "git+https://github.com/ZengZichao/MaxTiC-Next-Studio.git"
> 命令行功能不受影响：请使用核心仓库 MaxTiC-Next 的 maxtic-next。
> $ echo $?
> 3
> ```

## 启动

```bash
maxtic-studio
```

或在 Python 中启动：

```python
from maxtic_studio.main import main
main()
```

## 界面布局

```
┌──────────────────────────────────────────────────────────────────┐
│ 菜单：文件 | 运行 | 视图 | 设置 | 帮助                             │
├──────────────────────────────────────────────────────────────────┤
│ [运行 ▶] [取消 ■]  预设:[____▾] [重置默认]  [中文▾] [☀ 浅色]  就绪 │
├──────────────────────────────┬───────────────────────────────────┤
│ 基本设置 │ 高级参数           │ 结果：4 张指标卡                  │
│  输入（物种树 / 约束 / 前缀）│  [排名表格] [排名条形图]          │
│  核心参数（7 项）            │                                   │
│  实时 CLI 命令（只读）       │  [打开报告]      [用示例数据演示] │
│                              │  [导出 CSV] [导出 PNG] [导出 PDF] │
├──────────────────────────────┴───────────────────────────────────┤
│ 日志：[复制] [清空] [保存] + 等宽着色输出                        │
└──────────────────────────────────────────────────────────────────┘
```

工具条右侧的两个按钮是**语言**与**亮/暗主题**开关（详见下方两节）。
左栏与右栏各自包在滚动区里：窗口变矮时出滚动条，控件不会互相压字。

## 快速开始（5 分钟跑通一次示例）

1. 启动 `maxtic-studio`
2. 菜单 → **运行** → **用示例数据演示**（自动加载 `examples/minitree.tree` + `examples/Cyano_CUTConstraints.tsv`）
3. 点击 **运行 ▶**
4. 日志面板实时显示运行进度
5. 完成后右侧出现排名表与条形图
6. 点击 **在外部浏览器打开 HTML 报告** 查看交互式报告

## 参数说明

### 输入

| 参数 | 说明 |
|---|---|
| 物种树 | Newick 格式文件（内部节点标签在 bootstrap 字段） |
| 约束 | 一个或多个约束文件（空格或逗号双格式 TSV） |

> 两者都**透明支持压缩输入**：`.gz` / gzip 流与 tar 归档（`.tar.gz` / `.tgz` /
> `.tar`）可直接选入，不需要先手工解压；上游官方示例包（如 ALE 的
> `examples/reconciliations.tgz`）也能整包选用。边界与实测见手册 05 章 5.7。

### 核心参数

| 参数 | 默认 | 说明 |
|---|---|---|
| 随机种子 | 42 | 驱动 mix 平局与局部搜索 |
| 局部搜索时长 | 0 秒 | 0 = 关闭 |
| Metropolis 温度 | 0.001 | 局部搜索的接受尺度；越小越保守 |
| 随机化类型 | 0 | 0/1/2 |
| 最小转移距离 | 0 | 按 phylogenetic distance 列过滤 |
| 约束权重阈值 | 0.0 | 按权重比例过滤 |
| 随机树采样数 | 0 | 0 = 关闭 |

### 高级参数（标签页折叠）

- **上游适配器**：5 个上游工具与自动检测合并在同一页，由一个「上游工具适配器」
  下拉选择；下方**只展示当前所选工具真正会消费的参数**。

  | 所选工具 | 对应 CLI | 页面上出现的参数 |
  |---|---|---|
  | 无 | ——（按原生 TSV 解析） | 仅一行说明 |
  | 自动检测 | `--from auto` | 通用 5 项 + 端点命中率 + ARTra 转移类别 |
  | ALE | `--from ale` | 通用 5 项 + 约束来源口径（`--ale-source`） |
  | RANGER-DTLx / ecceTERA / AleRax | `--from ranger` 等 | 通用 5 项 + 端点命中率 |
  | ARTra | `--from artra` | 通用 5 项 + 端点命中率 + 转移类别 |

  「通用 5 项」= 最小支持度、最小家族规模、缓存目录、并行模式、静默适配器诊断。
  显隐矩阵按核心层各 `convert_from_*` 的真实签名推导：`convert_from_ale` 没有
  `min_endpoint_hit_rate` 入参，所以 ALE 下不显示端点命中率；转移类别只在 ARTra
  （以及可能检出 ARTra 的自动检测）下出现。选「无」时 `--ale-*` 等参数不会进入
  实时 CLI 预览，也不会写进保存的配置——它们没有消费方。
- **剪裁**：目标类群根节点剪裁
- **MCMC**：可逆 MH 采样器（初步实现，收敛诊断未经验证；样本不得当作后验使用）。
  **温度默认为 `auto`**（哨兵值 `0.0`，按实例的能量尺度即 `max(总权重,1)/100` 推导），
  与 CLI 一致；spin 框的范围就是 `auto` 这一档起步，并显示为
  `auto（按实例能量尺度推导）`，需要固定温度时才填正数（旧 GUI 下限为
  1e-6、默认 0.01，而 0.01 恰是让链实际冻结的温度，GUI 因此只会产出“不是后验样本”的样本；
  三个预设 quick / standard / strict 现也统一用 `auto`）
- **检查点**：长任务断点续跑
- **输出**：两阶段约束输出、命名风格（short / legacy）

> 近优解收集容量（CLI `--near-optimal-top-k` / API `top_k`）**没有** GUI 控件：桌面端固定用
> 默认值 50，即稳健性/敏感性摘要最多考察 50 个去重近优序。要放宽支持集请用 CLI 或 Python API
> （手册 03 章 3.6b、08 章 8.1b）。

## 取消运行

「取消 ■」按钮与 **菜单 → 运行 → 取消** 都走 `_on_cancel` → `RunEngine.cancel()` →
`gui/cancellation.py` 的 `StopToken`；令牌由 `cancellation_hook` 探测形参名后以
**`api.rank(stop_check=token.should_stop)`** 注入，一路传到
`Ranker.run` → `optimisation_locale`（局部搜索主循环体第一条语句）与
`MCMCSampler.sample`（每次链步之间）。因此：

- 取消在**迭代边界**真正打断计算，交付的是**截至取消点**的历史最优序，不抛异常、不毁掉结果；
  日志面板会推送一条说明，`run_metadata["cancelled"]` 可机器复核；
- 这与旧行为不同——过去按钮只是“等它跑完再丢弃结果”；
- 若下层不再接受该形参，日志面板会显式提示“当前内核版本不接受取消回调，取消只能在阶段边界生效”，
  而不是假装能中断；
- 唯一例外：一条还没产出任何样本就被取消的 MCMC 链会报错，而不是返回空统计（手册 08 章 8.9）。

## 配置管理

- **保存配置**（Ctrl+S）：将当前所有参数导出为 JSON 文件（含等效 CLI 命令）
- **打开配置**（Ctrl+O）：从 JSON 文件恢复参数
- 配置文件可分享给 CLI 用户复现实验

## 语言切换

工具条右侧的 **「中文 / English」** 按钮即当前界面语言，点开可直接选择另一种；
菜单 **设置 → 语言** 里有同一组选项。切换**立即生效**，无需重启：所有面板、
标签页、按钮、占位符、菜单和图表标题都会即时重画，并自动重算控件尺寸
（英文文案更长，重算后依旧不会互相挤压）。

语言偏好自动保存（QSettings），重启后保持。

## 亮 / 暗主题切换

工具条右侧的 **「☀ 浅色 / ☾ 深色」** 按钮即当前主题，点开可切换；
菜单 **设置 → 深色主题** 是同一个开关。两套主题共用一组设计令牌
（`theme.py` 的 `LIGHT` / `DARK`），QPalette、QSS、表格斑马纹与 matplotlib
图表配色全部同源，切换后图表立即按新令牌重绘。

主题偏好同样存入 QSettings，重启后保持。

## 快捷键

| 快捷键 | 功能 |
|---|---|
| Ctrl+R | 开始运行 |
| Ctrl+O | 打开配置 |
| Ctrl+S | 保存配置 |
| Ctrl+Shift+L | 在中文 / English 之间切换 |
| Ctrl+Shift+D | 在浅色 / 深色主题之间切换 |
| Ctrl+Q | 退出 |

## 打包分发

### 预打包应用（随发布一同提供）

正式发布包内含已冻结的 macOS 应用 **`release/MaxTiC-Next-Studio.app`**，
无需安装 Python 环境即可双击运行（首次打开见下方 Gatekeeper 说明）。

### 自行打包

打包配置在 `packaging/maxtic_studio.spec`，一键脚本：

```bash
# macOS（产物：release/MaxTiC-Next-Studio.app）
bash packaging/build_studio_app.sh
```

从同一软件包冻结桌面二进制：

```bash
# macOS / Linux / Windows
pyinstaller packaging/maxtic_studio.spec --noconfirm
```

### macOS 首次打开

未公证的 `.app` 在 Gatekeeper 下首次打开会报“无法验证开发者”：
- **方法一**：右键 → 打开 → 仍要打开
- **方法二**：终端执行 `xattr -cr /path/to/MaxTiC-Next-Studio.app`

## 应用图标

图标只有一份母版：`src/maxtic_studio/assets/maxtic-studio.svg` —— 一棵有根物种树、
一条跨越分支的横向转移弧、一个被点亮的内部节点（即 MTC 排名的对象），
配色取自 `theme.py` 的品牌令牌。

- **运行时**：`appicon.py` 定位该 SVG，交给 Qt 直接渲染为窗口图标与 macOS Dock 图块，
  源码运行、wheel 安装、`.app` 冻结三种形态都能找到它；
- **打包**：`packaging/make_app_icon.py` 用同一份 SVG 现场光栅化出 `.icns`
  （Qt SVG 渲染 + `iconutil`），再由 spec 传给 `BUNDLE(icon=...)`。

所以改图标只需改 SVG：仓库里不维护手画的 png/icns，也不存在两处不同步。
预览：`python packaging/make_app_icon.py --png /tmp/icon.png`。

> 一个踩过的坑：spec 里**不要**用 `BUNDLE(icon=...)` 传 icns。PyInstaller 会把传入的
> icns 重新编码一遍，实测丢掉 512/1024 两档，Retina 下的 Dock 图标就发虚了。现在改为
> 把我们自己 `iconutil` 出来的 icns 原样放进 `Contents/Resources`，再写 `CFBundleIconFile`。

## 技术架构

```
MaxTiC-Next Studio (PySide6 原生桌面端)
├─ UI 层：主窗口 / 表单 / 日志 / 结果视图
├─ 度量层：metrics.py 统一字号与控件高度（布局与绘制同源）
├─ 控制层：参数组装、运行引擎（QThread）
└─ 适配层：直接调用 maxtic_next.api.rank（同进程，非子进程）
```

- **无浏览器引擎**：不依赖 Chromium / WebView / Electron
- **算法复用**：GUI 仅作入口与展示，不重写算法
- **线程安全**：`api.rank` 在 QThread 中执行，stdout 流式推送至日志面板
