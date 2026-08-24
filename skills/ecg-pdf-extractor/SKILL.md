---
name: ecg-pdf-extractor
description: Extract 12-lead ECG waveforms and clinical metadata from GE CardioSoft / Schiller ECG PDF files into CSVs (500 Hz µV signals + ECG_records.csv metadata). Use when the user provides ECG PDF printouts and wants raw signal data, digitized waveforms, or clinical parameters extracted for analysis or ML training. Triggers on "ECG PDF", "extract ECG", "waveform extraction", "Cardiosoft", "Schiller".
---

# ECG-PDF-extractor skill

Drive the ECG-PDF-extractor CLI/Python API to convert ECG device PDFs into analysis-ready
CSV data. Works for any mix of Cardiosoft and Schiller PDFs in one folder.

## When to use

- User supplies ECG PDF printouts (vector PDFs, not scans) and wants waveform data or
  clinical metadata (heart rate, PQ/QRS/QT intervals, axes, patient info).
- User wants to batch-convert an entire folder of ECG PDFs.

Do NOT use for: raster/scanned PDFs (no OCR support), XML/native device exports,
or image-based waveform digitizing.

## Setup

The tool lives in a local clone of the repository. Locate or clone it first:

```bash
git clone https://github.com/BiomarkerResearch/ECG-PDF-extractor
cd ECG-PDF-extractor
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt        # Python 3.10+
```

Non-executable users can instead download a prebuilt app from GitHub Releases
(Windows x64 / macOS arm64 / Linux x64) — but agents should prefer the Python API.

## Recommended: Python API (works with arbitrary folders)

```python
import sys
sys.path.insert(0, "/path/to/ECG-PDF-extractor")   # repo root

from runner.execution_runner import ExecutionRunner

runner = ExecutionRunner(
    config_path="/path/to/ECG-PDF-extractor/config.ini",
    path_source="/folder/with/ecg/pdfs",     # any folder, mixed manufacturers OK
    path_sink="/folder/for/csv/output",
)
records = runner.run()
```

Never copy user PDFs into the repo's `data/original_ecgs/` — always pass
`path_source`/`path_sink` overrides.

Alternative CLI-only route: place PDFs in `data/original_ecgs/`, run `python3 runme.py`,
find results in `data/extracted_ecgs/`. Behavior is controlled by `config.ini`
(`manufacturer = Auto` is default; `seconds` sets duration, default 10).

## Outputs

1. **One CSV per recording** (`<pdf-stem>.csv`): 12 columns named
   `I,II,III,aVR,aVL,aVF,V1,V2,V3,V4,V5,V6`; one row per 2 ms sample
   (default 5000 rows = 10 s @ 500 Hz); values are calibrated amplitudes in microvolts.
2. **`ECG_records.csv`**: one row per PDF, 26 columns — `filename`, `patient_id`, `name`,
   `ecg_date`, `ecg_time`, `sex`, `age`, `birth_date`, `ethnicity`, `speed_mm_s`,
   `duration`, `available_leads`, `heart_rate`, `p_duration_ms`, `pq_ms`, `qrs_ms`,
   `qt_ms`, `qtc_ms`, `rr_interval_ms`, `pp_interval_ms`, `p_axis`, `qrs_axis`,
   `t_axis`, `software_version`, `device_model`, `device_serial`.
   Fields absent from a document stay empty.

⚠️ Outputs contain patient identifiers (PHI). Do not commit them; handle per data-governance rules.

## Verification checklist (run after every extraction)

- Count rows in `ECG_records.csv` == number of successfully processed PDFs.
- Each waveform CSV: shape `(seconds × 500, 12)` with exactly the 12 standard lead columns.
- Failed PDFs are logged as `WARNING Failed to extract <file>: <reason>` — report them to
  the user individually; they never corrupt other outputs.
- A warning listing records "with no metadata row" means those waveforms were extracted
  but their text layer yielded no metadata.
- Empty input folder is valid → header-only `ECG_records.csv`.

## Troubleshooting

| Symptom | Cause | Action |
|---|---|---|
| `Could not extract Eichzacke calibration` | Non-standard print layout or scanned PDF | Verify PDF is vector (text selectable); try `python3 debug_pdf.py` on the file |
| `Invalid ECG with N leads` | Firmware/layout variant not covered | Inspect graphics blocks via `debug_pdf.py`; extractor update may be needed |
| Metadata fields empty | English-locale export (regexes match German labels) | Expected behavior; fields stay empty rather than guessed |
| `%d %s PDF(s) skipped` warning | Explicit `manufacturer=` filter set | Reset `manufacturer = Auto` in config.ini |
| GUI/CLI opens many windows | Debug visualization flags enabled | Keep `vis_while_extraction`/`vis_after_extraction` = False |

## Reference

Repository: https://github.com/BiomarkerResearch/ECG-PDF-extractor
Full documentation: see README.md and CLAUDE.md in the repo root.
