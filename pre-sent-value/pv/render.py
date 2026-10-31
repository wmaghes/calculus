"""Render with Remotion, then loudness-normalise with FFmpeg."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from . import episode as E
from .config import BRAND, REMOTION, TARGET_LUFS, browser_executable, episode_dir, require_tool

DEFAULT_MUSIC = "placeholder-bed.mp3"


def _stage(ep_dir: Path, ep: dict) -> Path:
    """Build a minimal public dir for this render (only the files it needs)."""
    stage = REMOTION / ".stage" / ep_dir.name
    if stage.exists():
        shutil.rmtree(stage)
    pub = stage / "public"
    (pub / "brand").mkdir(parents=True)
    for sub in ("sfx", "music"):
        if (BRAND / sub).is_dir():
            shutil.copytree(BRAND / sub, pub / "brand" / sub, ignore=shutil.ignore_patterns("*.md"))
    dst_ep = pub / "episodes" / ep_dir.name
    dst_ep.mkdir(parents=True)
    for sub in ("assets", "audio"):
        if (ep_dir / sub).is_dir():
            shutil.copytree(ep_dir / sub, dst_ep / sub, ignore=shutil.ignore_patterns("*.json", "*.csv", "*.md"))
    return stage


def _props(ep_dir: Path, ep: dict, clip_id: str | None) -> dict:
    words_path = ep_dir / "audio" / "words.json"
    words = json.loads(words_path.read_text()) if words_path.exists() else []
    narration = ep.get("narration_file")
    music = ep.get("music") or DEFAULT_MUSIC
    return {
        "episode": {**ep, "slug": ep_dir.name},
        "words": words,
        "narrationSrc": f"episodes/{ep_dir.name}/{narration}" if narration and (ep_dir / narration).exists() else None,
        "musicSrc": f"brand/music/{music}" if (BRAND / "music" / music).exists() else None,
        "clipId": clip_id,
    }


def _remotion(args: list[str]) -> None:
    require_tool("npx")
    cmd = ["npx", "remotion", *args]
    if browser_executable():
        cmd.append(f"--browser-executable={browser_executable()}")
    print("$", " ".join(cmd))
    subprocess.run(cmd, cwd=REMOTION, check=True, env={**os.environ, "PV_BRAND_DIR": str(BRAND)})


def measure_loudness(path: Path) -> dict:
    """EBU R128 via ffmpeg loudnorm (print_format=json)."""
    r = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", f"loudnorm=I={TARGET_LUFS}:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.S)
    if not m:
        raise RuntimeError("could not measure loudness:\n" + r.stderr[-2000:])
    return json.loads(m.group(0))


def normalize(src: Path, dst: Path) -> dict:
    """Two-pass loudnorm to TARGET_LUFS, video stream copied untouched."""
    m = measure_loudness(src)
    af = (
        f"loudnorm=I={TARGET_LUFS}:TP=-1.5:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}"
        f":measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true"
    )
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(src), "-c:v", "copy", "-af", af,
         "-ar", "48000", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(dst)],
        check=True,
    )
    return m


def render(slug: str, what: str = "all", normalize_audio: bool | None = None) -> list[Path]:
    require_tool("ffmpeg")
    ep_dir = episode_dir(slug)
    ep = E.load(ep_dir)
    errs = E.validate(ep)
    if errs:
        raise SystemExit("episode.json invalid:\n  " + "\n  ".join(errs))
    out = ep_dir / "out"
    out.mkdir(exist_ok=True)
    stage = _stage(ep_dir, ep)
    jobs: list[tuple[str, str | None, Path]] = []
    if what in ("all", "master"):
        jobs.append(("Episode16x9", None, out / "final-16x9.mp4"))
    if what in ("all", "clips"):
        for i, c in enumerate(ep.get("clips", []), 1):
            if c.get("start") is not None and c.get("end") is not None:
                jobs.append(("Episode9x16", c["id"], out / f"final-9x16-clip{i}.mp4"))
    has_voice = bool(_props(ep_dir, ep, None)["narrationSrc"])
    if normalize_audio is None:
        normalize_audio = has_voice  # music-only test renders would be pumped up to -14 LUFS otherwise
    results = []
    for comp, clip, dst in jobs:
        props_file = stage / f"props-{clip or 'master'}.json"
        props_file.write_text(json.dumps(_props(ep_dir, ep, clip)))
        raw = stage / f"raw-{dst.name}"
        _remotion(["render", "src/index.ts", comp, str(raw), f"--props={props_file}", f"--public-dir={stage / 'public'}", "--codec=h264", "--crf=18"])
        if normalize_audio:
            m = normalize(raw, dst)
            print(f"loudness {m['input_i']} LUFS -> {TARGET_LUFS} LUFS: {dst}")
        else:
            shutil.copyfile(raw, dst)
            print(f"rendered (no loudness pass): {dst}")
        results.append(dst)
    if what in ("all", "thumbnail"):
        thumb = ep.get("thumbnail", {})
        tprops = stage / "thumb.json"
        tprops.write_text(json.dumps({
            "title": thumb.get("title", ep["title"]),
            "kicker": thumb.get("kicker", f"Episode {ep.get('number', '')}".strip()),
            "episodeSlug": ep_dir.name,
            "image": thumb.get("image"),
        }))
        _remotion(["still", "src/index.ts", "Thumbnail", str(out / "thumbnail.png"), f"--props={tprops}", f"--public-dir={stage / 'public'}"])
        results.append(out / "thumbnail.png")
    return results
