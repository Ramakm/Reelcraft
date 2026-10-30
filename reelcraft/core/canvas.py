"""Drawing toolkit: fonts, anti-aliased sprites, die-cut outlines, glows and fast compositing.

Sprites are RGBA uint8 arrays. Effects build a sprite once (cached) and `blit` it every frame with
its own position, scale, rotation and opacity, which keeps full-HD rendering fast.
"""
import os
from functools import lru_cache

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fonts")
FONT_FILES = {
    "display": "BebasNeue-Regular.ttf",
    "serif": "DMSerifDisplay-Regular.ttf",
    "serif-italic": "DMSerifDisplay-Italic.ttf",
    "ui": "Poppins-Medium.ttf",
    "ui-semi": "Poppins-SemiBold.ttf",
    "ui-bold": "Poppins-Bold.ttf",
    "hand": "CaveatBrush-Regular.ttf",
}
FONT_NAMES = tuple(FONT_FILES)

# One palette, used by default across the library so stacked effects always look related.
PALETTE = {
    "ink": "#111114", "paper": "#F6F1E7", "cream": "#EFE6D2", "coral": "#FF5A4F", "amber": "#FFB627",
    "lime": "#C6F432", "mint": "#4FE3B5", "sky": "#4AA8FF", "violet": "#8B5CF6", "rose": "#FF6FB5",
    "white": "#FFFFFF", "black": "#000000",
}


def rgb(color, default=(255, 255, 255)):
    """'#ff5a4f', 'coral', or an (r,g,b) tuple -> (r,g,b)."""
    if color is None:
        return default
    if isinstance(color, (tuple, list)):
        return tuple(int(c) for c in color[:3])
    c = PALETTE.get(str(color).lower(), str(color)).lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    try:
        return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        raise ValueError(f"not a colour: {color!r} (use a name like coral, or hex like #ff5a4f)")


@lru_cache(maxsize=128)
def font(name, size):
    path = os.path.join(FONT_DIR, FONT_FILES.get(name, FONT_FILES["ui-bold"]))
    try:
        return ImageFont.truetype(path, int(size))
    except OSError:
        return ImageFont.load_default()


def text_width(txt, fname, size, tracking=0):
    f = font(fname, size)
    return int(sum(f.getlength(ch) for ch in txt) + tracking * max(0, len(txt) - 1)) if tracking else int(f.getlength(txt))


# ---------- sprites ----------
def new_sprite(w, h):
    return np.zeros((int(h), int(w), 4), np.uint8)


def draw_sprite(w, h, painter, ss=3):
    """Run painter(draw, S) on a supersampled canvas and shrink it back for clean edges."""
    w, h = int(w), int(h)
    img = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    painter(ImageDraw.Draw(img), ss)
    return np.asarray(img.resize((w, h), Image.LANCZOS))


@lru_cache(maxsize=256)
def text_sprite(txt, fname="ui-bold", size=64, fill="#FFFFFF", stroke=0, stroke_fill="#000000", tracking=0, pad=6):
    f = font(fname, size)
    fill, stroke_fill = rgb(fill), rgb(stroke_fill)
    asc, desc = f.getmetrics()
    tw = text_width(txt, fname, size, tracking)
    w, h = tw + 2 * (pad + stroke), asc + desc + 2 * (pad + stroke)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x = pad + stroke
    if tracking:
        for ch in txt:
            d.text((x, pad + stroke), ch, font=f, fill=fill + (255,), stroke_width=stroke, stroke_fill=stroke_fill + (255,))
            x += f.getlength(ch) + tracking
    else:
        d.text((x, pad + stroke), txt, font=f, fill=fill + (255,), stroke_width=stroke, stroke_fill=stroke_fill + (255,))
    return np.asarray(img)


def rrect_sprite(w, h, radius, fill, outline=None, outline_w=0, alpha=255):
    fill = rgb(fill)

    def paint(d, S):
        d.rounded_rectangle([0, 0, w * S - 1, h * S - 1], radius=radius * S, fill=fill + (alpha,),
                            outline=rgb(outline) + (255,) if outline else None, width=outline_w * S)
    return draw_sprite(w, h, paint)


def pad_sprite(spr, n):
    return np.pad(spr, ((n, n), (n, n), (0, 0)))


def with_shadow(spr, blur=14, offset=(0, 8), opacity=0.45, color=(0, 0, 0)):
    """Soft drop shadow under a sprite; returns a larger sprite."""
    n = int(blur * 2.5) + max(abs(offset[0]), abs(offset[1]))
    spr = pad_sprite(spr, n)
    a = cv2.GaussianBlur(spr[..., 3], (0, 0), blur)
    M = np.float32([[1, 0, offset[0]], [0, 1, offset[1]]])
    a = cv2.warpAffine(a, M, (spr.shape[1], spr.shape[0]))
    sh = np.zeros_like(spr)
    sh[..., :3] = color
    sh[..., 3] = (a * opacity).astype(np.uint8)
    return over(sh, spr)


def with_outline(spr, width=10, color="#FFFFFF"):
    """Die-cut sticker border: dilate the alpha, fill with a flat colour, put the art on top."""
    spr = pad_sprite(spr, width + 2)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (width * 2 + 1, width * 2 + 1))
    a = cv2.dilate(spr[..., 3], k)
    a = cv2.GaussianBlur(a, (0, 0), 0.8)
    bd = np.zeros_like(spr)
    bd[..., :3] = rgb(color)
    bd[..., 3] = a
    return over(bd, spr)


