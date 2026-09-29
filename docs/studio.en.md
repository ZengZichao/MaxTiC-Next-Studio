# MaxTiC-Next Studio — Native Desktop Application User Guide

> 🌐 Chinese version: [studio.md](studio.md)

MaxTiC-Next Studio is the **native graphical desktop application** for MaxTiC
(PySide6 / Qt 6). It calls the same core algorithm (`maxtic_next.api.rank`) as the
`maxtic-next` command line, in-process. It is maintained as a **separate repository and
separate release artefact**: this repo depends on the installed `MaxTiC-Next` package and
contains no algorithm code, while the core repo contains no GUI code.

## Installation

```bash
# 1) the core algorithm repository
pip install "git+https://github.com/ZengZichao/MaxTiC-Next.git"

# 2) this repository (pulls in PySide6 and matplotlib)
pip install "git+https://github.com/ZengZichao/MaxTiC-Next-Studio.git"
```

After installation you get one command:
- `maxtic-studio`: the GUI entry point

(`maxtic-next` is provided by the core repository and is unrelated to this one.)

> **Behaviour when the GUI dependencies are missing**: the `maxtic-studio` entry point is
> registered unconditionally in `pyproject`, so rather than dumping a raw
> `ModuleNotFoundError` traceback it prints installation guidance and **exits with code 3**:
>
> ```
> $ maxtic-studio
> MaxTiC-Next Studio requires the GUI dependencies PySide6 (and matplotlib).
> Run `pip install -e .` at the root of the Studio repository.
> The command line is unaffected: use maxtic-next from the core repository.
> $ echo $?
> 3
> ```

## Launching

```bash
maxtic-studio
```

Or launch it from Python:

```python
from maxtic_studio.main import main
main()
```

## Interface layout

```
┌──────────────────────────────────────────────────────────────────┐
│ Menu: File | Run | View | Settings | Help                        │
├──────────────────────────────────────────────────────────────────┤
│ [Run ▶] [Cancel ■]  Preset:[____▾] [Reset]  [English▾] [☀ Light]│
├────────────────────────────────┬─────────────────────────────────┤
│ Basic │ Advanced               │ Results: 4 metric cards         │
│  inputs (tree / constraints /  │  [Ranking table] [Bar chart]    │
│          prefix)               │                                 │
│  core parameters (7 fields)    │  [Open report]   [Run demo]     │
│  live CLI command (read-only)  │  [CSV] [PNG] [PDF]              │
├────────────────────────────────┴─────────────────────────────────┤
│ Log: [Copy] [Clear] [Save] + colourised monospace output         │
└──────────────────────────────────────────────────────────────────┘
```

## Quick start (run the bundled example in 5 minutes)

1. Launch `maxtic-studio`
2. Menu → **Run** → **Demo with example data** (automatically loads
   `examples/minitree.tree` + `examples/Cyano_CUTConstraints.tsv`)
3. Click **Run ▶**
4. The log panel shows the run progress in real time
5. When the run finishes, the ranking table and bar chart appear on the right
6. Click **Open HTML report in external browser** to view the interactive report

## Parameter reference

### Inputs

| Parameter | Description |
|---|---|
| Species tree | Newick-format file (internal node labels in the bootstrap field) |
| Constraints | One or more constraint files (dual-format TSV, space- or comma-separated) |

> Both inputs **transparently support compressed data**: `.gz` / gzip streams and tar
> archives (`.tar.gz` / `.tgz` / `.tar`) can be selected directly, with no need to
> decompress them by hand first; official upstream example bundles (such as ALE's
> `examples/reconciliations.tgz`) can also be selected as a whole. Boundaries and
> verified behavior: see manual chapter 05 §5.7.

### Core parameters

| Parameter | Default | Description |
|---|---|---|
| Random seed | 42 | Drives `mix` tie-breaking and local search |
| Local search duration | 0 s | 0 = disabled |
| Metropolis temperature | 0.001 | Acceptance scale of the local search; smaller is more conservative |
| Randomization type | 0 | 0/1/2 |
| Minimum transfer distance | 0 | Filters by the phylogenetic distance column |
| Constraint weight threshold | 0.0 | Filters by weight proportion |
| Number of randomized tree samples | 0 | 0 = disabled |

### Advanced parameters (collapsed tabs)

- **Upstream Adapters**: the five upstream tools plus auto-detection now share a single
  page driven by one "Upstream Tool Adapter" combo box, and **only the parameters the
  selected tool actually consumes are shown**.

  | Selected tool | CLI equivalent | Fields shown |
  |---|---|---|
  | None | — (native TSV parsing) | a one-line note only |
  | Auto-detect | `--from auto` | 5 common + endpoint hit rate + ARTra transfer kind |
  | ALE | `--from ale` | 5 common + constraint source (`--ale-source`) |
  | RANGER-DTLx / ecceTERA / AleRax | `--from ranger`, … | 5 common + endpoint hit rate |
  | ARTra | `--from artra` | 5 common + endpoint hit rate + transfer kind |

  The "5 common" fields are min support, min family size, cache directory, parallel mode
  and silence-adapter-diagnostics. The visibility matrix is derived from the real
  signatures of the core `convert_from_*` functions: `convert_from_ale` has no
  `min_endpoint_hit_rate` parameter, so that field is hidden for ALE, and the transfer
  kind only appears for ARTra (and for auto-detection, which may resolve to ARTra).
  With "None" selected, `--ale-*` and friends are kept out of the live CLI preview and out
  of saved configurations — nothing would read them.
