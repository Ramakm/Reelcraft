"""Colour, texture and signal damage."""
import cv2
import numpy as np

from reelcraft.core.canvas import blit, fill_rect, rgb, text_sprite
from reelcraft.core.easing import smooth
from reelcraft.core.registry import Param, effect

from ._util import fade_io

# name: (contrast, saturation, brightness, shadow tint, highlight tint)
GRADES = {
    "noir":        (1.35, 0.0, -0.04, (0, 0, 0), (255, 255, 255)),
    "teal-orange": (1.12, 1.15, 0.0, (10, 70, 90), (255, 170, 90)),
    "sunset":      (1.08, 1.2, 0.02, (90, 30, 110), (255, 150, 70)),
    "frost":       (1.1, 0.8, 0.03, (20, 50, 110), (200, 230, 255)),
    "film":        (1.15, 0.9, 0.0, (20, 40, 30), (255, 225, 180)),
    "dream":       (0.88, 1.1, 0.07, (120, 80, 170), (255, 215, 235)),
    "pop":         (1.2, 1.5, 0.0, (0, 0, 0), (255, 255, 255)),
}


@effect("grade", "look", "Colour grade with presets: noir, teal-orange, sunset, frost, film, dream, pop.",
        params=[Param("look", "teal-orange", "Preset name.", tuple(GRADES)),
                Param("strength", 1.0, "0 = untouched, 1 = full look.")],
        aliases=("color", "colour", "lut", "moody"), default_len=4)
def grade(ctx, frame, look, strength):
    contrast, sat, bright, shadow, high = GRADES[look]
    x = frame.astype(np.float32) / 255
    x = (x - 0.5) * contrast + 0.5 + bright
    g = cv2.cvtColor(np.clip(x, 0, 1), cv2.COLOR_RGB2GRAY)[..., None]
    x = g + (x - g) * sat
    if look not in ("noir", "pop"):      # split-tone: shadows lean one way, highlights the other
        lo, hi = np.array(shadow, np.float32) / 255, np.array(high, np.float32) / 255
        x = x * (1 - 0.25 * (1 - g)) + 0.25 * (1 - g) * lo + 0.12 * g * (hi - 0.5) + 0.0
    out = (np.clip(x, 0, 1) * 255).astype(np.uint8)
    k = strength * fade_io(ctx, 0.3, 0.3)
    return cv2.addWeighted(out, k, frame, 1 - k, 0) if k < 0.999 else out


@effect("duotone", "look", "Two-colour poster look: one colour for shadows, one for highlights.",
        params=[Param("shadow", "violet", "Colour of the darks."), Param("highlight", "amber", "Colour of the lights."),
                Param("strength", 1.0, "Blend with the original.")],
        aliases=("two-tone",), default_len=3)
def duotone(ctx, frame, shadow, highlight, strength):
    g = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY).astype(np.float32)[..., None] / 255
    lo, hi = np.array(rgb(shadow), np.float32), np.array(rgb(highlight), np.float32)
    out = (lo + (hi - lo) * g).astype(np.uint8)
    k = strength * fade_io(ctx, 0.25, 0.25)
    return cv2.addWeighted(out, k, frame, 1 - k, 0)


@effect("glitch", "look", "Digital glitch: RGB tear, sliced rows and scanline flicker.",
        params=[Param("intensity", 1.0, "How violent it is."),
                Param("burst", 0.35, "Fraction of frames that glitch (the rest stay clean).")],
        aliases=("datamosh", "corrupt"), default_len=1.2)
