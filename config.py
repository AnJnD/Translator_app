import json
import os

CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".translator_meeting", "config.json")

DEFAULTS = {
    "soniox_api_key": "",
    "source_language": "ja",
    "target_language": "vi",
    "audio_source": "microphone",  # microphone | system | both
    "font_size": 14,
    "always_on_top": False,
    "show_original": True,
    "auto_translate": True,
    "context_terms": "",
}

SPEAKER_COLORS = {
    1: "#4FC3F7",  # light blue
    2: "#A5D6A7",  # light green
    3: "#FFB74D",  # orange
    4: "#CE93D8",  # purple
    5: "#F48FB1",  # pink
}

LANGUAGES = {
    "ja": "Japanese",
    "vi": "Vietnamese",
    "en": "English",
    "zh": "Chinese",
    "ko": "Korean",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "th": "Thai",
    "auto": "Auto-detect",
}


def load() -> dict:
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {**DEFAULTS, **data}
        except Exception:
            pass
    return dict(DEFAULTS)


def save(cfg: dict):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
