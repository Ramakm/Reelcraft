"""Captions from a subtitle file (.srt or .vtt), in four styles.

Reelcraft doesn't listen to audio. Bring a subtitle file from any transcription tool (CapCut, Whisper,
YouTube, Descript...) and this lays it out. Word timing inside a line is estimated from word length.
"""
import os
import re
from functools import lru_cache

from reelcraft.core.canvas import blit, rgb, rrect_sprite, text_sprite, text_width, with_shadow
from reelcraft.core.easing import lerp, out_back, out_cubic
from reelcraft.core.plan import PlanError
from reelcraft.core.registry import Param, effect

from ._util import wrap_words

STYLES = ("clean", "bold", "mixed", "highlight")
_TS = r"(?:(\d+):)?(\d+):(\d+)[,.](\d+)"


def _secs(h, m, s, ms):
    return int(h or 0) * 3600 + int(m) * 60 + int(s) + int(ms.ljust(3, "0")[:3]) / 1000


@lru_cache(maxsize=8)
def _load(path, mtime):
    try:
        raw = open(path, encoding="utf-8-sig").read().replace("\r\n", "\n")
    except OSError as e:
        raise PlanError(f"can't read subtitle file {path!r}: {e.strerror}") from None
    cues = []
    for block in re.split(r"\n\s*\n", raw):
        m = re.search(_TS + r"\s*-->\s*" + _TS, block)
        if not m:
            continue
        g = m.groups()
        text = block[m.end():]
        text = re.sub(r"<[^>]+>|\{[^}]*\}", "", text).replace("\n", " ").strip()
        if text:
            cues.append((_secs(*g[:4]), _secs(*g[4:]), text))
    if not cues:
        raise PlanError(f"no captions found in {path!r}. Expected .srt or .vtt with lines like 00:00:01,000 --> 00:00:03,000")
    return tuple(sorted(cues))


def _chunks(cues, max_words):
    """Split long cues into short readable chunks with proportionally divided time."""
    out = []
    for a, b, text in cues:
        words = text.split()
        parts = [words[i:i + max_words] for i in range(0, len(words), max_words)]
        if len(parts) > 1 and len(parts[-1]) == 1:          # no orphan word
            last = parts.pop()
            parts[-1] += last
        total = sum(len(w) for w in words) or 1
        t = a
        for p in parts:
            d = (b - a) * sum(len(w) for w in p) / total
            out.append((t, t + d, p))
            t += d
    return out


def _active_word(words, u):
    weights = [len(w) + 1 for w in words]
    acc, tot = 0, sum(weights)
    for i, w in enumerate(weights):
        acc += w
        if u * tot <= acc:
            return i
    return len(words) - 1


def _fonts(style, i, words):
    longest = max(range(len(words)), key=lambda k: len(words[k]))
    if style == "mixed":
        return ("serif-italic", 1.18) if i == longest else ("ui-bold", 1.0)
    return {"clean": ("ui-semi", 1.0), "bold": ("display", 1.0), "highlight": ("ui-bold", 1.0)}[style]


@effect("subtitles", "motion", "Captions from an .srt/.vtt file in four styles: clean, bold, mixed, highlight.",
        params=[Param("file", "", "Path to the .srt or .vtt file."), Param("style", "highlight", "Look of the captions.", STYLES),
                Param("accent", "amber", "Accent colour (the spoken word, or the emphasis word in mixed)."),
                Param("at", "auto", "auto, top, center, bottom, or x,y fractions."),
                Param("size", 0, "Type size at 1080 wide. 0 picks a good size for the style."),
                Param("max_words", 5, "Longest chunk shown at once.")],
        face=True, aliases=("captions", "srt", "vtt"), default_len=5)
def subtitles(ctx, frame, file, style, accent, at, size, max_words):
    if not file:
        raise PlanError("subtitles needs file=<path to .srt or .vtt>")
    path = os.path.abspath(os.path.expanduser(file))
    cues = _load(path, os.path.getmtime(path) if os.path.exists(path) else 0)
    t = ctx.t
    cur = next(((a, b, w) for a, b, w in _chunks(cues, max_words) if a <= t < b), None)
    if cur is None:
        return frame
    a, b, words = cur
    local, u = t - a, (t - a) / max(1e-6, b - a)
    base = ctx.px(size or {"clean": 62, "bold": 118, "mixed": 78, "highlight": 70}[style])
    upper = style == "bold"
    shown = [w.upper() if upper else w for w in words]
    fname0 = _fonts(style, 0, words)[0]
    lines = wrap_words(shown, fname0, int(base), ctx.W * 0.84)
    lh = base * (0.95 if style == "bold" else 1.38)
    block_h = lh * len(lines)
    if at == "auto":
        at = "bottom" if ctx.free_side() == "bottom" else "top"
    if at in ("top", "center", "bottom"):
        cx, cy = ctx.W / 2, {"top": ctx.H * 0.17, "center": ctx.H * 0.5, "bottom": ctx.H * 0.8}[at]
    else:
        fx, fy = (float(v) for v in at.split(","))
        cx, cy = fx * ctx.W, fy * ctx.H
    pop = out_back(local / 0.14, 1.6)
    fade = min(1.0, local / 0.06) * min(1.0, (b - t) / 0.06)
    gap = base * 0.26
    act = _active_word(words, u)
    sized = []
    idx = 0
    for ln in lines:
        row = []
        for w in ln:
            f, k = _fonts(style, idx, words)
            row.append((w, f, int(base * k), idx))
            idx += 1
        sized.append(row)
    def wid(w, f, s):      # highlight reserves room for the box on every word so nothing shifts when it moves
        return text_width(w, f, s) + (2 * int(s * 0.16) if style == "highlight" else 0)

    if style == "highlight":
        maxw = max(sum(wid(w, f, s) for w, f, s, _ in r) + gap * (len(r) - 1) for r in sized)
        blit(frame, rrect_sprite(int(maxw + base * 1.1), int(block_h + base * 0.5), int(base * 0.5), "#111114", alpha=170),
             cx, cy, scale=lerp(0.9, 1.0, pop), alpha=fade)
    y = cy - block_h / 2 + lh / 2
    for row in sized:
        widths = [wid(w, f, s) for w, f, s, _ in row]
        x = cx - (sum(widths) + gap * (len(row) - 1)) / 2
        for (w, f, s, i), ww in zip(row, widths):
            on = i == act
            if style == "bold":
                spr = text_sprite(w, f, s, "#FFFFFF", stroke=max(3, int(s * 0.09)), stroke_fill="#000000")
                spr = with_shadow(spr, blur=6, offset=(0, 5), opacity=0.5)
            elif style == "highlight" and on:
                t_ = text_sprite(w, f, s, "#111114", pad=0)
                px, py = int(s * 0.16), int(s * 0.04)
                box = rrect_sprite(t_.shape[1] + 2 * px, t_.shape[0] + 2 * py, int(s * 0.2), accent)
                blit(box, t_, px, py, anchor=(0, 0))
                spr = box
            elif style == "mixed":
                col = accent if f == "serif-italic" else "#FFFFFF"
                spr = with_shadow(text_sprite(w, f, s, col), blur=7, offset=(0, 4), opacity=0.55)
            else:
                spr = with_shadow(text_sprite(w, f, s, "#FFFFFF"), blur=8, offset=(0, 4), opacity=0.6)
            blit(frame, spr, x + ww / 2, y + (1 - out_cubic(local / 0.12)) * base * 0.15, scale=lerp(0.88, 1.0, pop) * (1.06 if on and style == "highlight" else 1.0), alpha=fade)
            x += ww + gap
        y += lh
    return frame
