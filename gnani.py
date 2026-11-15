import os
import httpx
from dotenv import load_dotenv

load_dotenv()
KEY = os.environ.get("GNANI_API_KEY", "")
HEADERS = {"X-API-Key-ID": KEY}
STT_URL = "https://api.vachana.ai/stt/v3"
TTS_URL = "https://api.vachana.ai/api/v1/tts/inference"

class GnaniError(Exception):
    pass

def transcribe(audio: bytes, filename: str = "audio.wav", lang: str = "indic-auto") -> str:
    try:
        r = httpx.post(
            STT_URL, headers=HEADERS,
            files={"audio_file": (filename, audio)},
            data={"model": "prisma-v3.0", "language_code": lang, "format": "transcribe"},
            timeout=60,
        )
    except httpx.HTTPError as e:
        raise GnaniError(f"STT network error: {e}")
    if r.status_code != 200:
        raise GnaniError(f"STT {r.status_code}: {r.text[:200]}")
    body = r.json()
    if not body.get("success"):
        raise GnaniError(f"STT failed: {body}")
    return body["transcript"]

def synthesize(text: str, lang: str = "hi-IN") -> bytes:
    payload = {
        "text": text, "voice": "Nalini", "model": "timbre-v2.5",
        "language": lang, "speed": 1.0,
        "audio_config": {"sample_rate": 48000, "num_channels": 1,
                         "sample_width": 2, "encoding": "linear_pcm",
                         "container": "wav"},
    }
    try:
        r = httpx.post(TTS_URL, headers=HEADERS, json=payload, timeout=60)
    except httpx.HTTPError as e:
        raise GnaniError(f"TTS network error: {e}")
    if r.status_code != 200:
        raise GnaniError(f"TTS {r.status_code}: {r.text[:200]}")
    return r.content