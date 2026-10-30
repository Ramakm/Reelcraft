"""Animated type and graphics that sit on top of the video."""
import math
import re
from functools import lru_cache

import cv2
import numpy as np

from reelcraft.core.canvas import (blit, draw_sprite, fill_rect, font, rgb, rrect_sprite, text_sprite, text_width,
                                   with_shadow)
from reelcraft.core.easing import clamp, lerp, out_back, out_cubic, out_expo, smooth
from reelcraft.core.registry import Param, effect

from ._util import fade_io, fit_size, place, wrap_words


# ---------- kinetic title ----------
@lru_cache(maxsize=256)
def _word(word, fname, size, color, accent, boxed):
    if boxed:
        t = text_sprite(word, fname, size, "#111114", pad=0)
        h, w = t.shape[:2]
        px, py = int(size * 0.18), int(size * 0.02)
        box = rrect_sprite(w + 2 * px, h + 2 * py, int(size * 0.14), accent)
        out = box.copy()
        from reelcraft.core.canvas import over, pad_sprite
        t = np.pad(t, ((py, py), (px, px), (0, 0)))
        return with_shadow(over(out, t), blur=8, offset=(0, 6), opacity=0.4)
    return with_shadow(text_sprite(word, fname, size, color), blur=9, offset=(0, 5), opacity=0.5)


def _layout_words(text, fname, size, max_w):
    toks = []
    for raw in text.split():
        accent = raw.startswith("*") and raw.endswith("*") and len(raw) > 2
        toks.append((raw.strip("*").upper() if fname == "display" else raw.strip("*"), accent))
    lines = wrap_words([t[0] for t in toks], fname, size, max_w)
    out, i = [], 0
    for ln in lines:
        out.append([toks[i + j] for j in range(len(ln))])
        i += len(ln)
    return out


@effect("kinetic-title", "motion", "Big words slam in one by one. Wrap a word in *stars* to put it in an accent box.",
        params=[Param("text", "WAIT FOR *IT*", "The words. *Star* a word to highlight it."),
                Param("at", "auto", "auto, top, bottom, center, a face anchor, or x,y fractions like 0.5,0.8."),
                Param("size", 170, "Type size at 1080 wide."), Param("color", "white", "Text colour."),
                Param("accent", "amber", "Highlight colour."), Param("font", "display", "Typeface.",
                                                                    ("display", "serif", "serif-italic", "ui-bold", "hand"))],
        face=True, aliases=("title", "words", "slam"), default_len=2.5)
