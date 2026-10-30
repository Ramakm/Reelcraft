"""Thin ffprobe / ffmpeg wrappers."""
import json
import shutil
import subprocess
from dataclasses import dataclass


class MediaError(RuntimeError):
    pass


def need_ffmpeg():
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            raise MediaError(f"{tool} not found. Install ffmpeg first (macOS: brew install ffmpeg, Windows: winget install ffmpeg).")


@dataclass
class Media:
    path: str
    width: int      # display size, rotation already applied
    height: int
    fps: float
    duration: float
    has_audio: bool


def probe(path):
    need_ffmpeg()
    r = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", path],
                       capture_output=True, text=True)
    if r.returncode:
        raise MediaError(f"ffprobe could not read {path!r}: {r.stderr.strip()[:200]}")
    info = json.loads(r.stdout)
    v = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    if v is None:
        raise MediaError(f"{path!r} has no video stream")
    w, h = int(v["width"]), int(v["height"])
    rot = int(v.get("tags", {}).get("rotate", 0) or 0)
    for sd in v.get("side_data_list", []):
        rot = int(sd.get("rotation", rot) or rot)
    if abs(rot) % 180 == 90:
        w, h = h, w
    num, den = (v.get("avg_frame_rate") or "30/1").split("/")
    fps = float(num) / float(den) if float(den) else 30.0
    if not 1 <= fps <= 240:
        fps = 30.0
    dur = float(v.get("duration") or info.get("format", {}).get("duration") or 0)
    return Media(path, w, h, fps, dur, any(s["codec_type"] == "audio" for s in info["streams"]))


def out_size(media, width=None, max_width=1080):
    """Even output dimensions. Never upscales past the source unless asked for an explicit width."""
    W = width or min(media.width, max_width)
    W -= W % 2
    H = int(round(W * media.height / media.width / 2)) * 2
    return W, H


def frames(media, W, H, fps, start=0.0, count=None):
    """Yield RGB frames (H, W, 3) uint8, auto-rotated and normalised to constant fps."""
    import numpy as np
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{start:.3f}", "-i", media.path,
           "-vf", f"fps={fps},scale={W}:{H}:flags=lanczos", "-pix_fmt", "rgb24"]
    if count:
        cmd += ["-frames:v", str(count)]
    cmd += ["-f", "rawvideo", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    size = W * H * 3
    try:
        while True:
            buf = p.stdout.read(size)
            if len(buf) < size:
                break
            yield np.frombuffer(buf, np.uint8).reshape(H, W, 3).copy()
    finally:
        p.stdout.close()
        p.kill()
        p.wait()


def encoder(media, out, W, H, fps, crf=18, audio=None):
    """ffmpeg process that takes raw RGB on stdin and muxes audio back in: the source's own, or `audio` (a wav)."""
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", f"{fps}", "-i", "-"]
    if audio or media.has_audio:
        cmd += ["-i", audio or media.path, "-map", "0:v", "-map", "1:a:0", "-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", str(crf), "-pix_fmt", "yuv420p", "-movflags", "+faststart", out]
    return subprocess.Popen(cmd, stdin=subprocess.PIPE)
