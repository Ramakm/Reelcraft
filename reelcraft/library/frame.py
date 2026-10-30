"""Effects that change the shape of the shot: bars, cards, reveals, borders."""
from functools import lru_cache

import cv2
import numpy as np

from reelcraft.core.canvas import blit, draw_sprite, fill_rect, paste_clip, rgb, rrect_sprite, text_sprite, with_glow, with_shadow
from reelcraft.core.easing import lerp, out_cubic, smooth
from reelcraft.core.registry import Param, effect

from ._util import fade_io, hold_curve


@effect("letterbox", "frame", "Cinematic bars slide in from top and bottom.",
        params=[Param("ratio", 0.0, "Aspect of the visible picture. 0 = auto: widescreen 2.39 on landscape video, 4:5 on vertical."),
                Param("color", "#000000", "Bar colour.")],
        aliases=("cinema", "bars"), default_len=4)
def letterbox(ctx, frame, ratio, color):
    ratio = ratio or (2.39 if ctx.W >= ctx.H else 0.8)
    visible = min(ctx.H, ctx.W / ratio)
    bar = max(0.0, (ctx.H - visible) / 2) * hold_curve(ctx, 0.5, 0.4)
    fill_rect(frame, 0, 0, ctx.W, bar, color)
    fill_rect(frame, 0, ctx.H - bar, ctx.W, ctx.H, color)
    return frame


@lru_cache(maxsize=8)
def _backdrop(W, H, color):
    c = np.array(rgb(color), np.float32)
    g = np.linspace(1.08, 0.78, H, dtype=np.float32)[:, None, None]
    return np.clip(np.broadcast_to(c, (H, W, 3)) * g, 0, 255).astype(np.uint8)


@lru_cache(maxsize=4)
def _card_base(w, h, r):
    return rrect_sprite(w, h, r, "#FBF8F1")


@lru_cache(maxsize=4)
def _card_shadow(w, h, r):
    return with_shadow(rrect_sprite(w, h, r, "#000000"), blur=26, offset=(0, 18), opacity=0.5)


@effect("polaroid", "frame", "The video shrinks into a tilted instant photo on a coloured table, with a handwritten caption.",
        params=[Param("caption", "", "Handwritten caption under the photo."),
                Param("color", "coral", "Table colour."), Param("tilt", -4.0, "Degrees the photo is rotated."),
                Param("size", 0.8, "Final width of the photo as a fraction of the frame.")],
        aliases=("photo", "instant", "card"), default_len=3.5)
def polaroid(ctx, frame, caption, color, tilt, size):
    W, H = ctx.W, ctx.H
    k = hold_curve(ctx, 0.45, 0.4)
    if k <= 0.001:
        return frame
    pad, bottom = int(W * 0.045), int(W * 0.16)
    cw, ch, r = W + 2 * pad, H + pad + bottom, int(W * 0.02)
    final = size * W / cw
    sc = lerp(1.0, final, out_cubic(k))
    base = _backdrop(W, H, color)
    card = _card_base(cw, ch, r).copy()
    card[pad:pad + H, pad:pad + W, :3] = frame
    card[pad:pad + H, pad:pad + W, 3] = 255
    if caption:
        t = text_sprite(caption, "hand", int(bottom * 0.5), "#2A2A2E")
        blit(card, t, cw / 2, pad + H + bottom * 0.5)
    ang = tilt * out_cubic(k)
    shadow_a = out_cubic(k)
    out = lerp_frames(frame, base, smooth(k * 1.6))    # table fades in as the photo shrinks
    blit(out, _card_shadow(cw, ch, r), W / 2, H / 2 + (H * 0.01), scale=sc, rot=ang, alpha=shadow_a)
    blit(out, card, W / 2, H / 2, scale=sc, rot=ang)
    return out


def lerp_frames(a, b, t):
    return cv2.addWeighted(a, 1 - t, b, t, 0) if 0 < t < 1 else (b if t >= 1 else a)


@effect("iris", "frame", "Circular reveal that opens (or closes) from the speaker's face.",
        params=[Param("mode", "open", "open reveals the shot, close hides it.", ("open", "close")),
                Param("color", "#000000", "Colour outside the circle.")],
        face=True, aliases=("circle-reveal", "iris-in"), default_len=0.9)
def iris(ctx, frame, mode, color):
    f, W, H = ctx.face, ctx.W, ctx.H
    u = out_cubic(ctx.u)
    reach = float(np.hypot(max(f.cx, W - f.cx), max(f.cy, H - f.cy)))
    radius = reach * (u if mode == "open" else 1 - u)
    mask = np.zeros((H, W), np.uint8)
    cv2.circle(mask, (int(f.cx), int(f.cy)), int(max(radius, 0)), 255, -1, cv2.LINE_AA)
    mask = cv2.GaussianBlur(mask, (0, 0), max(2, W * 0.004))[..., None] / 255.0
    bg = np.array(rgb(color), np.float32)
    return (frame * mask + bg * (1 - mask)).astype(np.uint8)


@lru_cache(maxsize=8)
def _neon(W, H, color, thick):
    inset = int(W * 0.035)

    def paint(d, S):
        d.rounded_rectangle([inset * S, inset * S, (W - inset) * S, (H - inset) * S], radius=int(W * 0.05) * S,
                            outline=rgb(color) + (255,), width=thick * S)
    return with_glow(draw_sprite(W, H, paint, ss=2), radius=int(W * 0.018), strength=1.6)


@effect("neon-frame", "frame", "A glowing neon border that flickers on and hums.",
        params=[Param("color", "lime", "Neon colour."), Param("thickness", 6, "Line thickness at 1080 wide.")],
        aliases=("neon", "glow-border"), default_len=4)
def neon_frame(ctx, frame, color, thickness):
    spr = _neon(ctx.W, ctx.H, color, max(2, int(ctx.px(thickness))))
    flick = 1.0 if ctx.lt > 0.5 else (0.2 if int(ctx.lt * 18) % 2 else 1.0)    # tube warming up
    hum = 0.9 + 0.1 * np.sin(ctx.t * 9)
    return blit(frame, spr, ctx.W / 2, ctx.H / 2, alpha=flick * hum * fade_io(ctx, 0.05, 0.3))
