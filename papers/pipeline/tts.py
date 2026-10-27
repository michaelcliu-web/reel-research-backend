import os

import requests

from papers.pipeline.render import media_path, probe_duration

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")

# ElevenLabs plans cap concurrent requests (typically 2).
MAX_CONCURRENT_REQUESTS = 2


def synthesize_scene(narration_text, pid, snum, hint):
    """Write the scene's narration audio; returns (audio_path, exact_duration). Blocking."""
    audio_dir = media_path("audio")
    os.makedirs(audio_dir, exist_ok=True)
    audio_path = os.path.join(audio_dir, f"{pid}_scene{snum}.mp3")
    tts_resp = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}",
        headers={
            "xi-api-key": ELEVENLABS_API_KEY,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
        json={
            "text": narration_text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        },
        timeout=60,
    )
    if tts_resp.status_code != 200:
        raise Exception(f"ElevenLabs TTS failed ({tts_resp.status_code}): {tts_resp.text[:300]}")
    with open(audio_path, "wb") as f:
        f.write(tts_resp.content)
    return audio_path, probe_duration(audio_path, hint)
