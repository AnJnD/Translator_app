# Meeting Translator

## Tong quan / Overview

Meeting Translator la ung dung desktop dich loi noi theo thoi gian thuc, duoc thiet ke de ho tro giao tiep da ngon ngu trong cac cuoc hop truc tuyen (Zoom, Microsoft Teams, Google Meet). Ung dung nghe am thanh tu microphone hoac am thanh he thong (system audio), nhan dien giong noi thanh van ban qua Soniox STT, tu dong phat hien ngon ngu cua tung nguoi noi, va dich 2 chieu giua 2 ngon ngu da cau hinh.

Meeting Translator is a real-time speech translation desktop app designed for multilingual online meetings (Zoom, Microsoft Teams, Google Meet). It captures audio from microphone or system audio (WASAPI loopback), performs speech-to-text via Soniox, auto-detects each speaker's language, and translates bidirectionally between two configured languages.

## Kien truc / Architecture

```
                    +------------------+
                    |    main.py       |
                    |  (PyQt6 GUI)     |
                    |  MainWindow      |
                    |  SettingsDialog  |
                    +--------+---------+
                             |
              +--------------+--------------+
              |              |              |
     +--------v---+  +------v------+  +----v--------+
     | audio_     |  | soniox_     |  | translator  |
     | capture.py |  | client.py   |  | .py         |
     | (Sound     |  | (WebSocket  |  | (Google     |
     |  Device)   |  |  STT)       |  |  Translate) |
     +------------+  +-------------+  +-------------+
              |              |
              v              v
     Microphone /     Soniox Cloud
     WASAPI Loopback  (soniox-2 model)
```

### Luong du lieu / Data Flow

1. `AudioCapture` bat am thanh tu mic va/hoac system audio (WASAPI loopback), chuyen doi sang PCM 16-bit 16kHz mono.
2. Cac chunk audio duoc gui den `SonioxClient` qua WebSocket (`wss://stt-rt.soniox.com/transcribe-websocket`).
3. Soniox tra ve cac token voi thong tin: text, speaker ID (0-based), language, is_provisional.
4. `SonioxClient` nhom cac token theo speaker, tao `SonioxSegment` (1-indexed speaker) va goi callback.
5. `MainWindow._handle_segment()` nhan segment, xac dinh huong dich dua tren ngon ngu phat hien duoc (dich 2 chieu), goi `translate()` trong background thread.
6. Ket qua duoc emit qua `pyqtSignal` ve main thread de cap nhat UI (original + translation panels).

### Dich 2 chieu / Bidirectional Translation

Logic trong `_handle_segment()` (main.py:476-487):
- Neu `detected_lang == cfg_tgt` (nguoi noi dung ngon ngu dich) -> dich nguoc ve ngon ngu nguon
- Neu `detected_lang == cfg_src` (nguoi noi dung ngon ngu nguon) -> dich sang ngon ngu dich
- Truong hop khac -> dich tu ngon ngu phat hien duoc sang ngon ngu dich

### Speaker Diarization

Soniox streaming diarization duoc bat voi `max_num_speakers: 4`. Moi speaker duoc gan mau sac rieng:
- Speaker 1: `#4FC3F7` (xanh duong nhat)
- Speaker 2: `#A5D6A7` (xanh la nhat)
- Speaker 3: `#FFB74D` (cam)
- Speaker 4: `#CE93D8` (tim)

### Provisional Text

Khi Soniox tra ve text tam thoi (provisional), no hien thi bang mau xam (`#666`). Khi segment hoan thanh (final), text provisional duoc xoa va thay the bang text cuoi cung (mau `#e0e0e0`). Vi tri bat dau cua provisional text duoc theo doi qua `_provisional_start`.

## Cau truc file / File Structure

```
Translator/
  main.py                  - Cua so chinh PyQt6, UI, xu ly segment, export
  config.py                - Load/save config JSON, ngon ngu, mau speaker
  audio_capture.py         - Bat am thanh mic + WASAPI loopback
  soniox_client.py         - Soniox WebSocket client, STT + diarization
  translator.py            - Google Translate API (free, khong can API key)
  translator_meeting.spec  - PyInstaller build spec (Windows .exe + macOS .app)
  requirements.txt         - Python dependencies
  BUILD.md                 - Huong dan build
  dist/
    MeetingTranslator.exe  - File thuc thi Windows da build
```

## Cong nghe su dung / Technology Stack

| Thanh phan | Cong nghe | Muc dich |
|---|---|---|
| GUI Framework | **PyQt6** (>= 6.6.0) | Giao dien desktop cross-platform, dark theme voi QSS |
| Speech-to-Text | **Soniox** (model soniox-2) | Nhan dien giong noi real-time qua WebSocket, ho tro speaker diarization va phat hien ngon ngu |
| Dich thuat | **Google Translate** (free API) | Dich van ban giua cac ngon ngu, khong can API key |
| Thu am | **sounddevice** (>= 0.4.6) + **NumPy** (>= 1.26) | Thu am thanh tu microphone va WASAPI loopback (system audio) |
| WebSocket | **websocket-client** (>= 1.7.0) | Ket noi WebSocket voi Soniox STT service |
| Build | **PyInstaller** (>= 6.0.0) | Dong goi thanh .exe (Windows) hoac .app/.dmg (macOS) |
| Ngon ngu | **Python 3.10+** | Ngon ngu chinh |

