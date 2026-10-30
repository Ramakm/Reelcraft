"""Sound effects, synthesised in code (no samples, nothing to license), plus the mixer that lays them
under a video's original audio. Every sound is deterministic, so renders are reproducible."""
import subprocess
import wave

import numpy as np

SR = 44100


# ---------- synthesis helpers ----------
def _t(dur):
    return np.arange(int(SR * dur)) / SR


def _sine(freq, dur):
    t = _t(dur)
    f = np.broadcast_to(freq, t.shape) if np.ndim(freq) else freq
    phase = 2 * np.pi * np.cumsum(f) / SR if np.ndim(f) else 2 * np.pi * f * t
    return np.sin(phase)


def _sweep(f0, f1, dur, curve=3.0):
    t = _t(dur)
    return _sine(f1 + (f0 - f1) * np.exp(-curve * t / dur), dur)


def _decay(dur, rate=6.0, attack=0.003):
    t = _t(dur)
    return np.exp(-rate * t / dur) * np.minimum(1, t / max(attack, 1e-4))


def _noise(dur, seed=0):
    return np.random.default_rng(seed).uniform(-1, 1, int(SR * dur))


def _lowpass(x, cutoff):
    a = 1 - np.exp(-2 * np.pi * cutoff / SR)
    n = int(min(len(x), 6 / max(a, 1e-3)))
    k = a * (1 - a) ** np.arange(n)
    return np.convolve(x, k)[: len(x)]


def _highpass(x, cutoff):
    return x - _lowpass(x, cutoff)


def _bell(freqs, dur, rate=7.0):
    return sum(a * _sine(f, dur) * _decay(dur, rate * (1 + 0.6 * i)) for i, (f, a) in enumerate(freqs))


def _sum(*xs):
    """Add arrays of different lengths (shorter ones are zero-padded)."""
    out = np.zeros(max(len(x) for x in xs))
    for x in xs:
        out[: len(x)] += x
    return out


def _place(buf, x, at):
    i = int(at * SR)
    buf[i:i + len(x)] += x[: max(0, len(buf) - i)]
    return buf


# ---------- the library ----------
def pop():            return _sweep(760, 190, 0.11, 5) * _decay(0.11, 5)
def soft_pop():       return _sweep(460, 250, 0.16, 4) * _decay(0.16, 4) * 0.9
def glass_tink():     return _bell([(2093, 1.0), (3135, 0.6), (5274, 0.35), (7040, 0.15)], 0.55, 8) * 0.5
def message():
    b = np.zeros(int(SR * 0.34))
    _place(b, _sine(988, 0.14) * _decay(0.14, 5), 0.0)
    _place(b, _sine(1319, 0.2) * _decay(0.2, 5), 0.11)
    return b * 0.7
def ding():           return _bell([(1568, 1.0), (4330, 0.45), (8470, 0.2)], 1.0, 5) * 0.55
def click():          return _sum(_highpass(_noise(0.03, 3), 1800) * _decay(0.03, 9) * 0.9, _sine(1500, 0.03) * _decay(0.03, 9) * 0.3)
def tick():           return _sine(2300, 0.025) * _decay(0.025, 8) * 0.6
def whoosh():
    n = _noise(0.6, 7)
    t = np.linspace(0, 1, len(n))
    low, high = _lowpass(n, 500), _lowpass(n, 6000)
    mix = low * (1 - t) + high * t
    return mix * np.sin(np.pi * t) ** 1.6 * 1.6
def swish():
    n = _noise(0.28, 8)
    t = np.linspace(0, 1, len(n))
    return (_lowpass(n, 1200) * (1 - t) + _lowpass(n, 9000) * t) * np.sin(np.pi * t) ** 1.4 * 1.5
def riser():
    d = 1.4
    t = np.linspace(0, 1, int(SR * d))
    raw = _noise(d, 9)
    n = _lowpass(raw, 400) * (1 - t) + _lowpass(raw, 5000) * t      # brightens as it climbs
    return (n * 0.6 + _sine(180 * (1 + 7 * t ** 2), d) * 0.3) * t ** 1.5
def impact():
    d = 0.7
    return _sum(_sweep(130, 38, d, 5) * _decay(d, 5), _lowpass(_noise(0.25, 4), 700) * _decay(0.25, 7) * 0.8)
def boom():
    d = 1.3
    return _sum(_sweep(110, 28, d, 4) * _decay(d, 3.5), _lowpass(_noise(0.5, 5), 400) * _decay(0.5, 5) * 0.7)
def stamp():          return _sum(_sweep(150, 60, 0.3, 6) * _decay(0.3, 8), _lowpass(_noise(0.12, 6), 2500) * _decay(0.12, 9) * 0.7)
def glitch():
    rng = np.random.default_rng(11)
    b = np.zeros(int(SR * 0.4))
    for i in range(7):
        d = rng.uniform(0.015, 0.05)
        sq = np.sign(_sine(rng.uniform(150, 2500), d)) * 0.35
        _place(b, sq * _decay(d, 2), i * 0.045 + rng.uniform(0, 0.02))
    return b + _highpass(_noise(0.4, 12), 3000) * _decay(0.4, 6) * 0.25
def sparkle():
    rng = np.random.default_rng(13)
    b = np.zeros(int(SR * 0.9))
    for i, f in enumerate(sorted(rng.choice([1568, 1760, 2093, 2349, 2637, 3136, 3520], 5, replace=False))):
        _place(b, _sine(f, 0.3) * _decay(0.3, 7) * 0.4, i * 0.07)
    return b
