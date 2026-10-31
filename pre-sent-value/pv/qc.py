"""Quality checks. Writes out/qc.md and exits non-zero on failure."""
from __future__ import annotations

import csv
import difflib
import json
import re
import subprocess
from pathlib import Path

from . import episode as E
from .captions import _norm
from .config import TARGET_LUFS, episode_dir
from .render import measure_loudness
from .voice import probe_duration

RUNTIME_MIN, RUNTIME_MAX = 160.0, 200.0  # 2:40 – 3:20


def _peak_db(path: Path) -> float:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "astats=measure_overall=Peak_level:measure_perchannel=0", "-f", "null", "-"],
                       capture_output=True, text=True)
    vals = re.findall(r"Peak level dB:\s*(-?[\d.]+|-inf)", r.stderr)
    return max(float(v) if v != "-inf" else -200.0 for v in vals) if vals else -200.0


def checks(ep_dir: Path, ep: dict, runtime=(RUNTIME_MIN, RUNTIME_MAX)) -> list[tuple[str, bool, str]]:
    res: list[tuple[str, bool, str]] = []
    master = ep_dir / "out" / "final-16x9.mp4"

    errs = E.validate(ep)
    res.append(("episode.json valid", not errs, "; ".join(errs) or "ok"))

    if master.exists():
        d = probe_duration(master)
        res.append(("runtime 2:40–3:20", runtime[0] <= d <= runtime[1], f"{d:.1f} s"))
        lufs = float(measure_loudness(master)["input_i"])
        res.append((f"loudness ≈ {TARGET_LUFS} LUFS (±1)", abs(lufs - TARGET_LUFS) <= 1.0, f"{lufs:.1f} LUFS"))
        pk = _peak_db(master)
        res.append(("master not clipped (peak < -0.5 dBFS)", pk < -0.5, f"peak {pk:.2f} dBFS"))
    else:
        res.append(("master rendered", False, f"{master} missing"))

    narr = ep_dir / (ep.get("narration_file") or "audio/narration.mp3")
    if narr.exists():
        pk = _peak_db(narr)
        res.append(("narration not clipped (peak < -0.1 dBFS)", pk < -0.1, f"peak {pk:.2f} dBFS"))
    raw = ep_dir / "audio" / "whisper_raw.json"
    if raw.exists():
        heard = json.loads(raw.read_text())
        script = E.narration_text(ep).split()
        ratio = difflib.SequenceMatcher(a=[_norm(w) for w in script], b=[_norm(h["word"]) for h in heard], autojunk=False).ratio()
        res.append(("captions match audio (≥ 92% word match)", ratio >= 0.92, f"{ratio:.1%}"))
        words = json.loads((ep_dir / "audio" / "words.json").read_text())
        mono = all(words[i]["start"] <= words[i + 1]["start"] for i in range(len(words) - 1))
        res.append(("caption timings monotonic", mono, f"{len(words)} words"))
    else:
        res.append(("captions generated", False, "run pv captions"))

    sc = ep["scenes"]
    gaps = [f"{a['id']}→{b['id']}" for a, b in zip(sc, sc[1:]) if a.get("end") is None or b.get("start") is None or abs(a["end"] - b["start"]) > 1e-3]
    first_ok = sc and sc[0].get("start") == 0
    last_ok = sc and ep.get("narration_duration") and abs((sc[-1].get("end") or 0) - ep["narration_duration"]) < 0.05
    res.append(("scene timings contiguous", not gaps and bool(first_ok) and bool(last_ok), ", ".join(gaps) or f"{len(sc)} scenes"))

    att = ep_dir / "assets" / "attribution.csv"
    logged = set()
    if att.exists():
        with att.open() as f:
            for row in csv.DictReader(f):
                logged.add(row.get("file", "").strip())
    images = sorted({s["visual"]["file"] for s in sc if s["visual"]["type"] == "archival_image" and s["visual"].get("file")})
    images += [p.relative_to(ep_dir).as_posix() for p in (ep_dir / "assets").glob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".tif"}]
    missing = sorted({i for i in images if i not in logged and Path(i).name not in logged})
    res.append(("every image has an attribution row", not missing, ", ".join(missing) or f"{len(set(images))} images logged"))
    return res


def run(slug: str) -> bool:
    ep_dir = episode_dir(slug)
    ep = E.load(ep_dir)
    res = checks(ep_dir, ep)
    lines = [f"# QC — {ep['title']}", "", "| check | result | detail |", "|---|---|---|"]
    lines += [f"| {name} | {'PASS' if ok else 'FAIL'} | {detail} |" for name, ok, detail in res]
    report = "\n".join(lines) + "\n"
    (ep_dir / "out").mkdir(exist_ok=True)
    (ep_dir / "out" / "qc.md").write_text(report)
    print(report)
    return all(ok for _, ok, _ in res)
