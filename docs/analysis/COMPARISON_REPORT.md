# Bao cao So sanh Chi tiet: Local App vs GitHub Repo (my-translator)

**Ngay tao:** 2026-05-25
**Local App:** Meeting Translator (Python/PyQt6)
**GitHub Repo:** My Translator v0.5.0 (Tauri + Rust + HTML/JS)

---

## 1. Diem giong nhau ve kien truc

### 1.1 Core Pipeline giong nhau
Ca hai app deu su dung cung mot luong du lieu co ban:
- **Audio Capture** -> **Soniox STT** (WebSocket) -> **Translation** -> **UI Display**
- Ca hai deu ket noi den cung endpoint: `wss://stt-rt.soniox.com/transcribe-websocket`
- Ca hai deu su dung model `stt-rt-v4` (trước day la `soniox-2`, nay la `stt-rt-v4`)
- Ca hai deu gui audio dang PCM s16le, 16kHz, mono

### 1.2 Soniox Configuration tuong tu
Ca hai deu gui config message voi cac field giong nhau:
- `api_key`, `model`, `audio_format`, `sample_rate`, `num_channels`
- `enable_endpoint_detection: true`
- `enable_speaker_diarization: true`
- `enable_language_identification: true`
- `language_hints` khi source language khong phai "auto"

### 1.3 Speaker Diarization
Ca hai deu ho tro speaker diarization va hien thi speaker labels.

### 1.4 Provisional Text
Ca hai deu xu ly provisional (tam thoi) va final text tu Soniox — hien thi provisional mau mo, thay the bang final text.

### 1.5 Audio Source Options
Ca hai deu ho tro 3 che do: Microphone, System Audio, Both.

### 1.6 Session Save
Ca hai deu luu transcript dang Markdown.

---

## 2. Diem khac nhau ve logic (chi tiet, co dan chung)

### 2.1 Audio Capture Approach

**Local App** (`audio_capture.py`, dong 1-122):
- Su dung **sounddevice** (Python binding cua PortAudio)
- Truc tiep capture o 16kHz mono (dong 68-74): `samplerate=SAMPLE_RATE, channels=CHANNELS`
- Tim WASAPI loopback bang keyword matching (dong 36-54): `"loopback", "stereo mix", "what u hear"`
- Block size 4000 samples (~250ms per chunk) (dong 8)
- Callback truc tiep chuyen doi va gui audio (dong 25-31)

**GitHub Repo** — Co 3 module rieng biet:
- **Microphone** (`src-tauri/src/audio/microphone.rs`, dong 1-278): Su dung **cpal** (Rust), ho tro nhieu sample format (F32, I16), co linear interpolation resampler
- **macOS System Audio** (`src-tauri/src/audio/system_audio.rs`, dong 1-159): Su dung **ScreenCaptureKit** native API, capture 48kHz stereo roi downsample ve 16kHz mono
- **Windows System Audio** (`src-tauri/src/audio/wasapi.rs`, dong 1-283): Su dung **WASAPI loopback** truc tiep qua Windows COM API, capture tu default render endpoint
- Audio forwarding (`src-tauri/src/commands/audio.rs`, dong 85-121): Batching audio moi **200ms** truoc khi gui len JS frontend

**Nhan xet:** GitHub repo co native WASAPI va ScreenCaptureKit, khong can tim loopback device bang keyword. Resampling chat luong hon (linear interpolation vs simple step_by). Batching 200ms giup giam overhead IPC.

### 2.2 STT Integration (Soniox Config)

**Local App** (`soniox_client.py`, dong 56-81):
- Model: `stt-rt-v4` (dong 60)
- Translation config: chi ho tro `two_way` (dong 73-78)
- Language hints: chi source language (dong 69)
- KHONG co `max_endpoint_delay_ms`
- KHONG co `language_hints_strict`
- KHONG co context/domain hints
- KHONG co session reset (chay lien tuc cho den khi disconnect)

**GitHub Repo** (`src/js/soniox.js`, dong 91-137):
- Model: `stt-rt-v4` (dong 98)
- Ho tro CA HAI `one_way` va `two_way` translation (dong 118-131)
- `max_endpoint_delay_ms` co the cau hinh (dong 102, mac dinh 3000ms)
- `language_hints_strict` option (dong 113-115)
- Khi two_way: gui language_hints cho CA HAI ngon ngu (dong 125)
- Rich context support: `general`, `terms`, `text`, `translation_terms` (dong 134, va `_buildContext` dong 405-449)
- **Session reset** moi 3 phut voi context carryover (dong 23, 348-376)

