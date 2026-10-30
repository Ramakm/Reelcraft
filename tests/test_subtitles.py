import numpy as np
import pytest

from reelcraft.core.plan import PlanError
from reelcraft.library import subtitles as S


def test_parse_srt_and_vtt(tmp_path):
    srt = tmp_path / "a.srt"
    srt.write_text("﻿1\r\n00:00:01,000 --> 00:00:02,500\r\n<i>Hello</i>\r\nthere\r\n\r\n2\r\n01:00:00,000 --> 01:00:01,000\r\nlate\r\n")
    cues = S._load(str(srt), 1)
    assert cues[0] == (1.0, 2.5, "Hello there") and cues[1][0] == 3600.0
    vtt = tmp_path / "a.vtt"
    vtt.write_text("WEBVTT\n\n00:01.500 --> 00:03.000\nshort form\n")
    assert S._load(str(vtt), 1) == ((1.5, 3.0, "short form"),)


def test_bad_files_explain_themselves(tmp_path):
    empty = tmp_path / "e.srt"
    empty.write_text("nothing here")
    with pytest.raises(PlanError, match="no captions"):
        S._load(str(empty), 2)
    with pytest.raises(PlanError, match="can't read"):
        S._load(str(tmp_path / "missing.srt"), 3)


def test_long_cues_split_without_orphans_and_keep_total_time():
    ch = S._chunks([(0.0, 6.0, "one two three four five six seven")], 3)
    assert [c[2] for c in ch] == [["one", "two", "three"], ["four", "five", "six", "seven"]]
    assert ch[0][0] == 0.0 and abs(ch[-1][1] - 6.0) < 1e-9
    assert all(abs(a[1] - b[0]) < 1e-9 for a, b in zip(ch, ch[1:]))


@pytest.mark.parametrize("style", S.STYLES)
def test_styles_draw_something_only_while_a_cue_is_active(style, frame, ctx):
    import os
    from reelcraft.core.registry import REGISTRY
    srt = os.path.join(os.path.dirname(__file__), "data", "sample.srt")
    fn = REGISTRY["subtitles"].fn
    ctx.window(1.5, 0.0, 8.0)
    on = fn(ctx, frame.copy(), file=srt, style=style, accent="amber", at="bottom", size=0, max_words=5)
    ctx.window(0.1, 0.0, 8.0)
    off = fn(ctx, frame.copy(), file=srt, style=style, accent="amber", at="bottom", size=0, max_words=5)
    assert not np.array_equal(on, frame) and np.array_equal(off, frame)
