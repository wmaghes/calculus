import json
from pathlib import Path

from pv import episode as E
from pv.captions import align, snap
from pv.cache import cached_bytes, key_for

ROOT = Path(__file__).resolve().parent.parent


def test_template_and_test_episode_validate():
    for p in [ROOT / "templates/episode", ROOT / "episodes/000-pipeline-test"]:
        assert E.validate(E.load(p)) == [], p


def test_align_keeps_script_spelling_and_fills_gaps():
    script = "Pre$ent Value compounds slowly".split()
    heard = [{"word": "present", "start": 0.0, "end": 0.4}, {"word": "value", "start": 0.5, "end": 0.8},
             {"word": "slowly", "start": 1.5, "end": 1.9}]  # "compounds" missed by recogniser
    out = align(script, heard)
    assert [w["word"] for w in out] == script
    assert out[2]["start"] >= out[1]["end"] and out[2]["end"] <= out[3]["start"]


def test_snap_makes_scenes_contiguous_and_sets_clips():
    ep = {"narration_duration": 4.0, "acts": [{"act": 1}],
          "clips": [{"id": "A", "from_scene": "a", "to_scene": "b"}],
          "scenes": [{"id": "a", "act": 1, "narration": "one two"}, {"id": "b", "act": 1, "narration": "three"}]}
    words = [{"word": w, "start": s, "end": s + 0.3} for w, s in [("one", 0.2), ("two", 0.6), ("three", 2.0)]]
    snap(ep, words)
    a, b = ep["scenes"]
    assert a["start"] == 0 and a["end"] == b["start"] == 2.0 and b["end"] == 4.0
    assert ep["clips"][0]["start"] == 0 and ep["clips"][0]["end"] == 4.0


def test_cache_calls_producer_once(tmp_path, monkeypatch):
    import pv.cache as C
    monkeypatch.setattr(C, "CACHE", tmp_path)
    calls = []
    produce = lambda: calls.append(1) or b"audio"
    p1, hit1 = cached_bytes("t", {"x": 1}, "bin", produce)
    p2, hit2 = cached_bytes("t", {"x": 1}, "bin", produce)
    assert (hit1, hit2) == (False, True) and p1 == p2 and len(calls) == 1
    assert key_for("t", {"a": 1, "b": 2}) == key_for("t", {"b": 2, "a": 1})


def test_no_secrets_committed():
    gi = (ROOT / ".gitignore").read_text()
    assert ".env" in gi.splitlines()
