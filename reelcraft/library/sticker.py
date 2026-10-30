"""Die-cut stickers, badges and particles. All art is drawn in code, so there are no image assets to license."""
import math
from functools import lru_cache

import numpy as np

from reelcraft.core.canvas import (blit, draw_sprite, over, rgb, rrect_sprite, text_sprite, tint, with_outline,
                                   with_shadow)
from reelcraft.core.easing import clamp, lerp, out_back, out_cubic, out_elastic, smooth
from reelcraft.core.registry import Param, effect

from ._util import fade_io, noise1, place


# ---------- shape toolkit ----------
def catmull(points, n=14, closed=True):
    """Smooth curve through control points (Catmull-Rom)."""
    P = [np.array(p, float) for p in points]
    out = []
    m = len(P)
    for i in range(m if closed else m - 1):
        p0, p1, p2, p3 = P[(i - 1) % m], P[i], P[(i + 1) % m], P[(i + 2) % m]
        for t in np.linspace(0, 1, n, endpoint=False):
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    return out


def lighten(c, k=0.45):
    return tuple(int(v + (255 - v) * k) for v in rgb(c))


def darken(c, k=0.3):
    return tuple(int(v * (1 - k)) for v in rgb(c))


def _poly(d, pts, S, fill):
    d.polygon([(x * S, y * S) for x, y in pts], fill=tuple(fill) + (255,))


# Each painter draws a sticker into a unit box (0..1) given a primary colour.
def _heart(d, S, c):
    pts = [(0.5 + 0.0296 * 16 * math.sin(t) ** 3,
            0.46 - 0.0296 * (13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)))
           for t in np.linspace(0, 2 * math.pi, 120)]
    _poly(d, pts, S, rgb(c))
    d.ellipse([0.2 * S, 0.2 * S, 0.34 * S, 0.3 * S], fill=lighten(c, 0.7) + (230,))


def _star(d, S, c):
    pts = [(0.5 + (0.46 if i % 2 == 0 else 0.2) * math.cos(-math.pi / 2 + i * math.pi / 5),
            0.53 + (0.46 if i % 2 == 0 else 0.2) * math.sin(-math.pi / 2 + i * math.pi / 5)) for i in range(10)]
    _poly(d, pts, S, rgb(c))
    inner = [(0.5 + (x - 0.5) * 0.5, 0.53 + (y - 0.53) * 0.5) for x, y in pts]
    _poly(d, inner, S, lighten(c, 0.35))


def _sparkle(d, S, c):
    pts = [(0.5 + 0.46 * math.cos(t) ** 3, 0.5 + 0.46 * math.sin(t) ** 3) for t in np.linspace(0, 2 * math.pi, 80)]
    _poly(d, pts, S, rgb(c))
    core = [(0.5 + 0.2 * math.cos(t) ** 3, 0.5 + 0.2 * math.sin(t) ** 3) for t in np.linspace(0, 2 * math.pi, 60)]
    _poly(d, core, S, lighten(c, 0.8))


def _bolt(d, S, c):
    pts = [(0.58, 0.04), (0.2, 0.55), (0.46, 0.55), (0.36, 0.96), (0.8, 0.4), (0.53, 0.4), (0.7, 0.04)]
    _poly(d, pts, S, rgb(c))
    _poly(d, [(0.58, 0.04), (0.44, 0.3), (0.58, 0.3), (0.66, 0.04)], S, lighten(c, 0.5))


def _arrow(d, S, c):
    ctrl = [(0.1, 0.85), (0.12, 0.35), (0.55, 0.12), (0.82, 0.3)]
    pts = []
    for t in np.linspace(0, 1, 40):
        a = (1 - t) ** 3, 3 * t * (1 - t) ** 2, 3 * t ** 2 * (1 - t), t ** 3
        pts.append((sum(w * p[0] for w, p in zip(a, ctrl)), sum(w * p[1] for w, p in zip(a, ctrl))))
    wd = 0.075
    for (x, y) in pts:
        d.ellipse([(x - wd / 2) * S, (y - wd / 2) * S, (x + wd / 2) * S, (y + wd / 2) * S], fill=rgb(c) + (255,))
    tip = pts[-1]
    ang = math.atan2(pts[-1][1] - pts[-4][1], pts[-1][0] - pts[-4][0])
    for da in (2.5, -2.5):
        ex, ey = tip[0] + 0.28 * math.cos(ang + da), tip[1] + 0.28 * math.sin(ang + da)
        d.line([(tip[0] * S, tip[1] * S), (ex * S, ey * S)], fill=rgb(c) + (255,), width=int(wd * S))
        d.ellipse([(ex - wd / 2) * S, (ey - wd / 2) * S, (ex + wd / 2) * S, (ey + wd / 2) * S], fill=rgb(c) + (255,))


