# TEST_SETUP.md -- Meeting Translator Testing Notes

## 1. How to Launch the App

### From source (development)

```bash
cd C:\Users\Omion\OneDrive\デスクトップ\Ominext\LuyenTap\Translator
pip install -r requirements.txt
python main.py
```

Entry point: `main.py` line 706 (`if __name__ == "__main__": main()`).
The `main()` function (line 698-703) creates a `QApplication`, sets the app name to "Meeting Translator", applies the "Fusion" Qt style, instantiates `MainWindow`, and enters `app.exec()`.

### From built executable

- **Windows**: `dist\MeetingTranslator.exe` (single-file onefile mode via PyInstaller)
- **macOS**: `dist/MeetingTranslator.app` (onedir mode, `.app` bundle)

The PyInstaller spec is `translator_meeting.spec`. Build command:

```bash
pyinstaller translator_meeting.spec
```

### Pre-launch requirement

A **Soniox API key** must be configured. Without it, clicking "Start Meeting" shows a warning dialog and opens Settings (main.py line 420-426). Get a free key at https://soniox.com.

---

## 2. Audio Capture (audio_capture.py)

### Supported audio sources

| Source value    | UI label             | What it captures                              |
|-----------------|----------------------|-----------------------------------------------|
| `"microphone"`  | Mic                  | Default system microphone                     |
| `"system"`      | System               | System audio via WASAPI loopback (Windows)    |
| `"both"`        | Mic + System (Both)  | Both mic and system audio as separate streams |

Audio source is selectable in two places:
1. **Main toolbar**: dropdown at the top right of the window (main.py line 286-291)
2. **Settings dialog**: Audio Source section (main.py line 88-100)

### Audio format

| Parameter    | Value         | Location                      |
|-------------|---------------|-------------------------------|
| Sample rate | 16000 Hz      | `audio_capture.py` line 6     |
| Channels    | 1 (mono)      | `audio_capture.py` line 7     |
| Block size  | 4000 samples (~250ms) | `audio_capture.py` line 8 |
| Input dtype | `float32`     | `audio_capture.py` line 69    |
| Output format | PCM 16-bit signed LE (int16) | `_to_pcm16()` line 11-14 |

The `_to_pcm16()` function (line 11-14) converts float32 audio to PCM 16-bit:
1. Averages channels to mono if multi-channel (`data.mean(axis=1)`)
2. Clips to [-1.0, 1.0]
3. Scales by 32767 and casts to `np.int16`
4. Returns raw bytes via `.tobytes()`

### System audio capture on Windows (WASAPI loopback)

The `_find_loopback_device()` method (line 33-54) searches for a loopback device in two passes:

**First pass** (line 40-45): Scans all devices for names containing any of these keywords (case-insensitive):
- `"loopback"`
- `"stereo mix"`
- `"what u hear"`
- `"wave out mix"`
- `"rec. playback"`

**Second pass / fallback** (line 47-53): Finds the default output device and checks if it has input channels (WASAPI loopback capability).

If no loopback device is found, a warning is printed: `"No WASAPI loopback device found. Try enabling 'Stereo Mix' in Windows sound settings."` (line 99).

### "Both" mode behavior

When `source="both"`, both mic and system streams are started independently (line 60-64). Each has its own callback (`_mic_callback` and `_sys_callback`) but both call the same `on_audio` handler. The audio chunks are interleaved. A warning is printed (line 61-64):
> `"WARNING: 'Both' mode sends mic and system audio as separate interleaved streams. For best accuracy, use a single source."`

### Stream lifecycle

- `start()` (line 56): Sets `_running = True`, creates and starts `sd.InputStream` objects.
- `stop()` (line 101): Sets `_running = False`, stops and closes all streams, clears the list.
- For system audio, the loopback device's actual channel count is queried and capped at 2 (line 85).

---

## 3. Transcript Output Format

### Display technology

