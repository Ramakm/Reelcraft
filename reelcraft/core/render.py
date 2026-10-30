"""Render a plan onto a video, or onto a handful of still frames for a quick look."""
import os
import tempfile

import numpy as np
from PIL import Image

from . import media as M
from . import sfx
from .context import Ctx
from .plan import Plan
from .registry import resolve
from .tracking import FaceTrack, cached_track


def _run_frame(frame, t, ctx, plan, track):
    ctx.face = track.at(t)
    frame = np.ascontiguousarray(frame)
    for it in plan.active(t):
        ctx.window(t, it.start, it.end, it.order)
        out = resolve(it.name).fn(ctx, frame, **it.params)
        if out is not None:
            frame = out
    return frame


def prepare(path, plan_builder, width=None, face=None, progress=None, use_cache=True):
    """Probe the clip, build the plan against its length and find the face if any effect needs it."""
    media = M.probe(path)
    W, H = M.out_size(media, width)
    plan = plan_builder(media.duration)
    if face is not None:
        track = FaceTrack.fixed(*face, W, H, found=True)
    elif plan.needs_face:
        track = cached_track(media, W, H, progress, use_cache)
    else:
        track = FaceTrack.default(W, H)
    return media, plan, track, W, H


def collect_cues(plan, auto):
    """Sound cues for a plan. `auto` adds each effect's default sound; explicit per-entry sounds always count."""
    cues = []
    for it in plan.items:
        if auto or (it.sound and it.sound != "none"):
            cues += sfx.cues_for(it)
    return cues


def render(path, out, plan_builder, width=None, face=None, crf=18, progress=None, sound=False):
    media, plan, track, W, H = prepare(path, plan_builder, width, face, use_cache=True)
    fps = media.fps
    ctx = Ctx(W, H, fps, track.at(0))
    cues = collect_cues(plan, sound)
    with tempfile.TemporaryDirectory() as tmp:
        wav = None
        if cues:
            wav = os.path.join(tmp, "mix.wav")
            sfx.write_wav(wav, sfx.mix(sfx.source_audio(path, media.duration), cues))
        _encode(media, out, plan, track, ctx, W, H, fps, crf, progress, wav)
    plan.cues = cues
    return plan


def _encode(media, out, plan, track, ctx, W, H, fps, crf, progress, wav):
    enc = M.encoder(media, out, W, H, fps, crf, audio=wav)
    total = max(1, int(media.duration * fps))
    try:
        for i, frame in enumerate(M.frames(media, W, H, fps)):
            enc.stdin.write(_run_frame(frame, i / fps, ctx, plan, track).tobytes())
            if progress and i % 5 == 0:
                progress(min(1.0, i / total))
    except BrokenPipeError:
        raise M.MediaError("ffmpeg stopped unexpectedly while encoding") from None
    finally:
        try:
            enc.stdin.close()
        except OSError:
            pass
        enc.wait()
    if enc.returncode:
        raise M.MediaError(f"ffmpeg failed with exit code {enc.returncode}")


def stills(path, plan_builder, times, width=None, face=None):
    """Render single frames at the given times. Returns (list of RGB arrays, plan)."""
    media, plan, track, W, H = prepare(path, plan_builder, width, face)
    ctx = Ctx(W, H, media.fps, track.at(0))
    out = []
    for t in times:
        t = min(max(0.0, t), max(0.0, media.duration - 1.0 / media.fps))
        frame = next(M.frames(media, W, H, media.fps, start=t, count=1), None)
        if frame is None:
            raise M.MediaError(f"no frame at {t:.2f}s")
        out.append(_run_frame(frame, t, ctx, plan, track))
    return out, plan


def save_sheet(images, path, cols=None, label=None):
    """Write one image, or a labelled contact sheet when there are several."""
    if len(images) == 1:
        Image.fromarray(images[0]).save(path)
        return
    cols = cols or min(len(images), 4)
    h, w = images[0].shape[:2]
    s = min(1.0, 540 / w)
    tw, th = int(w * s), int(h * s)
    rows = -(-len(images) // cols)
    sheet = Image.new("RGB", (cols * tw, rows * th), (17, 17, 20))
    for i, im in enumerate(images):
        sheet.paste(Image.fromarray(im).resize((tw, th), Image.LANCZOS), ((i % cols) * tw, (i // cols) * th))
    sheet.save(path)
