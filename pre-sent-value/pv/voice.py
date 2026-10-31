"""Narration via ElevenLabs (cached: re-running with the same text is free)."""
from __future__ import annotations

import shutil
import subprocess

import requests

from . import episode as E
from .cache import cached_bytes
from .config import env, episode_dir

API = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"


def synthesize(text: str) -> tuple[bytes, dict]:
    key = env("ELEVENLABS_API_KEY", required=True)
    voice_id = env("ELEVENLABS_VOICE_ID", required=True)
    payload = {
        "voice_id": voice_id,
        "model_id": env("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2"),
        "output_format": "mp3_44100_128",
        "text": text,
        # One consistent channel voice: keep these fixed across episodes.
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "style": 0.15, "use_speaker_boost": True},
    }

    def produce() -> bytes:
        r = requests.post(
            API.format(voice_id=voice_id),
            params={"output_format": payload["output_format"]},
            headers={"xi-api-key": key, "accept": "audio/mpeg"},
            json={k: payload[k] for k in ("text", "model_id", "voice_settings")},
            timeout=300,
        )
        if r.status_code != 200:
            raise SystemExit(f"ElevenLabs error {r.status_code}: {r.text[:500]}")
        return r.content

    path, hit = cached_bytes("elevenlabs", payload, "mp3", produce)
    return path.read_bytes(), {"cached": hit, "cache_file": str(path)}


def probe_duration(path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def run(slug: str, yes: bool = False) -> None:
    ep_dir = episode_dir(slug)
    ep = E.load(ep_dir)
    if not ep.get("approved_script"):
        raise SystemExit("Script not approved yet. Set \"approved_script\": true in episode.json after review (CHECKPOINT 2).")
    text = E.narration_text(ep)
    print(f"Narration: {E.word_count(ep)} words, {len(text)} characters.")
    if not yes:
        ans = input("This may spend ElevenLabs credits (free if cached). Continue? [y/N] ")
        if ans.strip().lower() != "y":
            raise SystemExit("Aborted.")
    data, info = synthesize(text)
    out = ep_dir / "audio" / "narration.mp3"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    ep["narration_file"] = "audio/narration.mp3"
    ep["narration_duration"] = round(probe_duration(out), 3)
    E.save(ep_dir, ep)
    print(f"{'cache hit' if info['cached'] else 'generated'} -> {out} ({ep['narration_duration']} s)")
    if shutil.which("ffprobe") is None:
        print("warning: ffprobe missing")
