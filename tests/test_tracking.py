import numpy as np

from reelcraft.core import tracking as T


def hit(t, cx, w=60, cy=200):
    return (t, cx, cy, w, w * 1.25)


def test_outlier_size_is_dropped():
    hits = [hit(i / 8, 240, 80) for i in range(12)]
    hits[6] = hit(6 / 8, 240, 14)                       # the tiny false positive that real footage produces
    times, boxes = T.assemble(hits, 1.0)
    assert boxes[:, 2].min() > 60 and len(times) == 11


def test_smoothing_never_blends_across_a_shot_cut():
    left = [hit(i / 8, 120) for i in range(8)]
    right = [hit(1 + i / 8, 380) for i in range(8)]     # the other speaker, on the other side of the frame
    times, boxes = T.assemble(left + right, 1.0)
    track = T.FaceTrack(times, boxes, 480, 854, True)
    assert abs(track.at(0.95).cx - 120) < 1.0           # holds until the cut...
    assert abs(track.at(1.05).cx - 380) < 6.0           # ...then snaps, never gliding through the middle
    mid = [track.at(t).cx for t in np.linspace(0.9, 1.1, 40)]
    assert not any(200 < c < 300 for c in mid)


def test_smoothing_still_calms_jitter_within_a_shot():
    rng = np.random.default_rng(0)
    hits = [hit(i / 8, 240 + rng.normal(0, 6)) for i in range(40)]
    _, boxes = T.assemble(hits, 1.0)
    assert boxes[:, 0].std() < np.array([h[1] for h in hits]).std()


def test_detector_loads_and_handles_an_empty_frame():
    det = T.make_detector(T.PROXY_W, 854)
    assert det.name in ("yunet", "haar")
    assert det(np.zeros((854, T.PROXY_W, 3), np.uint8)) == []