**Nhan xet:** GitHub repo co nhieu tuy chinh Soniox hon dang ke. Dac biet, session reset moi 3 phut va context carryover la tinh nang quan trong cho cac cuoc hop dai.

### 2.3 Translation Strategy

**Local App** (`main.py` dong 464-508, `translator.py` dong 1-39):
- **Uu tien Soniox built-in translation** (dong 475-476): Neu `soniox_translated.strip()` co noi dung -> su dung truc tiep
- **Fallback Google Translate** (dong 483-508): Chi khi Soniox khong tra ve translation
- Google Translate su dung free endpoint `translate.googleapis.com/translate_a/single?client=gtx` (dong 27)
- Logic dich 2 chieu tu dong (dong 489-497): Phat hien ngon ngu cua nguoi noi va tu dong dao chieu

**GitHub Repo** (`src/js/soniox.js` dong 268-344):
- **Chi su dung Soniox built-in translation** — KHONG co Google Translate fallback
- Phan loai token theo `translation_status`: `"original"`, `"translation"`, `"none"` (dong 301-318)
- `translation_status: "none"` (ngon ngu thu 3 trong two-way mode) duoc xu ly nhu original (dong 311-317)
- Co **local pipeline mode** (`scripts/local_pipeline.py`): Dung Whisper MLX + Gemma-3 LLM de chay offline tren Apple Silicon

**Nhan xet:** Local app co loi the voi Google Translate fallback (dam bao luon co ban dich). GitHub repo linh hoat hon voi 2 mode (cloud + local offline).

### 2.4 Speaker Diarization Handling

**Local App** (`soniox_client.py` dong 157-200, `config.py` dong 17-23):
- Speaker 0-based tu Soniox duoc chuyen sang 1-indexed (dong 195): `speaker=speaker + 1`
- Nhom token theo speaker truoc khi tao segment (dong 163-189)
- 5 mau speaker (dong 17-23 config.py)
- Speaker header hien thi voi ten va timestamp: `[Speaker 1 - 14:30:00]`

**GitHub Repo** (`src/js/soniox.js` dong 286-289, `src/js/ui.js` dong 377-382):
- Su dung speaker truc tiep tu token (dong 287-289): `speaker = token.speaker`
- Hien thi speaker label khi speaker thay doi (dong 379-381 ui.js): `Speaker ${seg.speaker}:`
- Hien thi language badge khi ngon ngu thay doi (dong 385-387 ui.js)
- Confidence score tracking (dong 296-299 soniox.js): highlight low-confidence segments

**Nhan xet:** GitHub repo co language badge va confidence tracking — hai tinh nang huu ich ma local app chua co.

### 2.5 Provisional/Streaming Text Handling

**Local App** (`main.py` dong 512-544):
- Theo doi `_provisional_start` (vi tri character) de biet doan provisional text (dong 222)
- Khi co provisional moi: xoa provisional cu, chen provisional moi tai vi tri cu (dong 518-540)
- Khi co final: xoa provisional, chen final text (dong 546-577)
- Provisional mau `#666`, final mau `#e0e0e0`
- Su dung QTextCursor operations truc tiep

**GitHub Repo** (`src/js/ui.js` dong 120-136):
- Provisional text luu trong `this.provisionalText` (dong 123)
- Moi lan render, toan bo HTML duoc rebuild tu segments array (dong 361-411)
- Co stale original cleanup: xoa originals > 10s chua co translation (dong 511-531)
- Co trim segments khi vuot qua maxChars (dong 495-504)
- Session log rieng biet, KHONG bi trim (dong 72-80)

**Nhan xet:** GitHub repo co tinh nang stale cleanup tot hon (tranh tich tu segments loi). Local app su dung text cursor manipulation truc tiep, hieu qua hon cho document lon nhung kho maintain.

### 2.6 Threading/Async Model

**Local App:**
- **Main thread**: PyQt6 event loop
- **WebSocket thread**: `run_forever()` trong daemon thread (dong 122-125 soniox_client.py)
- **Audio sender thread**: `_sender_loop()` gui audio moi 50ms (dong 127-141)
- **Keepalive thread**: gui keepalive moi 15s (dong 143-150)
- **Audio callback threads**: sounddevice callbacks
- **Translation threads**: Moi segment tao 1 daemon thread moi (dong 508 main.py)
- Cross-thread: `pyqtSignal` qua `_Bridge` class (dong 26-31 main.py)