Both panels use **QTextEdit** widgets (read-only) with **rich text** via `QTextCursor` and `QTextCharFormat`. No HTML is inserted directly; all formatting is done through Qt text cursor operations.

- **Original Transcript** panel: `self.orig_edit` (QTextEdit, left side of QSplitter)
- **Translation** panel: `self.trans_edit` (QTextEdit, right side of QSplitter)
- The splitter starts at 480/480 pixel ratio (main.py line 358).

### Segment display format

Each speaker's text block starts with a **header line** in the format:

```
[Speaker N -- HH:MM:SS]
```

where N is 1-4, and the timestamp is the local time when the segment is received. The header is rendered in the speaker's color with bold weight (font weight 700).

Header is only inserted when the speaker changes from the previous segment. Speaker tracking is per-panel:
- `_last_speaker_orig` for the Original panel
- `_last_speaker_trans` for the Translation panel

After the header, the actual text is appended with a trailing space. Multiple segments from the same speaker are concatenated on the same line(s).

### Speaker labels and colors

Defined in `main.py` line 214 and `config.py` lines 18-24:

| Speaker | Label        | Color (hex) | Description      |
|---------|-------------|-------------|------------------|
| 1       | Speaker 1   | `#4FC3F7`   | Light blue       |
| 2       | Speaker 2   | `#A5D6A7`   | Light green      |
| 3       | Speaker 3   | `#FFB74D`   | Orange           |
| 4       | Speaker 4   | `#CE93D8`   | Purple           |
| 5       | (fallback)  | `#F48FB1`   | Pink (in config) |

Speakers are clamped to range 1-4 in `_handle_segment()` (main.py line 484): `speaker = max(1, min(seg.speaker, 4))`.

A **speaker legend** is displayed above the transcript panels (main.py lines 330-338), showing colored dots for each of the 4 speakers.

### Provisional vs final text

**Provisional text** (in-progress, not yet confirmed by Soniox):
- Color: `#666` (dark gray) -- see main.py line 557
- Position tracked via `self._provisional_start` (character position in the document)
- When new provisional text arrives, the old provisional text is deleted from `_provisional_start` to document end, then new provisional text is inserted (main.py lines 537-540)
- Provisional text only appears in the **Original Transcript** panel (not in Translation)

**Final text** (confirmed by Soniox):
- Color: `#e0e0e0` (light gray, nearly white) -- see main.py line 591
- When a final segment arrives, any existing provisional text is replaced: the range from `_provisional_start` to end is deleted, then the final text is inserted (main.py lines 571-575)
- `_provisional_start` is reset to `None` after final text is placed

### Scroll behavior

Auto-scroll is on by default. When "Scroll Lock" is toggled on:
- Button text changes to "Scroll Lock ON" (main.py line 404)
- `_scroll_locked = True` prevents `ensureCursorVisible()` calls
- User can freely scroll back through transcript history

### Font

Default font: "Segoe UI", size from config (default 14). Adjustable 9-36 via A-/A+ buttons (main.py lines 369-376, 398-399).

---

## 4. Config File (config.py)

### Location

```
~/.translator_meeting/config.json
```

Full path on Windows: `C:\Users\<username>\.translator_meeting\config.json`

The directory `~/.translator_meeting/` is auto-created on first load or save (config.py lines 41, 53).

### Config path constant

`config.py` line 4:
```python
CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".translator_meeting", "config.json")
```

### Fields and defaults

Defined in `config.py` lines 6-16 (`DEFAULTS` dict):

| Field              | Default        | Description                                      |
|--------------------|----------------|--------------------------------------------------|
| `soniox_api_key`   | `""`           | Soniox API key (required for STT)                |
| `source_language`  | `"ja"`         | Source language (ISO 639-1 or "auto")             |
| `target_language`  | `"vi"`         | Target language (ISO 639-1, not "auto")           |
| `audio_source`     | `"microphone"` | Audio capture mode: microphone / system / both    |
| `font_size`        | `14`           | Display font size (range 9-36)                    |
| `always_on_top`    | `False`        | Keep window always on top (overlay mode)          |
| `show_original`    | `True`         | Show original transcript panel                    |
| `auto_translate`   | `True`         | Auto-translate segments                           |
| `context_terms`    | `""`           | Comma-separated domain terms for Soniox context   |