def kinetic_title(ctx, frame, text, at, size, color, accent, font):
    size = int(ctx.px(size))
    max_w = ctx.W * 0.88
    full = " ".join(w.strip("*") for w in text.split())
    size = fit_size(full if len(full) < 14 else full[:len(full) // 2 + 3], font, max_w, size)   # allow wrapping to ~2 lines
    lines = _layout_words(text, font, size, max_w)
    lh = size * (0.92 if font == "display" else 1.05)
    block_h = lh * len(lines)
    if at == "auto":
        at = ctx.free_side()
    if at in ("top", "bottom", "center"):
        cy = {"top": ctx.H * 0.06 + block_h / 2 + ctx.H * 0.04, "bottom": ctx.H * 0.94 - block_h / 2 - ctx.H * 0.04,
              "center": ctx.H / 2}[at]
        cx = ctx.W / 2
    else:
        cx, cy = place(ctx, at)
    exit_k = smooth((0.3 - ctx.left) / 0.3)
    n = 0
    for li, line in enumerate(lines):
        gap = size * 0.22
        widths = [text_width(w, font, size) + 2 * int(size * 0.18 if a else 0) for w, a in line]
        x = cx - (sum(widths) + gap * (len(line) - 1)) / 2
        y = cy - block_h / 2 + lh * (li + 0.5)
        for (w, a), ww in zip(line, widths):
            t0 = n * 0.1
            n += 1
            k = (ctx.lt - t0) / 0.32
            if k <= 0:
                x += ww + gap
                continue
            r = ctx.rng(n)
            spr = _word(w, font, size, rgb(color), rgb(accent), a)
            sc = out_back(k, 2.2) * (1 - 0.15 * exit_k)
            blit(frame, spr, x + ww / 2, y - lh * 0.18 * exit_k - (1 - out_cubic(k)) * size * 0.4, scale=sc,
                 rot=r.uniform(-3, 3) * (1 - out_cubic(k)) + (r.uniform(-1.5, 1.5) if a else 0),
                 alpha=clamp(k * 3) * (1 - exit_k))
            x += ww + gap
    return frame


# ---------- lower third ----------
@lru_cache(maxsize=16)
def _lower_third(name, role, accent, ink, size):
    fn, fr = font("ui-bold", size), font("ui", int(size * 0.5))
    wn, wr = text_width(name, "ui-bold", size), text_width(role, "ui", int(size * 0.5)) if role else 0
    padx, pady = int(size * 0.7), int(size * 0.42)
    w = max(wn, wr) + 2 * padx + int(size * 0.3)
    h = int(size * 1.25 + (size * 0.7 if role else 0) + 2 * pady)
    bar = int(size * 0.2)

    def paint(d, S):
        d.rounded_rectangle([0, 0, w * S, h * S], radius=int(size * 0.28) * S, fill=rgb(ink) + (238,))
        d.rounded_rectangle([0, 0, bar * S * 1.6, h * S], radius=int(size * 0.28) * S, fill=rgb(accent) + (255,))
        d.rectangle([bar * S, 0, bar * S * 2, h * S], fill=rgb(ink) + (238,))
    base = draw_sprite(w, h, paint)
    blit(base, text_sprite(name, "ui-bold", size, "#FFFFFF", pad=0), bar * 2 + padx * 0.55, pady + size * 0.62, anchor=(0, 0.5))
    if role:
        blit(base, text_sprite(role.upper(), "ui", int(size * 0.5), accent, tracking=int(size * 0.08), pad=0),
             bar * 2 + padx * 0.55, pady + size * 1.45, anchor=(0, 0.5))
    return with_shadow(base, blur=14, offset=(0, 8), opacity=0.4)


@effect("lower-third", "motion", "Name plate that wipes in at the bottom left.",
        params=[Param("name", "Your Name", "Main line."), Param("role", "Creator", "Small line under it (optional)."),
                Param("accent", "coral", "Accent stripe and role colour."), Param("ink", "#16161A", "Plate colour."),
                Param("size", 60, "Name size at 1080 wide.")],
        aliases=("nameplate", "name-tag", "intro-card"), default_len=3.5)
def lower_third(ctx, frame, name, role, accent, ink, size):
    spr = _lower_third(name, role, accent, ink, int(ctx.px(size)))
    h, w = spr.shape[:2]
    reveal = out_expo(ctx.lt / 0.55) * (1 - out_cubic(clamp((0.35 - ctx.left) / 0.35)))
    if reveal <= 0.01:
        return frame
    vis = max(2, int(w * reveal))
    crop = spr[:, :vis]
    x = ctx.W * 0.06
    y = ctx.H * 0.8 if ctx.free_side() == "bottom" else ctx.H * 0.14
    return blit(frame, crop, x, y, anchor=(0, 0.5))


# ---------- callout ----------
@effect("callout", "motion", "A ringed pin with a leader line and a label, like an annotation in a design review.",
        params=[Param("text", "Look here", "Label text."),
                Param("target", "face", "What it points at: face, above, left, right, chin, or x,y fractions."),
                Param("label_at", "auto", "Where the label sits: auto, or x,y fractions."),
                Param("color", "lime", "Line and ring colour.")],
        face=True, aliases=("annotation", "pin", "label"), default_len=2.5)
def callout(ctx, frame, text, target, label_at, color):
    tx, ty = place(ctx, target, 0.0 if target in ("face",) else 0.1)
    if label_at == "auto":
        side = 1 if tx < ctx.W * 0.5 else -1
        lx, ly = tx + side * ctx.W * 0.3, ty - ctx.H * 0.1
    else:
        lx, ly = place(ctx, label_at)
    lx, ly = float(np.clip(lx, ctx.W * 0.2, ctx.W * 0.8)), float(np.clip(ly, ctx.H * 0.06, ctx.H * 0.94))
    col = rgb(color)
    grow = out_cubic(ctx.lt / 0.45)
    fade = fade_io(ctx, 0.05, 0.25)
    ring_r = ctx.px(34) if target != "face" else ctx.face.w * 0.62
    pulse = 1 + 0.08 * math.sin(ctx.lt * 7)
    layer = frame.copy()
    th = max(2, int(ctx.px(5)))
    cv2.circle(layer, (int(tx), int(ty)), int(ring_r * pulse * out_back(ctx.lt / 0.3)), col, th, cv2.LINE_AA)
    ex, ey = lx - (ctx.px(18) if lx > tx else -ctx.px(18)), ly
    mx = tx + (ex - tx) * grow
    my = ty + (ey - ty) * grow
    d = math.hypot(ex - tx, ey - ty) or 1
    sx, sy = tx + (ex - tx) / d * ring_r, ty + (ey - ty) / d * ring_r
    cv2.line(layer, (int(sx), int(sy)), (int(mx), int(my)), col, th, cv2.LINE_AA)
    out = cv2.addWeighted(layer, fade, frame, 1 - fade, 0)
    size = int(ctx.px(54))
    pill = _pill(text, size, color)
    s = out_back((ctx.lt - 0.25) / 0.3)
    return blit(out, pill, lx, ly, scale=s, rot=-2, alpha=fade * clamp((ctx.lt - 0.25) * 8))


@lru_cache(maxsize=64)
def _pill(text, size, color):
    t = text_sprite(text, "ui-bold", size, "#111114", pad=0)
    h, w = t.shape[:2]
    px, py = int(size * 0.6), int(size * 0.3)
    box = rrect_sprite(w + 2 * px, h + 2 * py, (h + 2 * py) // 2, color)
    box = np.pad(box, ((0, 0), (0, 0), (0, 0)))
    blit(box, t, px, py, anchor=(0, 0))
    return with_shadow(box, blur=10, offset=(0, 6), opacity=0.4)


# ---------- stat card ----------
def _parse_number(s):
    m = re.fullmatch(r"([^\d\-]*)(-?[\d,]*\.?\d+)(.*)", s.strip())
    if not m:
        return None
    pre, num, suf = m.groups()
    dec = len(num.split(".")[1]) if "." in num else 0
    return pre, float(num.replace(",", "")), dec, suf, "," in num


def _fmt(pre, val, dec, suf, comma):
    body = f"{val:,.{dec}f}" if comma else f"{val:.{dec}f}"
    return pre + body + suf


@effect("stat-card", "motion", "Frosted-glass card with a number that counts up. Use your real figure.",
        params=[Param("value", "2.4M", "Final value, e.g. 2.4M, 97%, $4,200."),
                Param("label", "VIEWS", "Caption above the number."),
                Param("at", "below", "Where it sits: below, above, bottom, top or x,y fractions."),
                Param("accent", "lime", "Accent colour.")],
        face=True, aliases=("counter", "number", "kpi"), default_len=3.5)
def stat_card(ctx, frame, value, label, at, accent):
    W, H = ctx.W, ctx.H
    parsed = _parse_number(value)
    k = out_cubic(clamp(ctx.lt / max(0.8, ctx.dur * 0.6)))
    shown = _fmt(parsed[0], parsed[1] * k, parsed[2], parsed[3], parsed[4]) if parsed else value
    big = int(ctx.px(210))
    cw, chh = int(W * 0.68), int(big * 1.35 + ctx.px(96))
    cx, cy = place(ctx, at, 0.25)
    cy = float(np.clip(cy + (chh / 2 if at in ("below", "chin") else 0) - (chh / 2 if at == "above" else 0), chh / 2 + 20, H - chh / 2 - 20))
    cx = float(np.clip(cx, cw / 2 + 20, W - cw / 2 - 20))
    pop = out_back(ctx.lt / 0.45)
    fade = fade_io(ctx, 0.1, 0.3)
    if pop <= 0.01 or fade <= 0.01:
        return frame
    x0, y0 = int(cx - cw / 2), int(cy - chh / 2)
    # glass: blur what is behind the card, lift it with a white wash and a hairline border
    reg = frame[y0:y0 + chh, x0:x0 + cw]
    if reg.shape[:2] == (chh, cw):
        glass = cv2.GaussianBlur(reg, (0, 0), ctx.px(22))
        glass = (glass * 0.62 + 255 * 0.12).astype(np.uint8)
        m = rrect_sprite(cw, chh, int(ctx.px(44)), "#FFFFFF")
        card = np.dstack([glass, m[..., 3]])
        edge = rrect_sprite(cw, chh, int(ctx.px(44)), "#FFFFFF", outline="#FFFFFF", outline_w=max(1, int(ctx.px(2))), alpha=0)
        card = np.where(edge[..., 3:4] > 0, np.dstack([np.full_like(glass, 255), np.full(glass.shape[:2], 120, np.uint8)]), card)
        blit(frame, with_shadow(card.astype(np.uint8), blur=24, offset=(0, 16), opacity=0.35), cx, cy, scale=pop, alpha=fade)
        s = pop
        blit(frame, text_sprite(label.upper(), "ui-semi", int(ctx.px(34)), "#FFFFFF", tracking=int(ctx.px(5))),
             cx, cy - chh * 0.33 * 1.0, scale=s, alpha=fade * 0.85)
        blit(frame, with_shadow(text_sprite(shown, "display", big, "#FFFFFF"), blur=8, offset=(0, 5), opacity=0.35),
             cx, cy + chh * 0.07, scale=s, alpha=fade)
        bar_w = cw * 0.5 * k
        fill_rect(frame, cx - cw * 0.25, cy + chh * 0.42, cx - cw * 0.25 + bar_w, cy + chh * 0.42 + ctx.px(8), accent, fade)
    return frame


# ---------- countdown ----------
@effect("countdown", "motion", "A punchy 3-2-1 with a sweeping ring.",
        params=[Param("start", 3, "Number to count down from."), Param("at", "above", "Where it sits."),
                Param("color", "white", "Numeral colour."), Param("accent", "coral", "Ring colour.")],
        face=True, aliases=("321", "count"), default_len=3)
def countdown(ctx, frame, start, at, color, accent):
    n = max(1, start)
    step = ctx.dur / n
    idx = min(n - 1, int(ctx.lt / step))
    local = (ctx.lt - idx * step) / step
    num = n - idx
    cx, cy = place(ctx, at, 0.35)
    cy = float(np.clip(cy, ctx.px(220), ctx.H - ctx.px(220)))
    size = int(ctx.px(300))
    s = lerp(1.35, 1.0, out_cubic(local * 3)) * (1 - 0.25 * smooth((local - 0.8) / 0.2))
    a = clamp(local * 8) * (1 - smooth((local - 0.85) / 0.15))
    layer = frame.copy()
    R = int(ctx.px(210) * s)
    cv2.ellipse(layer, (int(cx), int(cy)), (R, R), -90, 0, 360 * local, rgb(accent), max(3, int(ctx.px(12))), cv2.LINE_AA)
    out = cv2.addWeighted(layer, 0.9 * a, frame, 1 - 0.9 * a, 0)
    return blit(out, with_shadow(text_sprite(str(num), "display", size, color), blur=12, opacity=0.5), cx, cy, scale=s, alpha=a)


# ---------- ticker ----------
@lru_cache(maxsize=16)
def _ticker_strip(text, size, W, color, ink):
    unit = text_sprite(f"{text}   •   ", "display", size, ink, pad=0)
    reps = int(np.ceil(W * 2.6 / unit.shape[1])) + 1
    tile = np.tile(unit, (1, reps, 1))
    h = int(size * 1.5)
    bg = np.empty((h, tile.shape[1], 3), np.uint8)
    bg[:] = rgb(color)
    blit(bg, tile, 0, h / 2, anchor=(0, 0.5))
    return bg, unit.shape[1]


@effect("ticker", "motion", "A scrolling news-style strip. Set it at an angle for a sticker-tape feel.",
        params=[Param("text", "BREAKING  •  YOU HAVE TO SEE THIS", "Message that repeats."),
                Param("at", "bottom", "top or bottom."), Param("color", "amber", "Strip colour."),
                Param("ink", "#111114", "Text colour."), Param("speed", 0.35, "Screens per second."),
                Param("tilt", -3.0, "Degrees of tilt.")],
        aliases=("marquee", "news", "tape"), default_len=4)
def ticker(ctx, frame, text, at, color, ink, speed, tilt):
    bg, period = _ticker_strip(text, int(ctx.px(60)), ctx.W, color, ink)
    off = int(ctx.lt * speed * ctx.W) % period
    view = bg[:, off:off + int(ctx.W * 1.5)]
    strip = np.dstack([view, np.full(view.shape[:2], 255, np.uint8)])
    k = out_cubic(ctx.lt / 0.4) * out_cubic(ctx.left / 0.3)
    y = ctx.H * (0.9 if at == "bottom" else 0.1)
    return blit(frame, strip, ctx.W / 2, y + (1 - k) * ctx.H * (0.15 if at == "bottom" else -0.15), rot=tilt, alpha=min(1, k * 4))


# ---------- progress bar ----------
@effect("progress-bar", "motion", "A slim pill-shaped bar that fills across the window. Great for 'wait for it'.",
        params=[Param("at", "top", "top or bottom."), Param("color", "lime", "Fill colour."),
                Param("label", "", "Small text over the bar (optional).")],
        aliases=("timer", "loading"), default_len=5)
def progress_bar(ctx, frame, at, color, label):
    W, H = ctx.W, ctx.H
    h = int(ctx.px(18))
    m = int(ctx.px(48))
    y = int(H * 0.05) if at == "top" else int(H * 0.95) - h
    fade = fade_io(ctx, 0.2, 0.25)
    track = rrect_sprite(W - 2 * m, h, h // 2, "#FFFFFF", alpha=70)
    blit(frame, track, m, y, anchor=(0, 0), alpha=fade)
    fw = max(h, int((W - 2 * m) * ctx.u))
    blit(frame, rrect_sprite(fw, h, h // 2, color), m, y, anchor=(0, 0), alpha=fade)
    if label:
        blit(frame, text_sprite(label.upper(), "ui-semi", int(ctx.px(30)), "#FFFFFF", stroke=2, tracking=int(ctx.px(4))),
             m, y + h + ctx.px(26), anchor=(0, 0.5), alpha=fade)
    return frame


# ---------- karaoke caption ----------
@effect("caption", "motion", "Karaoke caption: words light up one at a time across the window.",
        params=[Param("text", "this is how you say it", "The sentence."),
                Param("accent", "amber", "Colour of the word being spoken."),
                Param("at", "bottom", "top, center, bottom or x,y fractions."),
                Param("size", 70, "Type size at 1080 wide.")],
        aliases=("subtitle", "karaoke", "subs"), default_len=3)
def caption(ctx, frame, text, accent, at, size):
    words = text.split()
    if not words:
        return frame
    size = int(ctx.px(size))
    lines = wrap_words(words, "ui-bold", size, ctx.W * 0.82)
    lh = size * 1.35
    block_h = lh * len(lines)
    if at in ("top", "center", "bottom"):
        cx, cy = ctx.W / 2, {"top": ctx.H * 0.14, "center": ctx.H * 0.5, "bottom": ctx.H * 0.8}[at]
    else:
        cx, cy = place(ctx, at)
    fade = fade_io(ctx, 0.2, 0.2)
    active = min(len(words) - 1, int(ctx.u * len(words)))
    gap = size * 0.28
    maxw = max(sum(text_width(w, "ui-bold", size) for w in ln) + gap * (len(ln) - 1) for ln in lines)
    pill = rrect_sprite(int(maxw + size * 1.1), int(block_h + size * 0.55), int(size * 0.55), "#111114", alpha=185)
    blit(frame, pill, cx, cy, scale=lerp(0.92, 1.0, out_cubic(ctx.lt / 0.25)), alpha=fade)
    i = 0
    for li, ln in enumerate(lines):
        widths = [text_width(w, "ui-bold", size) for w in ln]
        x = cx - (sum(widths) + gap * (len(ln) - 1)) / 2
        y = cy - block_h / 2 + lh * (li + 0.5)
        for w, ww in zip(ln, widths):
            on = i == active
            spr = text_sprite(w, "ui-bold", size, accent if on else "#FFFFFF")
            blit(frame, spr, x + ww / 2, y - (size * 0.06 if on else 0), scale=1.12 if on else 1.0, alpha=fade * (1 if i <= active else 0.55))
            x += ww + gap
            i += 1
    return frame