**GitHub Repo:**
- **Frontend**: Single-threaded JS event loop (async/await)
- **Backend Rust**: Multi-threaded (Tauri commands chay trong thread pool)
- **Audio forwarding**: Rust thread bat audio, batch 200ms, gui qua IPC Channel (dong 85-121 audio.rs)
- **Soniox WebSocket**: Browser native WebSocket (async, non-blocking)
- **TTS**: Queue-based processing (dong 42-72 edge-tts.js)
- IPC: Tauri Channel (Rust -> JS) va invoke (JS -> Rust)

**Nhan xet:** GitHub repo co kien truc ro rang hon voi Rust backend xu ly performance-critical tasks (audio capture, resampling) va JS frontend xu ly UI. Local app don gian hon nhung tao nhieu threads nho (moi translation la 1 thread moi).

### 2.7 UI Architecture

**Local App** (`main.py` dong 203-661):
- **PyQt6** desktop native voi QSS dark theme (dong 147-198)
- 2 panel: Original Transcript + Translation, chia bang QSplitter (dong 327-344)
- QTextEdit read-only voi text formatting qua QTextCharFormat
- Font size controls (A-/A+), Scroll Lock
- Copy, Save, Clear buttons
- Settings dialog rieng (SettingsDialog class)

**GitHub Repo** (`src/js/app.js`, `src/js/ui.js`, `src/index.html`, `src/styles/main.css`):
- **Tauri** (Rust) + HTML/CSS/JS frontend
- Single-page overlay design voi 3 views: overlay, settings, sessions
- **Single view mode** (chi translation) va **Dual view mode** (original + translation)
- Overlay opacity co the dieu chinh (0-100%)
- **Always-on-top** mac dinh bat, co toggle
- **Compact mode** (an control bar)
- **Keyboard shortcuts**: Cmd+Enter (start/stop), Cmd+T (TTS), Cmd+1/2/3 (source), Cmd+P (pin), Cmd+D (compact)
- Font color picker (color dots)
- Max lines gioi han (tranh UI bi day)
- Toast notifications thay vi QMessageBox
- **Tab-based settings**: tach rieng STT, Display, TTS, About
- **Session history browser**: list + viewer trong app

**Nhan xet:** GitHub repo co UI phong phu va hien dai hon nhieu. Overlay mode, keyboard shortcuts, compact mode, va session browser la nhung tinh nang ma local app chua co.

### 2.8 TTS Capabilities

**Local App:**
- **KHONG co TTS** — chi hien thi text

**GitHub Repo** — 3 TTS providers:
- **Edge TTS** (mien phi, dong 1-87 edge-tts.js + dong 1-175 edge_tts.rs): Proxy qua Rust backend, DRM token generation, SSML support, speed control
- **ElevenLabs** (premium, dong 1-228 elevenlabs-tts.js): WebSocket streaming, Flash v2.5 model, TTFB tracking
- **Google Cloud TTS** (dong 1-138 google-tts.js): Chirp 3 HD voices, REST API
- **AudioPlayer** (dong 1-158 audio-player.js): Queue-based playback voi Web Audio API, backlog management
- TTS tu dong doc ban dich moi (dong 902-906 app.js)
- TTS bi disable trong two-way mode de tranh audio feedback loop (dong 741-745 app.js)

**Nhan xet:** Day la diem khac biet LON nhat. TTS la tinh nang rat gia tri cho accessibility va user experience.

### 2.9 Session Management

**Local App** (`main.py` dong 635-655):
- Luu manual khi user click Save (dong 636-655)
- Luu tai `~/.translator_meeting/sessions/session_{timestamp}.md`
- Mo file explorer sau khi luu (dong 650-655)
- Format don gian: header + original text + translation text

**GitHub Repo** (`src-tauri/src/commands/transcript.rs`, `src/js/app.js` dong 1384-1413, `src/js/ui.js` dong 284-313):
- **Auto-save** khi stop recording (dong 1355-1359 app.js)
- Luu tai app data dir (`com.personal.translator/transcripts/`)
- YAML frontmatter voi metadata: date, time, duration, source_lang, target_lang, mode, audio_source, model, segments count (dong 289-300 ui.js)
- **Session browser** trong app: list sessions, click de xem (dong 1543-1601 app.js)
- **Session log rieng biet** khong bi trim (dong 72-80 ui.js): dam bao luu day du du display buffer bi cat

**Nhan xet:** GitHub repo co session management tot hon nhieu — auto-save, metadata phong phu, va in-app browser.