def _check(d, S, c):
    d.ellipse([0.04 * S, 0.04 * S, 0.96 * S, 0.96 * S], fill=rgb(c) + (255,))
    d.ellipse([0.1 * S, 0.1 * S, 0.9 * S, 0.9 * S], outline=lighten(c, 0.4) + (255,), width=int(0.025 * S))
    pts = [(0.27, 0.52), (0.44, 0.69), (0.74, 0.34)]
    w = int(0.1 * S)
    d.line([(x * S, y * S) for x, y in pts], fill=(255, 255, 255, 255), width=w, joint="curve")
    for x, y in (pts[0], pts[-1]):
        d.ellipse([x * S - w / 2, y * S - w / 2, x * S + w / 2, y * S + w / 2], fill=(255, 255, 255, 255))


def _crown(d, S, c):
    pts = [(0.08, 0.78), (0.04, 0.28), (0.3, 0.52), (0.5, 0.14), (0.7, 0.52), (0.96, 0.28), (0.92, 0.78)]
    _poly(d, pts, S, rgb(c))
    d.rounded_rectangle([0.08 * S, 0.74 * S, 0.92 * S, 0.9 * S], radius=int(0.04 * S), fill=darken(c, 0.12) + (255,))
    for x, col in ((0.3, "#FF5A4F"), (0.5, "#4AA8FF"), (0.7, "#FF5A4F")):
        d.ellipse([(x - 0.04) * S, 0.78 * S, (x + 0.04) * S, 0.86 * S], fill=rgb(col) + (255,))
    for x, y in ((0.04, 0.28), (0.5, 0.14), (0.96, 0.28)):
        d.ellipse([(x - 0.05) * S, (y - 0.05) * S, (x + 0.05) * S, (y + 0.05) * S], fill=lighten(c, 0.5) + (255,))


def _flame(d, S, c):
    outer = [(0.5, 0.02), (0.68, 0.26), (0.9, 0.5), (0.86, 0.78), (0.62, 0.97), (0.38, 0.97), (0.14, 0.78), (0.1, 0.5), (0.3, 0.3)]
    _poly(d, catmull(outer, 10), S, rgb(c))
    inner = [(0.5, 0.36), (0.66, 0.58), (0.68, 0.8), (0.5, 0.94), (0.32, 0.8), (0.34, 0.58)]
    _poly(d, catmull(inner, 10), S, lighten(c, 0.55))
    core = [(0.5, 0.6), (0.58, 0.74), (0.5, 0.88), (0.42, 0.74)]
    _poly(d, catmull(core, 8), S, lighten(c, 0.9))


def _burst(d, S, c):
    n = 14
    pts = [(0.5 + (0.48 if i % 2 == 0 else 0.36) * math.cos(i * math.pi / n * 1.0 * 1), 0.5 + (0.48 if i % 2 == 0 else 0.36) * math.sin(i * math.pi / n)) for i in range(2 * n)]
    _poly(d, pts, S, rgb(c))
    inner = [(0.5 + (x - 0.5) * 0.82, 0.5 + (y - 0.5) * 0.82) for x, y in pts]
    _poly(d, inner, S, lighten(c, 0.25))


def _smile(d, S, c):
    d.ellipse([0.04 * S, 0.04 * S, 0.96 * S, 0.96 * S], fill=rgb(c) + (255,))
    d.ellipse([0.16 * S, 0.14 * S, 0.4 * S, 0.26 * S], fill=lighten(c, 0.6) + (200,))
    for x in (0.34, 0.66):
        d.ellipse([(x - 0.06) * S, 0.34 * S, (x + 0.06) * S, 0.54 * S], fill=(30, 22, 20, 255))
    d.arc([0.25 * S, 0.4 * S, 0.75 * S, 0.8 * S], 20, 160, fill=(30, 22, 20, 255), width=int(0.06 * S))


