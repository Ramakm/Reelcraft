"""The effect registry.

An effect is a plain function `fn(ctx, frame, **params) -> frame` registered with `@effect`.
Registration captures everything the CLI, the docs generator and Claude need to know about it,
so adding a new effect is one decorated function and nothing else.
"""
from dataclasses import dataclass, field

# Draw order: camera moves first, then colour, then framing, then everything that sits on top.
CATEGORIES = ["camera", "look", "frame", "motion", "sticker"]
CATEGORY_BLURB = {
    "camera": "Moves the picture itself: punches, drifts, shakes.",
    "look": "Colour, texture and signal damage.",
    "frame": "Changes the shape of the shot: bars, borders, reveals.",
    "motion": "Animated type and graphics that sit on top of the video.",
    "sticker": "Die-cut stickers, badges and particles.",
}


@dataclass
class Param:
    name: str
    default: object
    doc: str
    choices: tuple = ()

    @property
    def kind(self):
        return type(self.default).__name__


@dataclass
class Effect:
    name: str
    category: str
    summary: str
    fn: object
    params: list = field(default_factory=list)
    face: bool = False          # needs face tracking
    aliases: tuple = ()
    default_len: float = 2.5    # seconds, used when the plan gives no end

    def defaults(self):
        return {p.name: p.default for p in self.params}


REGISTRY = {}
_ALIASES = {}


def effect(name, category, summary, params=(), face=False, aliases=(), default_len=2.5):
    if category not in CATEGORIES:
        raise ValueError(f"unknown category {category!r}")

    def deco(fn):
        if name in REGISTRY:
            raise ValueError(f"duplicate effect {name!r}")
        REGISTRY[name] = Effect(name, category, summary, fn, list(params), face, tuple(aliases), default_len)
        for a in aliases:
            _ALIASES[a] = name
        return fn
    return deco


def resolve(name):
    """Look an effect up by name or alias; tolerant of case and underscores."""
    key = name.strip().lower().replace("_", "-").replace(" ", "-")
    key = _ALIASES.get(key, key)
    if key not in REGISTRY:
        close = [n for n in REGISTRY if key[:4] and n.startswith(key[:4])] or sorted(REGISTRY)[:6]
        raise KeyError(f"no effect called {name!r}. Did you mean: {', '.join(close[:6])}?")
    return REGISTRY[key]


def coerce(eff, raw):
    """Merge user options over defaults and cast each to the type of its default."""
    out = eff.defaults()
    known = {p.name: p for p in eff.params}
    for k, v in raw.items():
        if k not in known:
            raise KeyError(f"{eff.name} has no option {k!r}. Options: {', '.join(known) or 'none'}")
        d = known[k].default
        if isinstance(d, bool):
            v = v if isinstance(v, bool) else str(v).lower() in ("1", "true", "yes", "on")
        elif isinstance(d, int):
            v = int(float(v))
        elif isinstance(d, float):
            v = float(v)
        else:
            v = str(v)
        if known[k].choices and v not in known[k].choices:
            raise ValueError(f"{eff.name}.{k} must be one of {', '.join(map(str, known[k].choices))} (got {v!r})")
        out[k] = v
    return out


def by_category():
    groups = {c: [] for c in CATEGORIES}
    for e in REGISTRY.values():
        groups[e.category].append(e)
    for g in groups.values():
        g.sort(key=lambda e: e.name)
    return groups


def load_library():
    """Import every module under reelcraft.library so its effects register themselves."""
    import importlib, pkgutil
    from reelcraft import library
    for m in pkgutil.iter_modules(library.__path__):
        importlib.import_module(f"reelcraft.library.{m.name}")
    return REGISTRY
