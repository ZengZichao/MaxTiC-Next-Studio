# MaxTiC-Next Studio

> 原生桌面端（PySide6 / Qt 6）· 中英双语 · 亮暗双主题 · 免浏览器引擎
>
> 🌐 [English](README.en.md)

MaxTiC 用「最大时间一致性（MTC）」给物种树内部节点排序，以解释基因横向转移（HGT）
约束。本仓库是它的**图形化前端**：填参数、选文件、点运行、看排名、导出报告。

算法本身不在这里——它来自独立仓库 **[`MaxTiC-Next`](https://github.com/ZengZichao/MaxTiC-Next)**（CLI + Python API）。
Studio 只是入口与展示层，直接同进程调用 `maxtic_next.api.rank`，不重写、不 fork 任何
计算逻辑。两个仓库各自独立发行，互不含对方代码。

---

## 安装

```bash
# 1) 核心算法仓库
pip install "git+https://github.com/ZengZichao/MaxTiC-Next.git"

# 2) 本仓库（会一并拉起 PySide6 与 matplotlib）
pip install "git+https://github.com/ZengZichao/MaxTiC-Next-Studio.git"
```

已克隆到本地时改用可编辑安装：`pip install -e /path/to/MaxTiC-Next` 与 `pip install -e .`。
`MaxTiC-Next` 发布到 PyPI 后，第 1 步就是 `pip install MaxTiC-Next`。

## 启动

```bash
maxtic-studio          # 或 python -m maxtic_studio
```

没有安装 GUI 依赖时，`maxtic-studio` 不会抛裸回溯，而是打印安装指引并以退出码 `3` 退出；
命令行功能不受影响。

## 界面

```
┌────────────────────────────────────────────────────────────────────┐
│ [▶ 运行] [■ 取消]  预设:[▾] [重置默认]      [中文▾] [ 浅色]  就绪 │
├───────────────────────────┬────────────────────────────────────────┤
│ 基本设置 │ 高级参数        │ 结果：4 张指标卡 / 排名表 / 条形图     │
│  输入 · 核心参数 · CLI    │ 报告 · 导出 CSV/PNG/PDF                │
├───────────────────────────┴────────────────────────────────────────┤
│ 日志（等宽、着色、可复制/保存）                                    │
└────────────────────────────────────────────────────────────────────┘
```

- **实时 CLI 预览**：面板里改任何参数，下方即时给出可复制粘贴复现同一次运行的命令行。
- **表 ↔ 图联动**：点排名表某一行，条形图对应条高亮。
- **协作式取消**：长跑任务不会强杀，当前阶段跑完后干净退出。
- **拖拽输入**：物种树 / 约束文件可直接拖进输入框；目录位置被记住。

完整使用说明见 [`docs/studio.md`](docs/studio.md)
（[English](docs/studio.en.md)）。

## 双语与双主题

两个开关都在**工具条右侧**，一眼可见，不必翻菜单：

| | 入口 | 行为 |
|---|---|---|
| 界面语言 | 「中文 / English」按钮 · 设置菜单 · `Ctrl+Shift+L` | 立即重画全部面板、标签、按钮、占位符与图表标题，无需重启 |
| 界面主题 | 「☀ 浅色 / ☾ 深色」按钮 · 设置菜单 · `Ctrl+Shift+D` | QPalette、QSS、表格斑马纹与 matplotlib 配色同源切换 |

偏好写入 `QSettings`，重启保留。实现见 `i18n.py`（轻量 dict 翻译表，不引入 Qt Linguist
构建步骤）与 `theme.py`（一套设计令牌，浅/深只换值不换结构）。

## 布局为什么不会挤成一团

Qt 的 QSS `font-size` / `min-height` 只影响**绘制**，不保证进入控件的 `sizeHint`。
一旦「画出来的尺寸 > 布局预留的尺寸」，相邻控件就会互相压字。本仓库的约定是：

- 字号与控件高度全部集中在 `metrics.py`，通过 `setFont()` / `setMinimumHeight()` 落到
  控件上；QSS 只保留颜色、圆角与内边距；
- 左右两栏内容各包一层 `QScrollArea`：窗口再矮、文案再长，也只会出滚动条，
  不会让控件重叠；
- 语言切换后重跑一次 `enforce_metrics()`，因为英文文案更长，预留空间要跟着重算。

## 打包为桌面应用

```bash
pip install "git+https://github.com/ZengZichao/MaxTiC-Next.git" && pip install -e ".[dev]"
bash packaging/build_studio_app.sh          # 产物：release/MaxTiC-Next-Studio.app
```

未公证的 `.app` 首次打开会被 Gatekeeper 拦下：右键 → 打开，或
`xattr -cr release/MaxTiC-Next-Studio.app`。

## 测试

```bash
pytest tests/ -q            # GUI 用例自动走 offscreen 平台
```

## 目录结构

```
src/maxtic_studio/
├── main.py            入口：QApplication + 主题装配
├── main_window.py     主窗口：工具条 / 分割布局 / 菜单 / 运行控制 / 偏好
├── metrics.py         控件尺寸与字号令牌（布局与绘制的唯一事实来源）
├── theme.py           浅/深设计令牌 → QPalette + QSS
├── appicon.py         定位并渲染 SVG 图标母版（源码/安装/冻结三态通用）
├── i18n.py            中/英翻译表与 _() 查询
├── params.py          参数收集、校验、JSON 互转、CLI 命令拼装
├── run_engine.py      QThread 运行引擎（日志流 / 阶段 / 取消）
├── cancellation.py    StopToken / 每任务 stdout 守卫
├── node_scores.py     逐节点目标值变化量（不依赖 Qt）
├── results_view.py    排名表模型
├── widgets/           输入 / 高级参数 / 结果 / 日志 四个面板
└── assets/            maxtic-studio.svg —— 应用图标唯一母版
packaging/             PyInstaller spec、一键打包脚本、SVG→.icns 生成器
examples/              演示数据（随 .app 内置）
docs/                  使用说明（中 / 英）
tests/                 GUI 冒烟、布局不重叠、适配器显隐矩阵等回归用例
```

## 许可

CeCILL 2.1（与核心仓库一致）。图表依赖 matplotlib（PSF 系），GUI 依赖 PySide6（LGPL）。