ART = {  # name: (painter, default colour)
    "heart": (_heart, "#FF3D6E"), "star": (_star, "#FFB627"), "sparkle": (_sparkle, "#FFD84A"), "bolt": (_bolt, "#FFD020"),
    "arrow": (_arrow, "#FF5A4F"), "check": (_check, "#2FD18B"), "crown": (_crown, "#FFB627"), "flame": (_flame, "#FF6A2B"),
    "burst": (_burst, "#FF5A4F"), "smile": (_smile, "#FFCB3B"),
}
STICKERS = tuple(ART)


@lru_cache(maxsize=128)
def sticker_art(name, size, color=None):
    painter, default = ART[name]
    art = draw_sprite(size, size, lambda d, S: painter(d, S * size, color or default))   # painters draw in a unit box
    if name in ("sparkle",):
        return with_shadow(art, blur=size * 0.04, offset=(0, int(size * 0.03)), opacity=0.35)
    # die-cut: white border, then shadow
    return with_shadow(with_outline(art, max(3, int(size * 0.07)), "#FFFFFF"), blur=size * 0.05, offset=(0, int(size * 0.05)), opacity=0.4)


def _anim(ctx, mode, seed=0.0):
    """-> (scale, rotation_deg, dy_px, alpha) for a pop-in / idle / pop-out lifecycle."""
    k_in = out_back(ctx.lt / 0.4, 2.4)
    k_out = 1 - smooth((0.25 - ctx.left) / 0.25)
    sc, rot, dy = k_in * k_out, 0.0, 0.0
    idle = ctx.lt
    if mode == "float":
        dy = math.sin(idle * 2.6 + seed) * ctx.px(14)
    elif mode == "wiggle":
        rot = math.sin(idle * 7 + seed) * 9
    elif mode == "pulse":
        sc *= 1 + 0.09 * math.sin(idle * 8 + seed)
    elif mode == "spin":
        rot = 360 * out_cubic(ctx.lt / 0.8)
    elif mode == "bounce":
        dy = -abs(math.sin(idle * 4.5 + seed)) * ctx.px(36)
    return sc, rot, dy, clamp(ctx.lt * 12) * clamp(ctx.left * 8)


@effect("sticker", "sticker", "Pop a die-cut sticker onto the shot: " + ", ".join(STICKERS) + ".",
        params=[Param("name", "sparkle", "Which sticker.", STICKERS), Param("at", "top-right", "A face anchor (above, left, right, top-left, top-right, below) or x,y fractions like 0.8,0.2."),
                Param("size", 260, "Width at 1080 wide."), Param("color", "", "Override the sticker's main colour."),
                Param("tilt", -8.0, "Degrees of tilt."), Param("motion", "float", "Idle animation.", ("float", "wiggle", "pulse", "spin", "bounce", "none")),
                Param("flip", False, "Mirror it.")],
        face=True, aliases=("stickers", "emoji"), default_len=2.5)
def sticker(ctx, frame, name, at, size, color, tilt, motion, flip):
    x, y = place(ctx, at, 0.1)
    sc, rot, dy, a = _anim(ctx, motion)
    spr = sticker_art(name, max(32, int(ctx.px(size))), color or None)
    return blit(frame, spr, x, y + dy, scale=sc, rot=tilt + rot, alpha=a, flip_x=flip)