## Cau hinh / Configuration

Config duoc luu tai `~/.translator_meeting/config.json`:

```json
{
  "soniox_api_key": "",        // API key Soniox (bat buoc)
  "source_language": "ja",     // Ngon ngu nguon (ma ISO 639-1 hoac "auto")
  "target_language": "vi",     // Ngon ngu dich
  "audio_source": "microphone",  // "microphone" | "system" | "both"
  "font_size": 14,             // Co font (9-36)
  "always_on_top": false,      // Overlay mode
  "show_original": true,
  "auto_translate": true
}
```

### Ngon ngu ho tro

ja (Japanese), vi (Vietnamese), en (English), zh (Chinese), ko (Korean), fr (French), de (German), es (Spanish), th (Thai), auto (Auto-detect).

## Tinh nang UI / UI Features

- **Hai panel song song**: Original Transcript (trai) + Translation (phai) voi QSplitter co the keo chinh kich thuoc
- **Speaker legend**: Hien thi 4 speaker voi mau sac tuong ung phia tren transcript
- **Always-on-top**: Che do overlay, bat/tat trong Settings
- **Font size**: Nut A-/A+ de tang giam co chu (9-36)
- **Scroll Lock**: Nut toggle de tam dung auto-scroll, cho phep doc lai transcript cu
- **Session controls**: Start Meeting / Stop / Clear / Copy / Save
- **Save session**: Luu transcript dang .md tai `~/.translator_meeting/sessions/`
- **Settings dialog**: Cau hinh API key (masked), ngon ngu, nguon am thanh, display

## Thu am he thong / System Audio Capture

Tren Windows, app tim WASAPI loopback device theo thu tu:
1. Tim device co ten chua: "loopback", "stereo mix", "what u hear", "wave out mix", "rec. playback"
2. Fallback: tim default output device co input channels

Tren macOS can cai dat virtual audio device (vd: BlackHole, Soundflower).

Khi chon "Both" (mic + system), ca 2 stream gui rieng biet den Soniox — chat luong co the khong tot bang 1 nguon duy nhat.

## Threading Model

- **Main thread**: PyQt6 event loop, UI rendering
- **Soniox WebSocket thread**: `websocket.WebSocketApp.run_forever()` chay trong daemon thread
- **Audio sender thread**: `_sender_loop()` gui audio chunks tu queue moi 50ms
- **Audio callback threads**: `sounddevice` goi callback trong thread rieng cho moi stream
- **Translation threads**: Moi segment final tao 1 daemon thread moi de goi Google Translate (tranh block main thread)
- **Cross-thread communication**: Su dung `pyqtSignal` (`_Bridge` class) de emit du lieu tu worker threads ve main thread an toan

## Build

### Windows
```bash
pip install -r requirements.txt
pyinstaller translator_meeting.spec
# Output: dist/MeetingTranslator.exe
```

### macOS
```bash
pip install -r requirements.txt
pyinstaller translator_meeting.spec
# Output: dist/MeetingTranslator.app

# Tao .dmg (tuy chon):
hdiutil create -volname "MeetingTranslator" -srcfolder dist/MeetingTranslator.app -ov -format UDZO dist/MeetingTranslator.dmg
```

Dat `icon.ico` (Windows) hoac `icon.icns` (macOS) vao thu muc goc truoc khi build de co icon tuy chinh.

## API Key

Chi can duy nhat 1 API key: **Soniox** (lay mien phi tai soniox.com). Key duoc luu cuc bo tai `~/.translator_meeting/config.json` va chi gui den Soniox WebSocket endpoint khi ket noi. Google Translate su dung endpoint cong khai mien phi (khong can key).

## Luu y khi phat trien / Development Notes

- App su dung Qt Fusion style voi dark theme tuy chinh qua QSS stylesheet
- Tat ca hidden imports da duoc khai bao trong `translator_meeting.spec` de dam bao PyInstaller dong goi day du
- `tkinter`, `matplotlib`, `PIL`, `scipy` bi exclude khoi build de giam kich thuoc
- Config tu dong tao thu muc `~/.translator_meeting/` neu chua ton tai
- Khi dong app (`closeEvent`), session dang chay se duoc dung va config duoc luu tu dong

## Quy trinh push code / Git Commit Rules

- Commit message chi ghi noi dung thay doi, ngan gon, ro rang
- **KHONG** duoc them `Co-Authored-By`, `Reference`, link, hay bat ky metadata nao vao commit message
- **KHONG** duoc them `--no-verify`, `--no-gpg-sign` hay bat ky flag nao bo qua hook
- Format commit message:
  ```
  <mo ta ngan gon thay doi>

  - Chi tiet 1
  - Chi tiet 2
  ```
- Truoc khi push: luon chay `git status` va `git diff` de kiem tra thay doi
- Khong push truc tiep len main/master khi khong duoc yeu cau
- Khong amend commit truoc do tru khi duoc yeu cau ro rang
