"""Easing curves and tiny animation helpers. Every function maps 0..1 to 0..1 (overshoot allowed)."""
import math

import numpy as np


def clamp(x, lo=0.0, hi=1.0):
    """Works on floats and on whole numpy masks."""
    return np.clip(x, lo, hi) if isinstance(x, np.ndarray) else max(lo, min(hi, x))


def lerp(a, b, t):
    return a + (b - a) * t


def remap(x, a, b):
    """Progress of x between a and b, clamped to 0..1."""
    return clamp((x - a) / (b - a)) if b != a else 1.0


def smooth(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def out_cubic(x):
    return 1 - (1 - clamp(x)) ** 3


def in_cubic(x):
    return clamp(x) ** 3


def in_out_cubic(x):
    x = clamp(x)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def out_expo(x):
    x = clamp(x)
    return 1.0 if x >= 1 else 1 - 2 ** (-10 * x)


def out_back(x, s=1.70158):
    x = clamp(x) - 1
    return 1 + (s + 1) * x ** 3 + s * x ** 2


def out_elastic(x):
    x = clamp(x)
    if x in (0.0, 1.0):
        return x
    return 2 ** (-10 * x) * math.sin((x * 10 - 0.75) * (2 * math.pi) / 3) + 1


def envelope(u, fade_in=0.15, fade_out=0.15):
    """0 -> 1 -> 0 over a window, so an effect eases in and out of existence."""
    return smooth(u / fade_in) * smooth((1 - u) / fade_out) if fade_in and fade_out else 1.0


def pop(u, dur=0.35):
    """Overshooting scale-in used by stickers and badges (0 -> ~1.1 -> 1)."""
    return out_back(u / dur) if dur else 1.0


EASINGS = {
    "linear": lambda x: clamp(x), "smooth": smooth, "out": out_cubic, "in": in_cubic,
    "inout": in_out_cubic, "expo": out_expo, "back": out_back, "elastic": out_elastic,
}
