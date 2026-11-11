"""Natural narration with Gemini text-to-speech (uses GEMINI_API_KEY from backend/.env).

  python tts_gemini.py --model gemini-3.8-flash-lite-tts 05-blocked-ask 06-blocked+07-ok-card
  python tts_gemini.py                      # every storyboard line that has no natural WAV yet, one per request

An argument is one request: a single line id, or two ids joined with "+" (one request, split at the pause).
The free tier allows about 10 speech requests per day per model, so pairs stretch the allowance.

Writes work/voice/<id>.wav. The key is sent in a header and never printed. Only narration text goes to Google.
Every clip is transcribed and compared with the script before it is accepted.
"""
import base64
import json
import re
import subprocess
import sys
import time
import array
import wave
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
OUT = HERE / "work" / "voice"
DONE = OUT / "gemini-done.json"
REFERENCE = HERE / "work" / "voice-david"   # earlier narration; used only as a length target
DEFAULT_MODEL = "gemini-3.8-flash-tts"
VOICE = "Charon"
MAX_TEMPO = 1.3
CHECK_MODEL = "gemini-3.5-flash"
API = "https://generativelanguage.googleapis.com/v1beta/models"


class DailyQuota(Exception):
    pass


def api_key() -> str:
    for line in (HERE.parent.parent / "backend" / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("GEMINI_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("GEMINI_API_KEY not found in backend/.env")


def write_wav(path: Path, pcm: bytes) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(pcm)


def wav_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / w.getframerate()


def synth(client: httpx.Client, key: str, model: str, text: str) -> bytes:
    r = client.post(
        f"{API}/{model}:generateContent",
        headers={"x-goog-api-key": key},
        json={
            "contents": [{"parts": [{"text": text}]}],   # no style instruction: the model sometimes reads it aloud
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": VOICE}}},
            },
        },
    )
    if r.status_code != 200:
        err = r.json().get("error", {}) if "json" in r.headers.get("content-type", "") else {}
        quota_ids = [v.get("quotaId", "") for d in err.get("details", []) for v in (d.get("violations") or [])]
        if r.status_code == 429 and any("PerDay" in q for q in quota_ids):
            raise DailyQuota(f"daily free-tier limit reached for {model}")
        raise RuntimeError(f"{r.status_code} {err.get('status')} {str(err.get('message'))[:140]}")
    return base64.b64decode(r.json()["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])


def words(text: str) -> list:
    return "".join(c.lower() if c.isalnum() else " " for c in text).split()


def heard(client: httpx.Client, key: str, wav: Path) -> str | None:
    r = client.post(
        f"{API}/{CHECK_MODEL}:generateContent",
        headers={"x-goog-api-key": key},
        json={"contents": [{"parts": [
            {"text": "Transcribe this audio exactly, word for word. Output only the transcript."},
            {"inlineData": {"mimeType": "audio/wav", "data": base64.b64encode(wav.read_bytes()).decode()}}]}],
            "generationConfig": {"thinkingConfig": {"thinkingLevel": "minimal"}}},
    )
    if r.status_code != 200:
        return None
    return "".join(p.get("text", "") for p in r.json()["candidates"][0]["content"]["parts"]).strip()


def matches(transcript: str | None, text: str) -> bool | None:
    """Loose comparison (numbers are transcribed as digits): same opening, same ending, similar length."""
    if transcript is None:
        return None
    want, got = words(text), words(transcript)
    return bool(got) and got[:2] == want[:2] and got[-1] == want[-1] and 0.6 <= len(got) / len(want) <= 1.25


def declick(path: Path) -> str:
    """Remove the speech model's edge artifacts in place.

    Gemini TTS clips begin with a ~5 ms full-scale blip and end with ~125 ms of loud noise after the
    speech has finished. Both are audible as clicks/static at every cut. Strip them, then fade the
    edges (10 ms in, 15 ms out) so no clip starts or stops on a non-zero sample.
    """
    with wave.open(str(path), "rb") as w:
        sr, ch, sw, n = w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()
        assert ch == 1 and sw == 2, "mono 16-bit expected"
        a = array.array("h", w.readframes(n))
    win = max(1, sr // 200)  # 5 ms
    rms = [(sum(x * x for x in a[i:i + win]) / win) ** 0.5 for i in range(0, len(a) - win + 1, win)]
    start, end, notes = 0, len(a), []
    if len(rms) > 2 and rms[0] > 2000 and rms[1] < 300:
        start = 2 * win
        notes.append("head blip")
    i, run = len(rms) - 1, 0
    while i >= 0 and (rms[i] > 1000 or rms[i] == 0) and run < 60:
        i, run = i - 1, run + 1
    if 8 <= run < 60 and i >= 4 and all(r < 300 for r in rms[i - 3:i + 1]):
        end = (i + 1) * win
        notes.append(f"tail burst {run * 5} ms")
    a = a[start:end]
    fin, fout = sr // 100, int(sr * 0.015)
    for k in range(min(fin, len(a))):
        a[k] = int(a[k] * k / fin)
    for k in range(min(fout, len(a))):
        a[len(a) - 1 - k] = int(a[len(a) - 1 - k] * k / fout)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(a.tobytes())
    return ", ".join(notes) or "clean"


def silences(wav: Path) -> list:
    out = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(wav), "-af", "silencedetect=noise=-40dB:d=0.25", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", out)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", out)]
    return list(zip(starts, ends))


def finish(raw: Path, seg_id: str) -> float:
    """Trim edge silence, cap inner pauses at ~0.4 s, and speed up slightly if the read runs long."""
    final = OUT / f"{seg_id}.wav"
    tmp = OUT / f"{seg_id}.tmp.wav"
    declick(raw)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-af",
                    "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,"
                    "silenceremove=stop_periods=-1:stop_threshold=-45dB:stop_duration=0.4:stop_silence=0.4,"
                    "areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.08,areverse",
                    "-ar", "44100", str(tmp)], check=True)
    ref = REFERENCE / f"{seg_id}.wav"
    tempo = min(MAX_TEMPO, wav_seconds(tmp) / (wav_seconds(ref) * 1.12)) if ref.exists() else 1.0
    if tempo > 1.03:
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(tmp), "-af", f"atempo={tempo:.3f}", str(final)], check=True)
        tmp.unlink()
    else:
        tmp.replace(final)
    return round(wav_seconds(final), 2)


