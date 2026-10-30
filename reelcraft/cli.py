"""Command line: `reelcraft ...` (or `python -m reelcraft ...`)."""
import argparse
import os
import sys
import time

from reelcraft import __version__
from reelcraft.core import plan as P
from reelcraft.core import render as R
from reelcraft.core import sfx
from reelcraft.core import templates as T
from reelcraft.core.media import MediaError
from reelcraft.core.registry import CATEGORIES, CATEGORY_BLURB, by_category, load_library, resolve

DIM, BOLD, RESET = ("\033[2m", "\033[1m", "\033[0m") if sys.stdout.isatty() else ("", "", "")


def _parse_face(s):
    try:
        x, y, size = (float(v) for v in s.split(","))
    except ValueError:
        raise SystemExit("--face wants three fractions: x,y,size (for example 0.5,0.35,0.28)") from None
    return x, y, size


def _kv(pairs):
    out = {}
    for kv in pairs or []:
        k, sep, v = kv.partition("=")
        if not sep:
            raise SystemExit(f"--set wants key=value, got {kv!r}")
        out[k.strip()] = v
    return out


def _entries(args):
    entries = []
    overrides = _kv(getattr(args, "set", None))
    names = getattr(args, "template", None) or []
    if overrides and not names:
        raise SystemExit("--set needs --template")
    for name in names:
        entries += T.entries(name, overrides)
    if getattr(args, "plan", None):
        import json
        try:
            data = json.load(open(args.plan))
        except (OSError, ValueError) as e:
            raise SystemExit(f"couldn't read plan {args.plan!r}: {e}")
        entries += data["effects"] if isinstance(data, dict) else data
    for spec in getattr(args, "fx", None) or []:
        entries.append(P.parse_spec(spec))
    if getattr(args, "captions", None):
        entries.append({"fx": "subtitles", "file": args.captions, "style": args.caption_style, "start": 0, "end": "end"})
    return entries


def _plan_builder(args):
    entries = _entries(args)
    if not entries:
        raise SystemExit("nothing to do: give --template NAME, --plan plan.json, --captions file.srt and/or -e 'effect@start-end key=value'")
    return lambda duration: P.build(entries, duration)


def cmd_list(args):
    groups = by_category()
    for cat in CATEGORIES:
        if args.category and cat != args.category:
            continue
        print(f"\n{BOLD}{cat.upper()}{RESET}  {DIM}{CATEGORY_BLURB[cat]}{RESET}")
        for e in groups[cat]:
            print(f"  {e.name:<15} {e.summary}")
    print()
    return 0


def cmd_info(args):
    e = resolve(args.name)
    print(f"{BOLD}{e.name}{RESET}  [{e.category}]  default length {e.default_len}s" + ("  (tracks face)" if e.face else ""))
    print(f"  {e.summary}")
    if e.aliases:
        print(f"  {DIM}also: {', '.join(e.aliases)}{RESET}")
    for p in e.params:
        ch = f"  {{{'|'.join(map(str, p.choices))}}}" if p.choices else ""
        print(f"  {p.name:<10} = {p.default!r:<22} {p.doc}{ch}")
    return 0


def _progress(label):
    t0 = time.time()

    def cb(x):
        done = int(x * 28)
        sys.stderr.write(f"\r{label} [{'#' * done}{'.' * (28 - done)}] {x * 100:3.0f}%  {time.time() - t0:4.0f}s ")
        sys.stderr.flush()
    return cb


def cmd_render(args):
    out = args.output or os.path.splitext(args.input)[0] + "_reelcraft.mp4"
    plan = R.render(args.input, out, _plan_builder(args), args.width, _parse_face(args.face) if args.face else None,
                    args.crf, _progress("render"), sound=args.sound)
    sys.stderr.write("\r" + " " * 70 + "\r")
    for w in plan.warnings:
        print("warning:", w)
    extra = f", {len(plan.cues)} sound cue(s)" if plan.cues else ""
    print(f"{len(plan.items)} effect(s){extra} -> {out}")
    return 0


def cmd_still(args):
    times = [P.parse_time(t) for t in args.at.split(",")]
    imgs, plan = R.stills(args.input, _plan_builder(args), times, args.width, _parse_face(args.face) if args.face else None)
    R.save_sheet(imgs, args.output)
    for w in plan.warnings:
        print("warning:", w)
    print(f"{len(imgs)} frame(s) -> {args.output}")
    return 0


def cmd_templates(args):
    tpl = T.available()
    if args.name:
        t = T.get(args.name)
        print(f"{BOLD}{t['name']}{RESET}  [{t['niche'] or 'custom'}, {t['source']}]")
        print(f"  {t['summary']}")
        if t["params"]:
            print("  parameters (change with --set key=value):")
            for k, v in t["params"].items():
                print(f"    {k:<8} = {v!r}")
        print("  effects:", ", ".join(dict.fromkeys(e["fx"] for e in t["effects"])))
        return 0
    for name, t in sorted(tpl.items(), key=lambda kv: (kv[1]["source"] != "yours", kv[1]["niche"], kv[0])):
        tag = f"{DIM}[{t['niche'] or 'custom'}{', yours' if t['source'] == 'yours' else ''}]{RESET}"
        print(f"  {name:<18} {tag:<28} {t['summary']}")
    print(f"\n{len(tpl)} templates. Use one with: reelcraft render clip.mp4 out.mp4 --template NAME --set key=value")
    return 0


def cmd_look(args):
    if args.action == "save":
        entries = _entries(args)
        if not entries:
            raise SystemExit("nothing to save: give --template, --plan and/or -e specs describing the look")
        path = T.save(args.name, entries, args.summary or "")
        print(f"saved look {args.name!r} -> {path}")
        print(f"use it with: reelcraft render clip.mp4 out.mp4 --template {args.name}")
        return 0
    path = os.path.join(T.user_dir(), args.name + ".json")
    if not os.path.exists(path):
        raise SystemExit(f"no saved look called {args.name!r}")
    os.remove(path)
    print("deleted", args.name)
    return 0


