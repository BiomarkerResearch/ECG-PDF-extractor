"""
ECG-PDF-extractor — cross-platform GUI (PySide6, dark mode).

Usage:
    python3 ui.py
"""
import sys
import os
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QProgressBar, QTextEdit,
    QListWidget, QComboBox, QSpinBox, QFrame, QMessageBox,
    QGroupBox,
)

# Import detect_manufacturer lazily to avoid path issues at module load time
from PySide6.QtCore import Qt, QThread, Signal, QSize
from PySide6.QtGui import QFont

# ---------------------------------------------------------------------------
# Worker — runs the extraction pipeline off the main thread
# ---------------------------------------------------------------------------


class DetectionWorker(QThread):
    """Background worker for manufacturer detection."""
    sig_progress = Signal(int)          # 0-100
    sig_label = Signal(str, str, str)   # schiller, cardiosoft, unknown counts as formatted strings
    sig_finished = Signal()

    def __init__(self, input_folder):
        super().__init__()
        self.input_folder = input_folder

    def run(self):
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).resolve().parent))
        from utils.metadata.extract_metadata import detect_manufacturer

        pdfs = sorted(Path(self.input_folder).glob("*.pdf"))
        total = len(pdfs)
        if total == 0:
            self.sig_label.emit("Schiller: <b>0</b>", "Cardiosoft: <b>0</b>", "Unknown: <b>0</b>")
            self.sig_progress.emit(100)
            self.sig_finished.emit()
            return

        counts = {'Schiller': 0, 'Cardiosoft': 0, 'Unknown': 0}
        for i, pdf_path in enumerate(pdfs):
            try:
                with open(pdf_path, 'rb') as f:
                    mfr = detect_manufacturer(f.read())
                counts[mfr or 'Unknown'] += 1
            except Exception:
                counts['Unknown'] += 1

            pct = int((i + 1) / total * 100)
            self.sig_progress.emit(pct)
            self.sig_label.emit(
                f"Schiller: <b>{counts['Schiller']}</b>",
                f"Cardiosoft: <b>{counts['Cardiosoft']}</b>",
                f"Unknown: <b>{counts['Unknown']}</b>",
            )

        self.sig_finished.emit()


class ExtractionWorker(QThread):
    sig_progress = Signal(int)
    sig_log = Signal(str)
    sig_finished = Signal(str)
    sig_error = Signal(str)

    def __init__(self, input_folder, output_folder, seconds):
        super().__init__()
        self.input_folder = input_folder
        self.output_folder = output_folder
        self.seconds = seconds
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    # ---- helpers ----------------------------------------------------------

    def _log(self, text):
        self.sig_log.emit(text)

    def _count_pdfs(self, folder):
        return len(list(Path(folder).glob("*.pdf")))

    # ---- main work --------------------------------------------------------

    def run(self):
        try:
            project_root = str(Path(__file__).resolve().parent)
            config_path = os.path.join(project_root, "config.ini")

            if not os.path.isfile(config_path):
                raise FileNotFoundError(
                    f"config.ini not found at {config_path}. "
                    "Run the UI from the project root directory."
                )

            total_pdfs = self._count_pdfs(self.input_folder)
            if total_pdfs == 0:
                raise ValueError(
                    f"No .pdf files found in {self.input_folder}"
                )

            sys.path.insert(0, project_root)

            from runner.execution_runner import ExecutionRunner

            exr = ExecutionRunner(
                config_path=config_path,
                path_source=self.input_folder,
                path_sink=self.output_folder,
            )
            exr.manufacturer = 'Auto'
            exr.seconds = self.seconds

            # Intercept logger to track per-file progress
            import logging as _logging
            class _ProgressHandler(_logging.Handler):
                def __init__(self, outer):
                    super().__init__()
                    self._outer = outer
                    self._count = 0
                def emit(self, record):
                    msg = record.getMessage()
                    if msg.startswith('Converting "'):
                        self._count += 1
                        pct = 10 + int(self._count / self._outer.total_pdfs * 80)
                        self._outer.sig_progress.emit(min(pct, 90))
                        self._outer._log(f"  [{self._count}/{self._outer.total_pdfs}] {msg}")

            _ph = _ProgressHandler(self)
            _ph.total_pdfs = total_pdfs
            root_logger = _logging.getLogger()
            root_logger.addHandler(_ph)

            try:
                self._log(f"Starting extraction of {total_pdfs} PDF(s) …")
                self.sig_progress.emit(10)

                if not self._cancelled:
                    records = exr.run()
                    self.sig_progress.emit(90)

                self._log(f"Extracted {len(records)} record(s).")
                self._log(f"Output → {self.output_folder}")
                self.sig_progress.emit(100)
                self.sig_finished.emit("Extraction complete.")
            finally:
                root_logger.removeHandler(_ph)

        except Exception as exc:
            if not self._cancelled:
                self.sig_error.emit(str(exc))

    def stop(self):
        self.cancel()
        self.wait()


