# BUG REPORT - Meeting Translator v1.0

**Ngay tao:** 2026-05-25
**Nguon du lieu:** TEST_YOUTUBE.md (static code review), TEST_TEAMS.md (multi-speaker analysis), COMPARISON_REPORT.md (so sanh voi GitHub repo phuc-nt/my-translator)
**App version:** commit 0193c61

---

## 1. Bugs Found

### BUG-001 | Major | Hardcoded fallback "ja" khi source language la "auto"

- **Location:** `main.py`, dong 510
- **Code:** `dest = cfg_src if cfg_src != "auto" else "ja"`
- **Description:** Khi user chon source language = "auto" va nguoi noi su dung ngon ngu dich (target language), app dich nguoc ve tieng Nhat (ja) thay vi ngon ngu ma user mong muon. Vi du: user cau hinh auto -> vi, nguoi noi tieng Viet -> app dich sang tieng Nhat thay vi tieng Anh.
- **Impact:** Nguoi dung nhan ban dich sai ngon ngu khi dung che do auto-detect, gay nham lan trong cuoc hop.
- **Suggested Fix:** Thay vi hardcode "ja", cho phep user cau hinh "secondary language" trong Settings, hoac dung "en" (English) lam default hieu qua hon. Them truong `fallback_language` trong config.
- **GitHub Repo Reference:** GitHub repo khong co van de nay vi ho chi dung Soniox built-in translation (khong co Google Translate fallback path).

---

### BUG-002 | Major | Soniox two-way translation bi disable hoan toan khi source = "auto"

- **Location:** `soniox_client.py`, dong 89-96
- **Code:**
  ```python
  src = self._source_language if self._source_language != "auto" else None
  tgt = self._target_language
  if src and tgt and src != tgt:
      cfg["translation"] = { ... }
  ```
- **Description:** Khi source_language = "auto", bien `src` se la `None`, dieu kien `if src and tgt` se fail. Ket qua: Soniox KHONG duoc cau hinh translation, toan bo translation phai fallback sang Google Translate (free endpoint, co the bi rate-limit).
- **Impact:** Che do "auto" mat hoan toan Soniox built-in translation (chat luong cao hon, do tre thap hon). Nguoi dung chi nhan duoc Google Translate fallback voi chat luong va do tin cay thap hon.
- **Suggested Fix:** Khi source = "auto", van gui `one_way` translation config voi `target_language` thay vi bo qua hoan toan. Hoac hien thi canh bao cho user biet auto mode se khong co Soniox translation.
- **GitHub Repo Reference:** GitHub repo ho tro ca `one_way` va `two_way` translation (`src/js/soniox.js`, dong 118-131). Khi chi co target language, ho dung `one_way` mode.

---

### BUG-003 | Major | `_provisional_start` race condition khi nhieu speaker noi dong thoi

- **Location:** `main.py`, dong 537-540 (`_on_provisional`) va dong 571-575 (`_on_segment_ready`)
- **Description:** Chi co mot bien `_provisional_start` duy nhat theo doi vi tri provisional text. Khi Speaker 1 dang noi (provisional text hien thi) va Speaker 2 bat dau noi:
  1. Provisional cua Speaker 1 bi xoa
  2. Header Speaker 2 duoc chen
  3. `_provisional_start` tro den vi tri moi cua Speaker 2
  4. Neu Soniox gui final segment cua Speaker 1 SAU do, `_on_segment_ready` se xoa tu `_provisional_start` (vi tri cua Speaker 2) den cuoi -> mat ca header va provisional text cua Speaker 2
- **Impact:** Text bi hien thi sai speaker attribution, header bi mat, noi dung bi xoa nham khi co overlapping speech.
- **Suggested Fix:** Su dung dict `_provisional_starts: dict[int, int]` de theo doi provisional start per speaker. Hoac su dung mot cau truc du lieu phuc tap hon de quan ly provisional text doc lap cho tung speaker.
- **GitHub Repo Reference:** GitHub repo tranh van de nay bang cach rebuild toan bo HTML tu segments array moi lan render (`src/js/ui.js`, dong 361-411), thay vi manipulate text cursor truc tiep.

