"""Load / save / validate episode.json (the single source of truth)."""
from __future__ import annotations

import json
import re
from pathlib import Path

VISUAL_TYPES = {"archival_image", "map", "animated_graphic", "text_card"}
MOTIONS = {"kenburns", "pan", "zoom", "reveal"}


def load(ep_dir: Path) -> dict:
    return json.loads((ep_dir / "episode.json").read_text())


def save(ep_dir: Path, ep: dict) -> None:
    (ep_dir / "episode.json").write_text(json.dumps(ep, indent=2, ensure_ascii=False) + "\n")


def narration_text(ep: dict) -> str:
    return "\n\n".join(s["narration"].strip() for s in ep["scenes"] if s["narration"].strip())


def word_count(ep: dict) -> int:
    return len(re.findall(r"\S+", narration_text(ep)))


def validate(ep: dict) -> list[str]:
    errs: list[str] = []
    for key in ("slug", "title", "hook", "lesson", "runtime_target_seconds", "acts", "clips", "scenes"):
        if key not in ep:
            errs.append(f"missing top-level key: {key}")
    ids = set()
    for i, s in enumerate(ep.get("scenes", [])):
        where = f"scene[{i}] {s.get('id', '?')}"
        if s.get("id") in ids:
            errs.append(f"{where}: duplicate id")
        ids.add(s.get("id"))
        v = s.get("visual", {})
        if v.get("type") not in VISUAL_TYPES:
            errs.append(f"{where}: visual.type must be one of {sorted(VISUAL_TYPES)}")
        if s.get("motion") not in MOTIONS:
            errs.append(f"{where}: motion must be one of {sorted(MOTIONS)}")
        if v.get("type") == "archival_image" and not v.get("file") and not v.get("prompt"):
            errs.append(f"{where}: archival_image needs file or prompt")
    for c in ep.get("clips", []):
        for k in ("from_scene", "to_scene"):
            if c.get(k) and c[k] not in ids:
                errs.append(f"clip {c.get('id')}: {k} '{c[k]}' is not a scene id")
    return errs
