import numpy as np
import pytest

from reelcraft import demo
from reelcraft.core import media as M
from reelcraft.core import plan as P
from reelcraft.core import render as R

from .conftest import needs_ffmpeg

pytestmark = needs_ffmpeg


@pytest.fixture(scope="module")
def clip(tmp_path_factory):
    p = str(tmp_path_factory.mktemp("clip") / "demo.mp4")
    demo.make_demo_clip(p, 2)
    return p


def test_probe_and_size(clip):
    m = M.probe(clip)
    assert (m.width, m.height) == (720, 1280) and m.has_audio
    assert M.out_size(m) == (720, 1280)
    assert M.out_size(m, 540) == (540, 960)


def test_render_keeps_length_size_and_audio(clip, tmp_path):
    out = str(tmp_path / "o.mp4")
    R.render(clip, out, lambda d: P.build([{"fx": "punch-in", "start": 0.5, "end": 1.5}, {"fx": "badge", "text": "HI"}], d),
             width=360, face=demo.FACE)
    m = M.probe(out)
    assert (m.width, m.height) == (360, 640)
    assert m.has_audio and abs(m.duration - 2.0) < 0.2


def test_still_outside_window_matches_source(clip):
    plain, _ = R.stills(clip, lambda d: P.build([{"fx": "badge", "start": 1.5, "end": 1.9}], d), [0.2], width=360, face=demo.FACE)
    src = next(M.frames(M.probe(clip), 360, 640, 30, start=0.2, count=1))
    assert np.array_equal(plain[0], src)


def test_still_inside_window_differs(clip):
    imgs, _ = R.stills(clip, lambda d: P.build([{"fx": "badge", "start": 0, "end": 2}], d), [1.0], width=360, face=demo.FACE)
    src = next(M.frames(M.probe(clip), 360, 640, 30, start=1.0, count=1))
    assert not np.array_equal(imgs[0], src)