### 2.10 Error Handling & Reconnection

**Local App** (`soniox_client.py` dong 90-113):
- Error callback don gian: `on_error(str(error))` (dong 106)
- Khi WebSocket close: goi `on_disconnected()`, KHONG co auto-reconnect (dong 108-113)
- Khi WebSocket error: set `_connected = False` (dong 103-106)
- UI: Status label va dot indicator

**GitHub Repo** (`src/js/soniox.js` dong 470-516):
- **Auto-reconnect** voi max 3 lan (dong 19-20): `MAX_RECONNECT = 3`
- Reconnect delay tang dan: `RECONNECT_DELAY_MS * attempts` (dong 504)
- Chi tiet error codes: 4001/4003 (invalid key), 4029 (rate limit), 4002 (subscription), 1006 (connection lost) (dong 216-229)
- API error handling: 401, 429, 402, 400, 408 (dong 470-494)
- Context carryover khi reconnect (dong 512-514)
- **Seamless session reset** moi 3 phut — make-before-break: mo connection moi TRUOC khi dong connection cu (dong 366-376)
- Toast notifications cho loi cu the: "Invalid API key", "Rate limit exceeded", "Subscription issue"

**Nhan xet:** GitHub repo co error handling va reconnection vuot troi. Local app se mat ket noi vinh vien khi co loi mang tam thoi.

### 2.11 Context/Domain Hints gui den Soniox

**Local App** (`soniox_client.py` dong 56-81):
- Chi gui `language_hints` (dong 69)
- KHONG co context object
- KHONG co domain hints, terms, translation_terms

**GitHub Repo** (`src/js/soniox.js` dong 405-449, `src/js/app.js` dong 656-687):
- **General context**: Array cua `{key, value}` pairs (vd: domain=Medical) (dong 410-421)
- **Transcription terms**: Danh sach tu chuyen nganh de tang do chinh xac (dong 423-426)
- **Translation terms**: Mapping `{source, target}` (dong 429-432)
- **Text context**: Background text + carryover tu session truoc (dong 435-448)
- **Context carryover**: 500 ky tu cuoi cua ban dich gan day duoc gui khi session reset (dong 26-27, 452-466)
- UI cho phep user nhap context trong Settings (dong 580-604 app.js)

**Nhan xet:** Context/domain hints la tinh nang cuc ky quan trong cho do chinh xac dich thuat trong cac cuoc hop chuyen nganh (y te, ky thuat, phap ly). Local app hoan toan thieu tinh nang nay.

---

## 3. Cach tiep can nao tot hon cho tung phan va tai sao

### 3.1 Audio Capture
**Tot hon: GitHub Repo**
- Native WASAPI (Windows) va ScreenCaptureKit (macOS) cho hieu suat va do tin cay cao hon
- Linear interpolation resampling chat luong am thanh tot hon step_by
- macOS: `excludes_current_process_audio` ngan TTS feedback loop
- Tuy nhien, local app don gian hon va de maintain voi sounddevice

### 3.2 STT Integration
**Tot hon: GitHub Repo**
- Session reset moi 3 phut tranh timeout va degradation
- Context carryover dam bao tinh lien tuc
- `max_endpoint_delay_ms` cho phep user dieu chinh do nhanh nhan dien
- `language_hints_strict` cho truong hop chi can 2 ngon ngu cu the
- One-way va two-way translation options

### 3.3 Translation Strategy
**Local App tot hon o diem:** co Google Translate fallback khi Soniox translation fail
**GitHub Repo tot hon o diem:** co local offline mode (Whisper + Gemma-3)
**De xuat:** Ket hop ca hai — su dung Soniox translation chinh, fallback Google Translate, va co option offline

### 3.4 Error Handling & Reconnection
**Tot hon: GitHub Repo** (ro rang)
- Auto-reconnect la MUST HAVE cho ung dung real-time
- Make-before-break session reset dam bao khong mat audio
- Chi tiet error codes giup user hieu va xu ly van de

### 3.5 UI/UX
**Tot hon: GitHub Repo**
- Overlay mode thich hop cho cuoc hop truc tuyen
- Keyboard shortcuts tang toc su dung
- Compact mode tiet kiem man hinh
- Toast notifications khong intrusive

**Local App tot hon o diem:**
- 2 panel song song luon hien thi (phu hop khi muon doc ca original lan translation)
- Native desktop feel voi PyQt6

