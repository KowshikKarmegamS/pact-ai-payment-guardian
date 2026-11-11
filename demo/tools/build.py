"""Builds the PACT demo video from recorded frames + narration.

  python build.py            # everything
  python build.py --only 03-dash,04-mandate   # rebuild selected clips, then the final cut

Inputs : frames/<take>/ (from record.mjs), work/voice/<id>.wav (from tts.ps1), storyboard.json
Outputs: ../pact-hackathon-final.mp4, ../pact-recording-raw.mp4, ../pact-narration.txt,
         ../pact-demo-assets/captions.srt
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FRAMES = HERE / "frames"
WORK = HERE / "work"
DEMO = HERE.parent
ASSETS = DEMO / "pact-demo-assets"
FPS = 30
LEAD, TAIL = 0.45, 0.5          # silence before / after each narration line inside its clip
CARD_FADE = 0.45
XFADE = 0.35                      # crossfade between consecutive clips (replaces hard cuts)
PUSH_IN = 0.035                   # slow zoom over each app clip so held screens never look frozen


def run(args, cwd=None):
    proc = subprocess.run([str(a) for a in args], cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr[-3000:])
        raise SystemExit(f"command failed: {' '.join(str(a) for a in args[:6])} …")
    return proc.stdout


def probe(path) -> float:
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path]).strip())


def take_meta(take):
    return json.loads((FRAMES / take / "frames.json").read_text())


def build_take(take) -> Path:
    """Frames + timestamps -> constant-frame-rate MP4 with the original timing."""
    out = WORK / "takes" / f"{take}.mp4"
    meta_file = FRAMES / take / "frames.json"
    if out.exists() and out.stat().st_mtime > meta_file.stat().st_mtime:
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    meta = take_meta(take)
    frames = meta["frames"]
    lines = []
    for i, f in enumerate(frames):
        nxt = frames[i + 1]["t"] if i + 1 < len(frames) else meta["end"]
        lines.append(f"file '{(FRAMES / take / f['file']).as_posix()}'")
        lines.append(f"duration {max(nxt - f['t'], 0.001):.4f}")
    lines.append(f"file '{(FRAMES / take / frames[-1]['file']).as_posix()}'")
    lst = WORK / "takes" / f"{take}.txt"
    lst.write_text("\n".join(lines), encoding="utf-8")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-vf", f"fps={FPS},scale=1920:1080:flags=lanczos:in_range=full:out_range=tv,format=yuv420p", "-color_range", "tv",
         "-c:v", "libx264", "-crf", "14", "-preset", "veryfast", out])
    print(f"take {take}: {probe(out):.1f}s")
    return out


def marker(meta, name) -> float:
    t0 = meta["frames"][0]["t"]
    for m in meta["markers"]:
        if m["name"] == name:
            return m["t"] - t0
    raise SystemExit(f"marker {name!r} not found")


def build_clip(seg, index, total) -> dict:
    take = seg["take"]
    src = build_take(take)
    meta = take_meta(take)
    start = max(0.0, marker(meta, seg["from"]) + seg.get("fromOffset", 0.0))
    end = marker(meta, seg["to"]) + seg.get("toOffset", 0.0)
    span = end - start
    voice = WORK / "voice" / f"{seg['id']}.wav"
    narr = probe(voice)
    target = narr + LEAD + TAIL

    filters = []
    if seg.get("fit") == "pad":          # title cards play at their designed speed
        speed, dur = 1.0, max(span, target)
    else:
        speed = min(max(span / target, 0.8), 2.6)
        dur = target
    filters.append(f"setpts=(PTS-STARTPTS)/{speed:.4f}")
    filters.append(f"fps={FPS}")
    if seg.get("zoom"):
        x, y, w, h = seg["zoom"]
        filters.append(f"crop={w}:{h}:{x}:{y},scale=1920:1080:flags=lanczos")
    played = span / speed
    if played < dur:
        filters.append(f"tpad=stop_mode=clone:stop_duration={dur - played + 0.1:.3f}")
    is_card = take.startswith("card-")
    if not is_card:
        # Gentle push-in toward the centre. Upscale first so the moving crop does not jitter.
        frames = int(round(dur * FPS)) or 1
        filters.append("scale=3840:2160:flags=bicubic")
        filters.append(f"zoompan=z='1+{PUSH_IN}*on/{frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                       f":d=1:s=1920x1080:fps={FPS}")
    if is_card or index == 0:
        filters.append(f"fade=t=in:st=0:d={CARD_FADE}")
    if is_card or index == total - 1:
        filters.append(f"fade=t=out:st={dur - CARD_FADE:.3f}:d={CARD_FADE}")
    filters.append("format=yuv420p")

    clip = WORK / "clips" / f"{seg['id']}.mp4"
    clip.parent.mkdir(parents=True, exist_ok=True)
    run(["ffmpeg", "-y", "-ss", f"{start:.3f}", "-t", f"{span:.3f}", "-i", src, "-vf", ",".join(filters), "-t", f"{dur:.3f}",
         "-r", FPS, "-c:v", "libx264", "-crf", "15", "-preset", "veryfast", "-an", clip])

    audio = WORK / "clips" / f"{seg['id']}.wav"
    run(["ffmpeg", "-y", "-i", voice, "-af", f"adelay={int(LEAD * 1000)}:all=1,apad", "-t", f"{dur:.3f}", "-ar", "48000", "-ac", "2", audio])
    real = probe(clip)
    print(f"clip {seg['id']}: source {span:5.1f}s x{speed:.2f} -> {real:5.1f}s (voice {narr:.1f}s)")
    return {"id": seg["id"], "clip": clip, "audio": audio, "dur": real, "narr": narr, "caption": seg["caption"], "say": seg["say"]}


def ts_ass(t):
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def ts_srt(t):
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(round((s - int(s)) * 1000)):03d}"


def timeline(clips):
    """Start time of every clip once consecutive clips overlap by XFADE, and the total length."""
    starts, t = [], 0.0
    for c in clips:
        starts.append(t)
        t += c["dur"] - XFADE
    return starts, t + XFADE


def captions(clips):
    """Caption lines share each clip's narration time in proportion to their length."""
    events, srt, n = [], [], 0
    starts, total = timeline(clips)
    for c, t in zip(clips, starts):
        parts = [p.strip() for p in c["caption"].split("|") if p.strip()]
        weights = [len(p) + 8 for p in parts]
        cursor = t + LEAD
        for part, w in zip(parts, weights):
            d = c["narr"] * w / sum(weights)
            a, b = cursor, cursor + d + (0.25 if part is parts[-1] else 0.0)
            events.append(f"Dialogue: 0,{ts_ass(a)},{ts_ass(b)},Cap,,0,0,0,,{part}")
            n += 1
            srt.append(f"{n}\n{ts_srt(a)} --> {ts_srt(b)}\n{part}\n")
            cursor += d
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Segoe UI Semibold,40,&H00F6F0EC,&H00F6F0EC,&H26100B08,&H26100B08,0,0,0,0,100,100,0.4,0,3,12,0,2,160,160,48,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    (WORK / "captions.ass").write_text(header + "\n".join(events) + "\n", encoding="utf-8")
    ASSETS.mkdir(exist_ok=True)
    (ASSETS / "captions.srt").write_text("\n".join(srt), encoding="utf-8")
    return total