- **Pruning**: prune at the root node of the target taxon
- **MCMC**: reversible MH sampler (preliminary implementation; convergence diagnostics
  are not validated; samples must not be treated as posterior draws).
  **The temperature defaults to `auto`** (sentinel value `0.0`, derived from the
  per-instance energy scale, i.e. `max(total weight, 1)/100`), consistent with the CLI;
  the spin box starts from the `auto` level, displayed as
  `auto (derived from the per-instance energy scale)`; enter a positive number only when
  you need a fixed temperature (the old GUI had a lower bound of 1e-6 and a default of
  0.01, yet 0.01 is exactly the temperature at which the chain effectively freezes, so
  that GUI would only ever produce samples that "are not posterior samples"; the three
  presets quick / standard / strict now also uniformly use `auto`)
- **Checkpoint**: checkpoint/resume for long-running tasks
- **Output**: two-stage constraint output; naming style (short / legacy)

> The near-optimal solution collection capacity (CLI `--near-optimal-top-k` /
> API `top_k`) has **no** GUI control: the desktop app always uses the default value of
> 50, i.e. the robustness/sensitivity summary examines at most 50 deduplicated
> near-optimal rankings. To widen the support set, use the CLI or the Python API
> (manual chapter 03 §3.6b, chapter 08 §8.1b).

## Cancelling a run

Both the **Cancel ■** button and **Menu → Run → Cancel** go through `_on_cancel` →
`RunEngine.cancel()` → the `StopToken` in `gui/cancellation.py`; the token is probed by
parameter name by `cancellation_hook` and injected as
**`api.rank(stop_check=token.should_stop)`**, and is passed all the way down to
`Ranker.run` → `optimisation_locale` (the first statement of the local-search main loop
body) and `MCMCSampler.sample` (between each chain step). Therefore:

- Cancellation genuinely interrupts the computation at **iteration boundaries** and
  delivers the best ranking found **up to the cancellation point**, without raising an
  exception and without destroying the results; the log panel pushes a notice, and
  `run_metadata["cancelled"]` can be checked programmatically;
- This differs from the old behavior, in which the button merely "waited for the run to
  finish and then discarded the results";
- If the underlying layer no longer accepts that parameter, the log panel explicitly
  reports "the current kernel version does not accept a cancellation callback;
  cancellation only takes effect at stage boundaries" instead of pretending it can
  interrupt;
- The only exception: an MCMC chain cancelled before it has produced any sample raises
  an error instead of returning empty statistics (manual chapter 08 §8.9).

## Configuration management

- **Save configuration** (Ctrl+S): exports all current parameters to a JSON file
  (including the equivalent CLI command)
- **Open configuration** (Ctrl+O): restores parameters from a JSON file
- Configuration files can be shared with CLI users to reproduce experiments

## Language switching

Menu → **Settings** → **Language** → Chinese / English. A restart of the application is
required for the change to take effect. The language preference is saved automatically
(QSettings) and persists across restarts.

## Keyboard shortcuts

| Shortcut | Function |
|---|---|
| Ctrl+R | Start a run |
| Ctrl+O | Open configuration |
| Ctrl+S | Save configuration |
| Ctrl+Q | Quit |

## Packaging and distribution

### Pre-built application (shipped with releases)

Official release bundles include the frozen macOS application
**`release/MaxTiC-Next-Studio.app`**, which can be launched by double-clicking without
installing a Python environment (for the first launch, see the Gatekeeper notes below).

### Building the package yourself

The packaging configuration lives in `packaging/maxtic_studio.spec`; one-shot script:

```bash
# macOS (artifact: release/MaxTiC-Next-Studio.app)
bash packaging/build_studio_app.sh
```

To freeze the desktop binary from the same package:

```bash
# macOS / Linux / Windows
pyinstaller packaging/maxtic_studio.spec --noconfirm
```

### First launch on macOS

The first launch of an un-notarized `.app` under Gatekeeper reports "unable to verify
the developer":
- **Method 1**: right-click → Open → Open anyway
- **Method 2**: run `xattr -cr /path/to/MaxTiC-Next-Studio.app` in a terminal

## Application icon

There is exactly one icon master: `src/maxtic_studio/assets/maxtic-studio.svg` — a rooted
species tree, a lateral transfer arc crossing branches, and one lit-up internal node (the
thing MTC ranks), coloured from the brand tokens in `theme.py`.

- **At runtime**: `appicon.py` locates the SVG and Qt renders it directly as the window
  icon and the macOS Dock tile; it resolves from a source checkout, an installed wheel and
  a frozen `.app` alike.
- **When packaging**: `packaging/make_app_icon.py` rasterises the same SVG into an `.icns`
  (Qt SVG rendering + `iconutil`), which the spec hands to `BUNDLE(icon=...)`.

Changing the icon therefore means editing the SVG only: no hand-drawn png/icns is kept in
the repository, and the two cannot drift apart.
Preview: `python packaging/make_app_icon.py --png /tmp/icon.png`.

> One trap worth recording: do **not** hand the icns to `BUNDLE(icon=...)`. PyInstaller
> re-encodes whatever you pass it and, measured here, silently drops the 512/1024 variants,
> which makes the Dock icon soft on Retina. The spec instead drops our own `iconutil` output
> verbatim into `Contents/Resources` and points `CFBundleIconFile` at it.

## Technical architecture

```
MaxTiC-Next Studio (native PySide6 desktop app)
├─ UI layer: main window / forms / log / result views
├─ Metrics layer: metrics.py owns font sizes and control heights
│                (painting and layout reservation come from one source)
├─ Control layer: parameter assembly, run engine (QThread)
└─ Adapter layer: calls maxtic_next.api.rank directly (same process, not a subprocess)
```

- **No browser engine**: no dependency on Chromium / WebView / Electron
- **Algorithm reuse**: the GUI serves only as an entry point and a display layer; the
  algorithms are not reimplemented
- **Thread safety**: `api.rank` runs inside a QThread, and stdout is streamed to the
  log panel
