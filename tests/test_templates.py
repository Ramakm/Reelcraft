import json
import re

import pytest

from reelcraft.core import plan as P
from reelcraft.core import templates as T


def test_every_builtin_template_is_valid():
    tpl = T.available()
    assert len(tpl) >= 10
    for name, t in tpl.items():
        assert t["summary"] and t["niche"], name
        entries = T.entries(name)
        assert not re.search(r"\{\w+\}", json.dumps(entries)), f"{name} has an unfilled placeholder"
        for clip_len in (4.0, 8.0, 60.0):                       # relative times must fit any clip length
            plan = P.build(entries, clip_len)
            assert plan.items and not plan.warnings, (name, clip_len)
            assert all(0 <= i.start < i.end <= clip_len + 1e-6 for i in plan.items), (name, clip_len)


def test_set_overrides_and_rejects_unknown():
    e = T.entries("hype-intro", {"title": "HELLO"})
    assert any(x.get("text") == "HELLO" for x in e)
    with pytest.raises(P.PlanError, match="no parameter"):
        T.entries("hype-intro", {"titel": "x"})
    with pytest.raises(P.PlanError, match="no template"):
        T.get("nope")


def test_save_and_use_your_own_look(tmp_path, monkeypatch):
    monkeypatch.setenv("REELCRAFT_HOME", str(tmp_path))
    T.save("My Intro", [{"fx": "flash", "start": "0%"}, {"fx": "badge", "start": "10%", "end": "50%", "text": "{tag}"}], "mine")
    got = T.available()["my-intro"]
    assert got["source"] == "yours"
    assert T.entries("my-intro")[1]["text"] == "{tag}"          # unknown braces stay put, not an error
    with pytest.raises(P.PlanError):
        T.save("bad/name", [])


def test_percent_and_from_end_times():
    assert P.parse_time("25%", 8) == 2.0
    assert P.parse_time("-3", 10) == 7.0
    with pytest.raises(P.PlanError):
        P.parse_time("50%")