### Load behavior

`config.load()` (line 40-49):
1. Creates directory if missing
2. If `config.json` exists, reads and merges with DEFAULTS (file values override defaults)
3. If file missing or parse error, returns a copy of DEFAULTS

### Save behavior

`config.save(cfg)` (line 52-55):
1. Creates directory if missing
2. Writes JSON with indent=2 and `ensure_ascii=False` (supports Unicode)

### When config is saved

- On Settings dialog save (main.py line 410)
- On app close via `closeEvent` (main.py line 692)

### Supported languages

Defined in `config.py` lines 26-37 (`LANGUAGES` dict):

| Code   | Name        |
|--------|-------------|
| `ja`   | Japanese    |
| `vi`   | Vietnamese  |
| `en`   | English     |
| `zh`   | Chinese     |
| `ko`   | Korean      |
| `fr`   | French      |
| `de`   | German      |
| `es`   | Spanish     |
| `th`   | Thai        |
| `auto` | Auto-detect |

Note: `"auto"` is available for source language only. The target language combo excludes "auto" (main.py lines 79, 269).

---

## 5. Session Save Format

### Save directory

```
~/.translator_meeting/sessions/
```

Created on demand via `os.makedirs(..., exist_ok=True)` (main.py line 659).

### Filename format

```
session_YYYYMMDD_HHMMSS.md
```

Example: `session_20260525_143022.md`

Generated at main.py line 660-661.

### File content format (Markdown)

The session file is written at main.py lines 664-671. Structure:

```markdown
# Meeting Transcript -- YYYY-MM-DD HH:MM
**Source:** <source language name>  |  **Target:** <target language name>

## Original Transcript

<plain text from orig_edit.toPlainText()>

## Translation

<plain text from trans_edit.toPlainText()>
```

Note: The saved file contains **plain text** extracted from the QTextEdit widgets. Speaker headers (e.g., `[Speaker 1 -- 14:30:00]`) are included as they are part of the plain text content. Colors and formatting are not preserved in the saved file.

### Save triggers

1. **Manual save**: "Save" button (main.py line 680-688). After saving, opens the file's location in Explorer (Windows), Finder (macOS), or file manager (Linux).
2. **Auto-save on stop**: When stopping a session that has log entries, `_auto_save_session()` is called (main.py line 468-469). This writes to the same directory silently (no Explorer open).
3. **Copy**: The "Copy" button (main.py line 648-655) copies both panels to clipboard in the format:
   ```
   <original text>

   --- TRANSLATION ---

   <translation text>
   ```

---

## 6. Soniox Client Features (soniox_client.py)

### Connection details

- WebSocket URL: `wss://stt-rt.soniox.com/transcribe-websocket` (line 8)
- Model: `stt-rt-v4` (line 79, previously documented as "soniox-2" in CLAUDE.md)
- Audio format sent to Soniox: `pcm_s16le`, 16000 Hz, 1 channel (line 78-81)

### Config sent to Soniox on connect

Built by `_build_config()` (lines 75-108):

```json
{
  "api_key": "<key>",
  "model": "stt-rt-v4",
  "audio_format": "pcm_s16le",
  "sample_rate": 16000,
  "num_channels": 1,
  "enable_endpoint_detection": true,
  "enable_speaker_diarization": true,
  "enable_language_identification": true,
  "language_hints": ["<source_lang>"],
  "translation": {
    "type": "two_way",
    "language_a": "<source_lang>",
    "language_b": "<target_lang>"
  },
  "context": {
    "terms": ["term1", "term2"],
    "text": "<carryover text from previous session>"
  }
}
```

