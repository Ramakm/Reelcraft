import numpy as np
import pytest

from reelcraft.core import plan as P
from reelcraft.core import sfx


@pytest.mark.parametrize("name", sorted(sfx.SOUNDS))
def test_every_sound_is_finite_audible_and_short(name):
    x = sfx.render_sound(name)
    assert np.isfinite(x).all()
    assert 0.5 < np.abs(x).max() <= 0.91
    assert len(x) < sfx.SR * 2


def test_sounds_are_deterministic():
    assert np.array_equal(sfx.render_sound("whoosh"), sfx.render_sound("whoosh"))


def test_default_cues_point_at_real_sounds():
    from reelcraft.core.registry import REGISTRY
    for fx, snd in sfx.DEFAULT_CUE.items():
        assert fx in REGISTRY and snd in sfx.SOUNDS, (fx, snd)


def test_mix_puts_energy_at_the_cue_time():
    base = np.zeros((sfx.SR * 3, 2), np.float32)
    out = sfx.mix(base, [("pop", 1.0)])
    quiet, loud = np.abs(out[: sfx.SR - 10]).max(), np.abs(out[sfx.SR: sfx.SR + 2000]).max()
    assert quiet == 0 and loud > 0.1


def test_cues_for_respects_explicit_sound_and_multi_cue_effects():
    plan = P.build([{"fx": "countdown", "start": 0, "end": 3}, {"fx": "sticker", "start": 1, "sound": "none"},
                    {"fx": "badge", "start": 2, "sound": "coin"}, {"fx": "grade", "start": 0}])
    cues = {it.name: sfx.cues_for(it) for it in plan.items}
    assert len(cues["countdown"]) == 3
    assert cues["sticker"] == [] and cues["badge"] == [("coin", 2.0)] and cues["grade"] == []
