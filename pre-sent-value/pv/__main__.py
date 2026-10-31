"""python -m pv <command> <episode>"""
from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="pv", description="The Pre$ent Value pipeline")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("new", help="scaffold an episode from the template")
    s.add_argument("slug")
    s.add_argument("--title")

    s = sub.add_parser("script", help="export / import / draft the script")
    s.add_argument("episode")
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--export", action="store_true", help="episode.json -> script.md")
    g.add_argument("--import", dest="import_", action="store_true", help="script.md -> episode.json")
    g.add_argument("--draft", action="store_true", help="draft with the Anthropic API (costs money)")

    s = sub.add_parser("voice", help="narration via ElevenLabs (cached)")
    s.add_argument("episode")
    s.add_argument("--yes", action="store_true", help="skip the spend confirmation")

    s = sub.add_parser("captions", help="faster-whisper word timings + snap scene timing")
    s.add_argument("episode")

    s = sub.add_parser("render", help="render master, 9:16 clips and thumbnail")
    s.add_argument("episode")
    s.add_argument("--only", choices=["all", "master", "clips", "thumbnail"], default="all")
    s.add_argument("--no-normalize", action="store_true")

    s = sub.add_parser("qc", help="run quality checks")
    s.add_argument("episode")

    sub.add_parser("brand-assets", help="(re)generate placeholder music + sfx").add_argument("--force", action="store_true")

    a = p.parse_args(argv)
    if a.cmd == "new":
        from .new import run
        run(a.slug, a.title)
    elif a.cmd == "script":
        from . import script
        script.export(a.episode) if a.export else script.import_(a.episode) if a.import_ else script.draft(a.episode)
    elif a.cmd == "voice":
        from .voice import run
        run(a.episode, a.yes)
    elif a.cmd == "captions":
        from .captions import run
        run(a.episode)
    elif a.cmd == "render":
        from .render import render
        for path in render(a.episode, a.only, False if a.no_normalize else None):
            print("✓", path)
    elif a.cmd == "qc":
        from .qc import run
        return 0 if run(a.episode) else 1
    elif a.cmd == "brand-assets":
        from .brand_assets import generate
        generate(a.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
