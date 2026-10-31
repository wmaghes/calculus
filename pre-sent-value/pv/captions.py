"""Word timings with faster-whisper, aligned back to the script text, then
scene/act/clip timings snapped to the narration."""
from __future__ import annotations

import difflib
import json
import re
from pathlib import Path

from . import episode as E
from .cache import key_for
from .config import CACHE, env, episode_dir


def _norm(w: str) -> str:
    return re.sub(r"[^a-z0-9]", "", w.lower().replace("$", "s"))


def transcribe(audio: Path) -> list[dict]:
    """Return [{word,start,end}] from faster-whisper (cached by file hash)."""
    import hashlib

    model_name = env("WHISPER_MODEL", "small.en")
    digest = hashlib.sha256(audio.read_bytes()).hexdigest()
    cpath = CACHE / f"{key_for('whisper', {'audio': digest, 'model': model_name})}.json"
    if cpath.exists():
        return json.loads(cpath.read_text())
    from faster_whisper import WhisperModel

    model = WhisperModel(model_name, device="auto", compute_type="int8")
    segments, _ = model.transcribe(str(audio), word_timestamps=True, vad_filter=False, beam_size=5)
    words = [{"word": w.word.strip(), "start": round(w.start, 3), "end": round(w.end, 3)} for seg in segments for w in seg.words]
    CACHE.mkdir(exist_ok=True)
    cpath.write_text(json.dumps(words))
    return words


def align(script_words: list[str], heard: list[dict]) -> list[dict]:
    """Give every *script* word (correct spelling for captions) a timing from
    the closest whisper word; interpolate any the recogniser missed."""
    a = [_norm(w) for w in script_words]
    b = [_norm(h["word"]) for h in heard]
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    times: list[tuple[float, float] | None] = [None] * len(script_words)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal" or (tag == "replace" and i2 - i1 == j2 - j1):
            for k in range(i2 - i1):
                times[i1 + k] = (heard[j1 + k]["start"], heard[j1 + k]["end"])
        elif tag == "replace" and j2 > j1:
            # spread the heard span evenly over the script span
            t0, t1 = heard[j1]["start"], heard[j2 - 1]["end"]
            n = i2 - i1
            for k in range(n):
                times[i1 + k] = (t0 + (t1 - t0) * k / n, t0 + (t1 - t0) * (k + 1) / n)
    # interpolate gaps
    for i, t in enumerate(times):
        if t is None:
            prev = next((times[j][1] for j in range(i - 1, -1, -1) if times[j]), 0.0)
            nxt = next((times[j][0] for j in range(i + 1, len(times)) if times[j]), prev + 0.3)
            times[i] = (prev, max(prev, nxt))
    return [{"word": w, "start": round(s, 3), "end": round(e, 3)} for w, (s, e) in zip(script_words, times)]


def snap(ep: dict, words: list[dict]) -> None:
    """Contiguous scene timings: scene starts at its first word, ends where the
    next scene starts. First scene starts at 0, last ends at narration end."""
    idx = 0
    starts = []
    for s in ep["scenes"]:
        n = len(s["narration"].split())
        starts.append(words[idx]["start"] if n and idx < len(words) else None)
        idx += n
    total = ep.get("narration_duration") or (words[-1]["end"] if words else 0)
    # scenes with no narration inherit the next scene's start
    for i in range(len(starts) - 1, -1, -1):
        if starts[i] is None:
            starts[i] = starts[i + 1] if i + 1 < len(starts) else total
    starts[0] = 0.0
    for i, s in enumerate(ep["scenes"]):
        s["start"] = round(starts[i], 3)
        s["end"] = round(starts[i + 1] if i + 1 < len(starts) else total, 3)
    for act in ep.get("acts", []):
        sc = [s for s in ep["scenes"] if s.get("act") == act["act"]]
        if sc:
            act["start"], act["end"] = sc[0]["start"], sc[-1]["end"]
    by_id = {s["id"]: s for s in ep["scenes"]}
    for c in ep.get("clips", []):
        if c.get("from_scene") in by_id and c.get("to_scene") in by_id:
            c["start"] = by_id[c["from_scene"]]["start"]
            c["end"] = by_id[c["to_scene"]]["end"]


def run(slug: str) -> None:
    ep_dir = episode_dir(slug)
    ep = E.load(ep_dir)
    audio = ep_dir / (ep.get("narration_file") or "audio/narration.mp3")
    if not audio.exists():
        raise SystemExit(f"No narration at {audio}. Run `pv voice {slug}` first.")
    heard = transcribe(audio)
    script_words = E.narration_text(ep).split()
    words = align(script_words, heard)
    (ep_dir / "audio" / "words.json").write_text(json.dumps(words, indent=1))
    (ep_dir / "audio" / "whisper_raw.json").write_text(json.dumps(heard, indent=1))
    snap(ep, words)
    E.save(ep_dir, ep)
    ratio = difflib.SequenceMatcher(a=[_norm(w) for w in script_words], b=[_norm(h["word"]) for h in heard]).ratio()
    print(f"{len(words)} words aligned (script/audio match {ratio:.1%}); scene timings written to episode.json")