def with_glow(spr, radius=18, color=None, strength=1.0):
    """Soft halo behind a sprite. Defaults to the sprite's own average colour."""
    n = int(radius * 2.5)
    spr = pad_sprite(spr, n)
    solid = spr[..., 3] > 128
    if color is not None:
        col = rgb(color)
    elif solid.any():
        col = spr[..., :3][solid].mean(0)
    else:
        col = (255, 255, 255)
    a = cv2.GaussianBlur(spr[..., 3], (0, 0), radius)
    g = np.zeros_like(spr)
    g[..., :3] = col
    g[..., 3] = np.clip(a.astype(np.float32) * strength, 0, 255).astype(np.uint8)
    return over(g, spr)


def over(bottom, top):
    """Alpha-composite two same-sized RGBA sprites."""
    ta = top[..., 3:4].astype(np.float32) / 255
    ba = bottom[..., 3:4].astype(np.float32) / 255
    oa = ta + ba * (1 - ta)
    rgbo = (top[..., :3] * ta + bottom[..., :3] * ba * (1 - ta)) / np.maximum(oa, 1e-6)
    return np.dstack([rgbo, oa * 255]).clip(0, 255).astype(np.uint8)


def tint(spr, color):
    out = spr.copy()
    out[..., :3] = rgb(color)
    return out


# ---------- compositing ----------
def blit(frame, spr, cx, cy, scale=1.0, rot=0.0, alpha=1.0, anchor=(0.5, 0.5), flip_x=False):
    """Composite RGBA sprite onto an RGB frame in place. (cx, cy) is where the anchor lands."""
    if alpha <= 0.003 or scale <= 0.002:
        return frame
    H, W = frame.shape[:2]
    h, w = spr.shape[:2]
    ax, ay = anchor[0] * w, anchor[1] * h
    if flip_x:
        spr = spr[:, ::-1]
    if abs(scale - 1) < 1e-3 and abs(rot) < 1e-3:
        x0, y0 = int(round(cx - ax)), int(round(cy - ay))
        sx0, sy0 = max(0, -x0), max(0, -y0)
        x1, y1 = min(W, x0 + w), min(H, y0 + h)
        if x1 <= max(x0, 0) or y1 <= max(y0, 0):
            return frame
        src = spr[sy0:sy0 + (y1 - max(y0, 0)), sx0:sx0 + (x1 - max(x0, 0))]
        _mix(frame[max(y0, 0):y1, max(x0, 0):x1], src, alpha)
        return frame
    th = np.deg2rad(rot)
    c, s = np.cos(th) * scale, np.sin(th) * scale
    # sprite -> frame:  p' = R*S*(p - a) + c
    M = np.float32([[c, -s, cx - (c * ax - s * ay)], [s, c, cy - (s * ax + c * ay)]])
    corners = np.float32([[0, 0, 1], [w, 0, 1], [w, h, 1], [0, h, 1]]) @ M.T
    bx0, by0 = np.floor(corners.min(0)).astype(int) - 1
    bx1, by1 = np.ceil(corners.max(0)).astype(int) + 1
    bx0, by0, bx1, by1 = max(bx0, 0), max(by0, 0), min(bx1, W), min(by1, H)
    if bx1 <= bx0 or by1 <= by0:
        return frame
    M2 = M.copy()
    M2[:, 2] -= (bx0, by0)
    pre = spr.astype(np.float32)
    pre[..., :3] *= pre[..., 3:4] / 255.0
    warped = cv2.warpAffine(pre, M2, (bx1 - bx0, by1 - by0), flags=cv2.INTER_LINEAR,
                            borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    a = warped[..., 3:4] / 255.0 * alpha
    reg = frame[by0:by1, bx0:bx1]
    reg[:] = np.clip(warped[..., :3] * alpha + reg * (1 - a), 0, 255).astype(np.uint8)
    return frame


def _mix(region, src, alpha):
    a = src[..., 3:4].astype(np.float32) / 255.0 * alpha
    region[:] = np.clip(src[..., :3] * a + region * (1 - a), 0, 255).astype(np.uint8)


def fill_rect(frame, x0, y0, x1, y1, color, alpha=1.0):
    H, W = frame.shape[:2]
    x0, y0, x1, y1 = max(0, int(x0)), max(0, int(y0)), min(W, int(x1)), min(H, int(y1))
    if x1 <= x0 or y1 <= y0 or alpha <= 0:
        return frame
    reg = frame[y0:y1, x0:x1]
    reg[:] = (reg * (1 - alpha) + np.array(rgb(color), np.float32) * alpha).astype(np.uint8)
    return frame


def paste_clip(frame, inner, x, y, radius=0):
    """Paste an RGB array (e.g. the shrunk video) at x, y with optional rounded corners."""
    H, W = frame.shape[:2]
    h, w = inner.shape[:2]
    x, y = int(x), int(y)
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
    if x1 <= x0 or y1 <= y0:
        return frame
    sub = inner[y0 - y:y1 - y, x0 - x:x1 - x]
    if radius <= 0:
        frame[y0:y1, x0:x1] = sub
        return frame
    m = rrect_sprite(w, h, radius, "#FFFFFF")[..., 3][y0 - y:y1 - y, x0 - x:x1 - x, None] / 255.0
    frame[y0:y1, x0:x1] = (sub * m + frame[y0:y1, x0:x1] * (1 - m)).astype(np.uint8)
    return frame
