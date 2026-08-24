# CLAUDE.md

Project-level guidance for AI coding agents (Claude Code, opencode, …) working in this repository.

## What this project is

**ECG-PDF-extractor** — extracts 12-lead ECG waveforms and clinical metadata from vector PDFs
produced by GE CardioSoft and Schiller ECG devices. Output: one CSV per recording
(12 lead columns × N samples, values in µV @ 500 Hz) plus a consolidated `ECG_records.csv`
(26 metadata columns). Python 3.10+, MIT licensed.

## Essential commands

```bash
# setup (from repo root)
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# run full pipeline on whatever is in data/original_ecgs/ → writes data/extracted_ecgs/
python3 runme.py

# desktop GUI
python ui.py

# inspect raw PDF internals (pages, text layer, graphics blocks)
python3 debug_pdf.py
```

### Programmatic usage (preferred for agents)

```python
import sys; sys.path.insert(0, <repo_root>)
from runner.execution_runner import ExecutionRunner

runner = ExecutionRunner(
    config_path="<repo_root>/config.ini",   # defaults to repo config if omitted
    path_source="/any/input/folder",        # optional: overrides data/original_ecgs
    path_sink="/any/output/folder",         # optional: overrides data/extracted_ecgs
)
records = runner.run()
# records: {record_id: {"ecg_raw": {lead: [float µV samples]}, "metadata": {...},
#                       "clinical_parameters_inputs": {...}}}
```

Any input/output folders work — do **not** copy user PDFs into `data/original_ecgs`;
always pass `path_source`/`path_sink` overrides instead.

## Verifying results

- `ECG_records.csv`: row count must equal number of processed PDFs (header-only file is
  written even when nothing succeeds — stale-metadata protection).
- Waveform CSVs: shape `(seconds × 500, 12)`; columns exactly
  `I,II,III,aVR,aVL,aVF,V1,V2,V3,V4,V5,V6`.
- Failed PDFs fail loudly **per file** (log warning), never silently corrupt output.
- Records dropped for missing metadata trigger a `WARNING ... no metadata row`.
- There is no test suite — validate changes by running the pipeline end-to-end on real
  demo PDFs and checking the above invariants.

## Behavior & gotchas

- Manufacturer auto-detection runs per PDF (keyword scoring on page text); `Auto` is the
  default. Forcing `Cardiosoft`/`Schiller` in `config.ini` skips other brands with a warning.
- Amplitude calibration is **dynamic per document**: the printed 1 mV "Eichzacke" mark is
  located in each PDF's own coordinates → `gamma = 1000/span`. Never hardcode calibration
  constants.
- Interpolation: Akima splines onto a uniform grid, then Savitzky-Golay smoothing
  (window 11, order 2) applied **after** interpolation. Do not move smoothing before
  interpolation — uneven ink spacing then biases QRS timing (~40 ms observed).
- All 12 leads are resampled onto their common time window (`common_time_window`) to keep
  columns aligned.
- Extraction parses raw graphics operators tied to specific device firmware/print layouts
  (Cardiosoft S-block indices `[7,13)`/`[8,14)`, version detection v6.0/v6.5/v6.73;
  Schiller expects 6 segments/page, 500–1500 points each). New firmware may need
  extractor updates — extend, don't loosen validation.
- Metadata regexes match German device labels (`Herzfrequenz`, `Patienten-Nr.`, …);
  English-locale exports leave fields empty by design (no guessing).
- Vector PDFs only — scanned/raster printouts cannot be parsed.
- Keep visualization flags (`vis_while_extraction`, `vis_after_extraction`) **off** for
  batch processing; they open blocking windows per lead.
- Outputs contain patient identifiers (PHI) — never commit extracted data from real
  recordings.

## Code map

```
runner/execution_runner.py    orchestrator: detect → group → extract → post-process → merge
extractors/                   abstract base + Cardiosoft/Schiller extractors
utils/extract_utils/          graphics parsing, Eichzacke calibration, resampling, clipping
utils/metadata/               manufacturer detection + clinical regex parsers, CSV_COLUMNS
utils/data/                   scaling/derivation/merging, debug visualisation
data/original_ecgs|extracted_ecgs  default CLI folders (GUI passes its own)
.github/workflows/build.yml   PyInstaller builds (Linux x64, Win x64, macOS arm64)
```

## Release flow (maintainers)

1. Merge to `main`, bump version note if needed.
2. Trigger *Actions → Build Executables* (manual dispatch).
3. Download artifacts (already single-zip: one zip containing one runnable folder/app),
   attach them to a GitHub Release created manually.
