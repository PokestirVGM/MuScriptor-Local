"""Windows desktop preview. The engine runs separately; audio never leaves the PC."""
from __future__ import annotations

import uuid
import json
import os
from pathlib import Path
import shutil
import sys
from engine_install import install as install_engine

from PySide6.QtCore import QPointF, QProcess, QProcessEnvironment, QRectF, QSettings, QSize, QTimer, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QPainter, QPainterPath, QPalette, QPen, QPixmap, QRegion
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
    QFrame, QListView, QStyledItemDelegate, QLayout, QMainWindow, QMenu, QToolButton, QDialog, QProgressBar, QPushButton, QScrollArea, QSizePolicy, QStyle,
    QStyleOptionButton, QStyleOptionComboBox, QVBoxLayout, QWidget, QPlainTextEdit,
)

WINDOWS_APP_ID = "MuScriptor.Local.Desktop"


def configure_windows_identity():
    if sys.platform == "win32":
        import ctypes
        # Set this before Qt creates any windows so the taskbar does not group
        # the packaged launcher under Python's default application identity.
        set_id = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID
        set_id.argtypes = [ctypes.c_wchar_p]
        set_id.restype = ctypes.c_long
        result = set_id(WINDOWS_APP_ID)
        if result < 0:
            raise OSError(f"Windows application identity failed: {result:#x}")


def support_directory():
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "MuScriptor Local"
    return Path.home() / "Library/Application Support/MuScriptor Local"


def settings_icon(color):
    pixmap = QPixmap(48, 48)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QPen(color, 1.8, Qt.SolidLine, Qt.RoundCap))
    painter.translate(12, 12)
    painter.drawEllipse(QRectF(-6.5, -6.5, 13, 13))
    painter.drawEllipse(QRectF(-2.3, -2.3, 4.6, 4.6))
    for _ in range(8):
        painter.drawLine(0, -7, 0, -9)
        painter.rotate(45)
    painter.end()
    return QIcon(pixmap)


def instrument_add_icon(color):
    # Draw the circle-plus explicitly: Segoe UI's mathematical glyph can be
    # tiny or use an inconsistent fallback font on Windows.
    pixmap = QPixmap(32, 32)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QPen(color, 1.3, Qt.SolidLine, Qt.RoundCap))
    painter.drawEllipse(QRectF(1.5, 1.5, 13, 13))
    painter.drawLine(8, 5, 8, 11)
    painter.drawLine(5, 8, 11, 8)
    painter.end()
    return QIcon(pixmap)


