# Meeting Translator

Real-time speech translation for online meetings. Supports Zoom, Microsoft Teams, and Google Meet.

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![PyQt6](https://img.shields.io/badge/PyQt6-6.6+-41CD52?logo=qt&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS-blue)
![License](https://img.shields.io/badge/License-MIT-green)

## What is this?

Meeting Translator captures audio from your online meetings, recognizes speech in real-time with speaker identification (up to 4 speakers), and translates bidirectionally between two languages — all in a single desktop app.

Speaker A speaks Japanese, Speaker B speaks Vietnamese? The app auto-detects who is speaking which language and translates each person's words into the other language. No manual switching needed.

## Features

- **Real-time speech-to-text** — Powered by Soniox STT (model soniox-2) via WebSocket
- **Bidirectional translation** — Auto-detects each speaker's language and translates both ways
- **Speaker diarization** — Identifies up to 4 speakers with color-coded labels
- **Meeting audio capture** — Captures system audio (WASAPI loopback) from Zoom/Teams/Meet, or microphone, or both
- **Side-by-side display** — Original transcript on the left, translation on the right
- **Overlay mode** — Always-on-top window so you can read translations while in a meeting
- **Adjustable font size** — A-/A+ controls (range 9–36pt)
- **Scroll lock** — Pause auto-scroll to review earlier parts of the conversation
- **Save transcripts** — Export session as `.md` file with full original + translated text
- **Standalone executable** — Single `.exe` (Windows) or `.app` (macOS), no Python installation needed

## Supported Languages

| Language | Code |
|----------|------|
| Japanese | `ja` |
| Vietnamese | `vi` |
| English | `en` |
| Chinese | `zh` |
| Korean | `ko` |
| French | `fr` |
| German | `de` |
| Spanish | `es` |
| Thai | `th` |
| Auto-detect | `auto` |

## Quick Start

### Option 1: Download pre-built executable

Go to [Releases](https://github.com/AnJnD/Translator_app/releases) and download:
- **Windows**: `MeetingTranslator.exe`
- **macOS**: `MeetingTranslator.dmg`

Just run it. No installation required.

### Option 2: Run from source

```bash
# Clone
git clone https://github.com/AnJnD/Translator_app.git
cd Translator_app

# Install dependencies
pip install -r requirements.txt

# Run
python main.py
```

## Setup

1. **Get a Soniox API key** (free) at [soniox.com](https://soniox.com)
2. Launch the app and click **Settings**
3. Paste your Soniox API key
4. Select your source language (e.g., Japanese) and target language (e.g., Vietnamese)
5. Choose audio source:
   - **Microphone** — captures your voice
   - **System audio** — captures meeting output (requires Stereo Mix or WASAPI loopback enabled)
   - **Both** — captures both simultaneously
6. Click **Start Meeting**

> **Note**: Only a Soniox API key is required. The key is stored locally on your machine (`~/.translator_meeting/config.json`) and is only sent to Soniox servers for speech recognition. Translation uses Google Translate's free public endpoint (no API key needed).

## How It Works

```
 Microphone / System Audio
         │
         ▼
 ┌─────────────────┐     PCM 16-bit      ┌──────────────────┐
 │  Audio Capture   │ ──── 16kHz ──────▶  │  Soniox WebSocket │
 │  (sounddevice)   │     mono chunks     │  (STT + Diarize)  │
 └─────────────────┘                      └────────┬─────────┘
                                                   │
                                          tokens with speaker ID
                                          + detected language
                                                   │
                                                   ▼
                                          ┌──────────────────┐
                                          │ Translation Router│
                                          │ (2-way bilingual) │
                                          └────────┬─────────┘
                                                   │
                              ┌─────────────────────┴──────────────────┐
                              ▼                                        ▼
                    ┌──────────────────┐                     ┌──────────────────┐
                    │ Original Panel   │                     │ Translation Panel │
                    │ (speaker-colored)│                     │ (speaker-colored) │
                    └──────────────────┘                     └──────────────────┘
```

### Bidirectional Translation Logic

The app reads the language detected by Soniox for each speech segment:

- If Speaker A speaks in the **source language** → translates to the **target language**
- If Speaker B speaks in the **target language** → translates back to the **source language**
- This happens automatically per segment — no manual language switching

### Speaker Diarization

Soniox identifies up to 4 speakers in the audio stream. Each speaker gets a unique color:

- Speaker 1: Blue
- Speaker 2: Green
- Speaker 3: Orange
- Speaker 4: Purple

## System Audio Capture

To capture meeting audio (what you hear from Zoom/Teams/Meet):

### Windows
Enable one of these in **Windows Sound Settings** → **Recording**:
- Stereo Mix
- WASAPI Loopback
- What U Hear

The app auto-detects these devices. Select **System audio** or **Both** in the audio source dropdown.

### macOS
Install a virtual audio device like [BlackHole](https://existential.audio/blackhole/) or [Soundflower](https://github.com/mattingalls/Soundflower), then route your meeting audio through it.

## Build from Source

### Prerequisites
- Python 3.10+
- pip

### Windows (.exe)
```bash
pip install -r requirements.txt
pyinstaller translator_meeting.spec
# Output: dist/MeetingTranslator.exe
```

### macOS (.app + .dmg)
```bash
pip install -r requirements.txt
pyinstaller translator_meeting.spec
# Output: dist/MeetingTranslator.app

# Optional: create .dmg
hdiutil create -volname "MeetingTranslator" \
  -srcfolder dist/MeetingTranslator.app \
  -ov -format UDZO \
  dist/MeetingTranslator.dmg
```

### Automated Builds (CI/CD)

This repo includes a GitHub Actions workflow (`.github/workflows/build.yml`) that automatically builds both `.exe` and `.dmg` on every push to `main`. Tag a version (`git tag v1.0.0 && git push origin v1.0.0`) to create a GitHub Release with both files attached.

## Tech Stack

| Component | Technology |
|-----------|-----------|
| GUI | PyQt6 with custom dark theme (QSS) |
| Speech-to-Text | Soniox (soniox-2 model, WebSocket streaming) |
| Translation | Google Translate (free public API) |
| Audio Capture | sounddevice + NumPy (WASAPI loopback on Windows) |
| WebSocket | websocket-client |
| Build/Package | PyInstaller (single-file executable) |
| CI/CD | GitHub Actions (Windows + macOS runners) |

## Project Structure

```
├── main.py                  # PyQt6 main window, UI, segment handling
├── config.py                # Configuration load/save, language list, speaker colors
├── audio_capture.py         # Microphone + WASAPI loopback audio capture
├── soniox_client.py         # Soniox WebSocket client (STT + diarization)
├── translator.py            # Google Translate wrapper (free, no API key)
├── translator_meeting.spec  # PyInstaller build spec (Windows + macOS)
├── requirements.txt         # Python dependencies
├── BUILD.md                 # Detailed build instructions
└── .github/workflows/
    └── build.yml            # CI/CD: auto-build .exe + .dmg
```

## Configuration

Settings are stored at `~/.translator_meeting/config.json` and persisted automatically.

Transcripts are saved to `~/.translator_meeting/sessions/session_YYYYMMDD_HHMMSS.md`.

## Requirements

```
PyQt6>=6.6.0
sounddevice>=0.4.6
numpy>=1.26.0
websocket-client>=1.7.0
pyinstaller>=6.0.0
```
