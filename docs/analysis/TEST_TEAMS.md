# TEST AGENT 2 — Teams Meeting Multi-Speaker Test Results

**Date:** 2026-05-25  
**Scope:** Multi-speaker diarization, bidirectional translation, concurrent speaker handling, "Both" audio mode  
**Method:** Static code analysis + logic tracing (no live audio)

---

## Checklist

- [x] Speaker diarization logic analyzed — how IDs are assigned and displayed — **PASS**
- [x] Bidirectional translation logic verified for all language combinations — **PASS (with WARN)**
- [x] Multi-speaker color coding verified (4 colors) — **PASS (with WARN)**
- [x] Overlap/concurrent speaker handling analyzed — **PASS**
- [x] "Both" audio mode (mic + system) analyzed for potential issues — **WARN**
- [x] Edge cases identified (speaker > 4, speaker = 0, empty text, etc.) — **WARN**
- [x] Provisional text behavior with speaker changes analyzed — **WARN**
- [x] Potential bugs or issues documented — see below

---

## 1. Speaker Diarization Logic — **PASS**

### How IDs are assigned

**Soniox side (soniox_client.py:252-253):**
- Soniox returns tokens with a `speaker` field (0-based index).
- If `speaker` is missing or falsy, it defaults to 0: `speaker = token.get("speaker", 0) or 0`.

**Conversion to 1-indexed (soniox_client.py:283):**
- Before creating `SonioxSegment`, speaker is converted: `speaker=speaker + 1`.
- This means Soniox speaker 0 becomes Speaker 1, speaker 1 becomes Speaker 2, etc.

**Clamping in main.py:484:**
- `speaker = max(1, min(seg.speaker, 4))` — clamps to range [1, 4].
- This is correct for display purposes since only 4 speaker colors/labels are defined in the legend.

### How speakers are displayed (main.py:214, 547-552, 583-588, 606-616)

- `SPEAKER_LABEL` dict maps 1-4 to "Speaker 1" through "Speaker 4".
- Each speaker gets a color-coded header: `[Speaker N — HH:MM:SS]`.
- Header is only inserted when the speaker changes from the previous segment (`speaker != self._last_speaker_orig`).
- Separate tracking for original panel (`_last_speaker_orig`) and translation panel (`_last_speaker_trans`).

**Verdict: PASS** — Speaker ID assignment and display logic is correct and consistent.

---

## 2. Bidirectional Translation Logic — **PASS with WARN**

### Primary path: Soniox built-in translation (soniox_client.py:91-97)

When `source_language != "auto"` and `source != target`, Soniox is configured with:
```json
{
  "translation": {
    "type": "two_way",
    "language_a": "<source>",
    "language_b": "<target>"
  }
}
```
This means Soniox itself handles bidirectional translation at the STT level. Translated tokens come back with `translation_status: "translation"` and are grouped per speaker in `speaker_translation` dict.

### Fallback path: Google Translate (main.py:502-527)

When Soniox does NOT return a translation (`soniox_translated` is empty), the app falls back to Google Translate with bidirectional logic:

| Condition | Source | Destination | Example |
|-----------|--------|-------------|---------|
| `detected_lang == cfg_tgt` | detected_lang | cfg_src (or "ja" if auto) | Speaker speaks Vietnamese (target) -> translate to Japanese (source) |
| `detected_lang == cfg_src` | detected_lang | cfg_tgt | Speaker speaks Japanese (source) -> translate to Vietnamese (target) |
| else | detected_lang or cfg_src | cfg_tgt | Unknown language -> translate to target |

### Analysis of language combinations

**Case 1: src=ja, tgt=vi, speaker speaks Japanese**
- detected_lang="ja", cfg_src="ja", cfg_tgt="vi"
- Match: `detected_lang == cfg_src` -> translate ja->vi. **Correct.**

**Case 2: src=ja, tgt=vi, speaker speaks Vietnamese**
- detected_lang="vi", cfg_src="ja", cfg_tgt="vi"
- Match: `detected_lang == cfg_tgt` -> translate vi->ja. **Correct.**

**Case 3: src=ja, tgt=vi, speaker speaks English**
- detected_lang="en", no match -> translate en->vi (target). **Reasonable default.**

**Case 4: src=auto, tgt=vi, speaker speaks Japanese**
- detected_lang="ja", cfg_src="auto", cfg_tgt="vi"
- No match for `detected_lang == cfg_tgt` (ja != vi)
- No match for `detected_lang == cfg_src` (ja != auto)
- Falls to else: src=ja, dest=vi. **Correct.**