### 3.6 TTS
**Tot hon: GitHub Repo** (local app KHONG co)
- Edge TTS mien phi va chat luong tot
- Nhieu provider cho user lua chon

### 3.7 Session Management
**Tot hon: GitHub Repo**
- Auto-save khong bi mat du lieu
- Session browser tien loi
- Metadata phong phu de tra cuu sau

---

## 4. Doan code trong GitHub repo ma app local nen hoc hoi

### 4.1 Auto-Reconnect Logic
**File:** `__temp_github_repo/src/js/soniox.js`, dong 496-516
```javascript
_tryReconnect(reason) {
    if (this._reconnectAttempts >= MAX_RECONNECT) {
        this._setStatus('error');
        this.onError?.(`${reason}. Reconnect failed after ${MAX_RECONNECT} attempts.`);
        return;
    }
    this._reconnectAttempts++;
    const delay = RECONNECT_DELAY_MS * this._reconnectAttempts;
    setTimeout(() => {
        if (!this._intentionalDisconnect && this._config) {
            const carryover = this._getCarryoverContext();
            this._doConnect(this._config, carryover);
        }
    }, delay);
}
```
Local app can implement tuong tu trong `soniox_client.py` — them reconnect logic trong `on_close` handler.

### 4.2 Session Reset voi Context Carryover
**File:** `__temp_github_repo/src/js/soniox.js`, dong 348-376, 452-466
```javascript
_seamlessReset() {
    const carryover = this._getCarryoverContext();
    this._doConnect(this._config, carryover);
}

_addToHistory(text) {
    this._recentTranslations.push(text);
    let total = this._recentTranslations.reduce((sum, t) => sum + t.length, 0);
    while (total > CONTEXT_HISTORY_CHARS && this._recentTranslations.length > 1) {
        const removed = this._recentTranslations.shift();
        total -= removed.length;
    }
}
```
Local app can: (1) Them timer 3 phut de reset session, (2) Luu 500 ky tu dich gan day, (3) Gui kem context.text khi reconnect.

### 4.3 Rich Context Builder
**File:** `__temp_github_repo/src/js/soniox.js`, dong 405-449
Context object format:
```javascript
{
    general: [{key: 'domain', value: 'Medical'}],
    terms: ['specific', 'technical', 'terms'],
    text: 'Background context...',
    translation_terms: [{source: '...', target: '...'}]
}
```
Local app can them context support trong config va gui kem trong Soniox config message.

### 4.4 Stale Original Cleanup
**File:** `__temp_github_repo/src/js/ui.js`, dong 511-531
```javascript
_cleanupStaleOriginals() {
    const now = Date.now();
    const STALE_MS = 10000;
    const MAX_PENDING = 3;
    this.segments = this.segments.filter(seg => {
        if (seg.status === 'original' && (now - seg.createdAt) > STALE_MS) {
            return false;
        }
        return true;
    });
}
```
Local app can implement tuong tu de tranh tich tu segments chua duoc dich.

### 4.5 Translation Type: One-Way va Two-Way Options
**File:** `__temp_github_repo/src/js/soniox.js`, dong 118-131
```javascript
if (translationType === 'two_way' && languageA && languageB) {
    configMsg.translation = {
        type: 'two_way',
        language_a: languageA,
        language_b: languageB,
    };
    configMsg.language_hints = [languageA, languageB];
} else if (targetLanguage) {
    configMsg.translation = {
        type: 'one_way',
        target_language: targetLanguage,
    };
}
```
Hien tai local app chi ho tro two_way. Them one_way option cho truong hop don gian (nguoi dung chi can dich 1 chieu).

### 4.6 Endpoint Delay Configuration
**File:** `__temp_github_repo/src/js/soniox.js`, dong 102
```javascript
max_endpoint_delay_ms: endpointDelay || 3000,
```
Cho phep user dieu chinh thoi gian Soniox cho de ket thuc phat ngon. Nho hon = phan hoi nhanh hon nhung co the cat cau. Lon hon = chinh xac hon nhung cham hon.

### 4.7 Confidence Score Tracking
**File:** `__temp_github_repo/src/js/soniox.js`, dong 296-299
```javascript
if (token.confidence !== undefined && token.is_final && token.translation_status === 'original') {
    confidenceSum += token.confidence;
    confidenceCount++;
}
```
Hien thi confidence giup user biet do tin cay cua ban dich.

