"""Every effect must run on a synthetic frame at several moments and keep the frame valid."""
import os

import numpy as np
import pytest

from reelcraft.core.context import Face

from reelcraft.core.registry import REGISTRY, coerce

SRT = os.path.join(os.path.dirname(__file__), "data", "sample.srt")
SHOW = {"subtitles": {"file": SRT}, "kinetic-title": {"text": "WAIT FOR *IT*"}, "stat-card": {"value": "97%"}, "caption": {"text": "one two three four"}}


@pytest.mark.parametrize("name", sorted(REGISTRY))
@pytest.mark.parametrize("u", [0.0, 0.05, 0.5, 0.97])
def test_effect_runs(name, u, frame, ctx):
    eff = REGISTRY[name]
    ctx.window(1.0 + u * eff.default_len, 1.0, 1.0 + eff.default_len, 3)
    out = eff.fn(ctx, frame.copy(), **coerce(eff, SHOW.get(name, {})))
    assert out.shape == frame.shape and out.dtype == np.uint8


@pytest.mark.parametrize("name", sorted(REGISTRY))
def test_effect_is_deterministic(name, frame, ctx):
    """Stateless effects: same inputs, same pixels. This is what keeps stills identical to renders."""
    eff = REGISTRY[name]
    outs = []
    for _ in range(2):
        ctx.face = Face(180, 230, 90, 112)      # the renderer resets this every frame
        ctx.window(1.4, 1.0, 1.0 + eff.default_len, 2)
        outs.append(eff.fn(ctx, frame.copy(), **coerce(eff, SHOW.get(name, {}))))
    assert np.array_equal(*outs)


def test_effects_never_mutate_the_input_when_returning_new_frames(frame, ctx):
    eff = REGISTRY["grade"]
    before = frame.copy()
    ctx.window(1.5, 1.0, 3.0)
    eff.fn(ctx, frame, **eff.defaults())
    assert np.array_equal(frame, before)


def test_title_markup_handles_punctuation_and_multiword_spans():
    from reelcraft.library.motion import parse_markup
    assert parse_markup("WAIT FOR *IT*") == [("WAIT", False), ("FOR", False), ("IT", True)]
    assert parse_markup("CAN AI BECOME *CONSCIOUS*?") == [("CAN", False), ("AI", False), ("BECOME", False), ("CONSCIOUS?", True)]
    assert parse_markup("AI SOLVED *PROTEIN FOLDING* FAST") == [("AI", False), ("SOLVED", False), ("PROTEIN", True), ("FOLDING", True), ("FAST", False)]
    assert parse_markup("no stars here") == [("no", False), ("stars", False), ("here", False)]
    assert all("*" not in w for w, _ in parse_markup("*a* b* *c"))


def test_stickers_and_badges_stay_fully_on_screen_even_on_a_huge_face(frame):
    """A face bigger than the frame used to push top-left/top-right stickers half off the picture."""
    from reelcraft.core.context import Ctx, Face
    from reelcraft.core.registry import REGISTRY, coerce
    big = Ctx(360, 640, 30, Face(180, 320, 520, 650))
    for name, opts in (("badge", {"text": "NEW RECORD", "shape": "burst", "at": "top-left", "size": 90}),
                       ("sticker", {"name": "star", "at": "top-right", "size": 300})):
        eff = REGISTRY[name]
        big.window(1.2, 1.0, 3.5)
        base = np.zeros_like(frame)
        out = eff.fn(big, base.copy(), **coerce(eff, opts))
        ys, xs = np.nonzero(out.any(axis=2))
        assert xs.min() >= 0 and xs.max() <= 359 and ys.min() >= 0
        assert xs.min() > 2 and xs.max() < 357, f"{name} touches the left/right edge"