def shutter():
    b = np.zeros(int(SR * 0.2))
    _place(b, click() * 1.1, 0.0)
    _place(b, click() * 0.8, 0.07)
    return b
def coin():
    b = np.zeros(int(SR * 0.7))
    _place(b, _sine(1319, 0.08) * _decay(0.08, 3) * 0.6, 0.0)
    _place(b, _sine(1760, 0.5) * _decay(0.5, 5) * 0.6, 0.07)
    return b
def success():
    b = np.zeros(int(SR * 0.9))
    for i, f in enumerate((523, 659, 784, 1047)):
        _place(b, (_sine(f, 0.45) + 0.4 * _sine(f * 2, 0.45)) * _decay(0.45, 5) * 0.35, i * 0.09)
    return b
def typing():
    rng = np.random.default_rng(17)
    b = np.zeros(int(SR * 0.8))
    t = 0.0
    while t < 0.7:
        _place(b, click() * rng.uniform(0.5, 0.9), t)
        t += rng.uniform(0.045, 0.11)
    return b
def confetti_pop():
    return _sum(_sweep(900, 120, 0.12, 6) * _decay(0.12, 6) * 0.7, _highpass(_noise(0.4, 21), 2500) * _decay(0.4, 5) * 0.35)


SOUNDS = {
    "pop": (pop, "Bubble pop. The all-rounder."), "soft-pop": (soft_pop, "Gentler pop for small things."),
    "glass-tink": (glass_tink, "Bright glass tap."), "message": (message, "Two-note message arrival."),
    "ding": (ding, "Clean bell, good for a number landing."), "click": (click, "Crisp UI click."),
    "tick": (tick, "Tiny tick for counters."), "whoosh": (whoosh, "Big air sweep for moves and transitions."),
    "swish": (swish, "Short, quick sweep."), "riser": (riser, "Tension build, 1.4s."),
    "impact": (impact, "Deep hit for a shake or a reveal."), "boom": (boom, "Longer cinematic boom."),
    "stamp": (stamp, "Heavy thud."), "glitch": (glitch, "Digital stutter."), "sparkle": (sparkle, "Rising twinkle."),
    "shutter": (shutter, "Camera shutter."), "coin": (coin, "Two-note coin."), "success": (success, "Four-note win jingle."),
    "typing": (typing, "Keyboard typing burst."), "confetti-pop": (confetti_pop, "Party popper."),
}


def render_sound(name):
    key = name.strip().lower().replace("_", "-")
    if key not in SOUNDS:
        raise KeyError(f"no sound called {name!r}. Try: {', '.join(SOUNDS)}")
    x = SOUNDS[key][0]().astype(np.float32)
    fade = min(len(x), int(SR * 0.004))
    x[-fade:] *= np.linspace(1, 0, fade)
    peak = np.abs(x).max()
    return x / peak * 0.9 if peak > 0 else x


# ---------- default cues: which sound each effect makes, and when ----------
DEFAULT_CUE = {
    "sticker": "pop", "badge": "pop", "sparkles": "sparkle", "confetti": "confetti-pop", "float-up": "soft-pop",
    "kinetic-title": "pop", "stat-card": "ding", "lower-third": "swish", "callout": "click", "punch-in": "whoosh",
    "shake": "impact", "glitch": "glitch", "flash": "shutter", "polaroid": "shutter", "ticker": "swish", "iris": "whoosh",
    "whip": "whoosh", "sticker-swipe": "whoosh", "notification": "message", "speed-lines": "impact", "lens": "glass-tink",
    "underline": "swish", "terminal": "typing", "neon-frame": "click", "letterbox": "swish", "messages": "message",
    "countdown": "tick",
}


def cues_for(item):
    """-> list of (sound name, seconds). Explicit 'sound' on a plan entry wins; 'none' silences it."""
    if item.sound == "none":
        return []
    name = item.sound or DEFAULT_CUE.get(item.name, "")
    if not name:
        return []
    if item.name == "countdown":
        n = max(1, int(item.params.get("start", 3)))
        return [(name, item.start + i * (item.end - item.start) / n) for i in range(n)]
    if item.name == "messages":
        n = max(1, len([m for m in str(item.params.get("text", "")).split("|") if m.strip()]))
        return [(name, item.start + i * (item.end - item.start) * 0.7 / n) for i in range(n)]
    if item.name == "stat-card":
        return [(name, item.start + 0.05)]
    return [(name, item.start)]


def source_audio(path, duration):
    """Original audio as float32 stereo at 44.1 kHz, or silence if there is none."""
    n = int(duration * SR) + SR
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"],
                       capture_output=True)
    if r.returncode or not r.stdout:
        return np.zeros((n, 2), np.float32)
    a = np.frombuffer(r.stdout, np.float32).reshape(-1, 2)
    return np.vstack([a, np.zeros((max(0, n - len(a)), 2), np.float32)])[:n].copy()


def mix(base, cues, gain=0.55):
    """Lay (name, time) cues over base audio (n, 2). Returns the mix, soft-limited."""
    cache = {}
    for name, t in cues:
        if name not in cache:
            cache[name] = render_sound(name)
        x = cache[name] * gain
        i = int(max(0.0, t) * SR)
        if i >= len(base):
            continue
        seg = x[: len(base) - i]
        base[i:i + len(seg)] += seg[:, None]
    return np.tanh(base * 0.9) / np.tanh(0.9) if np.abs(base).max() > 1 else base


def write_wav(path, audio):
    pcm = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(pcm.shape[1] if pcm.ndim == 2 else 1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