### 4.8 Edge TTS Implementation (mien phi)
**File:** `__temp_github_repo/src-tauri/src/commands/edge_tts.rs`
**File:** `__temp_github_repo/src/js/edge-tts.js`
Day la tinh nang TTS mien phi va chat luong cao. Co the port sang Python voi thu vien `edge-tts` (pip install edge-tts).

### 4.9 Auto-Save on Stop
**File:** `__temp_github_repo/src/js/app.js`, dong 1355-1359
```javascript
if (this.transcriptUI.hasSessionContent()) {
    await this._saveTranscriptFile();
    this.transcriptUI.clearSession();
}
```
Local app nen tu dong luu khi stop thay vi chi luu khi user click Save.

### 4.10 Keyboard Shortcuts
**File:** `__temp_github_repo/src/js/app.js`, dong 425-513
Cmd/Ctrl + Enter (start/stop), Cmd+T (TTS), Cmd+1/2/3 (source switch), Cmd+P (pin), Cmd+D (compact).
Local app co the them QShortcut tuong tu trong PyQt6.

---

## 5. Tom tat va de xuat uu tien

### Uu tien CAO (Nen lam ngay)

| # | De xuat | Ly do | Do phuc tap |
|---|---------|-------|-------------|
| 1 | **Auto-reconnect khi mat ket noi** | Hien tai app die im khi mat mang, user phai restart. Day la bug nghiem trong cho ung dung real-time. | Trung binh |
| 2 | **Session reset moi 3 phut voi context carryover** | Soniox co the timeout hoac degrade sau thoi gian dai. Session reset dam bao chat luong on dinh. | Trung binh |
| 3 | **Auto-save transcript khi stop** | Hien tai chi save khi user click Save. Neu quen -> mat data. | Thap |
| 4 | **Them one_way translation option** | Hien tai chi co two_way. One_way don gian hon va phu hop cho nhieu truong hop. | Thap |

### Uu tien TRUNG BINH (Nen lam khi co thoi gian)

| # | De xuat | Ly do | Do phuc tap |
|---|---------|-------|-------------|
| 5 | **Context/domain hints cho Soniox** | Tang do chinh xac cho cac cuoc hop chuyen nganh. Them UI trong Settings de user nhap domain, terms, translation_terms. | Trung binh |
| 6 | **Endpoint delay setting** | Cho phep user dieu chinh balance giua toc do va do chinh xac. | Thap |
| 7 | **Confidence score hien thi** | Giup user biet doan nao co the khong chinh xac. | Thap |
| 8 | **Language badge** | Hien thi co ngon ngu ben canh speaker label khi ngon ngu thay doi. | Thap |
| 9 | **Keyboard shortcuts** | Ctrl+Enter (start/stop), Ctrl+S (save), v.v. Tang toc su dung. | Thap |
| 10 | **Stale segment cleanup** | Xoa segments qua 10s chua duoc dich de tranh tich tu loi. | Thap |

### Uu tien THAP (Nice-to-have)

| # | De xuat | Ly do | Do phuc tap |
|---|---------|-------|-------------|
| 11 | **TTS (Text-to-Speech)** | Doc ban dich thanh tieng. Co the dung `edge-tts` Python package (mien phi). | Cao |
| 12 | **Session browser** | Xem lai cac session cu trong app thay vi mo file explorer. | Trung binh |
| 13 | **Overlay/compact mode** | Cua so nho hon, trong suot, phu len cuoc hop. | Trung binh |
| 14 | **Dual view toggle** | Cho phep user chuyen giua hien thi 1 panel (chi translation) va 2 panel. | Thap |
| 15 | **YAML frontmatter** trong session files | Metadata phong phu: duration, languages, segment count de tra cuu. | Thap |

### Tom tat tong quat

Local app (Meeting Translator) co **nen tang tot** voi kien truc don gian, de hieu. Google Translate fallback la diem manh rieng. Tuy nhien, thieu nhieu tinh nang quan trong cho production use:

1. **Do tin cay**: Thieu auto-reconnect va session reset -> app khong on dinh trong cuoc hop dai
2. **Do chinh xac**: Thieu context hints, endpoint delay tuning, confidence tracking
3. **Trai nghiem nguoi dung**: Thieu TTS, keyboard shortcuts, auto-save, session browser
4. **Tinh linh hoat**: Thieu one_way option, language_hints_strict, view mode toggle

**De xuat tong the**: Tap trung vao 4 muc uu tien CAO truoc (reconnect, session reset, auto-save, one_way). Day la nhung thay doi co tac dong lon nhat voi do phuc tap vua phai, va deu co the hoc tu code cua GitHub repo.