- `language_hints` is only set if source language is not "auto" (line 86-87)
- `translation` is only set if both source and target are defined and differ (lines 89-96)
- `context.terms` comes from the comma-separated `context_terms` config (lines 99-101)
- `context.text` is the carryover text from session resets (lines 103-104)

### Auto-reconnect behavior

Constants (lines 10-12):
- `MAX_RECONNECT_ATTEMPTS = 3`
- `RECONNECT_DELAYS = [2, 4, 6]` (seconds, progressive backoff)

Reconnect flow (`_do_reconnect()`, lines 168-188):
1. If `_reconnect_count >= 3`, stop completely and fire error callback: `"Connection lost after 3 reconnect attempts"` (lines 169-175)
2. Otherwise, pick delay from `RECONNECT_DELAYS` based on attempt index (line 178)
3. Increment `_reconnect_count`, fire `on_reconnecting(attempt, max)` callback (lines 180-184)
4. Sleep for the delay, then call `_do_connect()` (lines 186-188)
5. Reconnect count resets to 0 on successful session reset (line 151)

### Session reset every 3 minutes

Constants (lines 10, 14):
- `SESSION_RESET_INTERVAL = 180` (seconds = 3 minutes)
- `CARRYOVER_CHARS = 500`

Flow (`_session_reset()`, lines 201-213):
1. A `threading.Timer` is started on each successful connect (line 122, calling `_start_session_timer()` at line 190-194)
2. After 180 seconds, `_session_reset()` fires
3. It takes the last 500 characters from `_recent_texts` as carryover (line 205)
4. Clears `_recent_texts` (line 206)
5. Sets `_session_resetting = True` and closes the WebSocket (lines 207-210)
6. The `on_close` handler detects `_session_resetting` flag (line 149) and triggers reconnect with 0.5s delay (line 152)
7. The new connection includes the carryover text in `context.text` via `_build_config()` (line 104)

This is transparent to the user -- the reconnect happens quickly and the context carryover helps Soniox maintain continuity.

### Context terms support

- Configured in Settings dialog under "Context (Domain Terms)" (main.py lines 103-112)
- Stored as `context_terms` in config (comma-separated string)
- Parsed into a list and sent as `context.terms` in the Soniox config (soniox_client.py lines 99-101)
- Example: `"Kubernetes, API gateway, sprint review"` becomes `["Kubernetes", "API gateway", "sprint review"]`

### Auto-save on stop

When `_stop()` is called in main.py (line 457-471):
1. Audio capture is stopped
2. Soniox client is disconnected
3. If `_session_log` has entries, `_auto_save_session()` is called (line 468-469)
4. The session is written to `~/.translator_meeting/sessions/session_<timestamp>.md`

### Keepalive mechanism

A keepalive loop runs in a daemon thread (lines 230-237):
- Every 15 seconds, sends `{"type": "keepalive"}` JSON message to the WebSocket
- Runs as long as `_running` and `_connected` are both True

### Audio sending

Audio chunks are queued via `send_audio()` (line 239-242) and sent by a sender loop thread (`_sender_loop()`, lines 214-228):
- Sender loop runs every 50ms (`time.sleep(0.05)`)
- Drains the queue under lock, sends each chunk as binary WebSocket frame (`OPCODE_BINARY`)

### Bidirectional translation

Soniox provides built-in two-way translation when configured with `translation.type = "two_way"`. Tokens come back with `translation_status` field:
- `"original"` -- original language text (grouped into `speaker_original`)
- `"translation"` -- translated text (grouped into `speaker_translation`)

The response handler (`_handle_response()`, lines 244-288) groups tokens by speaker and status, then creates `SonioxSegment` objects with both `text` (original) and `translated` (Soniox translation).

