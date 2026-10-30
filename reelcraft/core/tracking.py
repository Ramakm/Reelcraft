"""Find the speaker's face and keep it steady.

Pass one decodes a small grayscale proxy of the clip a few times per second, runs OpenCV's bundled
Haar cascades (no model downloads), then interpolates and smooths the result into a track that can
be sampled at any time. No face found? Effects fall back to a sensible upper-third default, and the
caller can always pin the face by hand.
"""
import json
import os
import subprocess

import cv2
import numpy as np

from .context import Face
from .media import Media

SAMPLE_FPS = 6
PROXY_W = 400


class FaceTrack:
    def __init__(self, times, boxes, W, H, found):
        self.times, self.boxes, self.W, self.H, self.found = times, boxes, W, H, found

    @classmethod
    def fixed(cls, cx, cy, size, W, H, found=False):
        """A face that never moves. cx, cy, size are fractions of the frame width/height."""
        w = size * W
        return cls(np.array([0.0]), np.array([[cx * W, cy * H, w, w * 1.25]]), W, H, found)

    @classmethod
    def default(cls, W, H):
        return cls.fixed(0.5, 0.36, 0.26, W, H, found=False)

    def at(self, t):
        if len(self.times) == 1:
            b = self.boxes[0]
        else:
            b = [np.interp(t, self.times, self.boxes[:, i]) for i in range(4)]
        return Face(float(b[0]), float(b[1]), float(b[2]), float(b[3]), self.found)


def _detectors():
    d = cv2.data.haarcascades
    return [cv2.CascadeClassifier(os.path.join(d, n)) for n in
            ("haarcascade_frontalface_default.xml", "haarcascade_profileface.xml")]


def _smooth(a, k):
    if len(a) < 3:
        return a
    k = min(k, len(a) // 2 * 2 - 1) or 1
    pad = np.pad(a, ((k // 2, k // 2), (0, 0)), mode="edge")
    ker = np.ones(k) / k
    return np.stack([np.convolve(pad[:, i], ker, mode="valid") for i in range(a.shape[1])], axis=1)


def track_faces(media, W, H, progress=None):
    """Return a FaceTrack in output (W x H) coordinates."""
    ph = int(round(PROXY_W * media.height / media.width / 2)) * 2
    cmd = ["ffmpeg", "-v", "error", "-i", media.path, "-vf", f"fps={SAMPLE_FPS},scale={PROXY_W}:{ph}",
           "-pix_fmt", "gray", "-f", "rawvideo", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    frontal, profile = _detectors()
    size = PROXY_W * ph
    hits, i, last = [], 0, None
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    while True:
        buf = proc.stdout.read(size)
        if len(buf) < size:
            break
        g = clahe.apply(np.frombuffer(buf, np.uint8).reshape(ph, PROXY_W))
        found = frontal.detectMultiScale(g, 1.1, 5, minSize=(PROXY_W // 14,) * 2)
        if len(found) == 0:
            found = profile.detectMultiScale(g, 1.1, 5, minSize=(PROXY_W // 12,) * 2)
        if len(found):
            # prefer the face nearest the previous one, otherwise the biggest
            if last is None:
                x, y, w, h = max(found, key=lambda r: r[2] * r[3])
            else:
                x, y, w, h = min(found, key=lambda r: abs(r[0] + r[2] / 2 - last[0]) + abs(r[1] + r[3] / 2 - last[1]))
            last = (x + w / 2, y + h / 2)
            hits.append((i / SAMPLE_FPS, x + w / 2, y + h / 2, w, h))
        i += 1
        if progress and i % 12 == 0:
            progress(i / SAMPLE_FPS / max(media.duration, 0.1))
    proc.wait()

    if len(hits) < max(2, i * 0.08):          # not enough evidence: don't guess
        return FaceTrack.default(W, H)
    a = np.array(hits)
    s = W / PROXY_W
    boxes = a[:, 1:5] * s
    boxes[:, 3] = np.maximum(boxes[:, 3], boxes[:, 2] * 1.15)   # Haar boxes are tight; heads are taller
    boxes[:, 1] -= boxes[:, 3] * 0.04
    boxes = _smooth(boxes, 7)
    return FaceTrack(a[:, 0], boxes, W, H, True)


def cached_track(media, W, H, progress=None, use_cache=True):
    cache = media.path + ".track.json"
    if use_cache and os.path.exists(cache) and os.path.getmtime(cache) >= os.path.getmtime(media.path):
        try:
            d = json.load(open(cache))
            if d["W"] == W and d["H"] == H:
                return FaceTrack(np.array(d["t"]), np.array(d["b"]), W, H, d["found"])
        except (OSError, KeyError, ValueError):
            pass
    tr = track_faces(media, W, H, progress)
    try:
        json.dump({"W": W, "H": H, "found": tr.found, "t": tr.times.tolist(), "b": tr.boxes.tolist()}, open(cache, "w"))
    except OSError:
        pass
    return tr