def cmd_sounds(args):
    for name, (_, desc) in sfx.SOUNDS.items():
        print(f"  {name:<14} {desc}")
    print("\nDefault cues (used with --sound):")
    for fx, snd in sorted(sfx.DEFAULT_CUE.items()):
        print(f"  {fx:<15} -> {snd}")
    return 0


def cmd_sound(args):
    sfx.write_wav(args.output, sfx.render_sound(args.name)[:, None])
    print("wrote", args.output)
    return 0


def cmd_doctor(args):
    import shutil
    ok = True
    for tool in ("ffmpeg", "ffprobe"):
        p = shutil.which(tool)
        print(f"{'ok ' if p else 'MISSING'} {tool} {p or ''}")
        ok &= bool(p)
    for mod in ("numpy", "cv2", "PIL"):
        try:
            __import__(mod)
            print(f"ok  {mod}")
        except ImportError:
            print(f"MISSING {mod}")
            ok = False
    print(f"ok  {len(load_library())} effects loaded, reelcraft {__version__}")
    return 0 if ok else 1


def cmd_catalog(args):
    from reelcraft.docs import write_catalog
    write_catalog(args.output)
    print("wrote", args.output)
    return 0


def cmd_demo(args):
    from reelcraft.demo import make_demo_clip
    make_demo_clip(args.output, args.seconds)
    print("wrote", args.output, "(face is at --face 0.5,0.38,0.24)")
    return 0


def cmd_gallery(args):
    from reelcraft.docs import write_gallery
    write_gallery(args.output, args.thumbs)
    return 0


def build_parser():
    ap = argparse.ArgumentParser(prog="reelcraft", description="Effects, stickers and motion graphics for talking-head video.")
    ap.add_argument("--version", action="version", version=f"reelcraft {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("input", help="source video")
        p.add_argument("--plan", help="JSON edit plan")
        p.add_argument("--template", action="append", metavar="NAME", help="start from a style template (see `reelcraft templates`)")
        p.add_argument("--set", action="append", metavar="KEY=VALUE", help="fill a template parameter (repeatable)")
        p.add_argument("--captions", metavar="FILE", help="add captions from an .srt or .vtt file")
        p.add_argument("--caption-style", default="highlight", choices=("clean", "bold", "mixed", "highlight"), help="caption look (default highlight)")
        p.add_argument("-e", "--fx", action="append", metavar="SPEC", help="inline effect, e.g. 'punch-in@2-3.5 zoom=1.5' (repeatable)")
        p.add_argument("--width", type=int, help="output width in px (default: source width, max 1080)")
        p.add_argument("--face", metavar="X,Y,SIZE", help="skip tracking and pin the face (fractions of the frame)")

    p = sub.add_parser("list", help="show every effect"); p.add_argument("category", nargs="?", choices=CATEGORIES); p.set_defaults(fn=cmd_list)
    p = sub.add_parser("info", help="options for one effect"); p.add_argument("name"); p.set_defaults(fn=cmd_info)
    p = sub.add_parser("render", help="render a video"); common(p)
    p.add_argument("output", nargs="?"); p.add_argument("--crf", type=int, default=18, help="x264 quality, lower is better (default 18)")
    p.add_argument("--sound", action="store_true", help="add each effect's default sound effect (off by default)"); p.set_defaults(fn=cmd_render)
    p = sub.add_parser("still", help="render a few frames to PNG to check the look before a full render"); common(p)
    p.add_argument("--at", required=True, help="comma-separated times, e.g. 2.5,4,7"); p.add_argument("output"); p.set_defaults(fn=cmd_still)
    p = sub.add_parser("templates", help="list style templates, or show one"); p.add_argument("name", nargs="?"); p.set_defaults(fn=cmd_templates)
    p = sub.add_parser("look", help="save or delete your own reusable look")
    p.add_argument("action", choices=("save", "delete")); p.add_argument("name")
    p.add_argument("--plan"); p.add_argument("--template", action="append"); p.add_argument("--set", action="append"); p.add_argument("-e", "--fx", action="append")
    p.add_argument("--summary", help="one line describing the look"); p.set_defaults(fn=cmd_look)
    p = sub.add_parser("sounds", help="list built-in sound effects and default cues"); p.set_defaults(fn=cmd_sounds)
    p = sub.add_parser("sound", help="export one sound effect as a wav to preview it"); p.add_argument("name"); p.add_argument("output"); p.set_defaults(fn=cmd_sound)
    p = sub.add_parser("doctor", help="check the install"); p.set_defaults(fn=cmd_doctor)
    p = sub.add_parser("catalog", help="regenerate docs/CATALOG.md"); p.add_argument("output", nargs="?", default="docs/CATALOG.md"); p.set_defaults(fn=cmd_catalog)
    p = sub.add_parser("demo", help="make a short sample clip to try things on"); p.add_argument("output", nargs="?", default="demo.mp4"); p.add_argument("--seconds", type=float, default=8); p.set_defaults(fn=cmd_demo)
    p = sub.add_parser("gallery", help="render a thumbnail for every effect"); p.add_argument("output", nargs="?", default="assets"); p.add_argument("--thumbs", action="store_true"); p.set_defaults(fn=cmd_gallery)
    return ap


def main(argv=None):
    load_library()
    args = build_parser().parse_args(argv)
    try:
        return args.fn(args)
    except (MediaError, P.PlanError, KeyError, ValueError) as e:
        print(f"error: {e.args[0] if isinstance(e, KeyError) and e.args else e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
