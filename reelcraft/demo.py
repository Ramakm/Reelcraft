"""A synthetic talking-head clip (an illustrated presenter on a moving backdrop) for trying effects
and for tests, with no real person or footage needed. Face is at x=0.5, y=0.38, size=0.24."""
import math
import subprocess

import cv2
import numpy as np

W, H, FPS = 720, 1280, 30
FACE = (0.5, 0.38, 0.24)


def _backdrop(t):
    y = np.linspace(0, 1, H, dtype=np.float32)[:, None]
    x = np.linspace(0, 1, W, dtype=np.float32)[None, :]
    a = 0.5 + 0.5 * np.sin(t * 0.6)
    r = 70 + 90 * (x * 0.6 + y * 0.4) + 25 * a
    g = 60 + 50 * y + 30 * np.sin(x * 4 + t * 0.8)
    b = 120 + 100 * (1 - y) * x + 20 * (1 - a)
    img = np.dstack([r, g, b]).clip(0, 255).astype(np.uint8)
    for i in range(7):                                       # drifting soft discs, so zooms and shakes read clearly
        cx = int((0.15 + 0.7 * ((i * 0.37 + t * 0.03 * (1 + i % 3)) % 1)) * W)
        cy = int((0.1 + 0.8 * ((i * 0.61 + 0.2) % 1)) * H)
        overlay = img.copy()
        cv2.circle(overlay, (cx, cy), int(W * (0.08 + 0.03 * (i % 3))), (255, 255, 255) if i % 2 else (20, 20, 40), -1, cv2.LINE_AA)
        img = cv2.addWeighted(overlay, 0.12, img, 0.88, 0)
    grid = img.copy()
    for gx in range(0, W, 90):
        cv2.line(grid, (gx, 0), (gx, H), (255, 255, 255), 1)
    return cv2.addWeighted(grid, 0.06, img, 0.94, 0)


def frame(t):
    img = _backdrop(t)
    bob = math.sin(t * 2.2) * 5
    fx, fy = int(FACE[0] * W), int((FACE[1]) * H + bob)
    r = int(FACE[2] * W * 0.5)
    # shoulders and torso
    cv2.ellipse(img, (fx, fy + int(r * 3.4)), (int(r * 2.5), int(r * 2.0)), 0, 180, 360, (36, 40, 62), -1, cv2.LINE_AA)
    cv2.rectangle(img, (fx - int(r * 2.5), fy + int(r * 3.4)), (fx + int(r * 2.5), H), (36, 40, 62), -1)
    cv2.rectangle(img, (fx - int(r * 0.35), fy + int(r * 0.9)), (fx + int(r * 0.35), fy + int(r * 2.0)), (214, 160, 128), -1)
    # head, hair, face
    cv2.ellipse(img, (fx, fy), (r, int(r * 1.22)), 0, 0, 360, (226, 172, 138), -1, cv2.LINE_AA)
    cv2.ellipse(img, (fx, fy - int(r * 0.3)), (int(r * 1.08), int(r * 1.05)), 0, 180, 360, (34, 26, 30), -1, cv2.LINE_AA)
    for sx in (-1, 1):
        ex = fx + sx * int(r * 0.4)
        blink = 0.12 if (t % 3.1) < 0.12 else 1.0
        cv2.ellipse(img, (ex, fy - int(r * 0.05)), (int(r * 0.12), max(1, int(r * 0.14 * blink))), 0, 0, 360, (30, 24, 26), -1, cv2.LINE_AA)
        cv2.line(img, (ex - int(r * 0.2), fy - int(r * 0.3)), (ex + int(r * 0.2), fy - int(r * 0.32)), (34, 26, 30), 3, cv2.LINE_AA)
    talk = abs(math.sin(t * 9)) * 0.5 + 0.3
    cv2.ellipse(img, (fx, fy + int(r * 0.55)), (int(r * 0.3), int(r * 0.16 * talk * 2)), 0, 0, 180, (120, 50, 60), -1, cv2.LINE_AA)
    return img


def make_demo_clip(path, seconds=8.0):
    n = int(seconds * FPS)
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-f", "lavfi", "-i", f"sine=frequency=220:duration={seconds}", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
           "-c:a", "aac", "-b:a", "96k", "-shortest", path]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(n):
        p.stdin.write(frame(i / FPS).tobytes())
    p.stdin.close()
    p.wait()
