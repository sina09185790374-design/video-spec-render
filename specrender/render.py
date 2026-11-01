"""Build and run the ffmpeg render for a validated spec.

One ffmpeg invocation: per-scene lavfi backgrounds (or looped input video),
drawtext/image overlays, filter_complex concat, exact canvas normalize,
optional music bed with fade-out, +faststart MP4 out.
"""

from __future__ import annotations

import shlex
import shutil
import subprocess

from .spec import DEFAULT_CANVAS, total_duration


def _hex_no_hash(color: str) -> str:
    return color.lstrip("#")


def _escape_drawtext(text: str) -> str:
    # drawtext filter escaping: \ : ' need backslashes
    return (text.replace("\\", r"\\")
                 .replace(":", r"\:")
                 .replace("'", r"\'")
                 .replace("\n", " "))


def _scene_filter(scene: dict, idx: int, canvas: dict, inputs: list) -> str:
    """Return the filter chain producing labelled stream [s{idx}]."""
    w, h, fps = canvas["width"], canvas["height"], canvas["fps"]
    dur = scene["duration"]
    bg = scene.get("background", {"kind": "solid", "color": "#0D1220"})
    kind = bg.get("kind", "solid")

    parts: list[str] = []
    if kind == "solid":
        src = (f"color=c=0x{_hex_no_hash(bg.get('color', '#000000'))}"
               f":s={w}x{h}:d={dur}:r={fps}")
        parts.append(f"{src},format=yuv420p,setsar=1[s{idx}raw]")
        cur = f"[s{idx}raw]"
    elif kind == "gradient":
        c0 = _hex_no_hash(bg.get("from", "#000000"))
        c1 = _hex_no_hash(bg.get("to", "#000000"))
        src = (f"gradients=s={w}x{h}:c0=0x{c0}:c1=0x{c1}"
               f":x0=0:y0=0:x1=0:y1={h}:d={dur}:r={fps}")
        parts.append(f"{src},format=yuv420p,setsar=1[s{idx}raw]")
        cur = f"[s{idx}raw]"
    else:  # video: loop the input to the scene duration, fill the canvas
        inp = len(inputs)
        inputs.append(("-loop", "1", "-t", str(dur), "-i", bg["file"]))
        parts.append(
            f"[{inp}:v]scale={w}:{h}:force_original_aspect_ratio=increase,"
            f"crop={w}:{h},setsar=1,fps={fps},trim=duration={dur},"
            f"setpts=PTS-STARTPTS,format=yuv420p[s{idx}raw]")
        cur = f"[s{idx}raw]"

    for j, ov in enumerate(scene.get("overlays", [])):
        out = f"[s{idx}o{j}]"
        if "image" in ov:
            inp = len(inputs)
            inputs.append(("-loop", "1", "-t", str(dur), "-i", ov["image"]))
            x = ov.get("x", "(W-w)/2")
            y = ov.get("y", f"{h}-h-120")
            parts.append(f"{cur}[{inp}:v]overlay=x={x}:y={y}:eof_action=pass{out}")
        else:
            size = ov.get("size", 64)
            y = ov.get("y", h - 360)
            color = _hex_no_hash(ov.get("color", "#FFFFFF"))
            box = ov.get("box", True)
            txt = _escape_drawtext(ov["text"])
            filt = (f"drawtext=font='DejaVu Sans':text='{txt}':"
                    f"fontsize={size}:fontcolor=0x{color}:"
                    f"x=(w-text_w)/2:y={y}")
            if box:
                filt += ":box=1:boxcolor=0x000000@0.55:boxborderw=18"
            parts.append(f"{cur}{filt}{out}")
        cur = out

    parts.append(f"{cur}copy[s{idx}]")
    return ";".join(parts)


def build_command(spec: dict, out_path: str, ffmpeg: str = "ffmpeg") -> list[str]:
    """Return the argv list for rendering *spec* to *out_path*."""
    canvas = dict(DEFAULT_CANVAS)
    canvas.update(spec.get("canvas", {}))
    out_opts = spec.get("out", {})
    crf = out_opts.get("crf", 18)
    preset = out_opts.get("preset", "medium")

    inputs: list[tuple[str, ...]] = []
    filters: list[str] = []
    for i, scene in enumerate(spec["scenes"]):
        filters.append(_scene_filter(scene, i, canvas, inputs))

    n = len(spec["scenes"])
    concat_in = "".join(f"[s{i}]" for i in range(n))
    filters.append(f"{concat_in}concat=n={n}:v=1:a=0[vcat]")
    w, h, fps = canvas["width"], canvas["height"], canvas["fps"]
    filters.append(
        f"[vcat]scale={w}:{h},setsar=1,fps={fps},format=yuv420p[vout]")

    argv = [ffmpeg, "-y"]
    for group in inputs:
        argv.extend(group)

    graph = ";".join(filters)
    maps = ["-map", "[vout]"]
    if "music" in spec:
        music = spec["music"]
        total = total_duration(spec)
        fade = float(music.get("fade_out", 1.0))
        fade_start = max(0.0, total - fade)
        music_idx = len(inputs)  # inputs may already hold video/image files
        argv += ["-i", music["file"]]
        graph += (";" + f"[{music_idx}:a]volume={music.get('volume', 0.5)},"
                  f"afade=t=out:st={fade_start}:d={fade},"
                  f"atrim=duration={total},asetpts=PTS-STARTPTS[aout]")
        maps += ["-map", "[aout]"]

    argv += ["-filter_complex", graph] + maps

    argv += ["-r", str(fps), "-c:v", "libx264", "-preset", preset,
             "-crf", str(crf), "-pix_fmt", "yuv420p",
             "-movflags", "+faststart", "-shortest", out_path]
    return argv


def check_ffmpeg(ffmpeg: str = "ffmpeg") -> str:
    path = shutil.which(ffmpeg)
    if not path:
        raise RuntimeError(f"ffmpeg not found ({ffmpeg!r} not on PATH)")
    return path


def render(spec: dict, out_path: str, ffmpeg: str = "ffmpeg",
           timeout: int = 600) -> None:
    """Render the spec to out_path; raise RuntimeError on ffmpeg failure."""
    check_ffmpeg(ffmpeg)
    argv = build_command(spec, out_path, ffmpeg)
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        tail = proc.stderr[-2000:] if proc.stderr else ""
        raise RuntimeError(f"ffmpeg failed (rc={proc.returncode}):\n{tail}")


def describe_command(argv: list[str]) -> str:
    return " ".join(shlex.quote(a) for a in argv)
