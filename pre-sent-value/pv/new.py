"""Scaffold a new episode from templates/episode/."""
from __future__ import annotations

import json
import re
import shutil

from .config import EPISODES, TEMPLATES


def run(slug: str, title: str | None = None) -> None:
    existing = sorted(p.name for p in EPISODES.iterdir() if p.is_dir() and re.match(r"\d{3}-", p.name) and not p.name.startswith("000-"))
    if not re.match(r"\d{3}-", slug):
        n = int(existing[-1][:3]) + 1 if existing else 1
        slug = f"{n:03d}-{slug}"
    dst = EPISODES / slug
    if dst.exists():
        raise SystemExit(f"{dst} already exists")
    shutil.copytree(TEMPLATES / "episode", dst)
    ep_path = dst / "episode.json"
    ep = json.loads(ep_path.read_text())
    ep["slug"] = slug
    ep["number"] = int(slug[:3])
    ep["title"] = title or slug[4:].replace("-", " ").title()
    ep_path.write_text(json.dumps(ep, indent=2, ensure_ascii=False) + "\n")
    print(f"created {dst}")