def main():
    only = None
    if "--only" in sys.argv:
        only = set(sys.argv[sys.argv.index("--only") + 1].split(","))
    sb = json.loads((HERE / "storyboard.json").read_text(encoding="utf-8"))
    segs = sb["segments"]
    cache = WORK / "clips.json"
    known = json.loads(cache.read_text()) if cache.exists() else {}
    clips = []
    for i, seg in enumerate(segs):
        if only is not None and seg["id"] not in only and seg["id"] in known:
            c = known[seg["id"]]
            c.update(clip=Path(c["clip"]), audio=Path(c["audio"]), caption=seg["caption"], say=seg["say"])
        else:
            c = build_clip(seg, i, len(segs))
        clips.append(c)
    cache.write_text(json.dumps({c["id"]: {**c, "clip": str(c["clip"]), "audio": str(c["audio"])} for c in clips}, indent=1))

    total = captions(clips)
    starts, _ = timeline(clips)

    # Picture: crossfade each clip into the next instead of a hard cut.
    args, chain, prev = ["ffmpeg", "-y"], [], "0:v"
    for c in clips:
        args += ["-i", c["clip"]]
    for k in range(1, len(clips)):
        chain.append(f"[{prev}][{k}:v]xfade=transition=fade:duration={XFADE}:offset={starts[k]:.3f}[x{k}]")
        prev = f"x{k}"
    run(args + ["-filter_complex", ";".join(chain) + f";[{prev}]format=yuv420p[v]", "-map", "[v]",
                "-c:v", "libx264", "-crf", "15", "-preset", "veryfast", "-r", FPS, WORK / "video.mp4"])

    # Voice: each declicked line placed on the crossfaded timeline, so picture and voice cannot drift.
    args, chain = ["ffmpeg", "-y"], []
    for k, c in enumerate(clips):
        args += ["-i", WORK / "voice" / f"{c['id']}.wav"]
        delay = int(round((starts[k] + LEAD) * 1000))
        chain.append(f"[{k}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={delay}:all=1[a{k}]")
    mix = "".join(f"[a{k}]" for k in range(len(clips)))
    run(args + ["-filter_complex",
                ";".join(chain) + f";{mix}amix=inputs={len(clips)}:normalize=0:duration=longest,apad,atrim=0:{total:.3f}[out]",
                "-map", "[out]", "-c:a", "pcm_s16le", WORK / "voice.wav"])

    # Original ambient bed: three soft sine partials with slow tremolo. Synthesized here; no third-party audio.
    bed = (f"sine=f=110:d={total:.2f},volume=0.5[a];sine=f=164.81:d={total:.2f},volume=0.32[b];sine=f=220:d={total:.2f},volume=0.2[c];"
           f"[a][b][c]amix=inputs=3:normalize=0,tremolo=f=0.11:d=0.5,lowpass=f=520,aecho=0.6:0.5:900:0.35,"
           f"volume=0.05,afade=t=in:d=2.5,afade=t=out:st={total - 3:.2f}:d=3,aformat=channel_layouts=stereo:sample_rates=48000[bed]")
    final = DEMO / "pact-hackathon-final.mp4"
    run(["ffmpeg", "-y", "-i", "video.mp4", "-i", "voice.wav", "-filter_complex",
         f"{bed};[1:a]highpass=f=70,acompressor=threshold=-20dB:ratio=2.5:attack=8:release=160,loudnorm=I=-16:TP=-1.5:LRA=9,"
         f"aformat=channel_layouts=stereo:sample_rates=48000[v];[v][bed]amix=inputs=2:normalize=0:duration=first[aout];"
         f"[0:v]ass=captions.ass,format=yuv420p[vout]",
         "-map", "[vout]", "-map", "[aout]", "-c:v", "libx264", "-profile:v", "high", "-crf", "18", "-preset", "medium", "-r", FPS,
         "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", "-t", f"{total:.3f}", final], cwd=WORK)

    lines = ["PACT - The AI Payment Authorization Gateway: narration script", "Voice: Google Gemini text-to-speech, voice Charon (generated by demo/tools/tts_gemini.py)", ""]
    for c, t in zip(clips, starts):
        lines.append(f"[{int(t // 60)}:{t % 60:04.1f}] {c['caption'].replace('|', ' ')}")
    lines.append(f"\nTotal running time: {int(total // 60)}:{total % 60:04.1f}")
    (DEMO / "pact-narration.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Raw application recording: the three app takes back to back, original timing, no narration.
    raws = [build_take(t) for t in ("app1", "app2", "app3", "app4", "app5", "app6") if (FRAMES / t / "frames.json").exists()]
    (WORK / "raw.txt").write_text("\n".join(f"file '{r.as_posix()}'" for r in raws), encoding="utf-8")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", WORK / "raw.txt", "-c:v", "libx264", "-crf", "21", "-preset", "medium",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", DEMO / "pact-recording-raw.mp4"])
    print(f"\nfinal: {final}  ({total:.1f}s)")


if __name__ == "__main__":
    main()
