#!/usr/bin/env python3
"""video-spec-render CLI.

    python3 main.py render examples/reel3.json out.mp4
    python3 main.py render spec.json out.mp4 --music bed.mp3 --check-audio
    python3 main.py validate spec.json
    python3 main.py demo            # renders examples/reel3.json, no network

Stdlib only. Needs ffmpeg on PATH (and ffprobe for the audio gate).
"""

from __future__ import annotations

import argparse
import json
import sys

from specrender import (SpecError, build_command, check_audio, check_ffmpeg,
                        describe_command, render, total_duration, validate)


def load_spec(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def cmd_validate(args) -> int:
    try:
        spec = validate(load_spec(args.spec))
    except (SpecError, json.JSONDecodeError, OSError) as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1
    n = len(spec["scenes"])
    print(f"OK: {n} scene(s), {total_duration(spec):.1f}s total")
    return 0


def cmd_render(args) -> int:
    try:
        spec = validate(load_spec(args.spec))
    except (SpecError, json.JSONDecodeError, OSError) as exc:
        print(f"INVALID SPEC: {exc}", file=sys.stderr)
        return 1
    if args.music:
        spec = dict(spec)
        spec["music"] = {"file": args.music, "volume": args.volume,
                         "fade_out": args.fade_out}
    try:
        check_ffmpeg()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if args.dry_run:
        print(describe_command(build_command(spec, args.out)))
        return 0
    print(f"Rendering {len(spec['scenes'])} scene(s), "
          f"{total_duration(spec):.1f}s -> {args.out} ...")
    try:
        render(spec, args.out)
    except RuntimeError as exc:
        print(f"RENDER FAILED: {exc}", file=sys.stderr)
        return 3
    if args.check_audio:
        try:
            db = check_audio(args.out, require_audio=True)
            print(f"audio gate passed (mean_volume {db:.1f} dB)")
        except RuntimeError as exc:
            print(f"AUDIO GATE FAILED: {exc}", file=sys.stderr)
            return 4
    print("done.")
    return 0


def cmd_demo(args) -> int:
    args.spec = "examples/reel3.json"
    args.out = args.out or "demo_reel.mp4"
    args.music = None
    args.volume = 0.5
    args.fade_out = 1.0
    args.check_audio = False
    args.dry_run = False
    return cmd_render(args)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Render a declarative JSON video spec to MP4 via ffmpeg.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("validate", help="validate a spec file")
    v.add_argument("spec")
    v.set_defaults(fn=cmd_validate)

    r = sub.add_parser("render", help="render a spec to MP4")
    r.add_argument("spec")
    r.add_argument("out")
    r.add_argument("--music", default=None, help="music bed file to mux")
    r.add_argument("--volume", type=float, default=0.5)
    r.add_argument("--fade-out", type=float, default=1.0)
    r.add_argument("--check-audio", action="store_true",
                   help="enforce the -50 dB audio gate after render")
    r.add_argument("--dry-run", action="store_true",
                   help="print the ffmpeg command without running it")
    r.set_defaults(fn=cmd_render)

    d = sub.add_parser("demo", help="render the bundled 3-scene sample reel")
    d.add_argument("--out", default=None)
    d.set_defaults(fn=cmd_demo)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
