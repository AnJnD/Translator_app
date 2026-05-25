"""Meeting Translator — main application window."""
import sys
import os
import threading
from datetime import datetime

from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QTextEdit, QDialog, QLineEdit,
    QFormLayout, QCheckBox, QGroupBox, QSplitter, QToolButton,
    QSpinBox, QMessageBox,
)
import subprocess
import platform

import config
from audio_capture import AudioCapture
from soniox_client import SonioxClient, SonioxSegment
from translator import translate


# ── Signals (cross-thread → Qt main thread) ──────────────────────────────────

class _Bridge(QObject):
    segment_ready  = pyqtSignal(int, str, str, str)  # speaker, color, original, translated
    provisional    = pyqtSignal(int, str, str)        # speaker, color, text
    status         = pyqtSignal(str, str)             # message, level
    connected      = pyqtSignal()
    disconnected   = pyqtSignal()
    reconnecting   = pyqtSignal(int, int)             # attempt, max_attempts


# ── Settings Dialog ──────────────────────────────────────────────────────────

class SettingsDialog(QDialog):
    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self.cfg = dict(cfg)
        self.setWindowTitle("Settings — Meeting Translator")
        self.setMinimumWidth(460)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # API key
        api_group = QGroupBox("Soniox API Key")
        api_form = QFormLayout(api_group)
        self.key_edit = QLineEdit(self.cfg.get("soniox_api_key", ""))
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_edit.setPlaceholderText("sk-…  Paste your Soniox API key")
        show_btn = QToolButton()
        show_btn.setText("👁")
        show_btn.setCheckable(True)
        show_btn.toggled.connect(
            lambda on: self.key_edit.setEchoMode(
                QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password
            )
        )
        row = QHBoxLayout()
        row.addWidget(self.key_edit)
        row.addWidget(show_btn)
        api_form.addRow("API Key:", row)
        link = QLabel('<a href="https://soniox.com">Get a free Soniox key →</a>')
        link.setOpenExternalLinks(True)
        api_form.addRow("", link)
        layout.addWidget(api_group)

        # Languages
        lang_group = QGroupBox("Languages")
        lang_form = QFormLayout(lang_group)
        self.src_combo = QComboBox()
        self.tgt_combo = QComboBox()
        for code, name in config.LANGUAGES.items():
            self.src_combo.addItem(f"{name} ({code})", code)
            if code != "auto":
                self.tgt_combo.addItem(f"{name} ({code})", code)
        _set_combo(self.src_combo, self.cfg.get("source_language", "ja"))
        _set_combo(self.tgt_combo, self.cfg.get("target_language", "vi"))
        lang_form.addRow("Transcribe from:", self.src_combo)
        lang_form.addRow("Translate to:", self.tgt_combo)
        layout.addWidget(lang_group)

        # Audio
        audio_group = QGroupBox("Audio Source")
        audio_form = QFormLayout(audio_group)
        self.audio_combo = QComboBox()
        self.audio_combo.addItem("🎤 Microphone only", "microphone")
        self.audio_combo.addItem("🔊 System audio (meeting output)", "system")
        self.audio_combo.addItem("🎤+🔊 Both", "both")
        _set_combo(self.audio_combo, self.cfg.get("audio_source", "microphone"))
        audio_form.addRow("Capture:", self.audio_combo)
        note = QLabel("System audio needs 'Stereo Mix' or WASAPI loopback enabled in Windows Sound Settings.")
        note.setWordWrap(True)
        note.setStyleSheet("color:#888;font-size:11px;")
        audio_form.addRow("", note)
        layout.addWidget(audio_group)

        # Context
        ctx_group = QGroupBox("Context (Domain Terms)")
        ctx_form = QFormLayout(ctx_group)
        self.terms_edit = QLineEdit(self.cfg.get("context_terms", ""))
        self.terms_edit.setPlaceholderText("e.g., Kubernetes, API gateway, sprint review")
        ctx_form.addRow("Terms:", self.terms_edit)
        ctx_note = QLabel("Comma-separated domain terms sent to Soniox to improve STT accuracy.")
        ctx_note.setWordWrap(True)
        ctx_note.setStyleSheet("color:#888;font-size:11px;")
        ctx_form.addRow("", ctx_note)
        layout.addWidget(ctx_group)

        # Display
        disp_group = QGroupBox("Display")
        disp_form = QFormLayout(disp_group)
        self.ontop_cb = QCheckBox("Always on top")
        self.ontop_cb.setChecked(self.cfg.get("always_on_top", False))
        disp_form.addRow(self.ontop_cb)
        spin_row = QHBoxLayout()
        self.font_spin = QSpinBox()
        self.font_spin.setRange(9, 36)
        self.font_spin.setValue(self.cfg.get("font_size", 14))
        spin_row.addWidget(self.font_spin)
        spin_row.addStretch()
        disp_form.addRow("Font size:", spin_row)
        layout.addWidget(disp_group)

        # Buttons
        btns = QHBoxLayout()
        save = QPushButton("Save")
        save.setDefault(True)
        save.clicked.connect(self._save)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(cancel)
        btns.addWidget(save)
        layout.addLayout(btns)

    def _save(self):
        self.cfg["soniox_api_key"]  = self.key_edit.text().strip()
        self.cfg["source_language"] = self.src_combo.currentData()
        self.cfg["target_language"] = self.tgt_combo.currentData()
        self.cfg["audio_source"]    = self.audio_combo.currentData()
        self.cfg["always_on_top"]   = self.ontop_cb.isChecked()
        self.cfg["font_size"]       = self.font_spin.value()
        self.cfg["context_terms"]   = self.terms_edit.text().strip()
        self.accept()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _set_combo(combo: QComboBox, value: str):
    for i in range(combo.count()):
        if combo.itemData(i) == value:
            combo.setCurrentIndex(i)
            return


