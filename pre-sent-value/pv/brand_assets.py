"""Generate ORIGINAL placeholder audio with FFmpeg synthesis.

Nothing is downloaded, so there is no licensing question. These are
placeholders: drop licensed files into brand/music/ and brand/sfx/ with the
same names (or set "music" in episode.json) to replace them.
"""
from __future__ import annotations

import subprocess

from .config import BRAND, require_tool


def _ff(args: list[str]) -> None:
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args], check=True)


def _sines(parts: list[tuple[float, float, float, float]]) -> str:
    # (amp, freq, lfo_period_s, phase): every freq*60 and 60/period is an integer -> seamless 60 s loop
    return "+".join(f"{a}*sin(2*PI*{f}*t)*(0.55+0.45*sin(2*PI*t/{p}+{ph}))" for a, f, p, ph in parts)


def _peak_normalize(path, target_db: float = -3.0) -> None:
    import re
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
                       capture_output=True, text=True)
    peak = float(re.search(r"max_volume: (-?[\d.]+) dB", r.stderr).group(1))
    tmp = path.with_name("tmp-" + path.name)
    _ff(["-i", str(path), "-af", f"volume={target_db - peak}dB", str(tmp)])
    tmp.replace(path)


def generate(force: bool = False) -> None:
    require_tool("ffmpeg")
    music, sfx = BRAND / "music", BRAND / "sfx"
    music.mkdir(parents=True, exist_ok=True)
    sfx.mkdir(parents=True, exist_ok=True)

    def want(p):
        return force or not p.exists()

    bed = music / "placeholder-bed.mp3"
    if want(bed):
        # warm, slow D-minor-ish pad: D2 A2 D3 F3 A3 C4
        expr = _sines([(0.16, 73.4, 20, 0), (0.12, 110.0, 15, 1), (0.10, 146.8, 12, 2), (0.07, 174.6, 30, 0.5),
                       (0.06, 220.0, 10, 3), (0.035, 261.6, 20, 4.2)])
        _ff(["-f", "lavfi", "-i", f"aevalsrc={expr}:s=48000:d=60",
             "-af", "lowpass=f=1800,aecho=0.8:0.7:120|260:0.25|0.15,volume=1.4,alimiter=limit=0.8",
             "-c:a", "libmp3lame", "-b:a", "192k", str(bed)])
    coin = sfx / "coin.mp3"
    if want(coin):
        expr = "(0.5*sin(2*PI*2093*t)+0.35*sin(2*PI*3136*t)+0.2*sin(2*PI*4186*t))*exp(-6*t)" \
               "+(0.3*sin(2*PI*2349*t)+0.2*sin(2*PI*3520*t))*exp(-9*(t-0.11))*gte(t\\,0.11)"
        _ff(["-f", "lavfi", "-i", f"aevalsrc={expr}:s=48000:d=0.9", "-af", "aecho=0.6:0.4:40:0.2", str(coin)])
    whoosh = sfx / "whoosh.mp3"
    if want(whoosh):
        _ff(["-f", "lavfi", "-i", "anoisesrc=d=0.8:c=pink:a=0.6:r=48000",
             "-af", "highpass=f=300,lowpass=f=3500,afade=t=in:d=0.35:curve=exp,afade=t=out:st=0.4:d=0.4", str(whoosh)])
    impact = sfx / "impact.mp3"
    if want(impact):
        _ff(["-f", "lavfi", "-i", "aevalsrc=0.9*sin(2*PI*(45+40*exp(-8*t))*t)*exp(-3.5*t):s=48000:d=1.4",
             "-af", "lowpass=f=400,alimiter=limit=0.9", str(impact)])
    waves = sfx / "waves.mp3"
    if want(waves):
        _ff(["-f", "lavfi", "-i", "anoisesrc=d=6:c=brown:a=0.5:r=48000",
             "-af", "lowpass=f=900,volume='0.5+0.5*sin(2*PI*t/3)':eval=frame,afade=t=in:d=0.5,afade=t=out:st=5:d=1", str(waves)])
    quill = sfx / "quill.mp3"
    if want(quill):
        _ff(["-f", "lavfi", "-i", "anoisesrc=d=0.7:c=white:a=0.25:r=48000",
             "-af", "bandpass=f=5000:w=3000,volume='0.3+0.7*abs(sin(2*PI*7*t))':eval=frame,afade=t=out:st=0.4:d=0.3", str(quill)])
    for p in sfx.glob("*.mp3"):
        _peak_normalize(p, -3.0)
    _peak_normalize(bed, -6.0)
    print(f"placeholder audio ready in {music} and {sfx}")