# ---------- badge ----------
@lru_cache(maxsize=64)
def _badge(text, shape, color, ink, size):
    t = text_sprite(text.upper(), "display", size, ink, tracking=int(size * 0.06), pad=0)
    th, tw = t.shape[:2]
    if shape == "burst":
        d_ = int(max(tw, th) * 1.9)
        base = draw_sprite(d_, d_, lambda d, S: _burst(d, S * d_, color))
        blit(base, t, d_ / 2, d_ / 2)
    elif shape == "tape":
        w, h = tw + int(size * 1.0), th + int(size * 0.4)
        base = rrect_sprite(w, h, int(size * 0.06), color)
        zig = draw_sprite(w, h, lambda d, S: [d.polygon([(x * S, 0), ((x + 6) * S, 0), ((x + 3) * S, h * 0.14 * S)], fill=(0, 0, 0, 40)) for x in range(0, w, 12)])
        base = over(base, zig)
        blit(base, t, w / 2, h / 2)
    else:  # pill
        w, h = tw + int(size * 1.0), th + int(size * 0.5)
        base = rrect_sprite(w, h, h // 2, color)
        blit(base, t, w / 2, h / 2)
    return with_shadow(with_outline(base, max(2, int(size * 0.07)), "#FFFFFF"), blur=size * 0.18, offset=(0, int(size * 0.14)), opacity=0.4)


@effect("badge", "sticker", "Text stickers: NEW, LIVE, POV, PART 1. Pill, burst or tape.",
        params=[Param("text", "NEW", "What it says."), Param("shape", "pill", "Badge shape.", ("pill", "burst", "tape")),
                Param("at", "top-left", "Anchor name or x,y fractions."), Param("color", "coral", "Fill colour."),
                Param("ink", "white", "Text colour."), Param("size", 78, "Type size at 1080 wide."),
                Param("tilt", -6.0, "Degrees of tilt."), Param("motion", "wiggle", "Idle animation.", ("float", "wiggle", "pulse", "bounce", "none"))],
        face=True, aliases=("tag", "label-sticker", "pill"), default_len=2.5)
def badge(ctx, frame, text, shape, at, color, ink, size, tilt, motion):
    x, y = place(ctx, at, 0.08)
    sc, rot, dy, a = _anim(ctx, motion)
    spr = _badge(text, shape, color, ink, max(16, int(ctx.px(size))))
    return blit(frame, spr, x, y + dy, scale=sc, rot=tilt + rot, alpha=a)


# ---------- particles ----------
CONFETTI = ["#FF5A4F", "#FFB627", "#C6F432", "#4FE3B5", "#4AA8FF", "#8B5CF6", "#FF6FB5"]


@lru_cache(maxsize=128)
def _bit(kind, w, h, color):
    if kind == "dot":
        return draw_sprite(w, w, lambda d, S: d.ellipse([0, 0, w * S - 1, w * S - 1], fill=rgb(color) + (255,)))
    if kind == "streamer":
        return rrect_sprite(max(2, w // 3), h * 2, max(1, w // 6), color)
    return rrect_sprite(w, h, max(1, h // 5), color)


@effect("confetti", "sticker", "Confetti cannon: a burst from a point, or a gentle rain from the top.",
        params=[Param("mode", "burst", "burst fires from a point, rain falls from the top.", ("burst", "rain")),
                Param("at", "below", "Burst origin: anchor name or x,y fractions."),
                Param("count", 90, "Number of pieces."), Param("size", 22, "Piece size at 1080 wide.")],
        face=True, aliases=("party", "celebrate"), default_len=3.2)
def confetti(ctx, frame, mode, at, count, size):
    ox, oy = place(ctx, at, 0.0) if mode == "burst" else (0, 0)
    g = ctx.H * 1.25
    t = ctx.lt
    for i in range(count):
        r = ctx.rng(i)
        col = CONFETTI[r.randrange(len(CONFETTI))]
        kind = r.choice(["rect", "rect", "dot", "streamer"])
        sz = int(ctx.px(size) * r.uniform(0.6, 1.2))
        if mode == "burst":
            ang = r.uniform(-math.pi * 0.95, -math.pi * 0.05)
            sp = r.uniform(0.45, 1.25) * ctx.H
            drag = math.exp(-2.1 * t)
            x = ox + math.cos(ang) * sp * (1 - drag) / 2.1
            y = oy + math.sin(ang) * sp * (1 - drag) / 2.1 + 0.5 * g * (t ** 2) * 0.55
            alive = clamp((ctx.dur - t) / 0.5)
        else:
            t0 = r.uniform(0, ctx.dur * 0.55)
            tt = t - t0
            if tt < 0:
                continue
            x = r.uniform(0, ctx.W) + math.sin(tt * 3 + i) * ctx.px(40)
            y = -ctx.px(40) + tt * ctx.H * r.uniform(0.35, 0.6)
            alive = 1.0
        if y > ctx.H + 60 or alive <= 0:
            continue
        spin = r.uniform(-540, 540) * t
        squash = abs(math.cos(t * r.uniform(3, 8) + i))
        blit(frame, _bit(kind, sz, max(3, int(sz * 0.5)), col), x, y, rot=spin, scale=0.4 + 0.6 * squash, alpha=alive)
    return frame


@effect("sparkles", "sticker", "Twinkling sparkles orbiting the speaker's head.",
        params=[Param("count", 9, "How many."), Param("color", "#FFE9A8", "Sparkle colour."), Param("size", 110, "Biggest sparkle at 1080 wide.")],
        face=True, aliases=("twinkle", "glitter", "shimmer"), default_len=3)
def sparkles(ctx, frame, count, color, size):
    f = ctx.face
    fade = fade_io(ctx, 0.3, 0.4)
    for i in range(count):
        r = ctx.rng(i)
        ang = r.uniform(0, 2 * math.pi) + ctx.lt * r.uniform(-0.5, 0.5)
        rad = r.uniform(0.85, 1.55)
        x = f.cx + math.cos(ang) * f.w * rad
        y = f.cy + math.sin(ang) * f.h * rad * 0.9
        tw = (math.sin(ctx.lt * r.uniform(3, 7) + i * 1.7) + 1) / 2
        s = int(ctx.px(size) * r.uniform(0.35, 1.0))
        blit(frame, sticker_art("sparkle", max(24, s), color), x, y, scale=0.25 + 0.75 * tw, rot=45 * tw, alpha=fade * (0.4 + 0.6 * tw))
    return frame


@effect("float-up", "sticker", "Stickers drift upward from the corner like live-stream reactions.",
        params=[Param("name", "heart", "Which sticker.", STICKERS), Param("count", 14, "How many rise over the window."),
                Param("size", 120, "Width at 1080 wide."), Param("side", "right", "Which edge they rise from.", ("left", "right", "both"))],
        aliases=("reactions", "hearts", "rise"), default_len=3.5)
def float_up(ctx, frame, name, count, size, side):
    for i in range(count):
        r = ctx.rng(i)
        t0 = (i / count) * ctx.dur * 0.7
        tt = ctx.lt - t0
        life = 2.0
        if tt < 0 or tt > life:
            continue
        k = tt / life
        edge = (1 if side == "right" else -1 if side == "left" else r.choice([-1, 1]))
        x0 = ctx.W * (0.88 if edge > 0 else 0.12)
        x = x0 + math.sin(tt * 3 + i) * ctx.px(40) * (1 if edge > 0 else 1) - edge * ctx.W * 0.08 * k
        y = ctx.H * 0.88 - k * ctx.H * r.uniform(0.45, 0.7)
        s = ctx.px(size) * r.uniform(0.6, 1.15)
        a = smooth(k * 8) * (1 - smooth((k - 0.65) / 0.35))
        blit(frame, sticker_art(name, max(32, int(s))), x, y, rot=math.sin(tt * 4 + i) * 14, scale=0.6 + 0.4 * out_back(k * 4), alpha=a)
    return frame


@effect("sticker-swipe", "sticker", "A diagonal colour slab sweeps across the screen carrying a column of stickers. A transition with personality.",
        params=[Param("names", "star|heart|sparkle|bolt|flame", "Stickers on the slab, separated by |."),
                Param("color", "coral", "Slab colour."), Param("size", 300, "Sticker width at 1080 wide."),
                Param("direction", "right", "Which way it sweeps.", ("right", "left"))],
        aliases=("sticker-transition", "wipe", "swipe"), default_len=1.1)
def sticker_swipe(ctx, frame, names, color, size, direction):
    import cv2
    from reelcraft.core.easing import in_out_cubic
    W, H = ctx.W, ctx.H
    sign = 1 if direction == "right" else -1
    u = in_out_cubic(ctx.u)
    slab_w = W * 0.62
    cx = (-0.45 + 1.9 * u) * W if sign > 0 else (1.45 - 1.9 * u) * W
    skew = math.tan(math.radians(14)) * H / 2
    pts = np.array([[cx - slab_w / 2 + skew, 0], [cx + slab_w / 2 + skew, 0], [cx + slab_w / 2 - skew, H], [cx - slab_w / 2 - skew, H]], np.int32)
    layer = frame.copy()
    cv2.fillConvexPoly(layer, pts, rgb(color), cv2.LINE_AA)
    edge = pts + np.array([[int(-sign * slab_w * 0.06), 0]] * 4, np.int32)
    cv2.polylines(layer, [edge], True, (255, 255, 255), max(3, int(ctx.px(8))), cv2.LINE_AA)
    out = layer
    kinds = [n for n in names.split("|") if n in ART] or ["star"]
    rows = 5
    for i in range(rows):
        r = ctx.rng(i)
        y = H * (i + 0.5) / rows
        x = cx + (y - H / 2) / H * -2 * skew + r.uniform(-1, 1) * slab_w * 0.12
        blit(out, sticker_art(kinds[i % len(kinds)], max(32, int(ctx.px(size) * r.uniform(0.8, 1.15)))), x, y,
             rot=r.uniform(-18, 18) + math.sin(ctx.lt * 6 + i) * 4)
    return out
