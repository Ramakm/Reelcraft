"""Helpers shared by effect modules (not an effect itself)."""
import math

import numpy as np

from reelcraft.core.canvas import text_width
from reelcraft.core.easing import clamp, out_cubic, smooth


def place(ctx, at, gap=0.15):
    """'above' | 'left' | ... or 'x,y' as fractions of the frame -> pixel position."""
    if "," in str(at):
        try:
            fx, fy = (float(v) for v in str(at).split(","))
        except ValueError:
            raise ValueError(f"position {at!r} should be a name like 'above' or fractions like '0.8,0.3'") from None
        return fx * ctx.W, fy * ctx.H
    return ctx.anchor(at, gap)


def fit_size(txt, fname, max_w, max_size, min_size=18):
    size = max_size
    while size > min_size and text_width(txt, fname, size) > max_w:
        size -= 2
    return size


def fade_io(ctx, fin=0.25, fout=0.25):
    """Opacity 0->1->0 using fixed seconds at each end, so short and long windows feel the same."""
    a = smooth(ctx.lt / fin) if fin else 1.0
    b = smooth(ctx.left / fout) if fout else 1.0
    return min(a, b)


def wrap_words(words, fname, size, max_w):
    lines, cur = [], []
    for w in words:
        trial = " ".join(cur + [w])
        if cur and text_width(trial, fname, size) > max_w:
            lines.append(cur)
            cur = [w]
        else:
            cur.append(w)
    if cur:
        lines.append(cur)
    return lines


def noise1(t, seed=0.0):
    """Smooth deterministic 1-D noise in about -1..1 (sum of incommensurate sines)."""
    return (math.sin(t * 6.1 + seed) + math.sin(t * 9.7 + seed * 1.7 + 1.3) + math.sin(t * 14.3 + seed * 2.3 + 2.1)) / 3


def hold_curve(ctx, fin=0.25, fout=0.25):
    """0 -> 1 -> 0 eased curve with fixed in/out durations; the zoom-in-hold-release shape."""
    return min(out_cubic(ctx.lt / fin) if fin else 1.0, out_cubic(ctx.left / fout) if fout else 1.0)


__all__ = ["place", "fit_size", "fade_io", "wrap_words", "noise1", "hold_curve", "np", "clamp"]