---

### BUG-004 | Major | `is_final` determination qua aggressive

- **Location:** `soniox_client.py`, dong 271
- **Code:** `is_final = any(p[1] for p in parts)`
- **Description:** Neu Soniox gui mot nhom tokens cho cung speaker ma chi co 1 token la `is_final=True` con cac token khac la provisional, toan bo text duoc coi la final. Dieu nay co the khien text provisional bi "finalize" qua som khi Soniox gui mixed tokens.
- **Impact:** Text chua hoan chinh co the duoc hien thi nhu final text va duoc dich, dan den ban dich khong chinh xac hoac khong day du.
- **Suggested Fix:** Chi danh dau la final khi TAT CA tokens deu la final: `is_final = all(p[1] for p in parts)`. Hoac tach tokens thanh 2 nhom (final va provisional) va xu ly rieng.
- **GitHub Repo Reference:** GitHub repo xu ly tung token rieng le va phan loai theo `translation_status` truoc khi nhom (`src/js/soniox.js`, dong 286-344).

---

### BUG-005 | Minor | `max_num_speakers` khong duoc gui trong Soniox config (documentation mismatch)

- **Location:** `soniox_client.py`, dong 75-108 (`_build_config`)
- **Description:** CLAUDE.md ghi ro "Soniox streaming diarization duoc bat voi `max_num_speakers: 4`" nhung thuc te field nay KHONG co trong `_build_config()`. Soniox co the tra ve nhieu hon 4 speakers.
- **Impact:** Khi co > 4 speakers, tat ca speakers tu 5 tro len bi clamp thanh Speaker 4 (dong 484 main.py: `speaker = max(1, min(seg.speaker, 4))`). Nguoi dung khong phan biet duoc cac speakers khac nhau.
- **Suggested Fix:** Them `"max_num_speakers": 4` vao `_build_config()`, hoac mo rong SPEAKER_LABEL va SPEAKER_COLORS trong config.py de ho tro nhieu speaker hon.
- **GitHub Repo Reference:** GitHub repo cung khong gui `max_num_speakers` nhung ho hien thi speaker ID truc tiep (`Speaker ${seg.speaker}:`) khong gioi han so luong.

---

### BUG-006 | Minor | Che do "Both" (mic + system) khong hien canh bao trong UI

- **Location:** `audio_capture.py`, dong 61-63
- **Description:** Khi user chon "Both" mode, canh bao chi in ra console (`print()`). Nguoi dung su dung GUI khong bao gio thay canh bao nay. Audio tu 2 nguon bi interleave ma khong dong bo, co the gay echo/feedback va nham lan speaker diarization.
- **Impact:** User chon "Both" ma khong biet chat luong se kem, co the nghi app bi loi.
- **Suggested Fix:** Hien thi QMessageBox warning hoac toast notification khi user chon "Both" trong audio_combo. Them text warning ngay duoi combo box.
- **GitHub Repo Reference:** GitHub repo co `excludes_current_process_audio` tren macOS (`src-tauri/src/audio/system_audio.rs`) de ngan TTS feedback loop — local app khong co co che tuong tu.

---

### BUG-007 | Minor | Session log append khong co lock — race condition tiem an

- **Location:** `main.py`, dong 496-501 va dong 520-525
- **Description:** `self._session_log.append()` duoc goi tu nhieu translation threads khac nhau (moi final segment tao 1 daemon thread moi tai dong 527). Mac du CPython GIL bao ve `list.append()`, nhung thu tu cac entries co the khong dung voi thu tu thuc te cua speech.
- **Impact:** Session log co the luu sai thu tu cac segments, dac biet khi co nhieu speakers cung noi.
- **Suggested Fix:** Su dung `threading.Lock` de bao ve `_session_log.append()`, hoac su dung `queue.Queue` de dam bao thu tu.
- **GitHub Repo Reference:** GitHub repo dung single-threaded JS event loop nen khong co van de nay.