class SelectionBox(QComboBox):
    """A unified rounded field with a scalable, borderless dropdown chevron."""
    def __init__(self, parent=None):
        super().__init__(parent)
        view = QListView(self)
        self.setView(view)
        # Qt's combo-specific delegate paints a raised native menu selection,
        # bypassing item styling. Use the regular list delegate for a flat menu.
        view.setItemDelegate(QStyledItemDelegate(view))
        popup = view.window()
        if isinstance(popup, QFrame):
            popup.setFrameShape(QFrame.NoFrame)
        popup.setWindowFlag(Qt.NoDropShadowWindowHint, True)

    def showPopup(self):
        super().showPopup()
        self.clip_popup()
        QTimer.singleShot(0, self.clip_popup)

    def clip_popup(self):
        # The native popup container extends beyond the styled list on Windows.
        # Clip that outer window too, so its square backing cannot show through.
        view = self.view()
        popup = view.window()
        bounds = QRectF(view.rect()).translated(QPointF(view.mapTo(popup, view.rect().topLeft())))
        shape = QPainterPath()
        shape.addRoundedRect(bounds, 6, 6)
        popup.setMask(QRegion(shape.toFillPolygon().toPolygon()))

    def paintEvent(self, event):
        super().paintEvent(event)
        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        arrow = self.style().subControlRect(QStyle.CC_ComboBox, option, QStyle.SC_ComboBoxArrow, self)
        center = QRectF(arrow).center()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        color = self.palette().color(QPalette.Active if self.isEnabled() else QPalette.Disabled, QPalette.Text)
        painter.setPen(QPen(color, 1.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawPolyline([
            QPointF(center.x() - 3.5, center.y() - 1.5),
            QPointF(center.x(), center.y() + 2),
            QPointF(center.x() + 3.5, center.y() - 1.5),
        ])
        painter.end()


class InstrumentResizeHandle(QWidget):
    """Small drag/keyboard grip for the instrument choices, in logical pixels."""
    def __init__(self, target):
        super().__init__()
        self.target = target
        self.drag_start = None
        self.setFixedHeight(12)
        self.setCursor(Qt.SizeVerCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName("Resize instrument list")
        self.setToolTip("Drag to resize the instrument list. Arrow keys also resize.")

    def resize_list(self, height):
        self.target.setFixedHeight(max(80, min(320, round(height))))
        self.setAccessibleDescription(f"Instrument list height: {self.target.height()} pixels")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start = (event.globalPosition().y(), self.target.height())
            self.setFocus()
            event.accept()

    def mouseMoveEvent(self, event):
        if self.drag_start is not None:
            y, height = self.drag_start
            self.resize_list(height + event.globalPosition().y() - y)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start = None
            event.accept()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Up, Qt.Key_Down):
            self.resize_list(self.target.height() + (20 if event.key() == Qt.Key_Down else -20))
            event.accept()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(self.palette().color(QPalette.Highlight if self.hasFocus() else QPalette.Mid))
        painter.drawRoundedRect(QRectF((self.width()-32)/2, 4, 32, 3), 1.5, 1.5)


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
        icon = self.resources / "assets/muscriptor.ico"
        if icon.is_file():
            app_icon = QIcon(str(icon))
            QApplication.instance().setWindowIcon(app_icon)
            self.setWindowIcon(app_icon)
        self.python = self.root / (".venv/Scripts/python.exe" if sys.platform == "win32" else ".venv/bin/python")
        self.worker = None
        self.installer = None
        self.buffer = b""
        self.busy = True
        self.transcription_id = None
        self.finish_ready = False
        self.finishing = False
        self.completed_seconds = 0
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
        self.has_session = False
        self.recovery_path = None
        self.restore_after_restart = None
        self.restore_latest_after_restart = False
        self.pending_timing = None
        self.saved_timing = ""
        self.web_url = None
        self.backend = "Detecting processor…"
        self.setWindowTitle("MuScriptor Local — 1.0 Release Candidate")
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
        title_row = QHBoxLayout(); title_row.setSpacing(12)
        self.header_logo = QLabel()
        self.header_logo.setFixedSize(76, 48)
        self.header_logo.setAccessibleName("MuScriptor logo")
        self.update_header_logo()
        title_row.addWidget(self.header_logo)
        brand = QVBoxLayout(); brand.setSpacing(3)
        brand.addWidget(styled_label("MuScriptor", "title"))
        brand.addWidget(styled_label("Independent adaptation by Pokestir", "caption"))
        title_row.addLayout(brand, 1)
        self.web_button = QPushButton("Open Web GUI ↗")
        self.web_button.setObjectName("link")
        self.web_button.clicked.connect(self.open_web_gui)
        title_row.addWidget(self.web_button)
        self.options_menu = QMenu(self)
        self.open_session_action = self.options_menu.addAction("Open Session…", lambda: self.open_session())
        self.recover_action = self.options_menu.addAction("Recover Last Session", lambda: self.open_session(self.recovery_path))
        self.options_menu.addSeparator()
        self.options_button = QToolButton()
        self.options_button.setObjectName("optionsGear")
        self.options_button.setIcon(settings_icon(QColor("#dedfe0" if self.palette().window().color().lightness() < 128 else "#25262a")))
        self.options_button.setIconSize(QSize(24, 24))
        self.options_button.setFixedSize(30, 30)
        self.options_button.setAccessibleName("Sessions and app options")
        self.options_button.setToolTip("Sessions and app options")
        self.options_button.setPopupMode(QToolButton.InstantPopup)
        self.options_button.setMenu(self.options_menu)
        title_row.addWidget(self.options_button)
        self.layout.addLayout(title_row)
        self.layout.addWidget(styled_label("Local audio-to-MIDI, with tempo and time-signature controls, optional quantization, and reusable sessions. Open the web GUI for sheet music and audio/MIDI preview.", "caption"))

        model_section, model_layout = panel("plain")
        model_layout.setContentsMargins(0, 0, 0, 0)
        model_header = QHBoxLayout()
        model_header.addWidget(styled_label("Model", "heading"))
        model_header.addStretch()
        self.cache_status = styled_label("", "caption")
        model_header.addWidget(self.cache_status)
        model_layout.addLayout(model_header)
        # Retain the model selection API and signals, presenting it as segments.
        self.model = SelectionBox(self)
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
        self.instrument_choices = choices
        instrument_resize = QVBoxLayout()
        instrument_resize.setSpacing(3)
        instrument_resize.addWidget(choices)
        self.instrument_resize_handle = InstrumentResizeHandle(choices)
        instrument_resize.addWidget(self.instrument_resize_handle)
        options.addLayout(instrument_resize)
        timing_main = QHBoxLayout()
        self.tempo_mode = SelectionBox()
        self.tempo_mode.addItem("Auto", "auto"); self.tempo_mode.addItem("Manual", "manual")
        self.tempo_meter = SelectionBox()
        self.tempo_meter.setEditable(True)
        for meter in ("Auto", "2/4", "3/4", "4/4", "6/8", "9/8", "12/8", "5/4", "7/8"):
            self.tempo_meter.addItem(meter)
        self.tempo_mode.setAccessibleName("Tempo")
        self.tempo_meter.setAccessibleName("Time signature")
        for title, combo in (("Tempo", self.tempo_mode), ("Time signature", self.tempo_meter)):
            column = QVBoxLayout(); column.setSpacing(5)
            column.addWidget(styled_label(title, "caption"))
            combo.setMinimumWidth(110)
            column.addWidget(combo)
            timing_main.addLayout(column, 1)
        self.quantize = OptionCheckBox("Strict quantization")
        timing_main.addWidget(self.quantize, 0, Qt.AlignBottom)
        options.addLayout(timing_main)
        self.manual_timing_widget = QWidget()
        manual_layout = QHBoxLayout(self.manual_timing_widget); manual_layout.setContentsMargins(0,0,0,0)
        self.tempo_bpm = QLineEdit("120"); self.tempo_bpm.setMaximumWidth(70); self.tempo_bpm.setAccessibleName("BPM")
        manual_layout.addWidget(QLabel("BPM")); manual_layout.addWidget(self.tempo_bpm); manual_layout.addWidget(styled_label("Sets the grid; playback stays at the original speed.", "caption"))
        options.addWidget(self.manual_timing_widget)
        self.tempo_subdivision = SelectionBox()
        for field_label, value in (("Snap to: Auto", "auto"), ("Eighth notes", "2"), ("Sixteenth notes", "4"), ("Eighth-note triplets", "3")):
            self.tempo_subdivision.addItem(field_label, value)
        options.addWidget(self.tempo_subdivision)
        self.tempo_subdivision.setVisible(False)
        self.quantize.toggled.connect(self.tempo_subdivision.setVisible)
        self.quantize_note = styled_label("Snaps note starts and ends to the grid. Check the click first: an incorrect grid can make rhythm worse. Turn off to restore original timing.", "caption")
        self.quantize_note.hide(); options.addWidget(self.quantize_note)
        self.quantize.toggled.connect(self.quantize_note.setVisible)
        advanced_toggle = QPushButton("Advanced timing ▸")
        advanced_toggle.setCheckable(True); advanced_toggle.setObjectName("link")
        options.addWidget(advanced_toggle, 0, Qt.AlignLeft)
        self.advanced_timing = QWidget()
        advanced = QVBoxLayout(self.advanced_timing); advanced.setContentsMargins(0,0,0,0)
        advanced.addWidget(styled_label("Tempo sets the grid without changing playback speed. Quantization moves notes.", "caption"))
        self.tempo_unit = SelectionBox()
        for field_label, value in (("Beat unit: From time signature", "auto"), ("Quarter note", "quarter"), ("Dotted quarter", "dotted-quarter"), ("Eighth note", "eighth")):
            self.tempo_unit.addItem(field_label, value)
        advanced.addWidget(self.tempo_unit)
        self.tempo_downbeat = QLineEdit("0"); self.tempo_downbeat.setAccessibleName("First downbeat seconds")
        row = QHBoxLayout(); row.addWidget(QLabel("First downbeat (seconds)")); row.addWidget(self.tempo_downbeat); advanced.addLayout(row)
        self.tempo_factor = SelectionBox()
        for field_label, value in (("Detected pulse: Normal", 1), ("Half tempo", .5), ("Double tempo", 2)):
            self.tempo_factor.addItem(field_label, value)
        advanced.addWidget(self.tempo_factor)
        advanced.addWidget(styled_label("6/8 usually counts dotted-quarter beats. Check Auto’s meter suggestions; enter corrections below.", "caption"))
        self.tempo_anchors = QPlainTextEdit()
        advanced.addWidget(styled_label("Beat anchors", "caption"))
        self.tempo_anchors.setPlaceholderText("0.5, 1\n2.5, 5")
        self.tempo_anchors.setAccessibleName("Beat anchors"); self.tempo_anchors.setFixedHeight(65)
        advanced.addWidget(self.tempo_anchors)
        advanced.addWidget(styled_label("Seconds, beat number. Use at least two anchors; beat 1 is the first downbeat.", "caption"))
        self.tempo_changes = QPlainTextEdit()
        advanced.addWidget(styled_label("Time-signature changes", "caption"))
        self.tempo_changes.setPlaceholderText("9, 3/4")
        self.tempo_changes.setAccessibleName("Meter changes"); self.tempo_changes.setFixedHeight(60)
        advanced.addWidget(self.tempo_changes)
        advanced.addWidget(styled_label("Bar number, signature. Bar 1 starts at the first downbeat.", "caption"))
        self.advanced_timing.hide(); options.addWidget(self.advanced_timing)
        advanced_toggle.toggled.connect(self.advanced_timing.setVisible)
        def tempo_mode_changed():
            manual = self.tempo_mode.currentData() == "manual"
            self.manual_timing_widget.setVisible(manual)
            self.tempo_downbeat.setEnabled(manual)
        self.tempo_mode.currentIndexChanged.connect(tempo_mode_changed)
        tempo_mode_changed()
        self.timing_summary = styled_label("", "caption")
        options.addWidget(self.timing_summary)
        self.reexport_button = QPushButton("Apply timing & save new MIDI")
        self.reexport_button.clicked.connect(self.apply_session)
        options.addWidget(self.reexport_button)
        self.preview_rhythm_button = QPushButton("Preview click")
        self.preview_rhythm_button.clicked.connect(lambda: self.send({"action": "preview_rhythm", "timing": self.timing_options()}, "Preparing click preview…"))
        options.addWidget(self.preview_rhythm_button)
        self.session_button = QPushButton("Save Session…")
        self.session_button.clicked.connect(self.save_session); options.addWidget(self.session_button)
        self.export_readiness = styled_label("", "caption")
        self.export_readiness.hide()
        options.addWidget(self.export_readiness)
        self.check_exports = self.options_menu.addAction("Check Export Requirements", lambda: self.send({"action": "capabilities"}, "Checking export requirements…"))
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
        self.finish_button = QPushButton("Finish here & save MIDI")
        self.finish_button.setToolTip("Saves fully completed 5-second sections. The unfinished section is omitted.")
        self.finish_button.clicked.connect(self.finish_transcription)
        self.layout.addWidget(self.finish_button, 0, Qt.AlignLeft)
        self.finish_hint = styled_label("", "caption")
        self.layout.addWidget(self.finish_hint)
        self.cancel_button = QPushButton("Cancel operation")
        self.cancel_button.clicked.connect(self.cancel_operation)
        self.layout.addWidget(self.cancel_button, 0, Qt.AlignLeft)
        self.error = styled_label("", "error")
        self.layout.addWidget(self.error)
        self.retry_button = QPushButton("Try Again")
        self.retry_button.clicked.connect(self.retry)
        self.layout.addWidget(self.retry_button, 0, Qt.AlignLeft)
        self.warning = styled_label("", "warning")
        self.layout.addWidget(self.warning)

        self.info_dialog = QDialog(self)
        self.info_dialog.setWindowTitle("MuScriptor — App Information")
        self.info_dialog.resize(470, 360)
        info = QVBoxLayout(self.info_dialog); info.setContentsMargins(22, 22, 22, 22); info.setSpacing(12)
        info.addWidget(styled_label("MuScriptor", "title"))
        info.addWidget(styled_label("Independent adaptation by Pokestir", "caption"))
        version_file = self.resources / "VERSION"
        version = version_file.read_text().strip() if version_file.is_file() else "1.0.0-rc.1"
        info.addWidget(styled_label("Version " + version, "caption"))
        self.footer = styled_label("Audio stays on this PC", "caption")
        info.addWidget(self.footer)
        self.hardware = styled_label("Detecting available processors…", "caption")
        info.addWidget(self.hardware)
        info.addWidget(styled_label("Processor", "captionHeading"))
        self.device = SelectionBox()
        self.device.addItem("Automatic", "auto")
        self.device.setAccessibleName("Processor")
        self.device.currentIndexChanged.connect(self.select_device)
        info.addWidget(self.device)
        self.memory_note = styled_label("Memory figures show total capacity, not free memory.", "caption")
        info.addWidget(self.memory_note)
        info.addWidget(styled_label("Model download folder", "captionHeading"))
        self.model_path = styled_label("Checking…", "path")
        info.addWidget(self.model_path)
        self.model_folder_button = QPushButton("Open Model Folder")
        self.model_folder_button.clicked.connect(self.open_model_folder)
        info.addWidget(self.model_folder_button, 0, Qt.AlignLeft)
        info.addWidget(styled_label("Audio is processed on this computer. Original MuScriptor by Kyutai and Mirelo.", "caption"))
        done = QPushButton("Done"); done.clicked.connect(self.info_dialog.accept)
        info.addWidget(done, 0, Qt.AlignRight)
        self.options_menu.addAction("Processor and App Information…", self.show_app_info)
        self.model_folder_action = self.options_menu.addAction("Open Model Folder", self.open_model_folder)
        self.layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(body)
        self.setCentralWidget(scroll)
        self.repair_action = self.options_menu.addAction("Repair Dependencies…", self.repair)
        self.options_menu.addAction("Show Logs", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.support / "Logs"))))
        self.update_instruments()
        self.refresh()
        if autostart:
            QTimer.singleShot(0, self.start)

    def show_app_info(self):
        self.info_dialog.show()
        self.info_dialog.raise_()
        self.info_dialog.activateWindow()

    def open_model_folder(self):
        path = self.model_path.text()
        if path and path != "Checking…":
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def update_header_logo(self):
        variant = "dark" if self.palette().window().color().lightness() < 128 else "light"
        image = QPixmap(str(self.resources / f"assets/muscriptor-header-{variant}.png"))
        if not image.isNull():
            image = image.scaled(228, 144, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            image.setDevicePixelRatio(3)
            self.header_logo.setPixmap(image)

    def apply_theme(self):
        if hasattr(self, "header_logo"):
            self.update_header_logo()
        dark = self.palette().window().color().lightness() < 128
        bg, card, field = ("#1e2528", "#242a2e", "#1e2528") if dark else ("#fafafa", "#f1f2f2", "#ffffff")
        text, muted, border = ("#dedfe0", "#a4a7a9", "#363d41") if dark else ("#25262a", "#666973", "#d4d5da")
        if hasattr(self, "options_button"):
            self.options_button.setIcon(settings_icon(QColor(text)))
        segment, selected = ("#30373b", "#474e52") if dark else ("#e5e6e7", "#ffffff")
        accent = "#479aff" if dark else "#007aff"
        self.setStyleSheet(f"""
            QMainWindow, QDialog, QWidget#content {{ background: {bg}; }}
            QWidget {{ color: {text}; font-family: 'Segoe UI', sans-serif; font-size: 13px; }}
            QLabel {{ background: transparent; border: none; }}
            QLabel#title {{ font-size: 29px; font-weight: 600; }}
            QToolButton#optionsGear {{ border: none; background: transparent; padding: 2px; }}
            QToolButton#optionsGear:hover {{ background: {segment}; border-radius: 5px; }}
            QToolButton#optionsGear::menu-indicator {{ image: none; }}
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
            QComboBox {{ padding-right: 30px; }}
            QComboBox:hover {{ border-color: {muted}; }}
            QComboBox:focus {{ border-color: {accent}; }}
            QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: top right; width: 28px; border: none; background: transparent; }}
            QComboBox::down-arrow {{ image: none; width: 0; height: 0; }}
            QComboBox QAbstractItemView {{ background: {field}; color: {text}; border: 1px solid {border}; border-radius: 6px; padding: 4px; selection-background-color: {accent}; selection-color: white; outline: none; }}
            QComboBox QAbstractItemView::item {{ min-height: 26px; padding: 2px 7px; border: none; border-radius: 4px; }}
            QComboBox QAbstractItemView::item:selected {{ background: {accent}; color: white; border: none; }}
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
            QMenu {{ background: {bg}; color: {text}; }}
            QMenu::item:selected {{ background: {segment}; }}
            QProgressBar {{ background: {card}; border: 1px solid {border}; border-radius: 5px; text-align: center; min-height: 12px; }}
            QProgressBar::chunk {{ background: {accent}; border-radius: 4px; }}
        """)

    def refresh(self):
        for widget in (self.model, self.model_segments, self.device, self.audio_button,
                       self.change_audio, self.folder_button, self.options_widget):
            widget.setEnabled(not self.busy and self.web_url is None)
        self.finish_button.setVisible(self.busy and (self.finish_ready or self.finishing))
        self.finish_button.setEnabled(self.finish_ready and not self.finishing)
        self.finish_button.setText("Finishing…" if self.finishing else "Finish here & save MIDI")
        self.finish_hint.setVisible(self.busy and self.finish_ready)
        self.finish_hint.setText(f"{self.completed_seconds:.0f} seconds completed. Finish here keeps these sections and skips the rest.")
        self.cancel_button.setVisible(self.busy and self.worker is not None and self.installer is None and self.web_url is None)
        self.open_session_action.setEnabled(not self.busy and self.web_url is None)
        self.recover_action.setEnabled(bool(self.recovery_path) and not self.busy and self.web_url is None)
        self.check_exports.setEnabled(not self.busy and self.web_url is None)
        self.session_button.setVisible(self.has_session)
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
        self.options_widget.setVisible(not self.setup or self.has_session)
        self.reexport_button.setVisible(self.result is not None)
        self.preview_rhythm_button.setVisible(self.result is not None)
        self.soundfont_widget.setVisible(self.create_ab.isChecked())
        self.ab_widget.setVisible(self.ab_result is not None)
        self.ab_path.setText(str(self.ab_result or ""))
        self.error.setVisible(bool(self.error.text()))
        self.warning.setVisible(bool(self.warning.text()))
        self.retry_button.setVisible(bool(self.error.text()) and not self.busy)
        folder_ready = bool(self.model_path.text()) and self.model_path.text() != "Checking…"
        self.model_folder_action.setEnabled(folder_ready)
        self.model_folder_button.setEnabled(folder_ready)
        self.footer.setText("MuScriptor " + self.model.currentData().title() + " • " + self.backend + " • Audio stays on this PC")
        if self.web_url:
            for widget in (self.audio_button, self.source_widget, self.options_widget,
                           self.output_widget, self.transcribe_button, self.complete_widget, self.ab_widget):
                widget.hide()

    def open_web_gui(self):
        if self.web_url:
            QDesktopServices.openUrl(QUrl(self.web_url))
        elif not self.busy and not self.setup and self.confirm_discard_timing():
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
        self.restore_latest_after_restart = True
        self.restore_after_restart = self.pending_timing = None
        self.has_session = False
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
            button = QPushButton(name.replace("_", " ").title())
            button.setIcon(instrument_add_icon(self.palette().color(QPalette.WindowText)))
            button.setIconSize(QSize(16, 16))
            button.setAccessibleName("Add " + name.replace("_", " "))
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
                install_engine(self.root, self.resources / "src/worker.py", self.resources / "upstream/muscriptor")
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
        process.readyReadStandardOutput.connect(lambda: self.read_events(process))
        process.finished.connect(lambda *_: self.engine_stopped(process))
        process.errorOccurred.connect(lambda _: self.fail("The local engine could not start. Use Repair Dependencies.") if process.error() == QProcess.FailedToStart else None)
        process.start(str(self.python), ["-u", str(self.root / "src/worker.py"), "--model", self.model.currentData(), "--device", str(self.settings.value("device", "auto"))])

    def engine_stopped(self, process):
        if self.worker is process and not self.closing:
            if self.web_url:
                self.restore_latest_after_restart = True
                self.restore_after_restart = self.pending_timing = None
            else:
                self.restore_after_restart = self.recovery_path if self.has_session else None
                self.pending_timing = self.timing_options() if self.restore_after_restart else None
            self.has_session = False
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

    def read_events(self, process=None):
        if self.worker is None or (process is not None and process is not self.worker):
            return
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
            if sys.platform == "win32" and not any(d["id"].startswith(("cuda:", "privateuseone:")) for d in event.get("devices", [])):
                self.hardware.setText(self.hardware.text() + "\nNo supported GPU is available to the engine. For AMD graphics, update the driver and choose the cog → Repair Dependencies to install DirectML support.")
        elif kind == "capabilities":
            self.busy = False
            self.export_readiness.show()
            self.export_readiness.setText("MIDI: ready. Sheet music in Web GUI: " + ("ready." if event.get("sheets") else "install MuseScore 4+.") + " A/B audio: " + ("choose a local SF2 SoundFont." if event.get("fluidsynth") else "install FluidSynth and choose a local SF2 SoundFont."))
        elif kind == "session_saved":
            self.saved_timing = json.dumps(self.timing_options(), sort_keys=True)
            self.busy = False; self.status.setText("Session saved.")
        elif kind == "session_loaded":
            self.has_session = True
            self.source = self.destination = self.ab_result = None
            self.restore_timing(event.get("timing", {}))
        elif kind == "ready":
            self.recovery_path = event.get("recovery_path")
            self.instrument_groups = event.get("instruments", self.instrument_groups)
            self.update_instruments()
            self.setup = not event["cached"]
            self.authenticated = event.get("authenticated", self.authenticated)
            self.cache_status.setText("Downloaded" if event["cached"] else "Download required")
            self.model_path.setText(event.get("directory", ""))
            self.busy = False
            self.status.setText("Choose audio and review its destination before transcribing.")
            if self.restore_latest_after_restart:
                self.restore_latest_after_restart = False
                self.restore_after_restart = self.recovery_path
            if self.restore_after_restart:
                path, self.restore_after_restart = self.restore_after_restart, None
                self.open_session(path)
            elif self.source and not self.destination:
                self.plan()
        elif kind == "authenticated":
            self.authenticated = True
        elif kind == "status":
            self.finish_ready = False
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
                self.finish_ready = bool(event.get("can_finish", False)) and not self.finishing
                self.completed_seconds = event.get("completed_seconds", 0)
                self.status.setText("Finishing completed sections and saving MIDI…" if self.finishing else "Transcribing…")
        elif kind == "planned":
            self.destination = Path(event["path"])
            self.busy = False
            self.status.setText("Ready when you are.")
        elif kind == "rhythm_preview":
            self.busy = False
            self.timing_summary.setText(event.get("message", ""))
            QDesktopServices.openUrl(QUrl.fromLocalFile(event["path"]))
        elif kind == "complete":
            self.finish_ready = self.finishing = False; self.transcription_id = None
            self.has_session = event.get("session", False)
            if self.has_session: self.recovery_path = event.get("recovery_path")
            self.timing_summary.setText(event.get("timing_summary", ""))
            self.ab_result = Path(event["ab_path"]) if event.get("ab_path") else None
            self.result = self.destination = Path(event["path"])
            self.busy = False
            self.status.setText(f"Partial MIDI saved: first {event.get('completed_seconds', 0):.1f} seconds." if event.get("partial") else "Transcription complete.")
            self.saved_timing = json.dumps(self.timing_options(), sort_keys=True)
            if self.pending_timing is not None:
                timing, self.pending_timing = self.pending_timing, None
                self.restore_timing(timing)
            if event.get("needs_save"):
                QTimer.singleShot(0, self.save_copy)
        elif kind == "warning":
            self.warning.setText("\n\n".join(filter(None, (self.warning.text(), event["message"]))))
        elif kind == "error":
            self.pending_timing = None
            self.finish_ready = self.finishing = False; self.transcription_id = None
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
        if not self.confirm_discard_timing(): return
        if self.busy:
            return
        if not path.is_file():
            self.fail("Choose an audio file stored on this computer.")
            return
        self.has_session = False
        self.timing_summary.clear()
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

    def timing_options(self):
        return dict(mode=self.tempo_mode.currentData(), bpm=self.tempo_bpm.text(), meter=self.tempo_meter.currentText().strip().lower(),
                    first_downbeat=self.tempo_downbeat.text(), unit=self.tempo_unit.currentData(),
                    quantize=self.quantize.isChecked(), subdivision=self.tempo_subdivision.currentData(),
                    factor=self.tempo_factor.currentData(), anchors=self.tempo_anchors.toPlainText(),
                    meter_changes=self.tempo_changes.toPlainText())

    def transcribe(self):
        if not self.busy and not self.setup and self.source and self.destination:
            self.transcription_id = uuid.uuid4().hex
            self.finish_ready = self.finishing = False; self.completed_seconds = 0
            command = {"action": "transcribe", "run_id": self.transcription_id, "path": str(self.source), "destination": str(self.destination),
                       "instruments": list(self.selected_instruments), "quantize": self.quantize.isChecked(),
                       "create_ab": self.create_ab.isChecked(), "timing": self.timing_options()}
            if self.soundfont:
                command["soundfont"] = str(self.soundfont)
            self.send(command, "Reading audio…")

    def confirm_discard_timing(self):
        if not self.has_session or self.saved_timing == json.dumps(self.timing_options(), sort_keys=True):
            return True
        from PySide6.QtWidgets import QMessageBox
        return QMessageBox.question(self, "Unsaved timing changes", "Discard unsaved timing changes? Save Session or Apply timing keeps them. The last applied session remains recoverable.", QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Cancel) == QMessageBox.Discard

    def finish_transcription(self):
        if not self.busy or not self.finish_ready or self.finishing or not self.transcription_id:
            return
        self.finishing = True; self.finish_ready = False
        warning = self.warning.text()
        self.send({"action": "finish_transcription", "run_id": self.transcription_id}, "Finishing completed sections and saving MIDI…")
        self.warning.setText(warning)
        self.refresh()

    def cancel_operation(self):
        self.finish_ready = self.finishing = False; self.transcription_id = None
        if not self.busy or not self.worker or self.installer:
            return
        self.restore_after_restart = self.recovery_path if self.has_session else None
        self.pending_timing = self.timing_options() if self.has_session else None
        process, self.worker = self.worker, None
        if sys.platform == "win32":
            QProcess.execute("taskkill.exe", ["/PID", str(process.processId()), "/T", "/F"])
        process.kill()
        if not process.waitForFinished(3000):
            self.worker = process
            self.status.setText("The operation is still stopping. Try Cancel again.")
            self.busy = True
            self.refresh()
            return
        self.has_session = False
        self.warning.setText("Operation cancelled. Your file and settings were kept.")
        self.start()

    def open_session(self, path=None):
        if self.busy or self.web_url:
            return
        if self.pending_timing is None and not self.confirm_discard_timing():
            return
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "Open MuScriptor Session", "", "MuScriptor session (*.muscriptor)")
        if path:
            self.send({"action": "load_session", "path": str(path)}, "Opening session…")

    def save_session(self):
        if self.busy or not self.has_session:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save Session", "Transcription.muscriptor", "MuScriptor session (*.muscriptor)")
        if path:
            self.send({"action": "save_session", "path": path, "timing": self.timing_options()}, "Saving session…")

    def apply_session(self):
        if self.busy or not self.has_session:
            return
        command = {"action": "reexport_session", "timing": self.timing_options()}
        if self.destination: command["destination"] = str(self.destination)
        self.send(command, "Updating MIDI…")

    def restore_timing(self, t):
        for widget, key, fallback in ((self.tempo_mode,"mode","auto"), (self.tempo_unit,"unit","auto"),
                                      (self.tempo_subdivision,"subdivision","auto"), (self.tempo_factor,"factor",1)):
            value = t.get(key, fallback)
            if key == "factor": value = float(value)
            if key == "subdivision": value = str(value)
            widget.setCurrentIndex(max(0, widget.findData(value)))
        self.tempo_meter.setCurrentText(str(t.get("meter", "auto")).replace("auto", "Auto"))
        self.tempo_bpm.setText(str(t.get("bpm", 120))); self.tempo_downbeat.setText(str(t.get("first_downbeat", 0)))
        self.quantize.setChecked(t.get("quantize", False))
        anchors = t.get("anchors", "")
        if isinstance(anchors, list): anchors = "\n".join(f"{a[0]}, {a[1]}" for a in anchors)
        self.tempo_anchors.setPlainText(anchors); self.tempo_changes.setPlainText(t.get("meter_changes", ""))

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
        if not self.confirm_discard_timing(): return
        self.has_session = False
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
        if self.has_session:
            self.restore_after_restart = self.recovery_path
            self.pending_timing = self.timing_options() if self.recovery_path else None
            self.has_session = False
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
                message = "Engine setup did not finish. Try Again repairs the installation. Open the cog → Show Logs for details."
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
        if not self.confirm_discard_timing():
            event.ignore(); return
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
    configure_windows_identity()
    app = QApplication(sys.argv)
    window = MainWindow(autostart="--smoke-test" not in sys.argv)
    window.show()
    if "--smoke-test" in sys.argv:
        QTimer.singleShot(250, app.quit)
    sys.exit(app.exec())