STYLESHEET = """
QMainWindow, QWidget { background:#1a1a2e; color:#e0e0e0; }
QGroupBox {
    border:1px solid #3a3a5a; border-radius:6px; margin-top:8px;
    color:#aaa; font-size:11px;
}
QGroupBox::title { subcontrol-origin:margin; left:8px; padding:0 4px; }
QPushButton {
    background:#2a2a4a; border:1px solid #4a4a7a; border-radius:5px;
    color:#e0e0e0; padding:5px 14px;
}
QPushButton:hover { background:#3a3a6a; }
QPushButton:pressed { background:#1a1a3a; }
QPushButton#start_btn {
    background:#1b5e20; border-color:#2e7d32;
    font-weight:bold; font-size:13px; padding:7px 22px;
}
QPushButton#start_btn:hover { background:#2e7d32; }
QPushButton#stop_btn {
    background:#7f0000; border-color:#c62828;
    font-weight:bold; font-size:13px; padding:7px 22px;
}
QPushButton#stop_btn:hover { background:#b71c1c; }
QComboBox {
    background:#2a2a4a; border:1px solid #4a4a7a; border-radius:4px;
    color:#e0e0e0; padding:3px 8px; min-width:100px;
}
QComboBox::drop-down { border:none; width:16px; }
QComboBox QAbstractItemView {
    background:#2a2a4a; color:#e0e0e0;
    selection-background-color:#4a4a8a;
}
QTextEdit {
    background:#0f0f20; border:1px solid #2a2a5a;
    border-radius:6px; color:#e0e0e0;
}
QScrollBar:vertical { background:#1a1a2e; width:8px; }
QScrollBar::handle:vertical {
    background:#3a3a6a; border-radius:4px; min-height:20px;
}
QLineEdit {
    background:#2a2a4a; border:1px solid #4a4a7a;
    border-radius:4px; color:#e0e0e0; padding:4px 8px;
}
QDialog { background:#1a1a2e; }
QLabel { color:#e0e0e0; }
QCheckBox { color:#e0e0e0; }
QSpinBox {
    background:#2a2a4a; border:1px solid #4a4a7a;
    border-radius:4px; color:#e0e0e0; padding:2px 6px;
}
"""

SPEAKER_LABEL = {1: "Speaker 1", 2: "Speaker 2", 3: "Speaker 3", 4: "Speaker 4"}


