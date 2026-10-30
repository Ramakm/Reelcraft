---
name: reelcraft
description: Add effects, stickers, motion graphics, captions, colour grades, sound effects and ready-made style templates to a video (punch-ins, kinetic titles, stat cards, lower thirds, chat bubbles, notifications, liquid-glass lens, confetti, glitch, VHS, halftone, polaroid frame and more). Effects follow the speaker's face. Use when the user types /reelcraft, names one of these effects, or asks to add an effect, zoom, sticker, title, caption, grade or animation to their video.
---

# Reelcraft

Edits a video with a library of effects. You write a short JSON plan, check a few frames, then render.
The user is often not technical: keep replies short, do the work yourself, never ask them to run commands.

Paths below are relative to this skill's folder. Use its absolute path. Run everything from that folder.

## 1. Set up (first run only)
Run `bash scripts/setup.sh`. It prints `READY` when done (1 to 3 minutes the first time).
- `NEED_FFMPEG`: install it (macOS `brew install ffmpeg`, Windows `winget install ffmpeg`, Linux `apt install ffmpeg`), then rerun.
- `NEED_PYTHON`: install Python 3.12 (macOS `brew install python@3.12`, Windows `winget install Python.Python.3.12`), then rerun.
- Windows uses `.venv\Scripts\python.exe` in place of `.venv/bin/python`.

Shorthand used below: `RC` = `.venv/bin/python -m reelcraft`.

## 2. Learn the effects
- `RC list` shows every effect by category. `RC list sticker` narrows it.
- `RC info <name>` shows one effect's options and defaults.
- `docs/CATALOG.md` has everything in one place.
Match the user's words to an effect (aliases work: "zoom" is `punch-in`, "subtitles" is `caption`). If unsure, show them a short list of 3 to 5 options.

## 2b. Templates, captions and sound
- **Templates** are whole looks. `RC templates` lists them, `RC templates <name>` shows its parameters. Use one with `--template <name> --set key=value`. They fit any clip length. Prefer a template when the user describes a vibe ("retro", "editorial", "tech explainer", "scrapbook") and then adjust with extra effects.
- **Captions**: `--captions file.srt --caption-style clean|bold|mixed|highlight`. You cannot hear audio, so you need a subtitle file from the user. If they have none, ask whether they have one (CapCut, Whisper, YouTube and Descript can export .srt); don't invent caption text from the video's frames.
- **Sound** is opt-in. Add `--sound` only if the user asks for sound effects. Pick a specific one per effect with `"sound": "coin"` (`"none"` mutes one). `RC sounds` lists them. It mixes under the original audio.
- **Save a look** the user likes: `RC look save <name> --plan <plan>`; reuse with `--template <name>`. Use percent times (`"40%"`) or from-the-end times (`"-3"`) so it fits other clips.

## 3. Timing
- If the user gives times ("at 3 seconds", "for the first 2s"), use them.
- If they say "when I say X", you cannot hear the video. Scrub it: `RC still <video> --plan <plan> --at 0,2,4,6,8 <sheet.png>` and read the contact sheet, or ask them for the time.
- No timing at all: pick short windows. 1.5 to 4 seconds per effect looks best. Never stack more than 3 overlays at once.
- Layers sort themselves (camera, look, frame, motion, sticker), so list effects in any order.

## 4. Plan, check, render
1. Write the plan next to their video as `<name>_plan.json`:
   ```json
   {"effects": [
     {"fx": "punch-in", "start": 2.0, "end": 3.5, "zoom": 1.4},
     {"fx": "kinetic-title", "start": 3.0, "end": 6.0, "text": "WAIT FOR *IT*"},
     {"fx": "sticker", "start": 3.2, "end": 6.0, "name": "flame", "at": "top-right"}
   ]}
   ```
   Everything except `fx`, `start`, `end` (and optional `sound`) is an option of that effect. Times are seconds, `m:ss`, a percent of the clip (`"40%"`) or counted from the end (`"-3"`). Omit `end` for the effect's default length. Ready-made starting points live in `examples/`.
2. Check first (fast, a few seconds):
   `RC still <video> --plan <plan> --at 2.7,4.5 <folder>/check.png`
   Open the PNG and look at it yourself. Fix anything that covers the face, runs off an edge, is hard to read, or fights another effect.
3. Render: `RC render <video> <name>_reelcraft.mp4 --plan <plan>`. Original audio is kept. Output is capped at 1080 wide; `--width 2160` for 4K (slower).
4. Tell them where the file is and remind them to watch it before posting.

Single effect without a plan: `RC render <video> out.mp4 -e "punch-in@2-3.5 zoom=1.5"` (repeat `-e` to stack).

## Real footage checklist
Before writing a plan, look at a contact sheet of the clip (`RC still <video> --at 0,5,10,... sheet.png`) and note:
- **Burned-in captions or logos.** Keep every graphic away from them: `at: top` on `lower-third`, `kinetic-title`, `notification`, and don't add `subtitles` over existing captions.
- **How tight the framing is.** On close-ups there's no room beside the face. Prefer top/bottom-edge graphics (`kinetic-title`, `notification`, `progress-bar`, stickers) over `messages` or `terminal`, and keep `punch-in` small (about 1.08) if it would crop a logo.
- **Cuts between speakers.** Face tracking handles them (it snaps at a cut, never glides). Check a still on each speaker.
- **Timing from the transcript.** If the user has an `.srt`, take moments from it. Otherwise ask for the times; don't guess from the picture.
Recipes for two real clips are in `examples/interview-explainer.json` and `examples/podcast-breakdown.json`.

## Rules of thumb
- Use the user's real words and numbers in titles, captions and stat cards. Never invent statistics.
- Face tracking is automatic. If a still shows effects aimed at the wrong spot (no face found or wrong person), pin it: `--face x,y,size` as fractions of the frame, e.g. `--face 0.5,0.35,0.28`.
- Wrap a word in `*stars*` inside `kinetic-title` text to put it in an accent box. Separate lines of `messages` and `terminal` with `|`.
- `at` takes a name (`above`, `below`, `left`, `right`, `top-left`, `top-right`, `top`, `bottom`, `center`) or `x,y` fractions like `0.8,0.2`.
- Colours are names (`coral`, `amber`, `lime`, `mint`, `sky`, `violet`, `rose`, `ink`, `paper`) or hex.
- Vertical video with the speaker in frame works best. It is a first draft: they approve before posting.
- No speech-to-text is built in.
- If `RC` errors, the message is written for humans. Fix the plan and retry; if it names a missing tool, run `RC doctor`.
