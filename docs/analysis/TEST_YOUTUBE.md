# YouTube Translation Test Report

**Date:** 2026-05-25
**Tester:** TEST AGENT 1 (automated)
**App Version:** Meeting Translator v1.0 (commit 0193c61)

## Test Environment

- **OS:** Windows 11 Home 10.0.26200
- **Working Directory:** C:\Users\Omion\OneDrive\デスクトップ\Ominext\LuyenTap\Translator
- **Built exe:** dist\MeetingTranslator.exe

## Test Execution Status

**BLOCKED** -- Shell access (Bash and PowerShell) was denied by the sandbox, preventing runtime execution of the app. The tests below could not be executed interactively. Instead, a thorough static code review was performed and manual test instructions are provided.

## Test Results

### 1. App Launches Successfully
- **Status:** BLOCKED (cannot run `python main.py`)
- **Code Review Finding:** Entry point at `main.py:698-707` is standard PyQt6 `QApplication` + `MainWindow`. No obvious launch blockers. Dependencies in `requirements.txt` are: PyQt6>=6.6.0, sounddevice>=0.4.6, numpy>=1.26.0, websocket-client>=1.7.0, pyinstaller>=6.0.0.

### 2. Soniox Connection Established
- **Status:** BLOCKED (cannot observe console logs)
- **Code Review Finding:** `SonioxClient.connect()` (soniox_client.py:69-73) starts WebSocket connection to `wss://stt-rt.soniox.com/transcribe-websocket`. On open, it sends config JSON including `api_key`, `model: "stt-rt-v4"`, and enables `speaker_diarization` + `language_identification`. Connection status is logged as `[Soniox] Sending config: ...`. Reconnect logic handles up to 3 attempts with delays [2, 4, 6] seconds.
- **Prerequisite:** Soniox API key must exist in `~/.translator_meeting/config.json`. If missing, the app shows a QMessageBox warning and opens Settings dialog (main.py:420-426). Could not verify if key exists since config file is outside project directory.

### 3. System Audio Capture Working
- **Status:** BLOCKED (cannot run app or check audio devices)
- **Code Review Finding:** `AudioCapture._find_loopback_device()` (audio_capture.py:33-53) searches for WASAPI loopback device by:
  1. Looking for device names containing: "loopback", "stereo mix", "what u hear", "wave out mix", "rec. playback"
  2. Fallback: finding default output device that has input channels
- **Potential Issue:** Many Windows 11 systems do not have Stereo Mix enabled by default. User must enable it in Sound Settings > Recording devices > right-click > Show Disabled Devices > Enable Stereo Mix. Alternatively, a virtual audio cable (e.g., VB-Audio Virtual Cable) can be used.

### 4. Transcript Generated from YouTube Audio
- **Status:** BLOCKED (cannot play YouTube video or observe transcript)
- **Code Review Finding:** Audio flow is: `AudioCapture` callback -> `_to_pcm16()` converts to 16-bit PCM at 16kHz mono -> `SonioxClient.send_audio()` queues bytes -> `_sender_loop()` sends via WebSocket every 50ms -> Soniox returns tokens -> `_handle_response()` groups by speaker and creates `SonioxSegment` -> callback to `MainWindow._handle_segment()`.
- **Suggested YouTube Test Video:** TED Talk "Do schools kill creativity?" by Ken Robinson: https://www.youtube.com/watch?v=iG9CE55wbtY (English speech, clear audio)

### 5. Transcript Accuracy
- **Status:** BLOCKED
- **Code Review Finding:** Using Soniox model `stt-rt-v4` which is their latest real-time STT model. Quality depends on: audio clarity, background noise, speaker accent. System audio capture should provide clean audio from YouTube (no ambient noise).

### 6. Vietnamese Translation Appears
- **Status:** BLOCKED
- **Code Review Finding:** Translation path has two mechanisms:
  1. **Soniox built-in translation** (soniox_client.py:91-96): Configured as `"translation": {"type": "two_way", "language_a": src, "language_b": tgt}`. If Soniox returns translated tokens (`translation_status == "translation"`), they are used directly.
  2. **Google Translate fallback** (main.py:502-527): If Soniox does not return translation (`soniox_translated` is empty), the app calls `translate()` from `translator.py` using free Google Translate API (`translate.googleapis.com`). Bidirectional logic determines src/dest based on detected language vs configured languages.
