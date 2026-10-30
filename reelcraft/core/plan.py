"""Edit plans: the list of effects to apply, and when.

A plan is JSON that Claude (or a person) can write by hand:

    {"effects": [
        {"fx": "punch-in", "start": 2.0, "end": 3.5, "zoom": 1.4},
        {"fx": "kinetic-title", "start": 3, "end": 6, "text": "WAIT FOR IT"}
    ]}

Anything besides fx/start/end (and the optional "sound") is an option for that effect.
Times can be seconds (2.5), m:ss (1:05.5), a percentage of the clip ("40%") or counted back from the end ("-3").
"""
import json
import re
from dataclasses import dataclass, field

from .registry import CATEGORIES, coerce, resolve


class PlanError(ValueError):
    pass


@dataclass
class Item:
    name: str
    start: float
    end: float
    params: dict
    order: int = 0
    sound: str = ""      # "" = use the effect's default cue (when sound is on), "none" = silent


@dataclass
class Plan:
    items: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    cues: list = field(default_factory=list)      # sound cues, filled in by the renderer

    def active(self, t):
        return [it for it in self.items if it.start <= t < it.end]

    @property
    def needs_face(self):
        return any(resolve(i.name).face for i in self.items)


def parse_time(v, duration=None):
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().lower()
    if s in ("end", "last") and duration is not None:
        return duration
    if s.endswith("%") or s.startswith("-"):
        if duration is None:
            raise PlanError(f"{v!r} is relative to the clip length, which isn't known here")
        try:
            return duration * float(s[:-1]) / 100 if s.endswith("%") else max(0.0, duration + float(s))
        except ValueError:
            raise PlanError(f"can't read {v!r} as a time") from None
    if re.fullmatch(r"\d+(\.\d+)?s?", s):
        return float(s.rstrip("s"))
    m = re.fullmatch(r"(?:(\d+):)?(\d+):(\d+(?:\.\d+)?)", s)
    if m:
        h, mi, sec = m.groups()
        return int(h or 0) * 3600 + int(mi) * 60 + float(sec)
    raise PlanError(f"can't read {v!r} as a time. Use seconds (2.5) or m:ss (1:05).")


def build(entries, duration=None):
    plan = Plan()
    for n, e in enumerate(entries):
        if not isinstance(e, dict) or "fx" not in e:
            raise PlanError(f"entry {n + 1} needs an 'fx' name")
        e = dict(e)
        e.pop("_comment", None)
        try:
            eff = resolve(e.pop("fx"))
        except KeyError as err:
            raise PlanError(str(err.args[0])) from None
        start = parse_time(e.pop("start", 0), duration)
        end = e.pop("end", None)
        end = start + eff.default_len if end is None else parse_time(end, duration)
        e.pop("options", None) if not isinstance(e.get("options"), dict) else e.update(e.pop("options"))
        sound = str(e.pop("sound", "") or "")
        e.pop("_comment", None)
        if end <= start:
            raise PlanError(f"{eff.name}: end ({end}) must be after start ({start})")
        if duration:
            if start >= duration:
                plan.warnings.append(f"{eff.name} starts at {start:.1f}s but the clip is only {duration:.1f}s long; skipped")
                continue
            if end > duration:
                end = duration
        try:
            params = coerce(eff, e)
        except (KeyError, ValueError) as err:
            raise PlanError(str(err.args[0])) from None
        plan.items.append(Item(eff.name, start, end, params, n, sound))
    # Stable sort by layer: camera < look < frame < motion < sticker; plan order breaks ties.
    plan.items.sort(key=lambda i: (CATEGORIES.index(resolve(i.name).category), i.order))
    return plan


def load(path, duration=None):
    try:
        data = json.load(open(path))
    except (OSError, ValueError) as err:
        raise PlanError(f"couldn't read plan {path!r}: {err}") from None
    return build(data["effects"] if isinstance(data, dict) else data, duration)


def parse_spec(spec):
    """'punch-in@2-3.5 zoom=1.4 text="hello there"' -> entry dict. Used by the CLI."""
    import shlex
    head, *rest = shlex.split(spec)
    name, _, when = head.partition("@")
    e = {"fx": name}
    if when:
        a, _, b = when.partition("-")
        if a:
            e["start"] = a
        if b:
            e["end"] = b
    for kv in rest:
        k, _, v = kv.partition("=")
        if not _:
            raise PlanError(f"option {kv!r} should look like key=value")
        e[k] = v
    return e
