"""Audio capture: microphone and/or WASAPI loopback (system audio on Windows)."""
import threading
import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
CHANNELS = 1
BLOCK_SIZE = 4000  # ~250ms per chunk


def _to_pcm16(data: np.ndarray) -> bytes:
    mono = data.mean(axis=1) if data.ndim > 1 else data
    clipped = np.clip(mono, -1.0, 1.0)
    return (clipped * 32767).astype(np.int16).tobytes()


class AudioCapture:
    def __init__(self, on_audio, source="microphone"):
        self._on_audio = on_audio
        self._source = source
        self._streams: list[sd.InputStream] = []
        self._lock = threading.Lock()
        self._running = False

    def _mic_callback(self, indata, frames, time, status):
        if self._running:
            self._on_audio(_to_pcm16(indata))

    def _sys_callback(self, indata, frames, time, status):
        if self._running:
            self._on_audio(_to_pcm16(indata))

    def _find_loopback_device(self):
        """Find WASAPI loopback or virtual audio device for system audio capture."""
        devices = sd.query_devices()
        loopback_keywords = [
            "loopback", "stereo mix", "what u hear", "wave out mix", "rec. playback",
        ]
        # First pass: known loopback/virtual audio device names
        for i, dev in enumerate(devices):
            name = dev.get("name", "").lower()
            if dev.get("max_input_channels", 0) > 0:
                for keyword in loopback_keywords:
                    if keyword in name:
                        return i
        # Second pass: default output device usable as input (WASAPI loopback)
        try:
            default_out = sd.query_devices(kind="output")
            for i, dev in enumerate(devices):
                if dev.get("name") == default_out.get("name") and dev.get("max_input_channels", 0) > 0:
                    return i
        except Exception:
            pass
        return None

    def start(self):
        self._running = True
        self._streams = []

        if self._source == "both":
            print(
                "[Audio] WARNING: 'Both' mode sends mic and system audio as separate "
                "interleaved streams. For best accuracy, use a single source."
            )

        if self._source in ("microphone", "both"):
            try:
                stream = sd.InputStream(
                    samplerate=SAMPLE_RATE,
                    channels=CHANNELS,
                    dtype="float32",
                    blocksize=BLOCK_SIZE,
                    callback=self._mic_callback,
                )
                stream.start()
                self._streams.append(stream)
            except Exception as e:
                print(f"[Audio] Microphone error: {e}")

        if self._source in ("system", "both"):
            loopback_idx = self._find_loopback_device()
            if loopback_idx is not None:
                try:
                    dev_info = sd.query_devices(loopback_idx)
                    ch = min(dev_info.get("max_input_channels", 1), 2)
                    stream = sd.InputStream(
                        device=loopback_idx,
                        samplerate=SAMPLE_RATE,
                        channels=ch,
                        dtype="float32",
                        blocksize=BLOCK_SIZE,
                        callback=self._sys_callback,
                    )
                    stream.start()
                    self._streams.append(stream)
                except Exception as e:
                    print(f"[Audio] System audio error: {e}")
            else:
                print("[Audio] No WASAPI loopback device found. Try enabling 'Stereo Mix' in Windows sound settings.")

    def stop(self):
        self._running = False
        for s in self._streams:
            try:
                s.stop()
                s.close()
            except Exception:
                pass
        self._streams = []

    @staticmethod
    def list_devices() -> list[dict]:
        result = []
        for i, dev in enumerate(sd.query_devices()):
            result.append({
                "index": i,
                "name": dev.get("name", ""),
                "inputs": dev.get("max_input_channels", 0),
                "outputs": dev.get("max_output_channels", 0),
            })
        return result
