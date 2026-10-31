"""Script tools.

  pv script <ep> --export   episode.json -> script.md (for review)
  pv script <ep> --import   script.md -> episode.json narration (after your edits / paste)
  pv script <ep> --draft    draft script.md with the Anthropic API from research.md (opt-in, costs money)

script.md scene blocks look like:
    ### s01 · text_card · kenburns
    Narration text...
"""
from __future__ import annotations

import re

from . import episode as E
from .cache import cached_bytes
from .config import env, episode_dir

BLOCK = re.compile(r"^### (?P<id>[\w-]+)[^\n]*\n(?P<body>.*?)(?=^### |^## |\Z)", re.S | re.M)


def export(slug: str) -> None:
    ep_dir = episode_dir(slug)
    ep = E.load(ep_dir)
    lines = [f"# {ep['title']}", "", f"**Hook:** {ep['hook']}", ""]
    for i, alt in enumerate(ep.get("hook_alternatives", []), 1):
        lines.append(f"**Alternative hook {i}:** {alt}")
    lines += ["", f"**Lesson:** {ep['lesson']}", "", f"Words: {E.word_count(ep)} (target 420–480)", ""]
    acts = {a["act"]: a["name"] for a in ep.get("acts", [])}
    clip_of = {}
    for c in ep.get("clips", []):
        ids = [s["id"] for s in ep["scenes"]]
        if c.get("from_scene") in ids and c.get("to_scene") in ids:
            for sid in ids[ids.index(c["from_scene"]): ids.index(c["to_scene"]) + 1]:
                clip_of[sid] = c["id"]
    cur = None
    for s in ep["scenes"]:
        if s.get("act") != cur:
            cur = s.get("act")
            lines += [f"## Act {cur} — {acts.get(cur, '')}", ""]
        tag = f" · ✂ clip {clip_of[s['id']]}" if s["id"] in clip_of else ""
        lines += [f"### {s['id']} · {s['visual']['type']} · {s['motion']}{tag}", s["narration"].strip(), ""]
    (ep_dir / "script.md").write_text("\n".join(lines))
    print(f"wrote {ep_dir / 'script.md'}")


def import_(slug: str) -> None:
    ep_dir = episode_dir(slug)
    ep = E.load(ep_dir)
    text = (ep_dir / "script.md").read_text()
    blocks = {m["id"]: " ".join(m["body"].split()) for m in BLOCK.finditer(text)}
    n = 0
    for s in ep["scenes"]:
        if s["id"] in blocks and blocks[s["id"]] != s["narration"]:
            s["narration"] = blocks[s["id"]]
            n += 1
    E.save(ep_dir, ep)
    print(f"updated narration for {n} scene(s); {E.word_count(ep)} words")


SYSTEM = """You write narration for The Pre$ent Value, a faceless animated finance-history channel.
Rules: one cohesive story (beginning, turning point, finish), not a list of facts; hook in the first sentence;
420-480 words in four acts; concrete sensory detail; curious, respectful, educational tone; never disparage any
people or culture; one lesson; no financial advice. Use ONLY facts in the research notes provided. Do not invent
quotes, dates or sources; if the notes mark something uncertain, phrase it as uncertain.
Output markdown: '## Act N — name' headings, then '### sNN · <visual type> · <motion>' scene blocks (25-35 scenes,
each 1-2 sentences), then two alternative hooks."""


def draft(slug: str) -> None:
    import anthropic

    ep_dir = episode_dir(slug)
    ep = E.load(ep_dir)
    research = (ep_dir / "research.md").read_text()
    model = env("ANTHROPIC_MODEL", "claude-opus-5-5")
    payload = {"model": model, "system": SYSTEM, "title": ep["title"], "lesson": ep.get("lesson", ""), "research": research}

    def produce() -> bytes:
        client = anthropic.Anthropic(api_key=env("ANTHROPIC_API_KEY", required=True))
        msg = client.messages.create(
            model=model,
            max_tokens=8000,
            system=SYSTEM,
            messages=[{"role": "user", "content": f"Episode: {ep['title']}\nLesson: {ep.get('lesson', '')}\n\nResearch notes:\n{research}"}],
        )
        return "".join(b.text for b in msg.content if b.type == "text").encode()

    path, hit = cached_bytes("anthropic-script", payload, "md", produce)
    out = ep_dir / "script.draft.md"
    out.write_bytes(path.read_bytes())
    print(f"{'cache hit' if hit else 'drafted'} -> {out}. Review, then copy into script.md and run --import.")
