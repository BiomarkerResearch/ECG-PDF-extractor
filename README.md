[![GitHub ECG-PDF-Extractor](https://img.shields.io/badge/github-ECG--PDF--Extractor-blue?logo=github)](https://github.com/BiomarkerResearch/ECG-PDF-extractor)  [![Python](https://img.shields.io/badge/Python-100_%25-blue?logo=python&logoColor=fff)](#)

# ECG-PDF-extractor

This python tool extracts raw **12-lead ECG waveforms** and **clinical metadata** from PDF files produced by
**GE CardioSoft** and **Schiller** ECG devices — no proprietary export formats, no XML,
no manual digitizing. The tool parses the raw vector graphics inside the PDF, recovers
the original waveform samples, calibrates them to physical units (µV), and writes clean,
analysis-ready CSV data for e.g. machine learning pipelines or clinical research.

```
ECG PDF (Cardiosoft / Schiller)  ──►  12-lead waveform CSVs (µV, 500 Hz)  +  ECG_records.csv (metadata)
```

---

This tool is based on our project "A data-pipeline processing electrocardiogram recordings for use in artificial intelligence algorithms" (Authors: J. Prim , T. Uhlemann , N. Gumpfer , D. Gruen , S. Wegener , S. Krug , J. Hannig , T. Keller , M. Guckert) presented at the ESC 2021 ([DOI: 10.1093/eurheartj/ehab724.3041ESC2021](https://doi.org/10.1093/eurheartj/ehab724.3041)). 

The present **ECG-PDF-extractor** uses code from the initially published research pipeline tool **ECG-Pipeline** ([GitHub Repo](https://github.com/JoshPrim/ECG-Pipeline)) by Joshua Prim. The new **ECG-PDF-extractor** within the current repository is a substantial rework including modern Python usage, PDF-only input, automatic manufacturer detection, clinical meta-data extraction, dynamic calibration, improved signal processing, and an added cross-platform desktop app (GUI).

---

## Table of Contents

- [Downloads](#downloads)
- [Features](#features)
- [Quick Start](#quick-start)
  - [Desktop App (GUI)](#desktop-app-gui)
  - [Command Line](#command-line)
  - [Python API](#python-api)
  - [AI Agent Integration](#ai-agent-integration)
- [Output Format](#output-format)
- [How It Works](#how-it-works)
- [Technical Stack](#technical-stack)
- [Configuration](#configuration)
- [Project Structure](#project-structure)
- [Debugging](#debugging)
- [Limitations & Data-Quality Notes](#limitations--data-quality-notes)
- [License](#license)

---

## Downloads

Ready-to-use executables are built automatically by GitHub Actions and published in the
[**Releases**](../../releases) tab:

| Platform | Artifact |
|----------|----------|
| Windows x86_64 | `ECG-PDF-extractor-windows-x86_64.zip` |
| macOS Apple Silicon (arm64) | `ECG-PDF-extractor-macos-arm64.app.zip` |
| Linux x86_64 | `ECG-PDF-extractor-linux-x86_64.zip` |

Download, unzip, and run — no Python installation required.
Builds are produced with PyInstaller.

## Features

- **PDF-only extraction** — recovers waveforms from raw PDF graphics operators (`m`, `l`, `S` path commands), not from screenshots or OCR
- **Manufacturers supported** — GE CardioSoft (v6.0 / v6.5 / v6.73 layouts) and Schiller, each with a dedicated extractor
- **Automatic manufacturer detection** — every PDF is classified by its text layer; mixed input folders are processed in one run
- **12 leads per recording** — I, II, III, aVR, aVL, aVF, V1–V6
- **500 Hz output sampling** — configurable duration (default 10 s = 5000 samples/lead)
- **Physically calibrated amplitudes** — per-document calibration against the PDF printed 1 mV reference mark (Eichzacke), values in µV
- **Clinical metadata extraction** — heart rate, P/QRS/QT intervals, axes, patient ID, sex, age, dates, device info parsed from the PDF text layer into a consolidated table
- **Cross-platform desktop GUI** — app with live progress, manufacturer detection counts, and a built-in 12-lead waveform viewer
- **Signal processing pipeline** — preamble-artifact removal, shape-preserving Akima spline interpolation, Savitzky-Golay smoothing, cross-lead time-window alignment, baseline correction

## Quick Start

### Desktop App (GUI)

1. Grab the executable for your OS from the [Releases](../../releases) page (or run `python ui.py`).
2. Select your **input folder** containing the ECG PDFs — any mix of Cardiosoft and Schiller.
   Manufacturer detection starts immediately and shows per-brand counts.
3. Select an **output folder** and adjust the duration if needed (seconds).
4. Hit **▶ Start Extraction**. Progress, per-file log messages, and the final records are shown;
   pick any record from the dropdown to inspect its 12-lead waveform plot.

### Command Line

```bash
git clone https://github.com/BiomarkerResearch/ECG-PDF-extractor && cd ECG-PDF-extractor

# create & activate a virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate            # Linux / macOS
# .venv\Scripts\activate             # Windows (cmd: .venv\Scripts\activate.bat)

pip install -r requirements.txt      # Python 3.10+

# place your ECG PDFs into data/original_ecgs/, then:
python3 runme.py
```

Deactivate the environment afterwards with `deactivate`.

Results are written to `data/extracted_ecgs/`. Behavior is controlled via `config.ini`
(see [Configuration](#configuration)).

### Python API

```python
from runner.execution_runner import ExecutionRunner

runner = ExecutionRunner(
    config_path="config.ini",
    path_source="path/to/pdf_folder",     # optional overrides
    path_sink="path/to/output_folder",    # optional overrides
)
records = runner.run()   # dict: record_id -> {"ecg_raw": {lead: [samples]}, "metadata": {...}, ...}
```

### AI Agent Integration

This repository ships agent-ready instructions: [`CLAUDE.md`](CLAUDE.md) provides
project context and commands for coding agents, and
[`skills/ecg-pdf-extractor/SKILL.md`](skills/ecg-pdf-extractor/SKILL.md)
is a portable skill definition that lets Claude Code / opencode operate the extractor
autonomously (setup, extraction on arbitrary folders, output verification, troubleshooting).
Copy it into `.opencode/skills/` or `.claude/skills/` to install.

## Output Format

For each processed PDF the extractor writes:

**1. One waveform CSV per recording** (`<pdf-name>.csv`) — 5000 rows × 12 columns
(one column per lead, header = lead names):

```csv
I,II,III,aVR,aVL,aVF,V1,V2,V3,V4,V5,V6
58.90665054,57.37796329,8.74510367,-60.98782341,...
55.02543565,52.05139212,6.72813761,-55.61165769,...
...
```

Rows are equidistant time samples at 500 Hz; values are calibrated amplitudes in
**microvolts (µV)**, baseline-corrected.

**2. A consolidated metadata table** (`ECG_records.csv`) — one row per PDF with all
extracted clinical parameters:

<details>
<summary>All 26 columns</summary>

`filename`, `patient_id`, `name`, `ecg_date`, `ecg_time`, `sex`, `age`, `birth_date`,
`ethnicity`, `speed_mm_s`, `duration`, `available_leads`, `heart_rate`,
`p_duration_ms`, `pq_ms`, `qrs_ms`, `qt_ms`, `qtc_ms`, `rr_interval_ms`,
`pp_interval_ms`, `p_axis`, `qrs_axis`, `t_axis`, `software_version`,
`device_model`, `device_serial`

</details>

Fields not present in a given document remain empty. ⚠️ Note that name/patient ID are
**personal health information** — handle outputs accordingly.

## How It Works

```
                    ┌──────────────────────────────────────────────┐
  ECG PDF ──► PyPDF2│ decompress content streams of each page      │
                    └──────────────────┬───────────────────────────┘
                                       ▼
                    ┌──────────────────────────────────────────────┐
                    │ manufacturer auto-detection (text layer)     │
                    │ → Cardiosoft / Schiller extractor            │
                    └──────────────────┬───────────────────────────┘
                                       ▼
        ┌──────────────────────────────────────────────────────────────────┐
        │ 1. parse graphics operators (m/l/S/Q blocks) → coordinate pairs  │
        │ 2. detect page orientation (Cardiosoft) → rotate if needed       │
        │ 3. locate Eichzacke calibration mark → gamma factor (per PDF!)   │
        │ 4. clip preamble/grid artifacts (median-threshold, last segment) │
        │ 5. scale amplitudes: value × gamma → microvolts                  │
        │ 6. resample ALL leads onto their common time window              │
        │    via Akima splines → 5000 equidistant points @ 500 Hz          │
        │ 7. Savitzky-Golay smoothing on the uniform grid                  │
        │ 8. baseline correction (flattest 124-sample window heuristic)    │
        └──────────────────────────────┬───────────────────────────────────┘
                                       ▼
                    ┌──────────────────────────────────────────────┐
                    │ regex parsers extract clinical metadata      │
                    │ from the PDF text layer → ECG_records.csv    │
                    └──────────────────────────────────────────────┘
```

### Signal-processing

**Dynamic per-PDF Eichzacke calibration.** Every ECG printout contains a 1 mV calibration pulse (the "Eichzacke"). The extractor locates this mark in each document's own graphics coordinates — Cardiosoft draws it as a stepped square in dedicated stroke blocks, Schiller as a small stepped/arrow shape near the page margin — measures its amplitude-direction span, and computes `gamma = 1000 µV / span`. This makes amplitude scaling correct even when zoom levels, or export options change the internal coordinate system between documents.

**Akima splines + Savitzky-Golay smoothing.** Raw ink coordinates are unevenly spaced and carry quantization noise. Leads are interpolated to the uniform 500 Hz grid with **shape-preserving Akima splines**, which avoid the ringing/overshoot of polynomial splines on sharp QRS complexes and eliminate flat-line segments produced by naive linear interpolation. Smoothing is then applied
with a **Savitzky-Golay filter (window 11, order 2) after  interpolation on the uniform grid** — deliberately *not* before: pre-smoothing sparse source points assumes equal spacing, which PDF ink density violates and which measurably shifted QRS timing by up to ~40 ms between leads. On the uniform grid the symmetric filter removes quantization jitter with zero group delay.

**Common-time-window alignment.** All 12 leads of one recording are resampled onto the intersection of their drawn time extents, so columns stay temporally aligned across the entire file.

## Technical Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.10+ |
| PDF parsing | PyPDF2 3.x (`PdfReader`, decompressed content streams) |
| Numerics / interpolation | NumPy, SciPy (`Akima1DInterpolator`, `savgol_filter`) |
| Tabular I/O | pandas |
| Desktop GUI | PySide6 (Qt6), dark theme, threaded workers |
| Visualization | Matplotlib (GUI canvas & debug plots), Pillow (PNG debug mode) |
| Progress UX | tqdm (CLI), Qt signal bridge (GUI) |
| Packaging | PyInstaller (`.spec` included) + GitHub Actions multi-platform builds |

Dependencies are pinned in [`requirements.txt`](requirements.txt).

## Configuration

`config.ini`, section `[pdf]`:

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `is_pdf` | bool | `True` | Must be `True`. Non-PDF input is not supported. |
| `override` | bool | `True` | Re-extract all PDFs (`True`) or reuse existing CSVs (`False`). |
| `manufacturer` | string | `Auto` | `Auto` detects the manufacturer per PDF; `Cardiosoft` or `Schiller` forces one extractor (other brands are skipped with a warning). |
| `seconds` | int | `10` | Duration to extract; total samples = `seconds × 500`. |
| `leads_to_use` | list | all 12 | Comma-separated lead names. |
| `vis_while_extraction` | bool | `False` | Per-lead debug plots during extraction. |
| `vis_with_matplotlib` | bool | `False` | Matplotlib (`True`) vs Pillow PNG (`False`) debug rendering. |
| `vis_after_extraction` | bool | `False` | Multi-lead overview plot after extraction. |
| `vis_scale` | float | `0.33` | Scale factor (0–1) for post-extraction plots. |

## Project Structure

```
ECG-PDF-extractor/
├── config.ini                          # Pipeline configuration
├── runme.py                            # CLI entry point
├── ui.py                               # PySide6 desktop app
├── debug_pdf.py                        # Low-level PDF inspection utility
├── requirements.txt
├── ECG-PDF-extractor.spec              # PyInstaller build recipe
├── .github/workflows/build.yml         # Release binary CI (Win/macOS/Linux)
├── runner/
│   └── execution_runner.py             # Orchestrator: detection → extraction → post-processing
├── extractors/
│   ├── abstract_extractor.py           # Base class
│   ├── extractor_cardiosoft.py         # GE CardioSoft extractor
│   └── extractor_schiller.py           # Schiller extractor
├── utils/
│   ├── data/
│   │   ├── data.py                     # Scaling, derivation, merging
│   │   └── visualisation.py            # Debug visualizations
│   ├── extract_utils/
│   │   └── extract_utils.py            # Graphics parsing, Eichzacke calibration,
│   │                                   #   Akima/Savitzky-Golay resampling, clipping
│   ├── metadata/
│   │   └── extract_metadata.py         # Manufacturer detection + clinical regex parsers
│   ├── file/file.py                    # Path helpers
│   └── misc/datastructure.py           # Shape utilities
└── data/
    ├── original_ecgs/                  # ← put your ECG PDFs here (any brand mix)
    └── extracted_ecgs/                 # ← CSV outputs land here
```

## Debugging

- Set `vis_while_extraction = True` to see per-page lead plots during extraction.
- `python3 debug_pdf.py` dumps pages, text layers, content streams, and graphics-block
  structure of every PDF in `data/original_ecgs/` — useful when adding support for new
  device firmware or print layouts.

## Limitations & Data-Quality Notes

- **! Vector PDFs only !** Scanned/raster ECG printouts cannot be parsed (no OCR).
- **Layout-sensitive parsing.** Extraction relies on the graphics-operator structure of specific device firmware/print layouts (Cardiosoft v6.x block indices, Schiller segment geometry). New firmware versions may require extractor updates — malformed documents fail loudly per file instead of producing silent garbage.
- **Metadata locale.** Clinical-field regexes match German labels (`Herzfrequenz`, `Patienten-Nr.`, …); English-locale exports may leave fields empty.
- **Fixed output rate.** Output is always 500 Hz; `seconds` controls coverage.
- **Source fidelity.** Small inter-lead timing offsets present in some source documents (e.g., V1–V3 drawn ~16–36 ms late on certain Cardiosoft exports) are reproduced faithfully rather than corrected — the extractor does not second-guess the device.

## License

Released under the MIT License — see [LICENSE.md](LICENSE.md).