**Case 5: src=auto, tgt=vi, speaker speaks Vietnamese**
- detected_lang="vi", cfg_src="auto", cfg_tgt="vi"
- Match: `detected_lang == cfg_tgt` -> src=vi, dest=cfg_src="auto" -> dest falls back to "ja"
- Translates vi->ja. **Reasonable but hardcoded fallback.**

### WARN: Hardcoded fallback to "ja" when source is "auto"

**File:** main.py:510  
**Code:** `dest = cfg_src if cfg_src != "auto" else "ja"`

When source is "auto" and someone speaks the target language, the reverse translation destination defaults to Japanese. This is a hardcoded assumption that may not match user intent (e.g., user wants English<->Vietnamese but gets Vietnamese->Japanese).

### WARN: Soniox two-way translation not configured when source is "auto"

**File:** soniox_client.py:89-96  
When `source_language == "auto"`, the condition `if src and tgt and src != tgt` fails because `src` is `None`. This means Soniox's built-in two-way translation is disabled entirely in auto mode, and ALL translation falls back to the Google Translate path. This is by design but could affect translation quality/latency.

**Verdict: PASS with WARN** — Logic is correct for explicit language pairs. The "auto" mode has a hardcoded Japanese fallback that may surprise users.

---

## 3. Multi-Speaker Color Coding — **PASS with WARN**

### Color definitions (config.py:18-24)

| Speaker | Color | Name |
|---------|-------|------|
| 1 | #4FC3F7 | Light blue |
| 2 | #A5D6A7 | Light green |
| 3 | #FFB74D | Orange |
| 4 | #CE93D8 | Purple |
| 5 | #F48FB1 | Pink |

### Legend display (main.py:331-338)

The speaker legend loop iterates over `config.SPEAKER_COLORS` but breaks at `num > 4`, so only 4 speakers are shown in the legend.

### Color lookup (main.py:485)

`color = config.SPEAKER_COLORS.get(speaker, "#e0e0e0")` — after clamping speaker to [1, 4], this will always match speakers 1-4. The default "#e0e0e0" is unreachable due to clamping.

### WARN: Speaker 5 color defined but never used

`config.py` defines a color for Speaker 5 (`#F48FB1` pink), but `main.py:484` clamps speaker IDs to max 4. This is dead code. If Soniox reports 5+ speakers, speakers 5+ will all be displayed as Speaker 4 with purple color, losing their individual identity.

**Verdict: PASS with WARN** — Colors work correctly for 4 speakers. Speaker 5 color in config is dead code.

---

## 4. Overlap/Concurrent Speaker Handling — **PASS**

### Token grouping (soniox_client.py:244-288)

The `_handle_response` method processes all tokens from a single WebSocket message:

1. Tokens are grouped by speaker ID into two dictionaries: `speaker_original` and `speaker_translation`.
2. Each speaker's tokens are aggregated: text is concatenated, `is_final` is true if ANY token for that speaker is final.
3. A `SonioxSegment` is created per speaker and emitted via callback.

**Key observations:**
- If Soniox returns tokens from multiple speakers in a single response, each speaker gets a separate `SonioxSegment`.
- The `for speaker, parts in speaker_original.items()` loop iterates over all speakers, so multiple segments can be emitted from one response.
- This is correct: each speaker's text is independent.

### Concurrent emission

Multiple `SonioxSegment` callbacks can fire in quick succession from the same WebSocket message. Since `_handle_segment` (main.py:483) uses `_bridge.provisional.emit()` and `_bridge.segment_ready.emit()` which are Qt signals, they will be queued and processed sequentially on the main thread. This is thread-safe.

**Verdict: PASS** — Multiple speakers in one response are correctly separated and emitted individually.

---

## 5. "Both" Audio Mode (Mic + System) — **WARN**

### How it works (audio_capture.py:60-98)

When `source="both"`:
1. A microphone `InputStream` is created with callback `_mic_callback`.
2. A system audio `InputStream` (WASAPI loopback) is created with callback `_sys_callback`.
3. Both callbacks call the same `_on_audio` function (which is `soniox.send_audio`).

### Issue: Interleaved audio streams

Both streams send audio chunks independently to the same Soniox WebSocket connection. The chunks are interleaved in the audio queue (`_audio_queue` in soniox_client.py:242), and the sender loop sends them in FIFO order.