# ── Main Window ───────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg = config.load()
        self._bridge = _Bridge()
        self._bridge.segment_ready.connect(self._on_segment_ready)
        self._bridge.provisional.connect(self._on_provisional)
        self._bridge.status.connect(self._set_status)
        self._bridge.connected.connect(self._on_connected)
        self._bridge.disconnected.connect(self._on_disconnected)
        self._bridge.reconnecting.connect(self._on_reconnecting)

        self._audio: AudioCapture | None = None
        self._soniox: SonioxClient | None = None
        self._running = False
        self._session_log: list[dict] = []
        self._last_speaker_orig = -1
        self._last_speaker_trans = -1
        self._provisional_start: int | None = None  # char position where provisional text begins
        self._scroll_locked = False

        self._build_ui()
        self._apply_cfg()

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.setWindowTitle("Meeting Translator")
        self.setMinimumSize(720, 520)
        self.resize(960, 680)
        self.setStyleSheet(STYLESHEET)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 8, 10, 6)
        root.setSpacing(6)

        # Title row
        top = QHBoxLayout()
        title = QLabel("🎙 Meeting Translator")
        title.setStyleSheet("color:#7986cb; font-size:17px; font-weight:bold;")
        top.addWidget(title)
        top.addStretch()

        # Language selectors
        self.src_combo = QComboBox()
        self.tgt_combo = QComboBox()
        for code, name in config.LANGUAGES.items():
            self.src_combo.addItem(name, code)
            if code != "auto":
                self.tgt_combo.addItem(name, code)
        _set_combo(self.src_combo, self.cfg["source_language"])
        _set_combo(self.tgt_combo, self.cfg["target_language"])
        self.src_combo.currentIndexChanged.connect(self._save_lang)
        self.tgt_combo.currentIndexChanged.connect(self._save_lang)

        arr = QLabel("→")
        arr.setStyleSheet("color:#7986cb; font-size:16px; padding:0 4px;")
        top.addWidget(QLabel("From:"))
        top.addWidget(self.src_combo)
        top.addWidget(arr)
        top.addWidget(QLabel("To:"))
        top.addWidget(self.tgt_combo)
        top.addSpacing(8)

        # Audio source
        self.audio_combo = QComboBox()
        self.audio_combo.addItem("🎤 Mic", "microphone")
        self.audio_combo.addItem("🔊 System", "system")
        self.audio_combo.addItem("🎤+🔊 Both", "both")
        _set_combo(self.audio_combo, self.cfg["audio_source"])
        top.addWidget(self.audio_combo)
        top.addSpacing(8)

        settings_btn = QPushButton("⚙ Settings")
        settings_btn.clicked.connect(self._open_settings)
        top.addWidget(settings_btn)
        root.addLayout(top)

        # Control row
        ctrl = QHBoxLayout()
        self.start_btn = QPushButton("▶  Start Meeting")
        self.start_btn.setObjectName("start_btn")
        self.start_btn.clicked.connect(self._start)
        self.stop_btn = QPushButton("■  Stop")
        self.stop_btn.setObjectName("stop_btn")
        self.stop_btn.clicked.connect(self._stop)
        self.stop_btn.setEnabled(False)
        ctrl.addWidget(self.start_btn)
        ctrl.addWidget(self.stop_btn)
        ctrl.addSpacing(12)
        self.dot = QLabel("●")
        self.dot.setStyleSheet("color:#444; font-size:20px;")
        self.status_lbl = QLabel("Ready")
        self.status_lbl.setStyleSheet("color:#888; font-size:12px;")
        ctrl.addWidget(self.dot)
        ctrl.addWidget(self.status_lbl)
        ctrl.addStretch()
        clear_btn = QPushButton("🗑 Clear")
        clear_btn.clicked.connect(self._clear)
        copy_btn = QPushButton("📋 Copy")
        copy_btn.clicked.connect(self._copy)
        save_btn = QPushButton("💾 Save")
        save_btn.clicked.connect(self._save_session)
        ctrl.addWidget(clear_btn)
        ctrl.addWidget(copy_btn)
        ctrl.addWidget(save_btn)
        root.addLayout(ctrl)

        # Speaker legend
        legend = QHBoxLayout()
        legend.addWidget(QLabel("Speakers: "))
        for num, clr in config.SPEAKER_COLORS.items():
            if num > 4:
                break
            lbl = QLabel(f"● {SPEAKER_LABEL.get(num, f'Speaker {num}')}")
            lbl.setStyleSheet(f"color:{clr}; font-size:12px; margin-right:8px;")
            legend.addWidget(lbl)
        legend.addStretch()
        root.addLayout(legend)

        # Transcript / translation panels
        splitter = QSplitter(Qt.Orientation.Horizontal)
        orig_box = QGroupBox("Original Transcript")
        ob_lay = QVBoxLayout(orig_box)
        ob_lay.setContentsMargins(4, 8, 4, 4)
        self.orig_edit = QTextEdit()
        self.orig_edit.setReadOnly(True)
        ob_lay.addWidget(self.orig_edit)
        splitter.addWidget(orig_box)

        trans_box = QGroupBox("Translation")
        tb_lay = QVBoxLayout(trans_box)
        tb_lay.setContentsMargins(4, 8, 4, 4)
        self.trans_edit = QTextEdit()
        self.trans_edit.setReadOnly(True)
        tb_lay.addWidget(self.trans_edit)
        splitter.addWidget(trans_box)
        splitter.setSizes([480, 480])
        root.addWidget(splitter, stretch=1)

        # Font controls + scroll lock
        frow = QHBoxLayout()
        self.scroll_lock_btn = QPushButton("Scroll Lock")
        self.scroll_lock_btn.setCheckable(True)
        self.scroll_lock_btn.setFixedWidth(90)
        self.scroll_lock_btn.toggled.connect(self._toggle_scroll_lock)
        frow.addWidget(self.scroll_lock_btn)
        frow.addStretch()
        fm = QPushButton("A-")
        fm.setFixedWidth(38)
        fm.clicked.connect(lambda: self._change_font(-1))
        fp = QPushButton("A+")
        fp.setFixedWidth(38)
        fp.clicked.connect(lambda: self._change_font(1))
        frow.addWidget(fm)
        frow.addWidget(fp)
        root.addLayout(frow)

        self._apply_font()

    # ── Settings & config ──────────────────────────────────────────────────────

    def _apply_cfg(self):
        flag = Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlag(flag, bool(self.cfg.get("always_on_top")))
        self.show()

    def _apply_font(self):
        size = self.cfg.get("font_size", 14)
        font = QFont("Segoe UI", size)
        self.orig_edit.setFont(font)
        self.trans_edit.setFont(font)

    def _save_lang(self):
        self.cfg["source_language"] = self.src_combo.currentData()
        self.cfg["target_language"] = self.tgt_combo.currentData()

    def _change_font(self, delta: int):
        self.cfg["font_size"] = max(9, min(36, self.cfg.get("font_size", 14) + delta))
        self._apply_font()

    def _toggle_scroll_lock(self, locked: bool):
        self._scroll_locked = locked
        self.scroll_lock_btn.setText("Scroll Lock ON" if locked else "Scroll Lock")

    def _open_settings(self):
        dlg = SettingsDialog(self.cfg, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.cfg = dlg.cfg
            config.save(self.cfg)
            _set_combo(self.src_combo, self.cfg["source_language"])
            _set_combo(self.tgt_combo, self.cfg["target_language"])
            _set_combo(self.audio_combo, self.cfg["audio_source"])
            self._apply_cfg()
            self._apply_font()

    # ── Session start/stop ────────────────────────────────────────────────────

    def _start(self):
        if not self.cfg.get("soniox_api_key"):
            QMessageBox.warning(
                self, "API Key Missing",
                "Please add your Soniox API key in Settings before starting.",
            )
            self._open_settings()
            return

        self._running = True
        self._last_speaker_orig = -1
        self._last_speaker_trans = -1
        self._provisional_start = None
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.audio_combo.setEnabled(False)
        self._set_status("Connecting…", "warn")

        src = self.src_combo.currentData()
        audio_src = self.audio_combo.currentData()

        tgt = self.tgt_combo.currentData()
        self._soniox = SonioxClient(
            api_key=self.cfg["soniox_api_key"],
            source_language=src,
            target_language=tgt,
            on_segment=self._handle_segment,
            on_error=lambda e: self._bridge.status.emit(f"Error: {e}", "error"),
            on_connected=lambda: self._bridge.connected.emit(),
            on_disconnected=lambda: self._bridge.disconnected.emit(),
            on_reconnecting=lambda a, m: self._bridge.reconnecting.emit(a, m),
            enable_diarization=True,
            context_terms=self.cfg.get("context_terms", ""),
        )
        self._soniox.connect()
        self._audio = AudioCapture(on_audio=self._soniox.send_audio, source=audio_src)
        self._audio.start()

    def _stop(self):
        self._running = False
        if self._audio:
            self._audio.stop()
            self._audio = None
        if self._soniox:
            self._soniox.disconnect()
            self._soniox = None
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.audio_combo.setEnabled(True)
        if self._session_log:
            self._auto_save_session()
        self._set_status("Stopped", "ok")
        self.dot.setStyleSheet("color:#444; font-size:20px;")

    def _clear(self):
        self.orig_edit.clear()
        self.trans_edit.clear()
        self._session_log.clear()
        self._last_speaker_orig = -1
        self._last_speaker_trans = -1
        self._provisional_start = None

    # ── Segment handling (from Soniox worker thread) ──────────────────────────

    def _handle_segment(self, seg: SonioxSegment):
        speaker = max(1, min(seg.speaker, 4))
        color = config.SPEAKER_COLORS.get(speaker, "#e0e0e0")

        if not seg.is_final:
            self._bridge.provisional.emit(speaker, color, seg.text)
            return

        original = seg.text
        soniox_translated = seg.translated

        if soniox_translated.strip():
            self._bridge.segment_ready.emit(speaker, color, original, soniox_translated)
            self._session_log.append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "speaker": speaker,
                "original": original,
                "translated": soniox_translated,
            })
        else:
            cfg_src = self.cfg.get("source_language", "auto")
            cfg_tgt = self.cfg.get("target_language", "vi")
            detected_lang = seg.language

            def _do():
                if detected_lang and detected_lang == cfg_tgt:
                    src = detected_lang
                    dest = cfg_src if cfg_src != "auto" else "ja"
                elif detected_lang and detected_lang == cfg_src:
                    src = detected_lang
                    dest = cfg_tgt
                else:
                    src = detected_lang if detected_lang else cfg_src
                    dest = cfg_tgt

                translated = translate(original, src=src, dest=dest)
                self._bridge.segment_ready.emit(speaker, color, original, translated)
                self._session_log.append({
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "speaker": speaker,
                    "original": original,
                    "translated": translated,
                })

            threading.Thread(target=_do, daemon=True).start()

    # ── Slots (main thread) ───────────────────────────────────────────────────

    def _on_provisional(self, speaker: int, color: str, text: str):
        widget = self.orig_edit
        cursor = widget.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        # Remove previous provisional text before inserting new provisional text
        if self._provisional_start is not None:
            cursor.setPosition(self._provisional_start)
            cursor.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
            cursor.removeSelectedText()

        # Insert speaker header if this is a new speaker
        if speaker != self._last_speaker_orig:
            if not widget.document().isEmpty():
                cursor.insertText("\n")
            hdr_fmt = QTextCharFormat()
            hdr_fmt.setForeground(QColor(color))
            hdr_fmt.setFontWeight(700)
            cursor.setCharFormat(hdr_fmt)
            label = SPEAKER_LABEL.get(speaker, f"Speaker {speaker}")
            time_str = datetime.now().strftime("%H:%M:%S")
            cursor.insertText(f"[{label} — {time_str}]\n")
            self._last_speaker_orig = speaker

        self._provisional_start = cursor.position()
        txt_fmt = QTextCharFormat()
        txt_fmt.setForeground(QColor("#666"))
        cursor.setCharFormat(txt_fmt)
        cursor.insertText(text)

        widget.setTextCursor(cursor)
        if not self._scroll_locked:
            widget.ensureCursorVisible()

    def _on_segment_ready(self, speaker: int, color: str, original: str, translated: str):
        widget = self.orig_edit
        cursor = widget.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        # Replace provisional text in original panel with the final segment
        if self._provisional_start is not None:
            cursor.setPosition(self._provisional_start)
            cursor.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
            cursor.removeSelectedText()
            self._provisional_start = None
        else:
            # No provisional text: insert header if speaker changed
            if speaker != self._last_speaker_orig:
                if not widget.document().isEmpty():
                    cursor.insertText("\n")
                hdr_fmt = QTextCharFormat()
                hdr_fmt.setForeground(QColor(color))
                hdr_fmt.setFontWeight(700)
                cursor.setCharFormat(hdr_fmt)
                label = SPEAKER_LABEL.get(speaker, f"Speaker {speaker}")
                time_str = datetime.now().strftime("%H:%M:%S")
                cursor.insertText(f"[{label} — {time_str}]\n")
                self._last_speaker_orig = speaker

        txt_fmt = QTextCharFormat()
        txt_fmt.setForeground(QColor("#e0e0e0"))
        cursor.setCharFormat(txt_fmt)
        cursor.insertText(original + " ")
        widget.setTextCursor(cursor)
        if not self._scroll_locked:
            widget.ensureCursorVisible()

        self._append(self.trans_edit, speaker, color, translated, last_attr="_last_speaker_trans")

    def _append(self, widget: QTextEdit, speaker: int, color: str,
                text: str, last_attr: str):
        last = getattr(self, last_attr)
        cursor = widget.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        if speaker != last:
            if not widget.document().isEmpty():
                cursor.insertText("\n")
            hdr_fmt = QTextCharFormat()
            hdr_fmt.setForeground(QColor(color))
            hdr_fmt.setFontWeight(700)
            cursor.setCharFormat(hdr_fmt)
            label = SPEAKER_LABEL.get(speaker, f"Speaker {speaker}")
            time_str = datetime.now().strftime("%H:%M:%S")
            cursor.insertText(f"[{label} — {time_str}]\n")
            setattr(self, last_attr, speaker)

        txt_fmt = QTextCharFormat()
        txt_fmt.setForeground(QColor("#e0e0e0"))
        cursor.setCharFormat(txt_fmt)
        cursor.insertText(text + " ")

        widget.setTextCursor(cursor)
        if not self._scroll_locked:
            widget.ensureCursorVisible()

    def _on_connected(self):
        self._set_status("Live — listening", "ok")

    def _on_reconnecting(self, attempt: int, max_attempts: int):
        self._set_status(f"Reconnecting… ({attempt}/{max_attempts})", "warn")

    def _on_disconnected(self):
        if self._running:
            self._set_status("Disconnected", "error")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.audio_combo.setEnabled(True)
        self._running = False

    def _set_status(self, msg: str, level: str = "ok"):
        self.status_lbl.setText(msg)
        clr = {"ok": "#4caf50", "warn": "#ff9800", "error": "#f44336"}.get(level, "#888")
        self.dot.setStyleSheet(f"color:{clr}; font-size:20px;")

    # ── Export ────────────────────────────────────────────────────────────────

    def _copy(self):
        text = (
            self.orig_edit.toPlainText()
            + "\n\n─── TRANSLATION ───\n\n"
            + self.trans_edit.toPlainText()
        )
        QApplication.clipboard().setText(text)
        self._set_status("Copied to clipboard", "ok")

    def _write_session_file(self) -> str:
        save_dir = os.path.join(os.path.expanduser("~"), ".translator_meeting", "sessions")
        os.makedirs(save_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(save_dir, f"session_{ts}.md")
        src_name = self.src_combo.currentText()
        tgt_name = self.tgt_combo.currentText()
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# Meeting Transcript — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
            f.write(f"**Source:** {src_name}  |  **Target:** {tgt_name}\n\n")
            f.write("## Original Transcript\n\n")
            f.write(self.orig_edit.toPlainText())
            f.write("\n\n## Translation\n\n")
            f.write(self.trans_edit.toPlainText())
        return path

    def _auto_save_session(self):
        try:
            path = self._write_session_file()
            print(f"[Session] Auto-saved → {path}")
        except Exception as e:
            print(f"[Session] Auto-save error: {e}")

    def _save_session(self):
        path = self._write_session_file()
        self._set_status(f"Saved → {path}", "ok")
        if platform.system() == "Windows":
            subprocess.Popen(f'explorer /select,"{path}"')
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", "-R", path])
        else:
            subprocess.Popen(["xdg-open", os.path.dirname(path)])

    def closeEvent(self, event):
        self._stop()
        config.save(self.cfg)
        super().closeEvent(event)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Meeting Translator")
    app.setStyle("Fusion")
    win = MainWindow()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