---

### BUG-008 | Minor | language_hints chi gui source language, khong gui target language

- **Location:** `soniox_client.py`, dong 86-87
- **Code:**
  ```python
  if self._source_language and self._source_language != "auto":
      cfg["language_hints"] = [self._source_language]
  ```
- **Description:** Chi source language duoc gui trong `language_hints`. Soniox co the khong nhan dien tot target language khi nguoi noi dung ngon ngu dich.
- **Impact:** Trong cuoc hop 2 chieu (vd: Nhat-Viet), khi nguoi Viet noi, Soniox co the khong nhan dien tot tieng Viet vi no khong nam trong language_hints.
- **Suggested Fix:** Gui ca source va target language: `cfg["language_hints"] = [self._source_language, self._target_language]`
- **GitHub Repo Reference:** GitHub repo gui CA HAI ngon ngu khi two_way mode (`src/js/soniox.js`, dong 125): `configMsg.language_hints = [languageA, languageB]`.

---

### BUG-009 | Cosmetic | Speaker 5 color duoc dinh nghia nhung khong bao gio su dung

- **Location:** `config.py`, dong 23 (`5: "#F48FB1"`)
- **Description:** Config dinh nghia mau cho Speaker 5 (pink) nhung `main.py` dong 484 clamp speaker ID ve [1, 4] va legend loop break tai `num > 4` (dong 333). Color Speaker 5 la dead code.
- **Impact:** Khong anh huong chuc nang, nhung code khong nhat quan (doc code se thac mac tai sao co 5 mau nhung chi dung 4).
- **Suggested Fix:** Xoa Speaker 5 khoi SPEAKER_COLORS, hoac mo rong support len 5+ speakers.
- **GitHub Repo Reference:** N/A

---

### BUG-010 | Cosmetic | CLAUDE.md documentation sai ve Soniox model name

- **Location:** CLAUDE.md
- **Description:** CLAUDE.md ghi model la `soniox-2`, nhung code thuc te su dung `stt-rt-v4` (`soniox_client.py`, dong 78). Documentation cung ghi `max_num_speakers: 4` nhung code khong gui field nay.
- **Impact:** Developer doc lai code se bi nham lan.
- **Suggested Fix:** Cap nhat CLAUDE.md voi model name chinh xac (`stt-rt-v4`) va ghi chu rang `max_num_speakers` chua duoc implement.
- **GitHub Repo Reference:** N/A

---

## 2. Features Working Correctly

