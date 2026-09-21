"""Windows desktop preview. The engine runs separately; audio never leaves the PC."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sys

from PySide6.QtCore import QProcess, QProcessEnvironment, QRectF, QSettings, QTimer, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
    QLayout, QMainWindow, QProgressBar, QPushButton, QScrollArea, QSizePolicy, QStyle,
    QStyleOptionButton, QVBoxLayout, QWidget,
)


def support_directory():
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "MuScriptor Local"
    return Path.home() / "Library/Application Support/MuScriptor Local"


def label(text=""):
    widget = QLabel(text)
    widget.setWordWrap(True)
    widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
    widget.setTextFormat(Qt.PlainText)
    widget.setTextInteractionFlags(Qt.TextSelectableByMouse)
    return widget


def styled_label(text="", role="secondary"):
    widget = label(text)
    widget.setObjectName(role)
    return widget


def panel(role="card", spacing=8):
    widget = QWidget()
    widget.setObjectName(role)
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(14, 14, 14, 14)
    layout.setSpacing(spacing)
    return widget, layout


class Waveform(QWidget):
    """Small vector waveform, independent of platform icon fonts."""
    def __init__(self):
        super().__init__()
        self.setFixedSize(28, 36)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(self.palette().text().color(), 1.5, Qt.SolidLine, Qt.RoundCap))
        for i, height in enumerate((6, 18, 28, 20, 8, 14)):
            x = 2 + i * 5
            painter.drawLine(x, (36 - height) // 2, x, (36 + height) // 2)


class AudioDropButton(QPushButton):
    def __init__(self):
        super().__init__()
        self.setObjectName("audioDrop")
        self.setAccessibleName("Choose audio or drop an audio file")
        self.setFixedHeight(155)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 20, 16, 20)
        layout.setSpacing(10)
        layout.addWidget(Waveform(), 0, Qt.AlignHCenter)
        for text, role in (("Drop an audio file here", "heading"),
                           ("or click to choose", "secondary"),
                           ("MP3 · WAV · FLAC · M4A / AAC", "tertiary")):
            child = styled_label(text, role)
            child.setAlignment(Qt.AlignCenter)
            child.setAttribute(Qt.WA_TransparentForMouseEvents)
            layout.addWidget(child)

    def paintEvent(self, event):
        # Qt's stylesheet dashes are dotted on some hosts; match the Mac stroke.
        dark = self.window().palette().window().color().lightness() < 128
        active = self.isEnabled() and (self.underMouse() or self.hasFocus() or self.property("dragging"))
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor("#22292d" if dark else "#f4f5f5"))
        pen = QPen(QColor("#479aff" if active else ("#474e52" if dark else "#c9cdd0")), 1.5)
        pen.setDashPattern([4, 3])
        painter.setPen(pen)
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 14, 14)


class OptionCheckBox(QCheckBox):
    """Keep Qt's input/accessibility behavior with a consistent rounded indicator."""
    def paintEvent(self, event):
        super().paintEvent(event)
        option = QStyleOptionButton()
        self.initStyleOption(option)
        indicator = self.style().subElementRect(QStyle.SE_CheckBoxIndicator, option, self)
        dark = self.window().palette().window().color().lightness() < 128
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if not self.isEnabled():
            painter.setOpacity(0.5)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#479aff" if self.isChecked() else ("#3a4246" if dark else "#dedfe1")))
        painter.drawRoundedRect(QRectF(indicator), 5, 5)
        if self.isChecked():
            painter.setPen(QPen(QColor("white"), 1.7, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            x, y = indicator.x(), indicator.y()
            painter.drawLine(x + 4, y + 8, x + 7, y + 11)
            painter.drawLine(x + 7, y + 11, x + 12, y + 5)


class CompletionMark(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(38, 38)
        self.setAccessibleName("Completed")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#32b65a"))
        painter.drawEllipse(1, 1, 36, 36)
        painter.setPen(QPen(QColor("white"), 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawLine(10, 19, 16, 25)
        painter.drawLine(16, 25, 28, 12)

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
        self.dependency_failed = False
        self.instrument_groups = []
        self.selected_instruments = []
        self.soundfont = None
        self.ab_result = None
        self.web_url = None
        self.backend = "Detecting processor…"
        self.setWindowTitle("MuScriptor Local")
        self.resize(560, 760)
        self.setMinimumSize(520, 600)
        self.setAcceptDrops(True)
        # Fusion keeps controls and checkbox indicators consistent across hosts.
        application = QApplication.instance()
        palette = application.palette()
        application.setStyle("Fusion")
        application.setPalette(palette)
        self.apply_theme()
        body = QWidget()
        body.setObjectName("content")
        # Let the scroll area use the wrapped height at the actual viewport width.
        # A fixed layout minimum otherwise includes several screens of blank space.
        body.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Ignored)
        self.layout = QVBoxLayout(body)
        self.layout.setContentsMargins(22, 28, 22, 22)
        self.layout.setSpacing(20)
        self.layout.setSizeConstraint(QLayout.SetNoConstraint)
        title_row = QHBoxLayout()
        title_row.addWidget(styled_label("MuScriptor Local", "title"), 1)
        self.web_button = QPushButton("Open Web GUI")
        self.web_button.setObjectName("link")
        self.web_button.clicked.connect(self.open_web_gui)
        title_row.addWidget(self.web_button)
        self.layout.addLayout(title_row)

        model_section, model_layout = panel("plain")
        model_layout.setContentsMargins(0, 0, 0, 0)
        model_header = QHBoxLayout()
        model_header.addWidget(styled_label("Model", "heading"))
        model_header.addStretch()
        self.cache_status = styled_label("", "caption")
        model_header.addWidget(self.cache_status)
        model_layout.addLayout(model_header)
        # Retain the model selection API and signals, presenting it as segments.
        self.model = QComboBox(self)
        self.model.hide()
        for size in ("small", "medium", "large"):
            self.model.addItem(size.title(), size)
        saved = self.settings.value("model", "large")
        self.model.setCurrentIndex(max(0, self.model.findData(saved)))
        self.model.currentIndexChanged.connect(self.select_model)
        self.model_segments = QWidget()
        self.model_segments.setObjectName("segments")
        segments = QHBoxLayout(self.model_segments)
        segments.setContentsMargins(0, 0, 0, 0)
        segments.setSpacing(0)
        self.model_segments.setFixedSize(210, 24)
        self.model_buttons = QButtonGroup(self)
        self.model_buttons.setExclusive(True)
        for index, size in enumerate(("Small", "Medium", "Large")):
            button = QPushButton(size)
            button.setCheckable(True)
            button.setObjectName("segment")
            self.model_buttons.addButton(button, index)
            segments.addWidget(button)
        self.model_buttons.idClicked.connect(self.model.setCurrentIndex)
        model_layout.addWidget(self.model_segments, 0, Qt.AlignLeft)
        model_layout.addWidget(styled_label("Small uses less memory · Medium balances size and accuracy · Large favors accuracy", "caption"))
        self.layout.addWidget(model_section)
        self.web_widget, web_layout = panel()
        web_layout.addWidget(styled_label("Web GUI running locally", "heading"))
        web_layout.addWidget(styled_label("Using this app’s selected model and processor. Keep the app open while using your browser."))
        web_layout.addWidget(styled_label("Web downloads use your browser’s save location. Returning to desktop stops the web GUI and any active web transcription.", "caption"))
        self.desktop_button = QPushButton("Return to Desktop")
        self.desktop_button.clicked.connect(self.return_to_desktop)
        web_layout.addWidget(self.desktop_button, 0, Qt.AlignLeft)
        self.layout.addWidget(self.web_widget)

        self.busy_widget, busy_layout = panel("plain", 12)
        self.busy_filename = styled_label("", "heading")
        self.busy_filename.setAlignment(Qt.AlignCenter)
        busy_layout.addWidget(self.busy_filename)
        self.status = styled_label("Checking local environment…")
        self.status.setAlignment(Qt.AlignCenter)
        busy_layout.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        busy_layout.addWidget(self.progress)
        self.progress_caption = styled_label("", "caption")
        self.progress_caption.setAlignment(Qt.AlignCenter)
        busy_layout.addWidget(self.progress_caption)
        self.layout.addWidget(self.busy_widget)

        self.setup_widget, setup_layout = panel()
        self.setup_heading = styled_label("", "heading")
        setup_layout.addWidget(self.setup_heading)
        setup_layout.addWidget(styled_label("Accept this model’s terms on Hugging Face. Each size needs its own acceptance; downloads are kept for future use."))
        links = QHBoxLayout()
        terms = QPushButton("Model terms")
        terms.setObjectName("link")
        terms.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(f"https://huggingface.co/MuScriptor/muscriptor-{self.model.currentData()}")))
        links.addWidget(terms)
        tokens = QPushButton("Get a read token")
        tokens.setObjectName("link")
        tokens.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://huggingface.co/settings/tokens")))
        links.addWidget(tokens)
        links.addStretch()
        setup_layout.addLayout(links)
        self.token = QLineEdit()
        self.token.setEchoMode(QLineEdit.Password)
        self.token.setPlaceholderText("Hugging Face read token")
        self.token.returnPressed.connect(self.download)
        setup_layout.addWidget(self.token)
        self.download_button = QPushButton("Download Model")
        self.download_button.setObjectName("primary")
        self.download_button.clicked.connect(self.download)
        setup_layout.addWidget(self.download_button, 0, Qt.AlignLeft)
        self.layout.addWidget(self.setup_widget)
        self.audio_button = AudioDropButton()
        self.audio_button.clicked.connect(self.choose_audio)
        self.layout.addWidget(self.audio_button)
        self.source_widget, source_layout = panel("plain")
        source_layout.setContentsMargins(0, 0, 0, 0)
        source_row = QHBoxLayout()
        source_row.addWidget(Waveform())
        self.source_name = styled_label("", "heading")
        source_row.addWidget(self.source_name, 1)
        self.change_audio = QPushButton("Change Audio…")
        self.change_audio.clicked.connect(self.choose_audio)
        source_row.addWidget(self.change_audio)
        source_layout.addLayout(source_row)
        self.layout.addWidget(self.source_widget)

        self.complete_widget, complete_layout = panel("plain", 12)
        complete_layout.addWidget(CompletionMark(), 0, Qt.AlignHCenter)
        complete = styled_label("Transcription complete", "heading")
        complete.setAlignment(Qt.AlignCenter)
        complete_layout.addWidget(complete)
        self.result_name = label()
        self.result_name.setAlignment(Qt.AlignCenter)
        complete_layout.addWidget(self.result_name)
        actions = QHBoxLayout()
        actions.addStretch()
        self.save_button = QPushButton("Save MIDI Copy…")
        self.save_button.setObjectName("primary")
        self.save_button.clicked.connect(self.save_copy)
        actions.addWidget(self.save_button)
        self.reveal_button = QPushButton("Reveal in Explorer")
        self.reveal_button.clicked.connect(lambda: self.reveal(self.result))
        actions.addWidget(self.reveal_button)
        actions.addStretch()
        complete_layout.addLayout(actions)
        self.another_button = QPushButton("Convert Another")
        self.another_button.setObjectName("link")
        self.another_button.clicked.connect(self.another)
        complete_layout.addWidget(self.another_button, 0, Qt.AlignHCenter)
        self.layout.addWidget(self.complete_widget)

        self.options_widget, options = panel(spacing=11)
        options.addWidget(styled_label("Instruments", "heading"))
        options.addWidget(styled_label("Leave empty to detect any supported instrument.", "caption"))
        self.selected_widget = QWidget()
        self.selected_layout = QVBoxLayout(self.selected_widget)
        self.selected_layout.setContentsMargins(0, 0, 0, 0)
        self.selected_layout.setSpacing(6)
        options.addWidget(self.selected_widget)
        self.instrument_search = QLineEdit()
        self.instrument_search.setObjectName("instrumentSearch")
        self.instrument_search.setPlaceholderText("Search instruments")
        self.instrument_search.setAccessibleName("Search instruments")
        self.instrument_search.textChanged.connect(self.update_instruments)
        options.addWidget(self.instrument_search)
        choices = QScrollArea()
        choices.setWidgetResizable(True)
        choices.setFixedHeight(100)
        choices.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.instrument_list = QWidget()
        self.instrument_layout = QVBoxLayout(self.instrument_list)
        self.instrument_layout.setContentsMargins(0, 0, 0, 0)
        self.instrument_layout.setSpacing(2)
        choices.setWidget(self.instrument_list)
        options.addWidget(choices)
        self.quantize = OptionCheckBox("Quantize MIDI for notation")
        options.addWidget(self.quantize)
        options.addWidget(styled_label("Off keeps performance timing. Both modes use upstream onset correction when a usable beat grid is detected.", "caption"))
        self.create_ab = OptionCheckBox("Create A/B audio render")
        self.create_ab.toggled.connect(self.refresh)
        options.addWidget(self.create_ab)
        self.soundfont_widget, soundfont_layout = panel("plain")
        soundfont_layout.setContentsMargins(0, 0, 0, 0)
        soundfont_layout.addWidget(styled_label("Original audio on the left; performance-timing MIDI synthesis on the right. Requires FluidSynth on PATH and a local SF2 SoundFont.", "caption"))
        self.soundfont_button = QPushButton("Choose SoundFont…")
        self.soundfont_button.clicked.connect(self.choose_soundfont)
        soundfont_layout.addWidget(self.soundfont_button, 0, Qt.AlignLeft)
        self.soundfont_path = styled_label("Choose a local .sf2 SoundFont.", "path")
        soundfont_layout.addWidget(self.soundfont_path)
        options.addWidget(self.soundfont_widget)
        self.layout.addWidget(self.options_widget)

        self.ab_widget, ab_layout = panel("plain")
        ab_layout.setContentsMargins(0, 0, 0, 0)
        ab_layout.addWidget(styled_label("A/B audio saved to", "heading"))
        self.ab_path = styled_label("", "path")
        ab_layout.addWidget(self.ab_path)
        self.reveal_ab = QPushButton("Reveal A/B Audio in Explorer")
        self.reveal_ab.clicked.connect(lambda: self.reveal(self.ab_result))
        ab_layout.addWidget(self.reveal_ab, 0, Qt.AlignLeft)
        self.layout.addWidget(self.ab_widget)
        self.output_widget, output_layout = panel()
        output_header = QHBoxLayout()
        self.output_heading = styled_label("MIDI destination", "heading")
        output_header.addWidget(self.output_heading)
        output_header.addStretch()
        self.folder_button = QPushButton("Change Folder…")
        self.folder_button.clicked.connect(self.choose_folder)
        output_header.addWidget(self.folder_button)
        output_layout.addLayout(output_header)
        self.output_path = styled_label("", "path")
        output_layout.addWidget(self.output_path)
        self.output_note = styled_label("Existing files are kept. A number is added if this name is taken.", "caption")
        output_layout.addWidget(self.output_note)
        self.layout.addWidget(self.output_widget)
        self.transcribe_button = QPushButton("Transcribe")
        self.transcribe_button.setObjectName("primary")
        self.transcribe_button.clicked.connect(self.transcribe)
        self.layout.addWidget(self.transcribe_button, 0, Qt.AlignLeft)
        self.error = styled_label("", "error")
        self.layout.addWidget(self.error)
        self.retry_button = QPushButton("Try Again")
        self.retry_button.clicked.connect(self.retry)
        self.layout.addWidget(self.retry_button, 0, Qt.AlignLeft)
        self.warning = styled_label("", "warning")
        self.layout.addWidget(self.warning)

        divider = QWidget()
        divider.setObjectName("divider")
        divider.setFixedHeight(1)
        self.layout.addWidget(divider)
        model_folder, folder_layout = panel("plain", 5)
        folder_layout.setContentsMargins(0, 0, 0, 0)
        folder_layout.addWidget(styled_label("Model download folder", "captionHeading"))
        self.model_path = styled_label("Checking…", "path")
        folder_layout.addWidget(self.model_path)
        self.layout.addWidget(model_folder)
        self.footer = styled_label("Audio stays on this PC", "caption")
        self.layout.addWidget(self.footer)
        self.hardware = styled_label("Detecting available processors…", "caption")
        self.layout.addWidget(self.hardware)
        processor, processor_layout = panel("plain", 8)
        processor_layout.setContentsMargins(0, 0, 0, 0)
        self.processor_toggle = QPushButton("▸ Processor settings")
        self.processor_toggle.setObjectName("link")
        self.processor_toggle.setCheckable(True)
        self.processor_toggle.toggled.connect(self.refresh)
        processor_layout.addWidget(self.processor_toggle, 0, Qt.AlignLeft)
        self.device = QComboBox()
        self.device.addItem("Automatic", "auto")
        self.device.setAccessibleName("Processor")
        self.device.currentIndexChanged.connect(self.select_device)
        processor_layout.addWidget(self.device)
        self.memory_note = styled_label("Memory figures show total capacity, not free memory.", "caption")
        processor_layout.addWidget(self.memory_note)
        self.layout.addWidget(processor)
        self.layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(body)
        self.setCentralWidget(scroll)
        menu = self.menuBar().addMenu("App")
        self.repair_action = menu.addAction("Repair Dependencies…", self.repair)
        menu.addAction("Show Logs", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.support / "Logs"))))
        self.update_instruments()
        self.refresh()
        if autostart:
            QTimer.singleShot(0, self.start)

    def apply_theme(self):
        dark = self.palette().window().color().lightness() < 128
        bg, card, field = ("#1e2528", "#242a2e", "#1e2528") if dark else ("#fafafa", "#f1f2f2", "#ffffff")
        text, muted, border = ("#dedfe0", "#a4a7a9", "#363d41") if dark else ("#25262a", "#666973", "#d4d5da")
        segment, selected = ("#30373b", "#474e52") if dark else ("#e5e6e7", "#ffffff")
        accent = "#479aff" if dark else "#007aff"
        self.setStyleSheet(f"""
            QMainWindow, QWidget#content {{ background: {bg}; }}
            QWidget {{ color: {text}; font-family: 'Segoe UI', sans-serif; font-size: 13px; }}
            QLabel {{ background: transparent; border: none; }}
            QLabel#title {{ font-size: 25px; font-weight: 600; }}
            QLabel#heading {{ font-size: 13px; font-weight: 600; }}
            QLabel#secondary, QLabel#caption, QLabel#path {{ color: {muted}; }}
            QLabel#caption, QLabel#path, QLabel#captionHeading, QLabel#tertiary {{ font-size: 11px; }}
            QLabel#captionHeading {{ font-weight: 600; }}
            QLabel#tertiary {{ color: {'#707679' if dark else '#85898c'}; }}
            QLabel#path {{ font-family: {'Consolas' if sys.platform == 'win32' else 'Menlo'}; }}
            QLabel#error {{ color: {'#ff8585' if dark else '#bd3035'}; }}
            QLabel#warning {{ color: {'#ffc46b' if dark else '#925500'}; }}
            QWidget#card {{ background: {card}; border-radius: 12px; }}
            QWidget#plain, QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
            QWidget#divider {{ background: {border}; }}
            QPushButton {{ background: {field}; border: 1px solid {border}; border-radius: 6px; padding: 5px 10px; }}
            QPushButton:hover {{ border-color: {accent}; }}
            QPushButton:focus, QLineEdit:focus, QComboBox:focus {{ border: 1px solid {accent}; }}
            QPushButton:disabled, QCheckBox:disabled, QComboBox:disabled {{ color: {muted}; }}
            QPushButton#primary {{ background: {accent}; border: 1px solid {accent}; color: white; font-weight: 500; padding: 7px 14px; }}
            QPushButton#primary:disabled {{ background: {border}; border-color: {border}; color: {muted}; }}
            QPushButton#link {{ background: transparent; border: 1px solid transparent; color: {accent}; padding: 3px 0; text-align: left; }}
            QPushButton#link:hover {{ color: {text}; }}
            QPushButton#instrument {{ background: transparent; border: 1px solid transparent; color: {text}; padding: 4px 0; text-align: left; }}
            QPushButton#instrument:hover {{ background: {segment}; }}
            QPushButton#instrument:focus, QPushButton#link:focus {{ border-color: {accent}; }}
            QPushButton#audioDrop {{ background: {'#22292d' if dark else '#f4f5f5'}; border: 1px dashed {selected if dark else border}; border-radius: 14px; padding: 0; }}
            QPushButton#audioDrop:hover, QPushButton#audioDrop[dragging="true"] {{ border: 1px dashed {accent}; background: {field}; }}
            QWidget#segments {{ background: {segment}; border: none; border-radius: 5px; }}
            QPushButton#segment {{ background: transparent; border: 1px solid transparent; border-radius: 5px; padding: 2px 0; font-weight: 500; }}
            QPushButton#segment:checked {{ background: {selected}; }}
            QPushButton#segment:focus {{ border-color: {accent}; }}
            QPushButton#selected {{ background: rgba(71, 154, 255, 25); border: 1px solid transparent; border-radius: 7px; padding: 0; }}
            QPushButton#selected:focus {{ border-color: {accent}; }}
            QLineEdit, QComboBox {{ background: {field}; border: 1px solid {border}; border-radius: 5px; padding: 5px 7px; }}
            QLineEdit#instrumentSearch {{ padding: 3px 5px; }}
            QCheckBox {{ spacing: 7px; background: transparent; }}
            QCheckBox::indicator {{ width: 16px; height: 16px; }}
            QCheckBox::indicator:unchecked {{ border: none; border-radius: 5px; background: {'#3a4246' if dark else '#dedfe1'}; }}
            QCheckBox::indicator:unchecked:hover {{ background: {selected}; }}
            QCheckBox:focus {{ outline: 1px solid {accent}; }}
            QScrollBar:vertical {{ background: {segment}; width: 10px; border-radius: 5px; margin: 0; }}
            QScrollBar::handle:vertical {{ background: {'#999d9f' if dark else '#a6aaad'}; border-radius: 5px; min-height: 20px; }}
            QScrollBar::handle:vertical:hover {{ background: {muted}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; border: none; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
            QMenuBar, QMenu {{ background: {bg}; color: {text}; }}
            QMenuBar::item:selected, QMenu::item:selected {{ background: {segment}; }}
            QProgressBar {{ background: {card}; border: 1px solid {border}; border-radius: 5px; text-align: center; min-height: 12px; }}
            QProgressBar::chunk {{ background: {accent}; border-radius: 4px; }}
        """)

    def refresh(self):
        for widget in (self.model, self.model_segments, self.device, self.audio_button,
                       self.change_audio, self.folder_button, self.options_widget):
            widget.setEnabled(not self.busy and self.web_url is None)
        self.web_button.setEnabled(not self.busy and not self.setup)
        self.web_widget.setVisible(self.web_url is not None)
        self.model_buttons.button(self.model.currentIndex()).setChecked(True)
        self.repair_action.setEnabled(not self.busy and self.web_url is None)
        self.setup_widget.setVisible(self.setup and not self.busy and self.result is None)
        self.setup_heading.setText("Set up MuScriptor " + self.model.currentData().title())
        self.token.setVisible(not self.authenticated)
        self.download_button.setText(("Download " if self.authenticated else "Connect and Download ") + self.model.currentData().title())
        self.folder_button.setVisible(self.source is not None and self.result is None and not self.busy)
        self.output_widget.setVisible(self.destination is not None)
        self.output_path.setText(str(self.destination or ""))
        self.output_heading.setText("MIDI saved to" if self.result else "MIDI destination")
        self.output_note.setVisible(self.result is None)
        self.audio_button.setVisible(not self.busy and self.source is None and self.result is None)
        self.source_widget.setVisible(not self.busy and self.source is not None and self.result is None)
        self.source_name.setText(self.source.name if self.source else "")
        self.busy_filename.setText(self.source.name if self.source else "")
        self.busy_filename.setVisible(self.source is not None)
        self.busy_widget.setVisible(self.busy)
        self.progress_caption.setVisible(self.progress.maximum() > 0)
        self.progress_caption.setText(f"{max(0, self.progress.value()) / 10:.0f}%")
        self.transcribe_button.setText("Transcribe with " + self.model.currentData().title())
        self.transcribe_button.setVisible(not self.busy and self.source is not None and self.result is None)
        self.transcribe_button.setEnabled(not self.busy and not self.setup and self.destination is not None)
        self.complete_widget.setVisible(self.result is not None and not self.busy)
        self.result_name.setText(self.result.name if self.result else "")
        self.options_widget.setVisible(not self.setup and self.result is None)
        self.soundfont_widget.setVisible(self.create_ab.isChecked())
        self.ab_widget.setVisible(self.ab_result is not None)
        self.ab_path.setText(str(self.ab_result or ""))
        self.error.setVisible(bool(self.error.text()))
        self.warning.setVisible(bool(self.warning.text()))
        self.retry_button.setVisible(bool(self.error.text()) and not self.busy)
        expanded = self.processor_toggle.isChecked()
        self.processor_toggle.setText(("▾" if expanded else "▸") + " Processor settings")
        self.device.setVisible(expanded)
        self.memory_note.setVisible(expanded)
        self.footer.setText("MuScriptor " + self.model.currentData().title() + " • " + self.backend + " • Audio stays on this PC")
        if self.web_url:
            for widget in (self.audio_button, self.source_widget, self.options_widget,
                           self.output_widget, self.transcribe_button, self.complete_widget, self.ab_widget):
                widget.hide()

    def open_web_gui(self):
        if self.web_url:
            QDesktopServices.openUrl(QUrl(self.web_url))
        elif not self.busy and not self.setup:
            self.send({"action": "web_gui"}, "Opening the local web GUI…")

    def return_to_desktop(self):
        if not self.web_url:
            return
        process, self.worker = self.worker, None
        if process and process.state() != QProcess.NotRunning:
            if sys.platform == "win32":
                QProcess.execute("taskkill.exe", ["/PID", str(process.processId()), "/T", "/F"])
                # Restricted Windows accounts may deny taskkill even for our
                # own worker. QProcess retains the handle needed to stop it.
                if process.state() != QProcess.NotRunning:
                    process.kill()
            else:
                process.kill()
            if not process.waitForFinished(3000):
                self.worker = process
                self.fail("The web GUI is still stopping. Try Return to Desktop again.")
                return
        self.web_url = None
        self.start()

    @staticmethod
    def clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()

    def update_instruments(self):
        self.clear_layout(self.selected_layout)
        self.clear_layout(self.instrument_layout)
        self.selected_widget.setVisible(bool(self.selected_instruments))
        for name in self.selected_instruments:
            button = QPushButton()
            button.setMinimumHeight(30)
            button.setObjectName("selected")
            button.setAccessibleName("Remove " + name.replace("_", " "))
            row = QHBoxLayout(button)
            row.setContentsMargins(7, 5, 7, 5)
            for text, stretch in ((name.replace("_", " ").title(), 1), ("×", 0)):
                child = label(text)
                child.setAttribute(Qt.WA_TransparentForMouseEvents)
                row.addWidget(child, stretch)
            button.clicked.connect(lambda checked=False, name=name: self.remove_instrument(name))
            self.selected_layout.addWidget(button)
        query = self.instrument_search.text().strip().casefold()
        matches = [name for name in self.instrument_groups if name not in self.selected_instruments and query in name.replace("_", " ").casefold()]
        for name in matches:
            button = QPushButton("⊕  " + name.replace("_", " ").title())
            button.setObjectName("instrument")
            button.clicked.connect(lambda checked=False, name=name: self.add_instrument(name))
            self.instrument_layout.addWidget(button)
        if not matches:
            self.instrument_layout.addWidget(styled_label("No matching instruments", "caption"))
        self.instrument_layout.addStretch()

    def add_instrument(self, name):
        if not self.busy and name in self.instrument_groups and name not in self.selected_instruments:
            self.selected_instruments.append(name)
            self.instrument_search.clear()
            self.update_instruments()

    def remove_instrument(self, name):
        if not self.busy and name in self.selected_instruments:
            self.selected_instruments.remove(name)
            self.update_instruments()

    def choose_soundfont(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose a local SF2 SoundFont", "", "SoundFont (*.sf2)")
        if path:
            self.soundfont = Path(path)
            self.soundfont_path.setText(path)

    def reveal(self, path):
        if path:
            if sys.platform == "win32":
                QProcess.startDetached("explorer.exe", ["/select,", str(path.resolve())])
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))

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
                shutil.copytree(self.resources / "upstream/muscriptor/web_dist", self.root / "upstream/muscriptor/web_dist", dirs_exist_ok=True)
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
            self.web_url = None
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
        if kind == "web_ready":
            url = QUrl(event.get("url", ""))
            if url.scheme() != "http" or url.host() != "127.0.0.1" or url.port() <= 0:
                self.fail("The local web GUI returned an invalid address.")
                return
            self.web_url = url.toString()
            self.busy = False
            QDesktopServices.openUrl(url)
        elif kind == "backend":
            self.backend = event["device"]
            self.hardware.setText(event.get("detail", ""))
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
            self.instrument_groups = event.get("instruments", self.instrument_groups)
            self.update_instruments()
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
            self.ab_result = Path(event["ab_path"]) if event.get("ab_path") else None
            self.result = self.destination = Path(event["path"])
            self.busy = False
            self.status.setText("Transcription complete.")
            if event.get("needs_save"):
                QTimer.singleShot(0, self.save_copy)
        elif kind == "warning":
            self.warning.setText("\n\n".join(filter(None, (self.warning.text(), event["message"]))))
        elif kind == "error":
            if event.get("code") == "dependencies":
                self.dependency_failed = True
            if event.get("code") == "auth":
                self.authenticated = False
                self.setup = True
            self.fail(event["message"])
        self.refresh()

    def fail(self, message):
        self.busy = False
        self.status.setText("Action needed")
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
        self.ab_result = None
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
            command = {"action": "transcribe", "path": str(self.source), "destination": str(self.destination),
                       "instruments": list(self.selected_instruments), "quantize": self.quantize.isChecked(),
                       "create_ab": self.create_ab.isChecked()}
            if self.soundfont:
                command["soundfont"] = str(self.soundfont)
            self.send(command, "Reading audio…")

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
        self.source = self.destination = self.result = self.ab_result = None
        self.error.clear()
        self.warning.clear()
        self.status.clear()
        self.refresh()

    def retry(self):
        if self.dependency_failed:
            self.repair()
        elif self.worker is None or self.worker.state() == QProcess.NotRunning:
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
        self.dependency_failed = True
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
                self.dependency_failed = False
                self.start()
            else:
                message = "Engine setup did not finish. Try Again repairs the installation. Open App → Show Logs for details."
                try:
                    log = (self.support / "Logs/setup.log").read_text(errors="replace")[-65536:].lower()
                    if "untrusted mount point" in log:
                        message = "Windows blocked a Python version link. Install the latest app update, then choose Try Again."
                    elif "no space left" in log or "not enough space" in log:
                        message = "There is not enough disk space for the engine. Free some space, then choose Try Again."
                    elif "access is denied" in log or "permission denied" in log:
                        message = "Windows denied access to the engine folder. Check its permissions, then choose Try Again."
                except OSError:
                    pass
                self.fail(message)

    def dragEnterEvent(self, event):
        if not self.busy and not self.web_url and event.mimeData().hasUrls() and len(event.mimeData().urls()) == 1 and event.mimeData().urls()[0].isLocalFile():
            self.audio_button.setProperty("dragging", True)
            self.audio_button.style().unpolish(self.audio_button)
            self.audio_button.style().polish(self.audio_button)
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self.audio_button.setProperty("dragging", False)
        self.audio_button.style().unpolish(self.audio_button)
        self.audio_button.style().polish(self.audio_button)
        event.accept()

    def dropEvent(self, event):
        self.dragLeaveEvent(event)
        if not self.busy and not self.web_url and event.mimeData().hasUrls() and len(event.mimeData().urls()) == 1 and event.mimeData().urls()[0].isLocalFile():
            self.stage(Path(event.mimeData().urls()[0].toLocalFile()))
            event.acceptProposedAction()

    def closeEvent(self, event):
        self.closing = True
        for process in (self.worker, self.installer):
            if process and process.state() != QProcess.NotRunning:
                if sys.platform == "win32":
                    # Include this worker's decoder / this installer's uv children.
                    QProcess.execute("taskkill.exe", ["/PID", str(process.processId()), "/T", "/F"])
                    if process.state() != QProcess.NotRunning:
                        process.kill()
                    process.waitForFinished(1500)
                    continue
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