def spoken_text(seg: dict) -> str:
    # The spoken script writes the name as a word ("Pact") so it is not spelled out letter by letter.
    return seg["say"].replace("A I", "AI").replace("I D,", "ID,").replace("A P I", "API").replace("M C P", "MCP")


def main():
    args = [a for a in sys.argv[1:]]
    if args and args[0] == "--declick":  # clean WAVs that were made before declick existed
        for f in sorted(OUT.glob("*.wav")):
            print(f"{f.name}: {declick(f)}")
        return
    model = DEFAULT_MODEL
    if "--model" in args:
        i = args.index("--model")
        model = args[i + 1]
        del args[i:i + 2]
    sb = json.loads((HERE / "storyboard.json").read_text(encoding="utf-8"))
    segs = {s["id"]: s for s in sb["segments"]}
    done = json.loads(DONE.read_text()) if DONE.exists() else {}
    groups = [a.split("+") for a in args] or [[i] for i in segs if i not in done]
    key = api_key()
    OUT.mkdir(parents=True, exist_ok=True)
    failed = []

    with httpx.Client(timeout=240) as client:
        for n, group in enumerate(groups):
            texts = [spoken_text(segs[i]) for i in group]
            label = "+".join(group)
            try:
                pcm = synth(client, key, model, "\n\n".join(texts))
            except DailyQuota as exc:
                print(f"STOP: {exc}. Finished lines are kept; remaining: {[g for g in groups[n:]]}")
                break
            except (RuntimeError, httpx.HTTPError) as exc:
                print(f"  {label}: request failed ({exc}); skipped")
                failed.append(label)
                time.sleep(20)
                continue

            whole = OUT / f"{label}.whole.wav"
            write_wav(whole, pcm)
            parts = [whole]
            if len(group) == 2:
                # Split at the pause nearest to where the first line should end (by share of characters).
                total = wav_seconds(whole)
                expect = total * len(texts[0]) / (len(texts[0]) + len(texts[1]))
                gaps = [(s, e) for s, e in silences(whole) if 0.15 * total < s < 0.85 * total]
                if not gaps:
                    print(f"  {label}: no pause found to split at; skipped")
                    failed.append(label)
                    whole.unlink()
                    continue
                s, e = min(gaps, key=lambda g: abs((g[0] + g[1]) / 2 - expect) - 0.6 * (g[1] - g[0]))
                cut = (s + e) / 2
                parts = [OUT / f"{group[0]}.part.wav", OUT / f"{group[1]}.part.wav"]
                subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(whole), "-t", f"{cut:.3f}", str(parts[0])], check=True)
                subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{cut:.3f}", "-i", str(whole), str(parts[1])], check=True)
                whole.unlink()

            for seg_id, text, part in zip(group, texts, parts):
                time.sleep(4)
                transcript = heard(client, key, part)
                ok = matches(transcript, text)
                if ok is False:
                    print(f"  {seg_id}: REJECTED, transcript does not match the script. Heard: {transcript}")
                    failed.append(seg_id)
                    part.unlink()
                    continue
                seconds = finish(part, seg_id)
                part.unlink(missing_ok=True)
                done[seg_id] = {"model": model, "voice": VOICE, "seconds": seconds, "verified": ok is True}
                DONE.write_text(json.dumps(done, indent=1))
                print(f"voiced {seg_id}: {seconds}s ({model}){'' if ok else ' [transcript check unavailable]'} | {transcript}")
            time.sleep(20)

    missing = [i for i in segs if i not in done]
    print(f"\n{len(done)} of {len(segs)} lines voiced. Missing: {missing or 'none'}. Failed this run: {failed or 'none'}")


if __name__ == "__main__":
    main()