def glitch(ctx, frame, intensity, burst):
    n = int(ctx.t * ctx.fps)
    r = ctx.rng(n * 7)
    if r.random() > burst:
        return frame
    H, W = frame.shape[:2]
    out = frame.copy()
    for _ in range(r.randint(3, 8)):                       # horizontal slice displacement
        y = r.randrange(H)
        h = r.randint(max(2, H // 90), max(4, H // 14))
        dx = int(r.uniform(-1, 1) * W * 0.09 * intensity)
        out[y:y + h] = np.roll(out[y:y + h], dx, axis=1)
    s = max(1, int(W * 0.008 * intensity * r.uniform(0.5, 1.6)))
    out[..., 0] = np.roll(out[..., 0], s, axis=1)           # channel split
    out[..., 2] = np.roll(out[..., 2], -s, axis=1)
    out[::4] = (out[::4] * 0.82).astype(np.uint8)           # scanlines
    return out


@effect("rgb-split", "look", "Chromatic aberration: red and blue fringes pull apart then snap back.",
        params=[Param("amount", 0.012, "Split distance as a fraction of the width."),
                Param("mode", "pulse", "pulse eases in and out; hold keeps it.", ("pulse", "hold"))],
        aliases=("chromatic", "aberration"), default_len=1.5)
def rgb_split(ctx, frame, amount, mode):
    k = fade_io(ctx, 0.2, 0.2) if mode == "pulse" else 1.0
    s = int(ctx.W * amount * k)
    if s < 1:
        return frame
    out = frame.copy()
    out[..., 0] = np.roll(frame[..., 0], s, axis=1)
    out[..., 2] = np.roll(frame[..., 2], -s, axis=1)
    return out


@effect("film", "look", "35mm feel: animated grain, gentle vignette and a faint flicker.",
        params=[Param("grain", 0.035, "Grain strength."), Param("vignette", 0.45, "Corner darkening, 0 to 1.")],
        aliases=("grain", "vignette", "16mm"), default_len=6)
def film(ctx, frame, grain, vignette):
    H, W = frame.shape[:2]
    rng = np.random.default_rng(int(ctx.t * ctx.fps) + ctx.seed)
    n = rng.normal(0, grain * 255, (H // 2, W // 2, 1)).astype(np.float32)
    n = cv2.resize(n, (W, H), interpolation=cv2.INTER_LINEAR)[..., None]
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2) / 1.414
    v = (1 - vignette * smooth((d - 0.35) / 0.65))[..., None]
    flick = 1 + 0.015 * np.sin(ctx.t * 37) 
    return np.clip(frame * v * flick + n, 0, 255).astype(np.uint8)


@effect("vhs", "look", "Tape-deck look: scanlines, colour bleed, wobble and a PLAY stamp.",
        params=[Param("label", "PLAY", "Corner label (empty to hide)."), Param("wobble", 1.0, "Horizontal jitter.")],
        aliases=("camcorder", "retro"), default_len=4)
def vhs(ctx, frame, label, wobble):
    H, W = frame.shape[:2]
    out = cv2.GaussianBlur(frame, (0, 0), 0.8)
    s = max(1, W // 220)
    out[..., 0] = np.roll(out[..., 0], s * 2, axis=1)
    out[..., 2] = np.roll(out[..., 2], -s, axis=1)
    ys = np.arange(H)
    shift = (wobble * W * 0.004 * np.sin(ys / 38.0 + ctx.t * 5) * (np.sin(ctx.t * 1.7) > 0.3)).astype(int)
    out = out[ys[:, None], (np.arange(W)[None, :] - shift[:, None]) % W]
    out[::3] = (out[::3] * 0.8).astype(np.uint8)
    band = int((ctx.t * 0.25 % 1.0) * H)                    # slow rolling noise band
    out[band:band + max(2, H // 60)] = np.clip(out[band:band + max(2, H // 60)].astype(np.int16) + 28, 0, 255)
    if label:
        blit(out, text_sprite(f"{label} >", "ui-bold", int(ctx.px(46)), "#FFFFFF", stroke=2, stroke_fill="#000000"),
             ctx.W * 0.07, ctx.H * 0.06, anchor=(0, 0.5))
    return out


@effect("spotlight", "look", "Kill the lights: the room goes dark and a soft pool of light stays on the speaker.",
        params=[Param("dim", 0.85, "How dark the room gets, 0 to 1."), Param("color", "#FFE9C4", "Tint of the light."),
                Param("size", 1.0, "Size of the lit area.")],
        face=True, aliases=("lights-out", "kill-the-lights"), default_len=3)
def spotlight(ctx, frame, dim, color, size):
    H, W = frame.shape[:2]
    f = ctx.face
    k = fade_io(ctx, 0.35, 0.35)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    rx, ry = f.w * 1.5 * size, f.h * 2.2 * size
    d = np.sqrt(((xx - f.cx) / rx) ** 2 + ((yy - (f.cy + f.h * 0.4)) / ry) ** 2)
    lit = (1 - smooth((d - 0.55) / 0.9))[..., None]
    shade = 1 - dim * k * (1 - lit)
    warm = np.array(rgb(color), np.float32) / 255
    out = frame * shade * (1 + (warm - 1) * 0.25 * lit * k)
    return np.clip(out, 0, 255).astype(np.uint8)


@effect("flash", "look", "Camera-flash pop. Perfect on a cut or a beat.",
        params=[Param("color", "#FFFFFF", "Flash colour.")], aliases=("pop-flash",), default_len=0.35)
def flash(ctx, frame, color):
    return fill_rect(frame, 0, 0, ctx.W, ctx.H, color, (1 - ctx.u) ** 2)


@effect("halftone", "look", "Printed-poster dots. Mono ink on paper, or let some colour bleed through.",
        params=[Param("cell", 16, "Dot spacing at 1080 wide."), Param("ink", "#16161A", "Dot colour."),
                Param("paper", "#F6F1E7", "Paper colour."), Param("color", 0.0, "0 = pure ink, 1 = full-colour dots."),
                Param("strength", 1.0, "Blend with the original.")],
        aliases=("print", "newsprint", "comic"), default_len=3)
def halftone(ctx, frame, cell, ink, paper, color, strength):
    H, W = frame.shape[:2]
    gray = cv2.GaussianBlur(cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY), (0, 0), max(1, ctx.px(cell) / 4)).astype(np.float32) / 255
    lo, hi = np.percentile(gray, (2, 98))
    gray = np.clip((gray - lo) / max(hi - lo, 1e-3), 0, 1) ** 0.75       # auto-levels so dots read on any footage
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    c = max(4.0, ctx.px(cell))
    ang = np.deg2rad(45)
    u = (xx * np.cos(ang) + yy * np.sin(ang)) / c
    v = (-xx * np.sin(ang) + yy * np.cos(ang)) / c
    pattern = (np.cos(2 * np.pi * u) + np.cos(2 * np.pi * v)) / 4 + 0.5          # 0..1, peaks at dot centres
    m = np.clip(((1 - gray) - (1 - pattern) * 0.9) * 6 + 0.5, 0, 1)[..., None]
    ink_c, paper_c = np.array(rgb(ink), np.float32), np.array(rgb(paper), np.float32)
    out = paper_c * (1 - m) + ink_c * m
    if color > 0:
        out = out * (1 - color) + (frame * (0.4 + 0.6 * (1 - m))) * color
    k = strength * fade_io(ctx, 0.25, 0.25)
    return np.clip(out * k + frame * (1 - k), 0, 255).astype(np.uint8)


@effect("sketch", "look", "Pencil sketch on paper, with an optional wash of the original colour.",
        params=[Param("paper", "#F6F1E7", "Paper colour."), Param("wash", 0.25, "How much original colour tints the drawing."),
                Param("strength", 1.0, "Blend with the original.")],
        aliases=("pencil", "drawing"), default_len=3)
def sketch(ctx, frame, paper, wash, strength):
    gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
    blur = cv2.GaussianBlur(255 - gray, (0, 0), max(3, ctx.px(9)))
    pencil = cv2.divide(gray, 255 - blur, scale=256).astype(np.float32)[..., None] / 255
    out = np.array(rgb(paper), np.float32) * pencil
    out = out * (1 - wash) + out * (0.55 + 0.45 * frame.astype(np.float32) / 255) * wash * 1.0 + out * 0 if wash else out
    k = strength * fade_io(ctx, 0.25, 0.25)
    return np.clip(out * k + frame * (1 - k), 0, 255).astype(np.uint8)