# ---------------------------------------------------------------------------
# Dark palette (applied globally)
# ---------------------------------------------------------------------------

DARK_STYLE = """
QMainWindow, QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: 'Segoe UI', system-ui, sans-serif;
}
QPushButton {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 10px 16px;
    font-size: 13px;
}
QPushButton:hover { background-color: #45475a; }
QPushButton:pressed { background-color: #585b70; }
QPushButton:disabled { background-color: #313244; color: #6c7086; }
QLabel { font-size: 13px; }
QProgressBar {
    border: 1px solid #45475a;
    border-radius: 5px;
    text-align: center;
    background-color: #313244;
}
QProgressBar::chunk {
    background-color: #89b4fa;
    border-radius: 4px;
}
QTextEdit, QListWidget {
    background-color: #181825;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 5px;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 12px;
}
QComboBox, QSpinBox {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 5px;
    padding: 5px 8px;
    font-size: 13px;
}
QComboBox::drop-down, QSpinBox::up-button, QSpinBox::down-button {
    background-color: transparent;
    border: none;
}
QGroupBox {
    font-weight: bold;
    font-size: 12px;
    border: 1px solid #45475a;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 14px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #89b4fa;
}
QScrollBar:vertical {
    background-color: #1e1e2e;
    width: 8px;
}
QScrollBar::handle:vertical {
    background-color: #45475a;
    border-radius: 4px;
}
"""


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ECG-PDF-extractor")
        self.setMinimumSize(1500, 780)
        self.setMaximumWidth(1900)

        self.input_folder = ""
        self.output_folder = ""
        self.worker = None
        self.detector = None
        self.extracted_records = {}

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setSpacing(24)
        main_layout.setContentsMargins(28, 28, 28, 28)

        # ---- Left column (controls) ---------------------------------------
        left_widget = QWidget()
        left_widget.setFixedWidth(210)
        left = QVBoxLayout(left_widget)
        left.setSpacing(14)

        self.btn_input = QPushButton("📂  Select Input Folder")
        self.btn_output = QPushButton("📁  Select Output Folder")
        self.btn_start = QPushButton("▶  Start Extraction")

        # Auto-detect info box (replaces manufacturer dropdown)
        self.grp_detection = QGroupBox("Manufacturer Detection")
        det_layout = QVBoxLayout(self.grp_detection)
        det_layout.setSpacing(6)
        self.lbl_det_schiller = QLabel("Schiller: <b>—</b>")
        self.lbl_det_cardio = QLabel("Cardiosoft: <b>—</b>")
        self.lbl_det_unknown = QLabel("Unknown: <b>—</b>")
        det_layout.addWidget(self.lbl_det_schiller)
        det_layout.addWidget(self.lbl_det_cardio)
        det_layout.addWidget(self.lbl_det_unknown)
        det_layout.addStretch()

        lbl_sec = QLabel("Duration (seconds):")
        self.spin_seconds = QSpinBox()
        self.spin_seconds.setRange(1, 60)
        self.spin_seconds.setValue(10)

        left.addWidget(self.btn_input)
        left.addWidget(self.btn_output)
        left.addSpacing(8)
        left.addWidget(self.grp_detection)
        left.addWidget(lbl_sec)
        left.addWidget(self.spin_seconds)
        left.addStretch()
        left.addWidget(self.btn_start)

        # ---- Right column (info + progress) -------------------------------
        right = QVBoxLayout()
        right.setSpacing(12)

        self.lbl_input_path = QLabel("No input folder selected.")
        self.lbl_output_path = QLabel("No output folder selected.")

        self.list_pdfs = QListWidget()

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p %")

        self.text_log = QTextEdit()
        self.text_log.setReadOnly(True)

        self.pdf_count_label = QLabel("PDFs found: <b>0</b>")

        # ---- Visualization column -----------------------------------------
        self.lbl_record_select = QLabel("Select record to visualize:")
        self.cmb_records = QComboBox()
        self.cmb_records.currentIndexChanged.connect(self._on_record_selected)

        self.fig = Figure(figsize=(12, 12), dpi=100)
        self.canvas = FigureCanvasQTAgg(self.fig)
        self.canvas.setStyleSheet("background-color: #1e1e2e;")

        right.addWidget(self._info_row("Input:", self.lbl_input_path))
        right.addWidget(self._info_row("Output:", self.lbl_output_path))
        right.addWidget(self.pdf_count_label)
        right.addWidget(QLabel("Files in input folder:"))
        right.addWidget(self.list_pdfs)
        right.addSpacing(4)
        right.addWidget(self.progress_bar)
        right.addWidget(self.text_log)

        # ---- Visualization column -----------------------------------------
        vis = QVBoxLayout()
        vis.setSpacing(8)
        vis.addWidget(self.lbl_record_select)
        vis.addWidget(self.cmb_records)
        vis.addWidget(QLabel("ECG Waveform:"))
        vis.addWidget(self.canvas, 1)

        main_layout.addWidget(left_widget)
        main_layout.addLayout(right, 1.5)
        main_layout.addLayout(vis, 2)

        # ---- Connections --------------------------------------------------
        self.btn_input.clicked.connect(self._select_input)
        self.btn_output.clicked.connect(self._select_output)
        self.btn_start.clicked.connect(self._toggle_start)

        self.cmb_records.setEnabled(False)
        self._clear_plot()

    # ---- helpers ----------------------------------------------------------

    @staticmethod
    def _info_row(label_text, value_label):
        container = QWidget()
        row = QHBoxLayout(container)
        lbl = QLabel(label_text)
        lbl.setStyleSheet("font-weight: bold;")
        row.addWidget(lbl)
        row.addStretch()
        row.addWidget(value_label)
        row.setContentsMargins(0, 0, 0, 0)
        return container

    # ---- folder selection -------------------------------------------------

    def _select_input(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select Input Folder (ECG PDFs)"
        )
        if not folder:
            return
        self.input_folder = folder
        self.lbl_input_path.setText(folder)
        self._refresh_pdf_list()

    def _select_output(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select Output Folder"
        )
        if not folder:
            return
        self.output_folder = folder
        self.lbl_output_path.setText(folder)

    # ---- PDF list ---------------------------------------------------------

    def _refresh_pdf_list(self):
        self.list_pdfs.clear()
        if not self.input_folder:
            return
        pdfs = sorted(p.stem for p in Path(self.input_folder).glob("*.pdf"))
        self.list_pdfs.addItems(pdfs)
        self.pdf_count_label.setText(f"PDFs found: <b>{len(pdfs)}</b>")

        # Reset detection labels while scanning
        self.lbl_det_schiller.setText("Schiller: <b>…</b>")
        self.lbl_det_cardio.setText("Cardiosoft: <b>…</b>")
        self.lbl_det_unknown.setText("Unknown: <b>…</b>")

        # Run detection in background thread with progress
        if self.detector and self.detector.isRunning():
            return  # already running from a previous selection
        self.progress_bar.setFormat("Detecting manufacturers … %p%")
        self.progress_bar.setValue(0)
        self.btn_start.setEnabled(False)

        self.detector = DetectionWorker(self.input_folder)
        self.detector.sig_progress.connect(self._on_detection_progress)
        self.detector.sig_label.connect(self._on_detection_labels)
        self.detector.sig_finished.connect(self._on_detection_done)
        self.detector.start()

    def _on_detection_progress(self, value):
        self.progress_bar.setValue(value)

    def _on_detection_labels(self, schiller, cardio, unknown):
        self.lbl_det_schiller.setText(schiller)
        self.lbl_det_cardio.setText(cardio)
        self.lbl_det_unknown.setText(unknown)

    def _on_detection_done(self):
        self.progress_bar.setFormat("%p %")
        self.progress_bar.setValue(0)
        self.btn_start.setEnabled(True)

    # ---- extraction -------------------------------------------------------

    def _toggle_start(self):
        if self.worker and self.worker.isRunning():
            self._stop_extraction()
        elif not self.btn_start.isEnabled():
            return  # detection still running, ignore click
        else:
            self._start_extraction()

    def _start_extraction(self):
        if not self.input_folder or not self.output_folder:
            QMessageBox.warning(
                self, "Missing folders",
                "Please select both an input folder and an output folder.",
            )
            return

        self.btn_start.setText("⏹  Stop Extraction")
        self.progress_bar.setFormat("%p %")
        self.progress_bar.setValue(0)
        self.text_log.clear()
        self._log_to_ui("Initializing …")

        self.worker = ExtractionWorker(
            input_folder=self.input_folder,
            output_folder=self.output_folder,
            seconds=self.spin_seconds.value(),
        )
        self.worker.sig_progress.connect(self._on_progress)
        self.worker.sig_log.connect(self._log_to_ui)
        self.worker.sig_finished.connect(self._on_finished)
        self.worker.sig_error.connect(self._on_error)
        self.worker.start()

    def _stop_extraction(self):
        if self.worker:
            self.worker.cancel()
            self._log_to_ui("Cancelling …")

    # ---- signal handlers --------------------------------------------------

    def _on_progress(self, value):
        self.progress_bar.setValue(value)

    def _log_to_ui(self, msg):
        self.text_log.append(msg)

    def _on_finished(self, msg):
        self.btn_start.setText("▶  Start Extraction")
        self.progress_bar.setFormat("%p %")
        self._log_to_ui(f"✅ {msg}")
        self._load_extracted_records()

    def _on_error(self, msg):
        self.btn_start.setText("▶  Start Extraction")
        self.progress_bar.setFormat("%p %")
        QMessageBox.critical(self, "Extraction Error", msg)
        self._log_to_ui(f"❌ {msg}")

    # ---- visualization helpers --------------------------------------------

    def _load_extracted_records(self):
        """Load per-record CSVs from the output folder into memory."""
        if not self.output_folder:
            return
        self.extracted_records = {}
        csv_files = sorted(Path(self.output_folder).glob("*.csv"))
        for f in csv_files:
            if f.name == "ECG_records.csv":
                continue
            try:
                df = pd.read_csv(f)
                record_id = f.stem
                leads = {}
                for col in df.columns:
                    leads[col] = df[col].astype(float).tolist()
                self.extracted_records[record_id] = leads
            except Exception as exc:
                self._log_to_ui(f"  ⚠ Could not load {f.name}: {exc}")

        self.cmb_records.clear()
        if self.extracted_records:
            self.cmb_records.addItems(sorted(self.extracted_records.keys()))
            self.cmb_records.setEnabled(True)
            self._on_record_selected(0)
        else:
            self._clear_plot()
            self._log_to_ui("  No CSV records found to visualize.")

    def _on_record_selected(self, index):
        record_id = self.cmb_records.currentText()
        if not record_id or record_id not in self.extracted_records:
            return
        self._plot_ecg(record_id)

    def _clear_plot(self):
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        ax.text(0.5, 0.5, "No record selected", ha="center", va="center",
                fontsize=14, color="#6c7086")
        ax.axis("off")
        self.canvas.draw()

    def _plot_ecg(self, record_id):
        leads = self.extracted_records.get(record_id)
        if not leads:
            return

        self.fig.clear()

        lead_order = ["I", "II", "III", "aVR", "aVL", "aVF",
                       "V1", "V2", "V3", "V4", "V5", "V6"]
        available = [l for l in lead_order if l in leads]
        if not available:
            available = sorted(leads.keys())

        n_leads = len(available)
        ncols = 2
        nrows = (n_leads + ncols - 1) // ncols

        bg = "#1e1e2e"
        fg = "#cdd6f4"
        grid_color = "#313244"
        self.fig.set_facecolor(bg)

        for idx, lead_name in enumerate(available):
            row = idx // ncols + 1
            col = idx % ncols + 1
            ax = self.fig.add_subplot(nrows, ncols, idx + 1)
            ax.set_facecolor(bg)

            data = np.array(leads[lead_name])
            sr = 500
            t = np.arange(len(data)) / sr

            color_map = {
                "I": "#f38ba8", "II": "#a6e3a1", "III": "#89b4fa",
                "aVR": "#fab387", "aVL": "#cba6f7", "aVF": "#f9e2af",
                "V1": "#94e2d5", "V2": "#74c7ec", "V3": "#b4befe",
                "V4": "#eba0ac", "V5": "#f2cdcd", "V6": "#cdd6f4",
            }
            ax.plot(t, data / 1000, color=color_map.get(lead_name, fg), linewidth=0.8)
            ax.set_title(f"Lead {lead_name}", fontsize=9, color=fg)
            ax.grid(True, color=grid_color, linestyle="-", alpha=0.5)
            ax.tick_params(colors=fg, labelsize=7)
            ax.set_xlabel("Time (s)", fontsize=7, color=fg)

        self.fig.tight_layout(pad=2.0)
        self.canvas.draw()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_STYLE)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
