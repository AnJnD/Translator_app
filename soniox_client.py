"""Soniox WebSocket client for real-time STT + speaker diarization + translation."""
import json
import threading
import time
import websocket


SONIOX_WS_URL = "wss://stt-rt.soniox.com/transcribe-websocket"


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
        enable_diarization: bool = True,
    ):
        self._api_key = api_key
        self._source_language = source_language
        self._target_language = target_language
        self._on_segment = on_segment
        self._on_error = on_error
        self._on_connected = on_connected
        self._on_disconnected = on_disconnected
        self._enable_diarization = enable_diarization

        self._ws: websocket.WebSocketApp | None = None
        self._thread: threading.Thread | None = None
        self._connected = False
        self._audio_queue: list[bytes] = []
        self._queue_lock = threading.Lock()
        self._send_thread: threading.Thread | None = None
        self._keepalive_thread: threading.Thread | None = None
        self._running = False

    def connect(self):
        self._running = True

        def on_open(ws):
            self._connected = True
            config = {
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
                config["language_hints"] = [self._source_language]

            src = self._source_language if self._source_language != "auto" else None
            tgt = self._target_language
            if src and tgt and src != tgt:
                config["translation"] = {
                    "type": "two_way",
                    "language_a": src,
                    "language_b": tgt,
                }

            print(f"[Soniox] Sending config: {json.dumps({k: v for k, v in config.items() if k != 'api_key'})}")
            ws.send(json.dumps(config))
            if self._on_connected:
                self._on_connected()

            self._send_thread = threading.Thread(target=self._sender_loop, daemon=True)
            self._send_thread.start()
            self._keepalive_thread = threading.Thread(target=self._keepalive_loop, daemon=True)
            self._keepalive_thread.start()

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
            if self._on_error:
                self._on_error(str(error))

        def on_close(ws, code, msg):
            print(f"[Soniox] WebSocket closed: code={code}, msg={msg}")
            self._connected = False
            self._running = False
            if self._on_disconnected:
                self._on_disconnected()

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
        if self._connected:
            with self._queue_lock:
                self._audio_queue.append(pcm_bytes)

    def _handle_response(self, data: dict):
        tokens = data.get("tokens", [])
        if not tokens:
            return

        # Separate original and translation tokens by speaker
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
        self._running = False
        self._connected = False
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
