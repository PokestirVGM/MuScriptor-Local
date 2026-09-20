"""Windows desktop preview. The engine runs separately; audio never leaves the PC."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sys

from PySide6.QtCore import QProcess, QProcessEnvironment, QSettings, QTimer, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QProgressBar, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)


def support_directory():
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "MuScriptor Local"
    return Path.home() / "Library/Application Support/MuScriptor Local"


def label(text=""):
    widget = QLabel(text)
    widget.setWordWrap(True)
    widget.setTextFormat(Qt.PlainText)
    widget.setTextInteractionFlags(Qt.TextSelectableByMouse)
    return widget


class MainWindow(QMainWindow):
    def __init__(self, root=None, autostart=True, settings=None):
        super().__init__()
        self.settings = settings or QSettings("MuScriptor", "MuScriptor Local")
        self.support = support_directory()
        self.frozen = getattr(sys, "frozen", False)
        self.root = Path(root) if root else (self.support / "Engine" if self.frozen else Path(__file__).resolve().parents[1])
        self.resources = Path(sys._MEIPASS) / "resources" if self.frozen else self.root
        self.python = self.root / (".venv/Scripts/python.exe" if sys.platform == "win32" else ".venv/bin/python")
        self.worker = None
        self.installer = None
        self.buffer = b""
        self.busy = True
        self.setup = False
        self.authenticated = False
        self.source = None
        self.destination = None
        self.result = None
        self.closing = False
        self.setWindowTitle("MuScriptor Local — Windows Preview")
        self.resize(660, 790)
        self.setAcceptDrops(True)
        body = QWidget()
        self.layout = QVBoxLayout(body)
        self.layout.setContentsMargins(28, 24, 28, 24)
        self.layout.setSpacing(14)
        title = label("AUDIO → MIDI")
        title.setStyleSheet("font-size: 26px; font-weight: 600;")
        self.layout.addWidget(title)
        self.model = QComboBox()
        for size in ("small", "medium", "large"):
            self.model.addItem(size.title(), size)
        saved = self.settings.value("model", "large")
        self.model.setCurrentIndex(max(0, self.model.findData(saved)))
        self.model.currentIndexChanged.connect(self.select_model)
        self.layout.addWidget(label("Model"))
        self.layout.addWidget(self.model)
        self.cache_status = label()
        self.layout.addWidget(self.cache_status)
        self.device = QComboBox()
        self.device.addItem("Automatic", "auto")
        self.device.currentIndexChanged.connect(self.select_device)
        self.layout.addWidget(label("Processor"))
        self.layout.addWidget(self.device)
        self.hardware = label("Detecting available processors…")
        self.layout.addWidget(self.hardware)
        self.setup_widget = QWidget()
        setup_layout = QVBoxLayout(self.setup_widget)
        setup_layout.setContentsMargins(0, 0, 0, 0)
        setup_layout.addWidget(label("Accept the selected model’s terms on Hugging Face. Each size needs its own acceptance."))
        links = QHBoxLayout()
        terms = QPushButton("Model Terms")
        terms.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(f"https://huggingface.co/MuScriptor/muscriptor-{self.model.currentData()}")))
        links.addWidget(terms)
        tokens = QPushButton("Get a Read Token")
        tokens.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://huggingface.co/settings/tokens")))
        links.addWidget(tokens)
        setup_layout.addLayout(links)
        self.token = QLineEdit()
        self.token.setEchoMode(QLineEdit.Password)
        self.token.setPlaceholderText("Hugging Face read token")
        self.token.returnPressed.connect(self.download)
        setup_layout.addWidget(self.token)
        self.download_button = QPushButton("Download Model")
        self.download_button.clicked.connect(self.download)
        setup_layout.addWidget(self.download_button)
        self.layout.addWidget(self.setup_widget)
        self.audio_button = QPushButton("Drop an audio file here, or click to choose")
        self.audio_button.setMinimumHeight(70)
        self.audio_button.clicked.connect(self.choose_audio)
        self.layout.addWidget(self.audio_button)
        self.output_heading = label("MIDI destination")
        self.layout.addWidget(self.output_heading)
        self.output_path = label()
        self.layout.addWidget(self.output_path)
        self.folder_button = QPushButton("Change Output Folder…")
        self.folder_button.clicked.connect(self.choose_folder)
        self.layout.addWidget(self.folder_button)
        self.transcribe_button = QPushButton("Transcribe")
        self.transcribe_button.clicked.connect(self.transcribe)
        self.layout.addWidget(self.transcribe_button)
        self.status = label("Checking local environment…")
        self.layout.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.layout.addWidget(self.progress)
        self.error = label()
        self.error.setStyleSheet("color: #cf4848")
        self.layout.addWidget(self.error)
        self.warning = label()
        self.layout.addWidget(self.warning)
        actions = QHBoxLayout()
        self.retry_button = QPushButton("Try Again")
        self.retry_button.clicked.connect(self.retry)
        actions.addWidget(self.retry_button)
        self.save_button = QPushButton("Save MIDI Copy…")
        self.save_button.clicked.connect(self.save_copy)
        actions.addWidget(self.save_button)
        self.another_button = QPushButton("Convert Another")
        self.another_button.clicked.connect(self.another)
        actions.addWidget(self.another_button)
        self.layout.addLayout(actions)
        self.layout.addWidget(label("Model download folder"))
        self.model_path = label("Checking…")
        self.layout.addWidget(self.model_path)
        self.layout.addWidget(label("Audio stays on this computer. Memory figures show total capacity, not free memory."))
        self.layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        self.setCentralWidget(scroll)
        menu = self.menuBar().addMenu("App")
        self.repair_action = menu.addAction("Repair Dependencies…", self.repair)
        menu.addAction("Show Logs", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.support / "Logs"))))
        self.refresh()
        if autostart:
            QTimer.singleShot(0, self.start)

    def refresh(self):
        for widget in (self.model, self.device, self.audio_button, self.folder_button):
            widget.setEnabled(not self.busy)
        self.repair_action.setEnabled(not self.busy)
        self.setup_widget.setVisible(self.setup and not self.busy)
        self.token.setVisible(not self.authenticated)
        self.download_button.setText(("Download " if self.authenticated else "Connect & Download ") + self.model.currentData().title())
        self.folder_button.setVisible(self.source is not None and self.result is None)
        self.output_heading.setVisible(self.destination is not None)
        self.output_path.setVisible(self.destination is not None)
        self.output_path.setText(str(self.destination or ""))
        self.output_heading.setText("MIDI saved to" if self.result else "MIDI destination — existing files are preserved")
        self.audio_button.setText(self.source.name + " — Change Audio…" if self.source else "Drop an audio file here, or click to choose")
        self.transcribe_button.setVisible(self.source is not None and self.result is None)
        self.transcribe_button.setEnabled(not self.busy and not self.setup and self.destination is not None)
        self.save_button.setVisible(self.result is not None)
        self.another_button.setVisible(self.result is not None)
        self.retry_button.setVisible(bool(self.error.text()) and not self.busy)
        self.progress.setVisible(self.busy)

    def start(self):
        self.busy = True
        self.error.clear()
        self.status.setText("Checking local environment…")
        self.refresh()
        if not self.python.is_file():
            self.busy = False
            self.repair()
            return
        if self.frozen:
            try:
                shutil.copy2(self.resources / "src/worker.py", self.root / "src/worker.py")
            except OSError:
                self.fail("The local engine could not be updated. Use Repair Dependencies.")
                return
        process = QProcess(self)
        self.worker = process
        self.buffer = b""
        process.setWorkingDirectory(str(self.root))
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("PYTHONUNBUFFERED", "1")
        environment.insert("PYTORCH_ENABLE_MPS_FALLBACK", "1")
        process.setProcessEnvironment(environment)
        logs = self.support / "Logs"
        logs.mkdir(parents=True, exist_ok=True)
        log = logs / "upstream.log"
        if log.exists() and log.stat().st_size > 4_000_000:
            log.replace(log.with_name("upstream.previous.log"))
        process.setStandardErrorFile(str(log), QProcess.Append)
        process.readyReadStandardOutput.connect(self.read_events)
        process.finished.connect(lambda *_: self.engine_stopped(process))
        process.errorOccurred.connect(lambda _: self.fail("The local engine could not start. Use Repair Dependencies.") if process.error() == QProcess.FailedToStart else None)
        process.start(str(self.python), ["-u", str(self.root / "src/worker.py"), "--model", self.model.currentData(), "--device", str(self.settings.value("device", "auto"))])

    def engine_stopped(self, process):
        if self.worker is process and not self.closing:
            self.worker = None
            self.fail("The engine stopped. Click Try Again to restart it.")
        process.deleteLater()

    def send(self, command, message="Working…"):
        if self.worker is None or self.worker.state() != QProcess.Running:
            self.fail("The engine connection closed. Click Try Again.")
            return
        self.busy = True
        self.error.clear()
        self.warning.clear()
        self.status.setText(message)
        self.progress.setRange(0, 0)
        self.refresh()
        self.worker.write((json.dumps(command) + "\n").encode())

    def read_events(self):
        self.buffer += bytes(self.worker.readAllStandardOutput())
        while b"\n" in self.buffer:
            line, self.buffer = self.buffer.split(b"\n", 1)
            try:
                self.receive(json.loads(line))
            except (ValueError, KeyError, TypeError):
                self.fail("The engine returned an unreadable response. Restart the app.")

    def receive(self, event):
        kind = event["type"]
        if kind == "backend":
            self.hardware.setText("Using " + event["device"] + "\n" + event.get("detail", ""))
            self.device.blockSignals(True)
            self.device.clear()
            self.device.addItem("Automatic", "auto")
            for device in event.get("devices", []):
                self.device.addItem(device["backend"] + " — " + device["name"], device["id"])
            requested = event.get("requested_device", "auto")
            self.device.setCurrentIndex(max(0, self.device.findData(requested)))
            self.settings.setValue("device", requested)
            self.device.blockSignals(False)
            if sys.platform == "win32" and not any(d["id"].startswith("cuda") for d in event.get("devices", [])):
                self.hardware.setText(self.hardware.text() + "\nNo CUDA GPU is available to PyTorch. This preview uses CPU for AMD/Intel graphics.")
        elif kind == "ready":
            self.setup = not event["cached"]
            self.authenticated = event.get("authenticated", self.authenticated)
            self.cache_status.setText("Downloaded" if event["cached"] else "Download required")
            self.model_path.setText(event.get("directory", ""))
            self.busy = False
            self.status.setText("Choose audio and review its destination before transcribing.")
        elif kind == "authenticated":
            self.authenticated = True
        elif kind == "status":
            self.status.setText(event["message"])
            self.progress.setRange(0, 0)
        elif kind in ("download", "progress"):
            completed, total = event.get("completed", 0), max(1, event.get("total", 1))
            self.progress.setRange(0, 1000)
            self.progress.setValue(min(1000, int(completed / total * 1000)))
            if kind == "download":
                self.model_path.setText(event["directory"])
                self.status.setText(f"Downloading {self.model.currentData().title()}… {completed / 1e9:.2f} / {total / 1e9:.2f} GB")
            else:
                self.status.setText("Transcribing…")
        elif kind == "planned":
            self.destination = Path(event["path"])
            self.busy = False
            self.status.setText("Ready when you are.")
        elif kind == "complete":
            self.result = self.destination = Path(event["path"])
            self.busy = False
            self.status.setText("Transcription complete.")
            if event.get("needs_save"):
                QTimer.singleShot(0, self.save_copy)
        elif kind == "warning":
            self.warning.setText(event["message"])
        elif kind == "error":
            if event.get("code") == "auth":
                self.authenticated = False
                self.setup = True
            self.fail(event["message"])
        self.refresh()

    def fail(self, message):
        self.busy = False
        self.error.setText(message)
        self.refresh()

    def select_model(self):
        self.settings.setValue("model", self.model.currentData())
        self.send({"action": "select_model", "model": self.model.currentData()}, "Switching model…")

    def select_device(self):
        self.send({"action": "select_device", "device": self.device.currentData()}, "Switching processor…")

    def download(self):
        if self.busy:
            return
        if self.authenticated:
            self.send({"action": "prepare"}, "Checking model…")
        elif self.token.text().strip():
            token = self.token.text().strip()
            self.token.clear()
            self.send({"action": "auth", "token": token}, "Connecting to Hugging Face…")

    def choose_audio(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose Audio", "", "Audio (*.wav *.mp3 *.flac *.m4a *.aac *.aiff *.ogg);;All files (*)")
        if path:
            self.stage(Path(path))

    def stage(self, path):
        if self.busy:
            return
        if not path.is_file():
            self.fail("Choose an audio file stored on this computer.")
            return
        self.source, self.destination, self.result = path, None, None
        self.plan()

    def plan(self, folder=None):
        command = {"action": "plan", "path": str(self.source)}
        if folder:
            command["directory"] = str(folder)
        self.send(command, "Checking MIDI destination…")

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose MIDI Output Folder", str((self.destination or self.source).parent))
        if folder:
            self.plan(folder)

    def transcribe(self):
        if not self.busy and not self.setup and self.source and self.destination:
            self.send({"action": "transcribe", "path": str(self.source), "destination": str(self.destination)}, "Reading audio…")

    def save_copy(self):
        if not self.result:
            return
        filename, _ = QFileDialog.getSaveFileName(self, "Save MIDI Copy", str(self.result), "MIDI (*.mid)")
        if filename:
            try:
                if Path(filename).resolve() != self.result.resolve():
                    from PySide6.QtCore import QSaveFile, QIODevice
                    output = QSaveFile(filename)
                    data = self.result.read_bytes()
                    if not output.open(QIODevice.WriteOnly) or output.write(data) != len(data) or not output.commit():
                        raise OSError("Save failed")
                self.result = self.destination = Path(filename)
                self.error.clear()
                self.refresh()
            except OSError:
                self.fail("The MIDI could not be saved there. Choose another folder.")

    def another(self):
        self.source = self.destination = self.result = None
        self.error.clear()
        self.warning.clear()
        self.status.clear()
        self.refresh()

    def retry(self):
        if self.worker is None or self.worker.state() == QProcess.NotRunning:
            self.start()
        elif self.setup:
            self.download()
        elif self.source and not self.destination:
            self.plan()
        else:
            self.transcribe()

    def repair(self):
        if self.busy:
            return
        if sys.platform != "win32":
            self.fail("Use the macOS app to repair this Mac’s environment.")
            return
        if self.worker:
            process, self.worker = self.worker, None
            process.kill()
            process.waitForFinished(3000)
        self.busy = True
        self.error.clear()
        self.status.setText("Installing private Python and dependencies… First setup needs Internet access.")
        self.refresh()
        process = QProcess(self)
        self.installer = process
        logs = self.support / "Logs"
        logs.mkdir(parents=True, exist_ok=True)
        process.setStandardOutputFile(str(logs / "setup.log"))
        process.setProcessChannelMode(QProcess.MergedChannels)
        process.errorOccurred.connect(lambda _: self.fail("Setup could not start. See Show Logs.") if process.error() == QProcess.FailedToStart else None)
        process.finished.connect(lambda code, _: self.setup_finished(code))
        process.start("powershell.exe", ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(self.resources / "tools/bootstrap-windows.ps1"), "-Root", str(self.root), "-Resources", str(self.resources)])

    def setup_finished(self, code):
        self.installer = None
        if not self.closing:
            if code == 0:
                self.start()
            else:
                self.fail("Setup failed. Check Internet access and App → Show Logs, then retry Repair Dependencies.")

    def dragEnterEvent(self, event):
        if not self.busy and event.mimeData().hasUrls() and len(event.mimeData().urls()) == 1 and event.mimeData().urls()[0].isLocalFile():
            event.acceptProposedAction()

    def dropEvent(self, event):
        if not self.busy and event.mimeData().hasUrls() and len(event.mimeData().urls()) == 1 and event.mimeData().urls()[0].isLocalFile():
            self.stage(Path(event.mimeData().urls()[0].toLocalFile()))
            event.acceptProposedAction()

    def closeEvent(self, event):
        self.closing = True
        for process in (self.worker, self.installer):
            if process and process.state() != QProcess.NotRunning:
                process.terminate()
                if not process.waitForFinished(1500):
                    process.kill()
                    process.waitForFinished(1500)
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow(autostart="--smoke-test" not in sys.argv)
    window.show()
    if "--smoke-test" in sys.argv:
        QTimer.singleShot(250, app.quit)
    sys.exit(app.exec())