| # | Feature | Ghi chu |
|---|---------|---------|
| 1 | **PyQt6 GUI voi dark theme** | Giao dien dep, nhat quan. QSS stylesheet (main.py:147-212) cover tat ca widgets. |
| 2 | **Speaker diarization display** | 0-based -> 1-indexed conversion chinh xac. 4 mau speaker hien thi dung. Header chi chen khi speaker thay doi. |
| 3 | **Soniox WebSocket connection** | Connect, send config, receive tokens — pipeline day du va chinh xac. |
| 4 | **Audio capture (mic + system rieng le)** | sounddevice capture, chuyen doi PCM 16-bit 16kHz mono chinh xac. |
| 5 | **Provisional text display** | Mau xam (#666) cho provisional, thay the bang final text (#e0e0e0). Hoat dong tot khi 1 speaker. |
| 6 | **Google Translate fallback** | translate.py su dung free endpoint, xu ly empty text va src==dest dung. Timeout 5s hop ly. |
| 7 | **Bidirectional translation (explicit languages)** | Khi ca source va target duoc chi dinh ro rang, logic dich 2 chieu chinh xac. |
| 8 | **Session auto-save on stop** | _stop() -> _auto_save_session() luu Markdown file voi original + translation. |
| 9 | **Session save voi file explorer** | Click Save mo file explorer highlight file vua luu (Windows, macOS, Linux). |
| 10 | **Copy to clipboard** | Gom ca original va translation voi separator. |
| 11 | **Font size controls** | A-/A+ nut (9-36 range), luu vao config. |
| 12 | **Scroll Lock toggle** | Tam dung auto-scroll de doc lai transcript cu. |
| 13 | **Settings dialog** | Config API key (masked), languages, audio source, font size, always-on-top, context terms. |
| 14 | **Always-on-top mode** | Toggle trong Settings, su dung Qt.WindowStaysOnTopHint. |
| 15 | **Reconnection logic** | 3 lan reconnect voi delay tang dan [2, 4, 6]s. Session reset moi 3 phut voi context carryover. |
| 16 | **Keepalive mechanism** | Ping moi 15s giu WebSocket connection. |
| 17 | **Thread safety (Qt signals)** | _Bridge class su dung pyqtSignal de communicate giua worker threads va main thread. |
| 18 | **Context terms support** | User co the nhap terms trong Settings, duoc gui den Soniox trong config.context.terms. |
| 19 | **Context carryover on session reset** | 500 ky tu cuoi cung duoc gui kem khi reconnect sau session reset 3 phut. |
| 20 | **Soniox built-in translation (two_way)** | Khi source va target duoc chi dinh, Soniox tra ve ban dich truc tiep — khong can Google Translate. |

---

## 3. Priority Fix Recommendations

### Uu tien 1: BUG-008 — Them target language vao language_hints
- **Ly do:** Fix don gian (1 dong code), tac dong lon — cai thien do chinh xac nhan dien ngon ngu cho cuoc hop 2 chieu.
- **Effort:** Rat thap (~5 phut)

### Uu tien 2: BUG-002 — Ho tro one_way translation khi source = "auto"
- **Ly do:** Che do "auto" la lua chon pho bien nhat cho user moi. Hien tai no mat hoan toan Soniox translation, chi dung Google Translate.
- **Effort:** Thap (~30 phut)

### Uu tien 3: BUG-001 — Thay hardcoded "ja" fallback
- **Ly do:** Lien quan den BUG-002 — khi fix auto mode, fallback nay cung can fix. Co the giai quyet dong thoi.
- **Effort:** Thap (~15 phut)

### Uu tien 4: BUG-004 — Fix is_final determination
- **Ly do:** Co the gay dich sai khi Soniox gui mixed tokens. Chuyen `any()` sang `all()` hoac tach xu ly.
- **Effort:** Thap (~15 phut)

### Uu tien 5: BUG-003 — Fix provisional text race condition
- **Ly do:** Anh huong truc tiep den UX khi co > 1 speaker. Can refactor _provisional_start thanh per-speaker tracking.
- **Effort:** Trung binh (~2 gio)

### Uu tien 6: BUG-005 — Them max_num_speakers vao Soniox config
- **Ly do:** Dam bao nhat quan giua config va display code. 1 dong code.
- **Effort:** Rat thap (~5 phut)

### Uu tien 7: BUG-006 — Them UI warning cho "Both" mode
- **Ly do:** User experience — tranh nham lan khi chon mode nay.
- **Effort:** Thap (~15 phut)

### Uu tien 8: BUG-010 — Cap nhat CLAUDE.md
- **Ly do:** Documentation chinh xac giup development nhanh hon.
- **Effort:** Rat thap (~10 phut)

---

## 4. Improvements from GitHub Repo (phuc-nt/my-translator)

### 4.1 Pattern dang hoc hoi NGAY (lien quan truc tiep den bugs)

| Bug | GitHub repo lam tot hon | File tham khao | Do uu tien |
|-----|------------------------|----------------|------------|
| BUG-002 | Ho tro `one_way` translation khi chi co target language | `src/js/soniox.js:118-131` | CAO |
| BUG-003 | Rebuild HTML tu segments array thay vi cursor manipulation -> khong co race condition | `src/js/ui.js:361-411` | CAO |
| BUG-008 | Gui CA HAI ngon ngu trong language_hints khi two_way | `src/js/soniox.js:125` | CAO |
| BUG-006 | Disable TTS khi "Both" mode de tranh feedback | `src/js/app.js:741-745` | TRUNG BINH |

### 4.2 Tinh nang nen them (tu GitHub repo)

| # | Tinh nang | Mo ta | File tham khao | Do uu tien |
|---|-----------|-------|----------------|------------|
| 1 | **Endpoint delay config** | Cho phep user dieu chinh `max_endpoint_delay_ms` (balance toc do vs chinh xac) | `src/js/soniox.js:102` | Trung binh |
| 2 | **Rich context builder** | General context, transcription terms, translation terms, text context | `src/js/soniox.js:405-449` | Trung binh |
| 3 | **Stale segment cleanup** | Xoa original segments > 10s chua co translation | `src/js/ui.js:511-531` | Trung binh |
| 4 | **Confidence score display** | Highlight low-confidence segments | `src/js/soniox.js:296-299` | Thap |
| 5 | **Language badge** | Hien thi co ngon ngu khi speaker doi ngon ngu | `src/js/ui.js:385-387` | Thap |
| 6 | **Keyboard shortcuts** | Ctrl+Enter (start/stop), Ctrl+S (save) | `src/js/app.js:425-513` | Thap |
| 7 | **Session browser** | Xem session cu trong app | `src/js/app.js:1543-1601` | Thap |
| 8 | **Edge TTS** | Doc ban dich thanh tieng (mien phi) | `src/js/edge-tts.js` + `src-tauri/src/commands/edge_tts.rs` | Thap |
| 9 | **Segment trimming** | Gioi han so ky tu hien thi, session log rieng khong bi trim | `src/js/ui.js:495-504, 72-80` | Thap |

### 4.3 Pattern code cu the nen adopt

**1. One-way + Two-way translation toggle** (fix BUG-002):
```python
# Thay vi:
src = self._source_language if self._source_language != "auto" else None
if src and tgt and src != tgt:
    cfg["translation"] = {"type": "two_way", ...}

# Lam:
if src and tgt and src != tgt:
    cfg["translation"] = {"type": "two_way", "language_a": src, "language_b": tgt}
    cfg["language_hints"] = [src, tgt]  # fix BUG-008
elif tgt:
    cfg["translation"] = {"type": "one_way", "target_language": tgt}
```

**2. Dual language_hints** (fix BUG-008):
```python
# Them trong _build_config(), sau khi set translation:
if src and tgt:
    cfg["language_hints"] = [src, tgt]
elif tgt:
    cfg["language_hints"] = [tgt]
```

**3. Stale segment cleanup** (pattern tu GitHub):
```python
# Them trong MainWindow:
def _cleanup_stale_segments(self):
    """Xoa segments original qua 10s chua co translation."""
    now = time.time()
    STALE_MS = 10.0
    self._pending_segments = [
        s for s in self._pending_segments
        if (now - s['created_at']) <= STALE_MS
    ]
```

---

## Tong ket

- **Tong so bugs:** 10 (0 Critical, 3 Major, 4 Minor, 2 Cosmetic, 1 Documentation)
- **Features hoat dong tot:** 20 tinh nang da xac nhan
- **Top 3 bugs can fix ngay:** BUG-008 (language_hints), BUG-002 (one_way translation), BUG-001 (hardcoded "ja")
- **Nhan xet tong the:** App co nen tang tot voi kien truc don gian, de hieu. Cac bugs chu yeu lien quan den che do "auto" (source language) va xu ly multi-speaker concurrent. Khong co bug nao la showstopper cho truong hop su dung chinh (2 nguoi noi, explicit languages). Cac fix uu tien 1-4 co the hoan thanh trong 1 gio va se cai thien dang ke chat luong.
