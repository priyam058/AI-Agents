"""ElevenLabs TTS — convert text to MP3 audio bytes."""
import httpx

from app.core.config import settings

_ELEVENLABS_BASE = "https://api.elevenlabs.io/v1"


def synthesize_speech(text: str) -> bytes:
    """Call ElevenLabs TTS API and return raw MP3 bytes."""
    url = f"{_ELEVENLABS_BASE}/text-to-speech/{settings.elevenlabs_voice_id}"
    headers = {
        "xi-api-key": settings.elevenlabs_api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "text": text,
        "model_id": "eleven_turbo_v2",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
            "style": 0.0,
            "use_speaker_boost": True,
        },
    }

    with httpx.Client(timeout=30) as client:
        response = client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.content
