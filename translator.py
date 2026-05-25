"""Translation via Google Translate (free, no API key required)."""
import re
import urllib.parse
import urllib.request
import json


_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def translate(text: str, src: str = "auto", dest: str = "vi") -> str:
    """Translate text using Google Translate. Returns original text on failure."""
    if not text.strip():
        return text
    if src == dest:
        return text

    try:
        encoded = urllib.parse.quote(text)
        url = (
            f"https://translate.googleapis.com/translate_a/single"
            f"?client=gtx&sl={src}&tl={dest}&dt=t&q={encoded}"
        )
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw = resp.read().decode("utf-8")
        data = json.loads(raw)
        parts = data[0] if data else []
        return "".join(p[0] for p in parts if p and p[0])
    except Exception as e:
        print(f"[Translate] Error: {e}")
        return text
