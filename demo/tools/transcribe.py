"""Transcribes narration WAVs with Gemini so the spoken words can be checked against the script.

  python transcribe.py work/voice/01-intro.wav [...]
"""
import base64
import sys
from pathlib import Path

import httpx

from tts_gemini import api_key

MODEL = "gemini-3.5-flash-lite"


def transcribe(client: httpx.Client, key: str, wav: Path) -> str:
    r = client.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent",
        headers={"x-goog-api-key": key},
        json={
            "contents": [{"parts": [
                {"text": "Transcribe this audio exactly, word for word. Output only the transcript."},
                {"inlineData": {"mimeType": "audio/wav", "data": base64.b64encode(wav.read_bytes()).decode()}},
            ]}],
            "generationConfig": {"thinkingConfig": {"thinkingLevel": "minimal"}},
        },
    )
    if r.status_code != 200:
        return f"<error {r.status_code}>"
    return "".join(p.get("text", "") for p in r.json()["candidates"][0]["content"]["parts"]).strip()


if __name__ == "__main__":
    key = api_key()
    with httpx.Client(timeout=120) as client:
        for arg in sys.argv[1:]:
            print(f"{Path(arg).stem}: {transcribe(client, key, Path(arg))}")
