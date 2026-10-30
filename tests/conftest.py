import shutil

import numpy as np
import pytest

from reelcraft.core.context import Ctx, Face
from reelcraft.core.registry import load_library

load_library()
needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")


@pytest.fixture
def frame():
    rng = np.random.default_rng(1)
    return rng.integers(0, 255, (640, 360, 3), dtype=np.uint8)


@pytest.fixture
def ctx():
    c = Ctx(360, 640, 30, Face(180, 230, 90, 112))
    return c
