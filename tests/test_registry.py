import pytest

from reelcraft.core.registry import CATEGORIES, REGISTRY, coerce, resolve


def test_every_effect_is_well_formed():
    assert len(REGISTRY) >= 25
    for e in REGISTRY.values():
        assert e.category in CATEGORIES
        assert e.summary and e.summary[0].isalnum(), e.name
        assert e.default_len > 0
        for p in e.params:
            assert p.doc, f"{e.name}.{p.name} needs a doc string"
            if p.choices:
                assert p.default in p.choices, f"{e.name}.{p.name} default not in choices"


def test_aliases_resolve_and_do_not_collide():
    assert resolve("Lean_In").name == "punch-in"
    assert resolve("zoom").name == "punch-in"
    names = [a for e in REGISTRY.values() for a in e.aliases]
    assert len(names) == len(set(names))
    assert not set(names) & set(REGISTRY)


def test_unknown_effect_suggests():
    with pytest.raises(KeyError, match="Did you mean"):
        resolve("punhc")


def test_coerce_casts_and_validates():
    e = resolve("punch-in")
    assert coerce(e, {"zoom": "1.8", "hold": "no"}) == {"zoom": 1.8, "target": "face", "hold": False, "snap": 0.18}
    with pytest.raises(KeyError):
        coerce(e, {"zoomm": 2})
    with pytest.raises(ValueError):
        coerce(e, {"target": "moon"})
