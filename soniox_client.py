"""Soniox WebSocket client for real-time STT + speaker diarization + translation."""
import json
import threading
import time
import websocket


SONIOX_WS_URL = "wss://stt-rt.soniox.com/transcribe-websocket"

SESSION_RESET_INTERVAL = 180
MAX_RECONNECT_ATTEMPTS = 3
RECONNECT_DELAYS = [2, 4, 6]
CARRYOVER_CHARS = 500


class SonioxSegment:
    __slots__ = ("text", "translated", "speaker", "is_final", "language")

    def __init__(self, text: str, translated: str, speaker: int,
                 is_final: bool, language: str = ""):
        self.text = text
        self.translated = translated
        self.speaker = speaker
        self.is_final = is_final
        self.language = language


class SonioxClient:
    def __init__(
        self,
        api_key: str,
        source_language: str = "ja",
        target_language: str = "vi",
        on_segment=None,
        on_error=None,
        on_connected=None,
        on_disconnected=None,
        on_reconnecting=None,
        enable_diarization: bool = True,
        context_terms: str = "",
    ):
        self._api_key = api_key
        self._source_language = source_language
        self._target_language = target_language
        self._on_segment = on_segment
        self._on_error = on_error
        self._on_connected = on_connected
        self._on_disconnected = on_disconnected
        self._on_reconnecting = on_reconnecting
        self._enable_diarization = enable_diarization
        self._context_terms = context_terms

        self._ws: websocket.WebSocketApp | None = None
        self._thread: threading.Thread | None = None
        self._connected = False
        self._audio_queue: list[bytes] = []
        self._queue_lock = threading.Lock()
        self._send_thread: threading.Thread | None = None
        self._keepalive_thread: threading.Thread | None = None
        self._running = False

        self._intentional_stop = False
        self._reconnect_count = 0
        self._session_timer: threading.Timer | None = None
        self._session_resetting = False
        self._recent_texts: list[str] = []
        self._carryover_text = ""

    def connect(self):
        self._intentional_stop = False
        self._running = True
        self._reconnect_count = 0
        self._do_connect()

    def _build_config(self) -> dict:
        cfg = {
            "api_key": self._api_key,
            "model": "stt-rt-v4",
            "audio_format": "pcm_s16le",
            "sample_rate": 16000,
            "num_channels": 1,
            "enable_endpoint_detection": True,
            "enable_speaker_diarization": self._enable_diarization,
            "enable_language_identification": True,
        }
        if self._source_language and self._source_language != "auto":
            cfg["language_hints"] = [self._source_language]

        src = self._source_language if self._source_language != "auto" else None
        tgt = self._target_language
        if src and tgt and src != tgt:
            cfg["translation"] = {
                "type": "two_way",
                "language_a": src,
                "language_b": tgt,
            }

        ctx = {}
        if self._context_terms:
            terms = [t.strip() for t in self._context_terms.split(",") if t.strip()]
            if terms:
                ctx["terms"] = terms
        if self._carryover_text:
            ctx["text"] = self._carryover_text
        if ctx:
            cfg["context"] = ctx

        return cfg

    def _do_connect(self):
        def on_open(ws):
            self._connected = True
            cfg = self._build_config()
            print(f"[Soniox] Sending config: {json.dumps({k: v for k, v in cfg.items() if k != 'api_key'})}")
            ws.send(json.dumps(cfg))
            if self._on_connected:
                self._on_connected()
            self._send_thread = threading.Thread(target=self._sender_loop, daemon=True)
            self._send_thread.start()
            self._keepalive_thread = threading.Thread(target=self._keepalive_loop, daemon=True)
            self._keepalive_thread.start()
            self._start_session_timer()

        def on_message(ws, message):
            try:
                data = json.loads(message)
                if "error" in data:
                    print(f"[Soniox] Server error: {data['error']}")
                    if self._on_error:
                        self._on_error(data["error"])
                    return
                self._handle_response(data)
            except Exception as e:
                print(f"[Soniox] Parse error: {e}")

        def on_error(ws, error):
            print(f"[Soniox] WebSocket error: {error}")
            self._connected = False

        def on_close(ws, code, msg):
            print(f"[Soniox] WebSocket closed: code={code}, msg={msg}")
            self._connected = False
            self._cancel_session_timer()

            if self._intentional_stop:
                self._running = False
                if self._on_disconnected:
                    self._on_disconnected()
            elif self._session_resetting:
                self._session_resetting = False
                self._reconnect_count = 0
                threading.Thread(target=self._do_reconnect, args=(0.5,), daemon=True).start()
            elif self._running:
                threading.Thread(target=self._do_reconnect, daemon=True).start()

        self._ws = websocket.WebSocketApp(
            SONIOX_WS_URL,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
        )
        self._thread = threading.Thread(
            target=self._ws.run_forever, kwargs={"ping_interval": 20}, daemon=True
        )
        self._thread.start()

    def _do_reconnect(self, delay=None):
        if self._reconnect_count >= MAX_RECONNECT_ATTEMPTS:
            self._running = False
            if self._on_error:
                self._on_error("Connection lost after 3 reconnect attempts")
            if self._on_disconnected:
                self._on_disconnected()
            return

        if delay is None:
            delay = RECONNECT_DELAYS[min(self._reconnect_count, len(RECONNECT_DELAYS) - 1)]

        self._reconnect_count += 1
        attempt = self._reconnect_count
        print(f"[Soniox] Reconnecting in {delay}s (attempt {attempt}/{MAX_RECONNECT_ATTEMPTS})...")
        if self._on_reconnecting:
            self._on_reconnecting(attempt, MAX_RECONNECT_ATTEMPTS)

        time.sleep(delay)
        if self._running and not self._intentional_stop:
            self._do_connect()

    def _start_session_timer(self):
        self._cancel_session_timer()
        self._session_timer = threading.Timer(SESSION_RESET_INTERVAL, self._session_reset)
        self._session_timer.daemon = True
        self._session_timer.start()

    def _cancel_session_timer(self):
        if self._session_timer:
            self._session_timer.cancel()
            self._session_timer = None

    def _session_reset(self):
        if not self._running or self._intentional_stop:
            return
        print("[Soniox] Session reset (3 min) — reconnecting with context carryover...")
        self._carryover_text = "".join(self._recent_texts)[-CARRYOVER_CHARS:]
        self._recent_texts.clear()
        self._session_resetting = True
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass

    def _sender_loop(self):
        while self._running and self._connected:
            chunks = []
            with self._queue_lock:
                if self._audio_queue:
                    chunks = self._audio_queue[:]
                    self._audio_queue.clear()
            for chunk in chunks:
                if self._ws and self._connected:
                    try:
                        self._ws.send(chunk, websocket.ABNF.OPCODE_BINARY)
                    except Exception as e:
                        print(f"[Soniox] Send error: {e}")
                        break
            time.sleep(0.05)

    def _keepalive_loop(self):
        while self._running and self._connected:
            time.sleep(15)
            if self._ws and self._connected:
                try:
                    self._ws.send(json.dumps({"type": "keepalive"}))
                except Exception:
                    pass

    def send_audio(self, pcm_bytes: bytes):
        if self._running:
            with self._queue_lock:
                self._audio_queue.append(pcm_bytes)

    def _handle_response(self, data: dict):
        tokens = data.get("tokens", [])
        if not tokens:
            return

        speaker_original: dict[int, list] = {}
        speaker_translation: dict[int, list] = {}

        for token in tokens:
            speaker = token.get("speaker", 0) or 0
            text = token.get("text", "")
            is_final = token.get("is_final", False)
            lang = token.get("language", "")
            status = token.get("translation_status", "original")

            entry = (text, is_final, lang)
            if status == "translation":
                if speaker not in speaker_translation:
                    speaker_translation[speaker] = []
                speaker_translation[speaker].append(entry)
            else:
                if speaker not in speaker_original:
                    speaker_original[speaker] = []
                speaker_original[speaker].append(entry)

        for speaker, parts in speaker_original.items():
            original_text = "".join(p[0] for p in parts)
            is_final = any(p[1] for p in parts)
            language = parts[-1][2] if parts else ""

            trans_parts = speaker_translation.get(speaker, [])
            translated_text = "".join(p[0] for p in trans_parts)

            if original_text.strip():
                if is_final:
                    self._recent_texts.append(original_text)
                seg = SonioxSegment(
                    text=original_text,
                    translated=translated_text,
                    speaker=speaker + 1,
                    is_final=is_final,
                    language=language,
                )
                if self._on_segment:
                    self._on_segment(seg)

    def disconnect(self):
        self._intentional_stop = True
        self._running = False
        self._connected = False
        self._cancel_session_timer()
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
