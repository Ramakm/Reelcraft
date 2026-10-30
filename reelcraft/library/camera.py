"""Camera moves: the picture itself zooms, drifts and shakes."""
import math

from reelcraft.core.registry import Param, effect

from ._util import hold_curve, noise1


@effect("punch-in", "camera", "Quick punch-in toward the speaker, holds, then eases back out.",
        params=[Param("zoom", 1.4, "How close to get (1.0 = none, 2.0 = double)."),
                Param("target", "face", "What to push toward.", ("face", "center")),
                Param("hold", True, "Ease back out at the end. Turn off to stay zoomed."),
                Param("snap", 0.18, "Seconds the push-in takes.")],
        face=True, aliases=("zoom", "lean-in", "push"), default_len=1.6)
def punch_in(ctx, frame, zoom, target, hold, snap):
    k = hold_curve(ctx, snap, snap * 1.6 if hold else 0)
    z = 1 + (min(zoom, 2.5) - 1) * k
    cx, cy = (ctx.face.cx, ctx.face.cy) if target == "face" else (ctx.W / 2, ctx.H / 2)
    # push toward the face but keep it from drifting off-screen
    return ctx.zoom(frame, z, cx * 0.5 + ctx.W / 4, cy * 0.5 + ctx.H / 4)


@effect("drift", "camera", "Slow cinematic push (or pull) across the whole window.",
        params=[Param("amount", 0.12, "Zoom gained over the window (negative pulls back)."),
                Param("pan", 0.02, "Sideways drift as a fraction of the width.")],
        aliases=("slow-push", "ken-burns"), default_len=6)
def drift(ctx, frame, amount, pan):
    u = ctx.u
    return ctx.zoom(frame, 1 + amount * u + (0.02 if amount >= 0 else 0.0), dx=pan * ctx.W * (u - 0.5))


@effect("shake", "camera", "Impact shake that starts hard and settles, like a bass drop.",
        params=[Param("intensity", 1.0, "1.0 is a firm hit, 2.0 is an earthquake.")],
        aliases=("impact", "rumble"), default_len=0.7)
def shake(ctx, frame, intensity):
    decay = (1 - ctx.u) ** 2
    a = ctx.W * 0.018 * intensity * decay
    t = ctx.t * 1.0
    return ctx.zoom(frame, 1.04 + 0.02 * intensity * decay, dx=a * noise1(t * 3, 0.0), dy=a * noise1(t * 3, 5.0),
                    rot=1.2 * intensity * decay * noise1(t * 3, 9.0))


@effect("pulse", "camera", "Beat-matched zoom pulse. Give it the song's BPM.",
        params=[Param("bpm", 120.0, "Beats per minute."),
                Param("amount", 0.06, "How hard each beat hits.")],
        aliases=("beat", "bounce"), default_len=4)
def pulse(ctx, frame, bpm, amount):
    phase = (ctx.lt * bpm / 60.0) % 1.0
    k = math.exp(-phase * 7) * min(1, ctx.lt * 6) * min(1, ctx.left * 6)
    return ctx.zoom(frame, 1 + amount * k)


@effect("whip", "camera", "Whip-pan: a fast sideways smear that peaks mid-window. Hides a cut or punctuates a beat.",
        params=[Param("direction", "left", "Which way the camera whips.", ("left", "right", "up", "down")),
                Param("strength", 0.3, "How violent the smear is.")],
        aliases=("whip-pan", "swish-pan", "smear"), default_len=0.5)
def whip(ctx, frame, direction, strength):
    import cv2
    import numpy as np
    k = math.sin(math.pi * ctx.u) ** 2
    H, W = frame.shape[:2]
    horiz = direction in ("left", "right")
    span = W if horiz else H
    sign = -1 if direction in ("left", "up") else 1
    shift = int(sign * span * strength * 0.6 * k)
    out = np.roll(frame, shift, axis=1 if horiz else 0)
    n = max(1, int(span * strength * 0.35 * k)) | 1
    if n > 1:
        ker = np.zeros((n, n), np.float32)
        ker[n // 2, :] = 1 / n
        out = cv2.filter2D(out, -1, ker if horiz else ker.T, borderType=cv2.BORDER_REFLECT)
    return out