- **Translation display:** Final text shown in right panel ("Translation") with speaker colors. Provisional text shown in gray (#666) in left panel only.

### 7. Latency Acceptable (< 3 seconds)
- **Status:** BLOCKED (cannot measure)
- **Code Review Finding:** Expected latency components:
  - Audio chunk: ~250ms (BLOCK_SIZE=4000 at 16kHz)
  - Send interval: 50ms (`_sender_loop` sleep)
  - Soniox STT processing: typically 200-500ms for provisional, 1-2s for final
  - Translation: Soniox inline translation adds ~0ms extra; Google Translate fallback adds ~200-500ms (5s timeout)
  - **Estimated total:** 1-3 seconds for final translated text. Provisional (untranslated) original text should appear within ~500ms.

### 8. Pause/Resume Behavior Correct
- **Status:** BLOCKED (cannot interact with YouTube player)
- **Code Review Finding:** When YouTube is paused:
  - `AudioCapture` callbacks continue running but receive silence (zero-amplitude audio)
  - `SonioxClient._sender_loop()` keeps sending silent audio chunks
  - Soniox endpoint detection (`enable_endpoint_detection: true`) should finalize any pending segment
  - No transcript should appear during silence
  - On resume, new audio resumes flowing through the same pipeline
  - **Session timer:** Every 180 seconds, the session auto-resets with context carryover (last 500 chars). A long pause could trigger this reset.
  - **Potential concern:** Keepalive pings sent every 15 seconds keep the WebSocket alive during pauses.

### 9. Auto-Save Session Works on Stop
- **Status:** BLOCKED (cannot click Stop button)
- **Code Review Finding:** `_stop()` (main.py:457-471) checks `if self._session_log:` and calls `_auto_save_session()`. This writes a `.md` file to `~/.translator_meeting/sessions/session_YYYYMMDD_HHMMSS.md` containing:
  - Header with date, source/target languages
  - Original Transcript section (plain text from QTextEdit)
  - Translation section (plain text from QTextEdit)
  - Console log: `[Session] Auto-saved -> <path>`
- **Also triggers on app close:** `closeEvent()` (main.py:690-692) calls `_stop()` then `config.save()`.

## Manual Test Instructions

Since automated runtime testing was blocked, here are step-by-step instructions to perform the test manually:

### Prerequisites
1. Ensure Python 3.10+ is installed with all dependencies: `pip install -r requirements.txt`
2. Enable Stereo Mix in Windows Sound Settings:
   - Right-click speaker icon in taskbar > Sounds > Recording tab
   - Right-click empty area > Show Disabled Devices
   - Right-click "Stereo Mix" > Enable
3. Have a Soniox API key (free at https://soniox.com)

### Steps

```
Step 1: Launch the app
> cd C:\Users\Omion\OneDrive\デスクトップ\Ominext\LuyenTap\Translator
> python main.py

Step 2: Configure (if first run)
- Click "Settings" button
- Paste Soniox API key
- Set Source: English, Target: Vietnamese
- Set Audio Source: System audio
- Click Save

Step 3: Select audio source in main window
- Change dropdown to "System" (system audio)

Step 4: Open YouTube
- Open browser, navigate to: https://www.youtube.com/watch?v=iG9CE55wbtY
- Or any English speech video (TED Talk, CNN, etc.)

Step 5: Start session
- Click "Start Meeting" button
- Console should show: [Soniox] Sending config: {...}
- Status should change to "Live -- listening" (green dot)

Step 6: Play YouTube video for ~60 seconds
- Watch left panel for original English transcript (provisional in gray, final in white)
- Watch right panel for Vietnamese translation
- Note time from speech to transcript appearance

Step 7: Test pause/resume
- Pause YouTube video
- Wait 5 seconds -- no new transcript should appear
- Resume video -- transcript should continue

Step 8: Stop session
- Click "Stop" button
- Check console for: [Session] Auto-saved -> ...
- Check ~/.translator_meeting/sessions/ for saved .md file

Step 9: Verify saved session
- Open the saved .md file
- Confirm it contains both original transcript and translation
```

### Expected Console Output Pattern
```
[Soniox] Sending config: {"model": "stt-rt-v4", "audio_format": "pcm_s16le", ...}
[Soniox] WebSocket closed: code=... (if session reset occurs at 3 min)
[Soniox] Session reset (3 min) -- reconnecting with context carryover...
[Session] Auto-saved -> C:\Users\Omion\.translator_meeting\sessions\session_20260525_XXXXXX.md
```

## Code Quality Observations (from static review)

1. **Audio capture is robust:** Handles both mic and system audio with proper error handling for missing devices.
2. **Reconnection logic is solid:** 3 attempts with increasing delays, session reset every 3 minutes with text carryover.
3. **Thread safety is correct:** Uses `pyqtSignal` bridge for cross-thread UI updates, `threading.Lock` for audio queue.
4. **Translation fallback is good:** Soniox inline translation first, Google Translate as backup.
5. **Provisional text handling is clean:** Tracks position, replaces on finalization.
6. **Minor concern:** The free Google Translate endpoint (`translate.googleapis.com`) may rate-limit or block under heavy use.
7. **Minor concern:** `_session_log` is checked but individual translation threads append to it without a lock -- potential (unlikely) race condition.

## Summary

| Test Case | Status | Notes |
|---|---|---|
| App launches | BLOCKED | Code review: no issues found |
| Soniox connection | BLOCKED | Requires API key in config |
| System audio capture | BLOCKED | Requires Stereo Mix enabled |
| Transcript from YouTube | BLOCKED | Pipeline code is correct |
| Transcript accuracy | BLOCKED | Uses Soniox stt-rt-v4 model |
| Vietnamese translation | BLOCKED | Dual path: Soniox + Google fallback |
| Latency < 3s | BLOCKED | Estimated 1-3s from code analysis |
| Pause/Resume | BLOCKED | Endpoint detection should handle |
| Auto-save on stop | BLOCKED | Code path verified correct |

**Overall Result:** BLOCKED -- All 9 test cases could not be executed due to sandbox shell restrictions. Static code review found no defects that would prevent the tests from passing. Manual execution following the instructions above is required.
