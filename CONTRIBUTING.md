# Contributing

Adding an effect is one decorated function. That's the whole API.

```python
# reelcraft/library/look.py
from reelcraft.core.registry import Param, effect

@effect("tint", "look", "Wash the frame in one colour.",
        params=[Param("color", "coral", "Wash colour."), Param("amount", 0.3, "Strength, 0 to 1.")],
        default_len=3)
def tint(ctx, frame, color, amount):
    ...
    return frame
```

Every effect module in `reelcraft/library/` is discovered automatically. The CLI, the plan validator, the docs and the tests all read the same registration, so there is nothing else to wire up.

## House rules

1. **Pure functions.** An effect may only depend on `ctx` and `frame`. No state carried between frames. This is what makes `still` and `render` produce identical pixels, and the test suite checks it.
2. **Everything is authored at 1080 wide.** Wrap sizes in `ctx.px(...)` so the effect looks the same at any resolution.
3. **Respect the face.** Use `ctx.anchor(...)`, `ctx.free_side()` or `ctx.face` and set `face=True` so titles and stickers don't cover the speaker.
4. **Ease everything.** Nothing should appear or vanish in one frame unless that is the effect. Use `fade_io`, `hold_curve` and the curves in `core/easing.py`.
5. **Draw in code.** No bundled images or third-party art. Fonts must be OFL or Apache licensed with the licence file added to `reelcraft/fonts/`.
6. **Describe every option.** Each `Param` needs a one-line doc; tests fail without it.
7. **Pick the layer.** `camera` < `look` < `frame` < `motion` < `sticker`. Effects draw in that order whatever order the plan lists them.

## Adding a template

A template is one JSON file in `reelcraft/templates/` with a `niche`, a one-line `summary`, `params` (the `{placeholders}` people can `--set`) and `effects`. Use relative times (`"40%"`, `"-3"`) so it fits any clip. The test suite builds every template at 4, 8 and 60 seconds and fails on unfilled placeholders.

## Adding a sound

Write a function returning a numpy array in `reelcraft/core/sfx.py` and register it in `SOUNDS`. Keep it synthesized and deterministic (seed any noise). To make an effect play it by default, add it to `DEFAULT_CUE`.

## Workflow

```bash
bash scripts/setup.sh
.venv/bin/python -m pip install pytest
.venv/bin/python -m pytest                       # all effects x 4 moments, determinism, end-to-end render
.venv/bin/python -m reelcraft demo out/demo.mp4  # synthetic presenter, no footage needed
.venv/bin/python -m reelcraft still out/demo.mp4 --face 0.5,0.38,0.24 -e "tint@0-3" --at 1.5 out/look.png
.venv/bin/python -m reelcraft catalog            # refresh docs/CATALOG.md
.venv/bin/python -m reelcraft gallery assets     # refresh assets/gallery.jpg
```

Open the PR with the `still` image of your effect attached.
