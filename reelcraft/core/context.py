"""Per-frame context handed to every effect."""
import random
from dataclasses import dataclass, replace

import cv2
import numpy as np

from .easing import clamp


@dataclass
class Face:
    cx: float
    cy: float
    w: float
    h: float
    found: bool = True

    @property
    def top(self): return self.cy - self.h / 2
    @property
    def bottom(self): return self.cy + self.h / 2
    @property
    def left(self): return self.cx - self.w / 2
    @property
    def right(self): return self.cx + self.w / 2


class Ctx:
    """Everything an effect may read. Effects must be pure functions of this and the frame:
    no state carried between frames, which is what makes stills and full renders identical."""

    def __init__(self, W, H, fps, face):
        self.W, self.H, self.fps = W, H, fps
        self.face = face
        self.t = self.start = 0.0
        self.end = 1.0
        self.index = 0
        self.seed = 0

    def window(self, t, start, end, index=0):
        self.t, self.start, self.end, self.index = t, start, end, index
        self.seed = 1009 * (index + 1)

    @property
    def dur(self): return max(1e-6, self.end - self.start)
    @property
    def lt(self): return self.t - self.start             # seconds since the effect began
    @property
    def u(self): return clamp(self.lt / self.dur)         # 0..1 progress through the window
    @property
    def left(self): return self.dur - self.lt            # seconds remaining
    @property
    def unit(self): return min(self.W, self.H) / 1080     # scale factor so sizes feel the same at any resolution

    def rng(self, salt=0):
        return random.Random(self.seed + salt)

    def px(self, v):
        """Size authored for a 1080-wide frame, scaled to this render."""
        return v * self.W / 1080

    def anchor(self, where, gap=0.15):
        """Named spots relative to the speaker's face. `gap` is in face-heights."""
        f = self.face
        g = gap * f.h
        spots = {
            "above": (f.cx, f.top - g), "below": (f.cx, f.bottom + g),
            "left": (f.left - g - f.w * 0.1, f.cy), "right": (f.right + g + f.w * 0.1, f.cy),
            "face": (f.cx, f.cy), "chin": (f.cx, f.bottom + g),
            "top-left": (f.left - g, f.top - g), "top-right": (f.right + g, f.top - g),
            "center": (self.W / 2, self.H / 2),
            "top": (self.W / 2, self.H * 0.12), "bottom": (self.W / 2, self.H * 0.86),
        }
        if where not in spots:
            raise ValueError(f"unknown position {where!r}. Try: {', '.join(spots)}")
        x, y = spots[where]
        return float(np.clip(x, 0, self.W)), float(np.clip(y, 0, self.H))

    def free_side(self):
        """'top' or 'bottom', whichever has more room away from the face."""
        return "top" if self.face.top > self.H - self.face.bottom else "bottom"

    def zoom(self, frame, z, cx=None, cy=None, dx=0.0, dy=0.0, rot=0.0):
        """Scale the picture about (cx, cy), optionally shifting/rotating. Keeps self.face in sync."""
        cx = self.W / 2 if cx is None else cx
        cy = self.H / 2 if cy is None else cy
        M = cv2.getRotationMatrix2D((cx, cy), rot, z)
        M[:, 2] += (dx, dy)
        out = cv2.warpAffine(frame, M, (self.W, self.H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        f = self.face
        nx, ny = M @ np.array([f.cx, f.cy, 1.0])
        self.face = replace(f, cx=float(nx), cy=float(ny), w=f.w * z, h=f.h * z)
        return out
