# MaxTiC-Next Studio

> Native desktop front-end (PySide6 / Qt 6) · bilingual UI · light & dark themes · no browser engine
>
> [中文](README.md)

MaxTiC ranks the internal nodes of a species tree by **Maximum Time Consistency** (MTC)
against lateral gene transfer constraints. This repository is its **graphical front-end**:
pick files, tune parameters, run, read the ranking, export reports.

The algorithm itself lives in a separate repository, **[`MaxTiC-Next`](https://github.com/ZengZichao/MaxTiC-Next)**
(CLI + Python API). Studio is only an entry point and a view: it calls `maxtic_next.api.rank`
in-process and rewrites no computation. Each repository ships independently and contains
none of the other's code.

---

## Install

```bash
# 1) the core algorithm repository
pip install "git+https://github.com/ZengZichao/MaxTiC-Next.git"

# 2) this repository (pulls in PySide6 and matplotlib)
pip install "git+https://github.com/ZengZichao/MaxTiC-Next-Studio.git"
```

Working from local clones instead: `pip install -e /path/to/MaxTiC-Next` then `pip install -e .`.
Once `MaxTiC-Next` is published to PyPI, step 1 becomes `pip install MaxTiC-Next`.

## Launch

```bash
maxtic-studio          # or: python -m maxtic_studio
```

If the GUI dependencies are missing, `maxtic-studio` prints install instructions and
exits with status `3` instead of dumping a bare traceback. The CLI is unaffected.

## Interface

```
┌────────────────────────────────────────────────────────────────────┐
│ [▶ Run] [■ Cancel]  Preset:[▾] [Reset]      [English▾] [ Light]  │
├───────────────────────────┬────────────────────────────────────────┤
│ Basic │ Advanced          │ Results: 4 metric cards / table / chart│
│  input · core params · CLI│  report · export CSV/PNG/PDF           │
├───────────────────────────┴────────────────────────────────────────┤
│ Log (monospace, colourised, copy/save)                             │
└────────────────────────────────────────────────────────────────────┘
```

- **Live CLI preview** — every parameter edit immediately yields the exact command line
  that reproduces the run.
- **Table ↔ chart linking** — selecting a ranking row highlights the matching bar.
- **Cooperative cancellation** — a long run finishes its current stage and exits cleanly
  rather than being killed.
- **Drag & drop** — drop species trees and constraint files onto the inputs; the last
  directory is remembered.

Full walkthrough: [`docs/studio.en.md`](docs/studio.en.md).

## Language and theme

Both switches sit in the **toolbar**, always visible — no menu digging:

| | Entry points | Behaviour |
|---|---|---|
| Language | "中文 / English" button · Settings menu · `Ctrl+Shift+L` | Redraws every panel, tab, button, placeholder and chart title immediately; no restart |
| Theme | "☀ Light / ☾ Dark" button · Settings menu · `Ctrl+Shift+D` | QPalette, QSS, table striping and matplotlib colours all switch from one token set |

Preferences persist in `QSettings`. See `i18n.py` (a lightweight dict table — no Qt
Linguist build step) and `theme.py` (one design token set; light and dark only change
values, never structure).

## Why the layout never collapses

Qt style-sheet `font-size` / `min-height` affect **painting only** and are not guaranteed
to enter a widget's `sizeHint`. As soon as "painted size > space the layout reserved",
neighbouring widgets start printing over each other. The convention here is:

- every font size and control height lives in `metrics.py` and is applied through
  `setFont()` / `setMinimumHeight()`; QSS keeps only colours, radii and padding;
- both columns are wrapped in a `QScrollArea`, so a short window or a long translation
  produces a scroll bar instead of overlapping controls;
- `enforce_metrics()` runs again after a language switch, because English strings are
  longer and the reserved space has to be recomputed.

## Building the desktop app

```bash
pip install "git+https://github.com/ZengZichao/MaxTiC-Next.git" && pip install -e ".[dev]"
bash packaging/build_studio_app.sh          # -> release/MaxTiC-Next-Studio.app
```

An un-notarised `.app` is blocked by Gatekeeper on first launch: right-click → Open, or
`xattr -cr release/MaxTiC-Next-Studio.app`.

## Tests

```bash
pytest tests/ -q            # GUI cases run on the offscreen Qt platform
```

## Layout

```
src/maxtic_studio/
├── main.py            entry point: QApplication + theme assembly
├── main_window.py     toolbar / split layout / menus / run control / preferences
├── metrics.py         control sizes and font tokens (single source of truth)
├── theme.py           light/dark design tokens → QPalette + QSS
├── appicon.py         locates and renders the SVG icon master
├── i18n.py            zh/en tables and the _() lookup
├── params.py          parameter collection, validation, JSON round-trip, CLI builder
├── run_engine.py      QThread run engine (log stream / stages / cancellation)
├── cancellation.py    StopToken / per-task stdout guard
├── node_scores.py     per-node objective deltas (Qt-free)
├── results_view.py    ranking table model
├── widgets/           input / advanced / results / log panels
└── assets/            maxtic-studio.svg — the single icon master
packaging/             PyInstaller spec, build script, SVG→.icns generator
examples/              demo data (bundled into the .app)
docs/                  user manual (zh / en)
tests/                 GUI smoke, no-overlap layout, adapter visibility matrix, icon tests
```

## License

CeCILL 2.1, same as the core repository. Charts depend on matplotlib (PSF family), the GUI
on PySide6 (LGPL).
