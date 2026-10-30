"""Interface-style graphics: chat bubbles, notification banners, a typing terminal, hand-drawn marks."""
import math
from functools import lru_cache

import cv2
import numpy as np

from reelcraft.core.canvas import (blit, draw_sprite, font, glass_sprite, over, rgb, rrect_sprite, text_sprite,
                                   text_width, with_shadow)
from reelcraft.core.easing import clamp, lerp, out_back, out_cubic, smooth
from reelcraft.core.registry import Param, effect

from ._util import fade_io, place, wrap_words
from .sticker import STICKERS, sticker_art


# ---------- messages ----------
@lru_cache(maxsize=64)
def _bubble(text, size, fill, ink, side):
    f = text_sprite(text, "ui", size, ink, pad=0)
    th, tw = f.shape[:2]
    px, py = int(size * 0.62), int(size * 0.38)
    w, h = tw + 2 * px, th + 2 * py
    tail = int(size * 0.5)
    spr = np.zeros((h + 4, w + tail, 4), np.uint8)
    ox = 0 if side == "left" else tail
    body = rrect_sprite(w, h, min(h // 2, int(size * 0.8)), fill)
    spr[:h, ox:ox + w] = body
    # the little tail: a circle tucked under the bottom corner, as in a chat app
    cx = ox + (int(size * 0.35) if side == "left" else w - int(size * 0.35))
    t = draw_sprite(tail * 2, tail * 2, lambda d, S: d.ellipse([0, 0, tail * 2 * S - 1, tail * 2 * S - 1], fill=rgb(fill) + (255,)))
    x0 = cx - tail
    spr = np.pad(spr, ((0, tail // 2), (tail, tail), (0, 0)))
    ty = h - tail + tail // 2
    reg = spr[ty:ty + 2 * tail, x0 + tail:x0 + tail + 2 * tail]
    if reg.shape[:2] == t.shape[:2]:
        spr[ty:ty + 2 * tail, x0 + tail:x0 + tail + 2 * tail] = over(reg, t)
    blit(spr, text_sprite(text, "ui", size, ink, pad=0), ox + tail + px + tw / 2, py + th / 2 + 0)
    return with_shadow(spr, blur=10, offset=(0, 6), opacity=0.28)


@effect("messages", "motion", "Chat bubbles pop in one after another, like a group text. Separate messages with |.",
        params=[Param("text", "hey|are you free tonight?|yes!! finally", "Messages, separated by |."),
                Param("side", "alternate", "Who sends them.", ("alternate", "left", "right")),
                Param("accent", "#0A84FF", "Colour of the sent bubbles."), Param("size", 46, "Text size at 1080 wide."),
                Param("at", "auto", "auto, top, bottom, or x,y fractions for the newest bubble.")],
        face=True, aliases=("chat", "texts", "imessage"), default_len=4)
def messages(ctx, frame, text, side, accent, size, at):
    msgs = [m.strip() for m in text.split("|") if m.strip()]
    if not msgs:
        return frame
    n = len(msgs)
    step = ctx.dur * 0.7 / n
    px = int(ctx.px(size))
    sprites = []
    for i, m in enumerate(msgs):
        s = side if side != "alternate" else ("right" if i % 2 == 0 else "left")
        sprites.append((_bubble(m, px, accent if s == "right" else "#E9E9EE", "#FFFFFF" if s == "right" else "#111114", s), s))
    if at == "auto":
        at = ctx.free_side()
    base_y = {"bottom": ctx.H * 0.86, "top": ctx.H * 0.34}.get(at)
    if base_y is None:
        base_y = place(ctx, at)[1]
    fade = 1 - smooth((0.35 - ctx.left) / 0.35)
    shown = [i for i in range(n) if ctx.lt >= i * step]
    if not shown:
        return frame
    newest = shown[-1]
    gap = ctx.px(18)
    # y of each bubble (bottom edge) relative to the newest, which sits on the baseline
    y = base_y
    ys = {}
    for i in reversed(range(newest + 1)):
        h = sprites[i][0].shape[0]
        ys[i] = y
        y -= h * 0.82 + gap
    # when a new bubble arrives the older ones glide up
    slide = (1 - out_cubic((ctx.lt - newest * step) / 0.3)) * (sprites[newest][0].shape[0] * 0.82 + gap) if newest else 0
    for i in range(newest + 1):
        spr, s = sprites[i]
        k = out_back((ctx.lt - i * step) / 0.3, 1.9)
        x = ctx.W * (0.9 if s == "right" else 0.1)
        yy = ys[i] + (slide if i < newest else 0)
        blit(frame, spr, x, yy, scale=k, alpha=clamp((ctx.lt - i * step) * 10) * fade, anchor=(1.0 if s == "right" else 0.0, 1.0))
    return frame


# ---------- notification ----------
@effect("notification", "motion", "A glass notification banner drops in from the top, like a phone alert.",
        params=[Param("app", "REELCRAFT", "App name in small caps."), Param("title", "New follower", "Bold line."),
                Param("body", "Someone just loved your edit", "Second line."),
                Param("icon", "heart", "Sticker used as the app icon.", STICKERS),
                Param("at", "top", "top or bottom.", ("top", "bottom"))],
        aliases=("banner", "alert"), default_len=3.5)
def notification(ctx, frame, app, title, body, icon, at):
    W, H = ctx.W, ctx.H
    w, h = int(W * 0.9), int(W * 0.2)
    r = int(h * 0.3)
    k = out_back(ctx.lt / 0.5, 1.3) * (1 - out_cubic(clamp((0.35 - ctx.left) / 0.35)))
    if k <= 0.01:
        return frame
    rest = H * 0.055 if at == "top" else H * 0.945 - h
    off = (1 - k) * (-(h + rest) if at == "top" else (h + rest))
    y0 = int(rest + off)
    x0 = (W - w) // 2
    card = glass_sprite(frame, x0, y0, w, h, r, blur=ctx.px(24), dark=0.55, wash=0.18)
    pad = int(h * 0.2)
    ic = sticker_art(icon, int(h * 0.56))
    blit(card, ic, pad + ic.shape[1] / 2 - h * 0.04, h / 2)
    tx = pad * 2 + int(h * 0.56)
    blit(card, text_sprite(app.upper(), "ui-semi", int(h * 0.15), "#E8E8EE", tracking=int(h * 0.02), pad=0), tx, h * 0.24, anchor=(0, 0.5))
    avail = w - tx - pad
    t_size = int(h * 0.22)
    while text_width(title, "ui-bold", t_size) > avail and t_size > 12:
        t_size -= 1
    blit(card, text_sprite(title, "ui-bold", t_size, "#FFFFFF", pad=0), tx, h * 0.5, anchor=(0, 0.5))
    b_size = int(h * 0.18)
    while text_width(body, "ui", b_size) > avail and b_size > 10:
        b_size -= 1
    blit(card, text_sprite(body, "ui", b_size, "#EDEDF2", pad=0), tx, h * 0.74, anchor=(0, 0.5))
    return blit(frame, with_shadow(card, blur=22, offset=(0, 14), opacity=0.35), W / 2, y0 + h / 2)


# ---------- terminal ----------
@effect("terminal", "motion", "A dark terminal window that types commands, with a blinking cursor. Lines starting with # are output.",
        params=[Param("text", "reelcraft render clip.mp4|# done: 1 video, 6 effects", "Lines, separated by |."),
                Param("title", "zsh", "Window title."), Param("at", "auto", "auto, top, bottom, center or x,y fractions."),
                Param("size", 44, "Text size at 1080 wide.")],
        face=True, aliases=("code", "shell", "cli"), default_len=4)
def terminal(ctx, frame, text, title, at, size):
    lines = [l for l in text.split("|") if l.strip()]
    if not lines:
        return frame
    px = int(ctx.px(size))
    prompt = "$ "
    cmds = [l for l in lines if not l.startswith("#")]
    total = sum(len(l) for l in cmds) or 1
    typed = int(total * clamp(ctx.lt / max(0.5, ctx.dur * 0.6)))
    # work out what each line shows right now
    rows, left = [], typed
    cmd_done = True
    for l in lines:
        if l.startswith("#"):
            if cmd_done:
                rows.append((l[1:].strip(), True))
            continue
        take = min(len(l), max(0, left))
        left -= len(l)
        rows.append((prompt + l[:take], False))
        cmd_done = take >= len(l)
        if not cmd_done:
            break
    longest = max(text_width(prompt + l.lstrip("#").strip(), "mono", px) for l in lines)
    w = int(min(ctx.W * 0.9, longest + px * 2.4))
    lh = px * 1.55
    head = int(px * 1.7)
    h = int(head + lh * len(lines) + px * 1.0)
    card = rrect_sprite(w, h, int(px * 0.7), "#17181D")
    hd = rrect_sprite(w, head + 20, int(px * 0.7), "#24262D")[:head + 4]
    card[:head + 4] = over(card[:head + 4], hd)
    for i, c in enumerate(("#FF5F57", "#FEBC2E", "#28C840")):
        d = int(px * 0.5)
        dot = draw_sprite(d, d, lambda dr, S, c=c: dr.ellipse([0, 0, d * S - 1, d * S - 1], fill=rgb(c) + (255,)))
        blit(card, dot, px * 0.9 + i * px * 0.8, head / 2)
    blit(card, text_sprite(title, "ui", int(px * 0.55), "#9EA3B0", pad=0), w / 2, head / 2)
    blink = int(ctx.lt * 2.2) % 2 == 0
    for i, (row, is_out) in enumerate(rows):
        y = head + px * 0.8 + lh * i + lh / 2
        if is_out:
            blit(card, text_sprite(row, "mono", px, "#4FE3B5", pad=0), px * 1.1, y, anchor=(0, 0.5))
        else:
            if row.startswith(prompt):
                blit(card, text_sprite("$", "mono", px, "#C6F432", pad=0), px * 1.1, y, anchor=(0, 0.5))
                body = row[len(prompt):]
                bx = px * 1.1 + text_width(prompt, "mono", px)
            else:
                body, bx = row, px * 1.1
            if body:
                blit(card, text_sprite(body, "mono", px, "#F2F2F5", pad=0), bx, y, anchor=(0, 0.5))
            if i == len(rows) - 1 and blink and not is_out:
                cx = bx + text_width(body, "mono", px) + 3
                card[int(y - px * 0.55):int(y + px * 0.55), int(cx):int(cx + px * 0.5), :] = (242, 242, 245, 255)
    if at == "auto":
        at = "bottom" if ctx.free_side() == "bottom" else "top"
    cx = ctx.W / 2
    cy = {"top": ctx.H * 0.1 + h / 2, "bottom": ctx.H * 0.92 - h / 2, "center": ctx.H / 2}.get(at)
    if cy is None:
        cx, cy = place(ctx, at)
    k = out_back(ctx.lt / 0.4, 1.4) * (1 - out_cubic(clamp((0.3 - ctx.left) / 0.3)))
    return blit(frame, with_shadow(card, blur=20, offset=(0, 14), opacity=0.45), cx, cy, scale=k, alpha=clamp(k * 3))


# ---------- hand-drawn marks ----------
def _stroke_points(style, cx, cy, w, h, seed):
    if style == "circle":
        n = 70
        th = np.linspace(-0.4, 2 * math.pi * 1.06, n)
        r = 1 + 0.06 * np.sin(th * 3 + seed) + 0.05 * th / (2 * math.pi)
        return np.stack([cx + np.cos(th) * w / 2 * r, cy + np.sin(th) * h / 2 * r], 1)
    if style == "box":
        c = [(-0.5, -0.5), (0.5, -0.52), (0.51, 0.5), (-0.52, 0.48), (-0.5, -0.46)]
        pts = []
        for (x0, y0), (x1, y1) in zip(c, c[1:]):
            for t in np.linspace(0, 1, 14, endpoint=False):
                pts.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t))
        pts.append(c[-1])
        a = np.array(pts)
        return np.stack([cx + a[:, 0] * w, cy + a[:, 1] * h], 1)
    t = np.linspace(0, 1, 50)
    wob = np.sin(t * math.pi * 2.2 + seed) * h * 0.06
    if style == "highlight":
        return np.stack([cx - w / 2 + t * w, cy + wob * 0.3], 1)
    return np.stack([cx - w / 2 + t * w, cy + wob + t * h * 0.12], 1)


@effect("underline", "motion", "A marker draws itself: an underline, circle, box or highlighter swipe around a spot.",
        params=[Param("style", "underline", "What gets drawn.", ("underline", "circle", "box", "highlight")),
                Param("at", "below", "Where: a face anchor or x,y fractions like 0.5,0.7."),
                Param("width", 0.5, "Width as a fraction of the frame."), Param("height", 0.12, "Height as a fraction of the frame width (circle, box, highlight)."),
                Param("color", "amber", "Marker colour."), Param("thickness", 12, "Pen width at 1080 wide.")],
        face=True, aliases=("circle", "marker", "highlight-swipe", "scribble"), default_len=2)
def underline(ctx, frame, style, at, width, height, color, thickness):
    cx, cy = place(ctx, at, 0.2)
    w, h = ctx.W * width, ctx.W * height
    pts = _stroke_points(style, cx, cy, w, h, ctx.seed % 7)
    prog = out_cubic(ctx.lt / max(0.35, min(0.9, ctx.dur * 0.4)))
    n = max(2, int(len(pts) * prog))
    col = rgb(color)
    th = max(2, int(ctx.px(thickness * (3.2 if style == "highlight" else 1))))
    layer = frame.copy()
    p = pts[:n].astype(np.int32)
    cv2.polylines(layer, [p.reshape(-1, 1, 2)], False, col, th, cv2.LINE_AA)
    for q in (p[0], p[-1]):
        cv2.circle(layer, (int(q[0]), int(q[1])), th // 2, col, -1, cv2.LINE_AA)
    a = fade_io(ctx, 0.02, 0.3) * (0.5 if style == "highlight" else 1.0)
    return cv2.addWeighted(layer, a, frame, 1 - a, 0)
