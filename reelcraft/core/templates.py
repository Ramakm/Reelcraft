"""Style templates and saved looks.

A template is a named, reusable plan whose times are relative to the clip ("40%" or "-3" for three
seconds before the end), so it fits a 6 second clip and a 60 second clip alike. Text in `{braces}` is
filled from its `params`, which you override with --set key=value.

Built-in templates ship in reelcraft/templates/. Your own are saved to ~/.reelcraft/looks/
(set REELCRAFT_HOME to move it) and can be used the same way.
"""
import glob
import json
import os
import re

from .plan import PlanError

BUILTIN_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
_SAFE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,40}$")


def user_dir():
    return os.path.join(os.environ.get("REELCRAFT_HOME") or os.path.expanduser("~/.reelcraft"), "looks")


def _read(path):
    try:
        return json.load(open(path))
    except (OSError, ValueError) as e:
        raise PlanError(f"couldn't read template {path!r}: {e}") from None


def available():
    """name -> dict(meta..., source='built-in'|'yours', path). Your own looks win over built-ins of the same name."""
    found = {}
    for source, d in (("built-in", BUILTIN_DIR), ("yours", user_dir())):
        for path in sorted(glob.glob(os.path.join(d, "*.json"))):
            name = os.path.splitext(os.path.basename(path))[0]
            data = _read(path)
            found[name] = {"name": name, "niche": data.get("niche", ""), "summary": data.get("summary", ""),
                           "params": data.get("params", {}), "source": source, "path": path,
                           "effects": data.get("effects", [])}
    return found


def get(name):
    tpl = available()
    key = name.strip().lower().replace("_", "-").replace(" ", "-")
    if key not in tpl:
        raise PlanError(f"no template called {name!r}. Available: {', '.join(sorted(tpl))}")
    return tpl[key]


def fill(value, params):
    """Replace {key} in strings (recursively). Unknown braces are left alone."""
    if isinstance(value, str):
        return re.sub(r"\{(\w+)\}", lambda m: str(params.get(m.group(1), m.group(0))), value)
    if isinstance(value, dict):
        return {k: fill(v, params) for k, v in value.items()}
    if isinstance(value, list):
        return [fill(v, params) for v in value]
    return value


def entries(name, overrides=None):
    """The template's plan entries with parameters filled in."""
    tpl = get(name)
    params = {**tpl["params"], **(overrides or {})}
    unknown = set(overrides or {}) - set(tpl["params"])
    if unknown:
        raise PlanError(f"template {tpl['name']!r} has no parameter {sorted(unknown)[0]!r}. "
                        f"Parameters: {', '.join(tpl['params']) or 'none'}")
    return fill(tpl["effects"], params)


def save(name, effects, summary="", niche="custom"):
    key = name.strip().lower().replace(" ", "-")
    if not _SAFE.match(key):
        raise PlanError("look names use letters, numbers, - and _ (for example: my-intro)")
    d = user_dir()
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, key + ".json")
    json.dump({"niche": niche, "summary": summary or "My saved look", "params": {}, "effects": effects},
              open(path, "w"), indent=2)
    return path
