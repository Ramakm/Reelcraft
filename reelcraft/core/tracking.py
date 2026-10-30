"""Find the speaker's face and keep it steady.

Pass one decodes a small proxy of the clip a few times per second and runs a face detector on it: YuNet
(a 230 KB model bundled in reelcraft/models) when available, otherwise the Haar cascades that ship with
OpenCV. Detections are cleaned up (outliers dropped) and smoothed, but never across a shot cut, then
turned into a track that can be sampled at any time. No face found? Effects fall back to a sensible
upper-third default, and the caller can always pin the face by hand.
"""
import json
import os
import subprocess

import cv2
import numpy as np

from .context import Face

SAMPLE_FPS = 8
PROXY_W = 480
CUT_JUMP = 0.28          # a face centre moving more than this fraction of the width between samples is a cut
MODEL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", "face_detection_yunet_2023mar.onnx")


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


class _Yunet:
    name = "yunet"

    def __init__(self, w, h):
        self.det = cv2.FaceDetectorYN.create(MODEL, "", (w, h), 0.6, 0.3, 5)

    def __call__(self, bgr):
        _, f = self.det.detect(bgr)
        if f is None:
            return []
        # head box from the face box: YuNet frames brow-to-chin, a head is taller and starts above the brow
        return [(x + w / 2, y + h / 2 - h * 0.08, w * 1.12, h * 1.3, float(sc)) for x, y, w, h, *_, sc in f]


class _Haar:
    name = "haar"

    def __init__(self, w, h):
        d = cv2.data.haarcascades
        self.frontal, self.profile = (cv2.CascadeClassifier(os.path.join(d, n)) for n in
                                      ("haarcascade_frontalface_default.xml", "haarcascade_profileface.xml"))
        self.clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        self.w = w

    def __call__(self, bgr):
        g = self.clahe.apply(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY))
        found = self.frontal.detectMultiScale(g, 1.1, 5, minSize=(self.w // 14,) * 2)
        if len(found) == 0:
            found = self.profile.detectMultiScale(g, 1.1, 5, minSize=(self.w // 12,) * 2)
        return [(x + w / 2, y + h / 2 - h * 0.04, w, max(h, w * 1.15), 1.0) for x, y, w, h in found]


def make_detector(w, h):
    if os.path.exists(MODEL) and hasattr(cv2, "FaceDetectorYN"):
        try:
            return _Yunet(w, h)
        except cv2.error:
            pass
    return _Haar(w, h)


def assemble(hits, scale):
    """Turn raw detections [(t, cx, cy, w, h), ...] into a clean (times, boxes) track.

    Drops outliers (a detection whose size is wildly off its neighbours), then smooths, but a jump in
    position is treated as a shot cut: positions hold until the cut and snap after it, never glide."""
    a = np.array(hits, float)
    a[:, 1:] *= scale
    n = len(a)
    if n >= 5:                                         # outliers: size far from the local median
        keep = np.ones(n, bool)
        for i in range(n):
            lo, hi = max(0, i - 3), min(n, i + 4)
            med = np.median(a[lo:hi, 3])
            keep[i] = 0.55 < a[i, 3] / max(med, 1e-6) < 1.8
        a = a[keep]
    times, boxes = a[:, 0], a[:, 1:5]
    cuts = [i for i in range(1, len(a)) if abs(boxes[i, 0] - boxes[i - 1, 0]) > CUT_JUMP * scale * PROXY_W]
    t_out, b_out = [], []
    edges = [0] + cuts + [len(a)]
    for s, e in zip(edges, edges[1:]):
        seg = _smooth(boxes[s:e], 5)
        t_out.extend(times[s:e])
        b_out.extend(seg)
        if e < len(a):                                 # hold the last position right up to the cut
            t_out.append(times[e] - 1e-3)
            b_out.append(seg[-1])
    return np.array(t_out), np.array(b_out)


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
           "-pix_fmt", "bgr24", "-f", "rawvideo", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    detect = make_detector(PROXY_W, ph)
    size = PROXY_W * ph * 3
    hits, i, last = [], 0, None
    while True:
        buf = proc.stdout.read(size)
        if len(buf) < size:
            break
        found = detect(np.frombuffer(buf, np.uint8).reshape(ph, PROXY_W, 3).copy())
        if found:
            # stay with the person we were following if they're still there, otherwise take the most prominent
            if last is None:
                pick = max(found, key=lambda f: f[2] * f[3] * f[4])
            else:
                near = min(found, key=lambda f: abs(f[0] - last[0]) + abs(f[1] - last[1]))
                big = max(found, key=lambda f: f[2] * f[3] * f[4])
                pick = near if abs(near[0] - last[0]) < PROXY_W * CUT_JUMP else big
            last = pick
            hits.append((i / SAMPLE_FPS, *pick[:4]))
        i += 1
        if progress and i % 12 == 0:
            progress(i / SAMPLE_FPS / max(media.duration, 0.1))
    proc.stdout.close()
    proc.wait()

    if len(hits) < max(2, i * 0.08):          # not enough evidence: don't guess
        return FaceTrack.default(W, H)
    times, boxes = assemble(hits, W / PROXY_W)
    return FaceTrack(times, boxes, W, H, True)


def cached_track(media, W, H, progress=None, use_cache=True):
    cache = media.path + ".track2.json"
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