**Potential problems:**
1. **Echo/feedback:** The same speech may be captured by both mic and system audio, causing duplicate or garbled transcription.
2. **Speaker diarization confusion:** Soniox receives alternating chunks from two different audio sources with different acoustic characteristics. This could confuse the speaker diarization model, potentially assigning the same person to multiple speaker IDs.
3. **Audio quality:** The warning at audio_capture.py:61-63 acknowledges this: "For best accuracy, use a single source."
4. **No mixing/synchronization:** Audio chunks from both sources are not time-aligned or mixed. A 250ms chunk from the mic might be followed by a 250ms chunk from system audio that covers a different time window.

### Mitigating factor

The app prints a warning when "Both" mode is selected. However, this is only printed to console (stdout), not shown to the user in the UI.

**Verdict: WARN** — "Both" mode works but with known quality trade-offs. The console warning is not visible to users in the GUI. Recommend adding a visible UI warning when "Both" is selected.

---

## 6. Edge Cases — **WARN**

### Speaker > 4

**Soniox config (soniox_client.py):** No `max_num_speakers` is set in `_build_config()`. The CLAUDE.md documentation says "max_num_speakers: 4" but this is NOT actually sent in the config. Soniox's default may allow more speakers.

**Clamping (main.py:484):** `speaker = max(1, min(seg.speaker, 4))` — Speaker IDs > 4 are clamped to 4. Multiple distinct speakers (5, 6, 7...) would all appear as "Speaker 4" with purple color. This loses information.

**_handle_response (soniox_client.py:283):** The conversion `speaker + 1` happens before clamping. Soniox speaker 0 -> 1, speaker 3 -> 4, speaker 4 -> 5, speaker 5 -> 6. So if Soniox returns speaker 4 (0-based), it becomes 5, which gets clamped to 4 in main.py.

### Speaker = 0 (from Soniox)

Soniox speaker 0 -> converted to 1 in `SonioxSegment`. This is correct.

### Missing speaker field

`token.get("speaker", 0) or 0` — if speaker is `None` or `0`, defaults to 0. Then `0 + 1 = 1`. Correct.

### Empty text

`if original_text.strip():` (soniox_client.py:277) — empty or whitespace-only text is filtered out. **Correct.**

### translate() with empty text

`translator.py:19-20` — returns text unchanged if empty. **Correct.**

### translate() with src == dest

`translator.py:21-22` — returns text unchanged. **Correct.** This handles the edge case where detected language equals destination.

### Session reset and speaker continuity

After session reset (soniox_client.py:201-208), the WebSocket reconnects. `_last_speaker_orig` and `_last_speaker_trans` in `MainWindow` are NOT reset. This means if the same speaker continues after reconnect, no duplicate header is inserted. If Soniox reassigns speaker IDs after reconnect (likely), the header logic will correctly detect the "new" speaker.

**Verdict: WARN** — Most edge cases handled. Main concern is `max_num_speakers` not being set in the Soniox config, and the documentation being inaccurate about this.

---

## 7. Provisional Text Behavior with Speaker Changes — **WARN**

### Normal provisional flow (main.py:531-563)