In `main.py` `_handle_segment()` (lines 483-527):
- If Soniox provides a translation (`seg.translated` is non-empty), it is used directly (line 494-501)
- If Soniox does not provide a translation, a fallback to Google Translate is used in a background thread (lines 502-527)
- The Google Translate fallback implements bidirectional logic:
  - If detected language == target language: translate back to source language
  - If detected language == source language: translate to target language
  - Otherwise: translate from detected language to target language

### SonioxSegment data class

Defined at lines 16-26 with `__slots__`:

| Field        | Type   | Description                                    |
|-------------|--------|------------------------------------------------|
| `text`       | str    | Original transcribed text                      |
| `translated` | str    | Soniox-provided translation (may be empty)     |
| `speaker`    | int    | 1-indexed speaker ID (converted from 0-based)  |
| `is_final`   | bool   | True if segment is finalized                   |
| `language`   | str    | Detected language code (e.g., "ja", "en")      |

---

## 7. Threading Model Summary

| Thread                | Location                        | Purpose                                           |
|-----------------------|---------------------------------|---------------------------------------------------|
| Main (Qt event loop)  | `main.py` line 703              | UI rendering, signal/slot handling                |
| WebSocket thread      | `soniox_client.py` line 163-166 | `run_forever()` for Soniox connection             |
| Audio sender thread   | `soniox_client.py` line 118-119 | Drains audio queue every 50ms                     |
| Keepalive thread      | `soniox_client.py` line 120-121 | Sends keepalive every 15s                         |
| Audio mic callback    | sounddevice internal            | Fires `_mic_callback` per audio block             |
| Audio system callback | sounddevice internal            | Fires `_sys_callback` per audio block             |
| Translation threads   | `main.py` line 527              | One daemon thread per final segment (Google TL)   |
| Session timer         | `soniox_client.py` line 192     | `threading.Timer` for 3-min session reset         |
| Reconnect thread      | `soniox_client.py` line 152,154 | Handles reconnect with delay                      |

Cross-thread communication uses `pyqtSignal` via the `_Bridge` class (main.py lines 26-32). Worker threads emit signals; Qt main thread handles them in slots.

---

## 8. Dependencies

From `requirements.txt`:

| Package            | Min version | Purpose                              |
|--------------------|------------|--------------------------------------|
| PyQt6              | 6.6.0      | GUI framework                        |
| sounddevice        | 0.4.6      | Audio capture (mic + WASAPI)         |
| numpy              | 1.26.0     | Audio data conversion (float->int16) |
| websocket-client   | 1.7.0      | WebSocket connection to Soniox       |
| pyinstaller        | 6.0.0      | Build tool (not runtime dependency)  |

No Google Translate library is needed -- translation uses direct HTTP requests to `translate.googleapis.com` (translator.py lines 25-35).

---

## 9. Quick Test Checklist

1. [ ] Install dependencies: `pip install -r requirements.txt`
2. [ ] Run `python main.py` -- window should appear with dark theme
3. [ ] Open Settings, enter Soniox API key
4. [ ] Select source/target languages and audio source
5. [ ] Click "Start Meeting" -- status should change to "Connecting..." then "Live -- listening"
6. [ ] Speak into microphone -- provisional text should appear in gray (#666)
7. [ ] Wait for final text -- should turn light gray (#e0e0e0) with translation in right panel
8. [ ] Verify speaker labels appear as `[Speaker N -- HH:MM:SS]` in speaker colors
9. [ ] Test Scroll Lock toggle
10. [ ] Test A-/A+ font size buttons
11. [ ] Click "Stop" -- session should auto-save to `~/.translator_meeting/sessions/`
12. [ ] Click "Save" manually -- should open Explorer at saved file location
13. [ ] Click "Copy" -- clipboard should contain both transcript and translation
14. [ ] Test "Clear" button -- both panels should empty
15. [ ] Verify reconnect: disconnect network briefly, check status shows "Reconnecting... (1/3)"
16. [ ] Verify 3-minute session reset: let a session run > 3 minutes, watch console for `"Session reset (3 min)"` message
