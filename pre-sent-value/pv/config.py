"""Paths, environment and tool discovery."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EPISODES = ROOT / "episodes"
REMOTION = ROOT / "remotion"
TEMPLATES = ROOT / "templates"
CACHE = ROOT / ".cache"


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover
        return
    load_dotenv(ROOT / ".env")


_load_env()

# A second channel = a copied brand folder + PV_BRAND_DIR pointing at it.
BRAND = Path(os.environ.get("PV_BRAND_DIR", ROOT / "brand")).resolve()

FPS = 30
INTRO_SECONDS = 2.0
OUTRO_SECONDS = 3.0
TAIL_SECONDS = 0.6
TARGET_LUFS = -14.0


def env(name: str, default: str | None = None, required: bool = False) -> str | None:
    val = os.environ.get(name, default)
    if required and not val:
        raise SystemExit(f"Missing {name}. Add it to {ROOT / '.env'} (see .env.example).")
    return val


def episode_dir(slug: str) -> Path:
    """Accept '001-wenamun', '001' or 'wenamun'."""
    direct = EPISODES / slug
    if direct.is_dir():
        return direct
    matches = [p for p in EPISODES.iterdir() if p.is_dir() and (p.name.startswith(slug + "-") or p.name.endswith("-" + slug))]
    if len(matches) == 1:
        return matches[0]
    raise SystemExit(f"Episode '{slug}' not found in {EPISODES}")


def browser_executable() -> str | None:
    """Pre-installed headless Chrome, if any (else Remotion downloads one)."""
    if os.environ.get("REMOTION_BROWSER"):
        return os.environ["REMOTION_BROWSER"]
    for cand in Path("/opt/pw-browsers").glob("chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell"):
        return str(cand)
    return None


def require_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise SystemExit(f"'{name}' not found on PATH. Install it first (see README).")
    return path