1. Provisional text is displayed in gray (#666) in the original panel.
2. `_provisional_start` tracks the character position where provisional text begins.
3. When new provisional text arrives, old provisional text is removed (from `_provisional_start` to end) and replaced.
4. When final text arrives, provisional text is removed and replaced with final text in white (#e0e0e0).

### Speaker change during provisional text

**Scenario:** Speaker 1 is speaking (provisional text visible), then Speaker 2 starts speaking.

**What happens in `_on_provisional` (main.py:531-563):**
1. New provisional arrives with speaker=2.
2. `_provisional_start is not None` -> old provisional text (from Speaker 1) is removed (lines 537-540).
3. `speaker != self._last_speaker_orig` -> a new speaker header for Speaker 2 is inserted (lines 543-553).
4. `_last_speaker_orig` is updated to speaker 2.
5. New `_provisional_start` is set after the header.
6. Provisional text for Speaker 2 is inserted.

**Problem:** Speaker 1's provisional text is completely removed and never finalized. If Speaker 1 was mid-sentence and Soniox sends the final segment for Speaker 1 AFTER provisional text for Speaker 2 has started, the `_on_segment_ready` will:
1. Check `_provisional_start is not None` -> true (but it now points to Speaker 2's provisional area).
2. Remove everything from `_provisional_start` to end -> this removes Speaker 2's provisional text AND Speaker 2's header.
3. Insert Speaker 1's final text at that position -> text appears under Speaker 2's context.

This is a **race condition** between speakers. The single `_provisional_start` variable cannot track provisional text from multiple speakers simultaneously.

### Impact

In practice, Soniox typically finalizes Speaker 1's text before emitting Speaker 2's provisional text, so this race is uncommon. However, with fast speaker switches or overlapping speech, the display could momentarily show incorrect attribution.

**Verdict: WARN** — Single `_provisional_start` creates a potential display glitch when speakers overlap. The glitch is self-correcting (final text replaces provisional), but intermediate display may be briefly incorrect.

---

## 8. Potential Bugs and Issues

### BUG 1: Documentation mismatch — `max_num_speakers` not sent (Medium)

**CLAUDE.md** states: "Soniox streaming diarization duoc bat voi `max_num_speakers: 4`"  
**Actual code (soniox_client.py:75-85):** No `max_num_speakers` field in `_build_config()`.  
**Impact:** Soniox may use its own default (potentially more than 4 speakers). Speakers beyond 4 are clamped and lose identity.  
**Fix:** Add `"max_num_speakers": 4` to the config, or increase the speaker color/label support to match Soniox's actual limit.

### BUG 2: Hardcoded "ja" fallback in auto mode (Low)

**File:** main.py:510  
**Code:** `dest = cfg_src if cfg_src != "auto" else "ja"`  
**Impact:** When source="auto" and someone speaks the target language, reverse translation always goes to Japanese regardless of user's actual context.  
**Fix:** Could default to English ("en") or ask the user to specify a secondary language for auto mode.

### BUG 3: "Both" mode warning only in console (Low)

**File:** audio_capture.py:61-63  
**Impact:** Users selecting "Both" mode in the GUI see no warning about potential quality issues.  
**Fix:** Show a QMessageBox or status bar warning when "Both" is selected.

### BUG 4: Provisional start race with multi-speaker (Low)

**File:** main.py:537-540, 571-575  
**Impact:** Single `_provisional_start` variable can cause brief display glitches when speakers overlap.  
**Fix:** Track provisional start per speaker, or clear provisional text more carefully when speaker changes.

### BUG 5: Speaker 5 unreachable despite color being defined (Cosmetic)

**File:** config.py:23 defines Speaker 5 color, main.py:484 clamps to [1,4], main.py:333 breaks legend at num > 4.  
**Impact:** Dead code. If the intent is to support 5 speakers, clamping and legend need updating.

### BUG 6: `is_final` determination is too aggressive (Low)

**File:** soniox_client.py:271  
**Code:** `is_final = any(p[1] for p in parts)`  
**Impact:** If even one token in a speaker's group is marked final, the entire aggregated text is treated as final. This could cause partial text to be treated as final if Soniox sends a mix of provisional and final tokens for the same speaker in one response.

### OBSERVATION: Thread safety of `_handle_segment`

`_handle_segment` (main.py:483) is called from the Soniox WebSocket thread. It reads `self.cfg` (main.py:503-504) which could be modified by the main thread (e.g., in `_open_settings`). This is a potential race condition, though in practice `dict.get()` in CPython is atomic due to the GIL.

---

## Summary

| # | Item | Verdict | Key Finding |
|---|------|---------|-------------|
| 1 | Speaker diarization | **PASS** | 0-based to 1-indexed conversion correct, clamped to [1,4] |
| 2 | Bidirectional translation | **PASS/WARN** | Correct for explicit pairs; "auto" mode has "ja" hardcoded fallback |
| 3 | Color coding | **PASS/WARN** | 4 colors work; Speaker 5 color is dead code |
| 4 | Concurrent speakers | **PASS** | Tokens correctly grouped per speaker, Qt signals ensure thread safety |
| 5 | "Both" audio mode | **WARN** | Interleaved streams may confuse diarization; no UI warning |
| 6 | Edge cases | **WARN** | `max_num_speakers` not sent to Soniox despite docs claiming it |
| 7 | Provisional + speaker switch | **WARN** | Single `_provisional_start` can cause brief display glitches |
| 8 | Bugs documented | — | 6 issues found (0 critical, 1 medium, 5 low/cosmetic) |

**Overall assessment:** The multi-speaker system is well-designed and handles the common cases correctly. The main areas of concern are: (1) the missing `max_num_speakers` config parameter, (2) the hardcoded Japanese fallback in auto mode, and (3) the single-provisional-start limitation with concurrent speakers. None of these are showstoppers for typical 2-3 speaker meeting scenarios.
