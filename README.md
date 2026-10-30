<h1 align="center">Reelcraft</h1>
<p align="center"><b>Effects, stickers and motion graphics for talking-head video.</b><br>
Tell Claude what you want. It plans the edit, checks the frames and renders the video.</p>

<p align="center"><img src="assets/gallery.jpg" alt="Every Reelcraft effect on a sample clip" width="900"></p>

## What you get

29 effects in five layers. They stack in a fixed order, so you can list them any way you like and the result still looks right.

| Layer | What it does | Effects |
|---|---|---|
| **Camera** | Moves the picture | `punch-in` `drift` `shake` `pulse` |
| **Look** | Colour, texture, signal damage | `grade` `duotone` `film` `vhs` `glitch` `rgb-split` `spotlight` `flash` |
| **Frame** | Reshapes the shot | `letterbox` `polaroid` `iris` `neon-frame` |
| **Motion** | Animated type and graphics | `kinetic-title` `lower-third` `caption` `callout` `stat-card` `countdown` `ticker` `progress-bar` |
| **Sticker** | Die-cut art and particles | `sticker` (10 designs) `badge` `confetti` `sparkles` `float-up` |

Every option of every effect is in the [catalog](docs/CATALOG.md).

Titles, stickers and callouts find the speaker's face and stay clear of it. Nothing needs an image file: stickers, badges and particles are drawn in code, and the fonts are open-licensed.

## Install

```bash
git clone https://github.com/Ramakm/claude-video-effects ~/.claude/skills/reelcraft
```

Restart Claude Code. The first time you use it, Claude runs the setup (about 2 minutes) and installs `ffmpeg` if you don't have it.

Prefer the command line? It works without Claude too:

```bash
cd ~/.claude/skills/reelcraft && bash scripts/setup.sh
.venv/bin/reelcraft list
```

## Use it with Claude

Drop a video into the chat and describe the edit:

```
/reelcraft punch in when I say "watch this", then a LIVE badge top left
/reelcraft add my name as a lower third for the first 3 seconds, teal-orange grade
/reelcraft finish with confetti and a stat card saying 2.4M views
```

Claude writes a plan, renders a few check frames, fixes anything off, then saves `yourvideo_reelcraft.mp4` next to the original with your audio untouched.

## Use it from the terminal

```bash
# See what exists
reelcraft list
reelcraft info kinetic-title

# Check the look in seconds before committing to a render
reelcraft still clip.mp4 -e "kinetic-title@2-5 text='WAIT FOR *IT*'" -e "sticker@2.2-5 name=flame" --at 3 check.png

# Render
reelcraft render clip.mp4 out.mp4 --plan examples/hype-intro.json
```

A plan is plain JSON. Anything besides `fx`, `start` and `end` is an option of that effect:

```json
{"effects": [
  {"fx": "grade", "start": 0, "end": 8, "look": "teal-orange", "strength": 0.8},
  {"fx": "punch-in", "start": 3.8, "end": 5, "zoom": 1.45},
  {"fx": "kinetic-title", "start": 4, "end": 7, "text": "WAIT FOR *IT*"},
  {"fx": "sticker", "start": 4.2, "end": 7, "name": "flame", "at": "top-right"}
]}
```

Starter plans: [`hype-intro`](examples/hype-intro.json), [`results-drop`](examples/results-drop.json), [`retro-tape`](examples/retro-tape.json).

No footage handy? `reelcraft demo demo.mp4` makes a sample clip with an illustrated presenter.

## How it works

```
video ─► probe ─► face track ─┐
                              ▼
plan.json ─► validate ─► per-frame loop: camera → look → frame → motion → sticker ─► ffmpeg ─► mp4 + original audio
```

- **Registry.** Each effect is one decorated function. The CLI, plan validation, docs and tests all read the same registration, so a new effect needs no other wiring.
- **Pure functions.** An effect depends only on the frame and the clock, never on earlier frames. A `still` is therefore pixel-identical to the same frame in a full render.
- **Face tracking.** OpenCV's bundled cascades on a small proxy of the clip, interpolated and smoothed. No model downloads. If no face is found, effects fall back to a sensible spot, and `--face x,y,size` pins it by hand.
- **Resolution independent.** Everything is authored at 1080 wide and scaled, so a 4K render looks like the 1080 one.

## Honest notes

- This is v0.1: a first draft you review, not a finished edit. Watch it before you post.
- It doesn't add sound or transcribe speech. For "when I say X" timing, Claude scrubs frames or asks you for the time.
- Face tracking works best with one front-facing speaker in decent light.
- Roadmap: a person cut-out so titles can sit behind the speaker, transitions between clips, caption timing from a transcript.

## Contributing

An effect is about 15 lines. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Credits

Fonts (SIL OFL): Bebas Neue, DM Serif Display, Poppins, Caveat Brush. Licences are in [`reelcraft/fonts/`](reelcraft/fonts). Everything else is MIT, see [LICENSE](LICENSE).
