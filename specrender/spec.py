"""Validate the video-spec JSON document.

A spec is a plain dict (parsed from JSON) with this shape:

    {
      "canvas": {"width": 1080, "height": 1920, "fps": 30},   # optional
      "scenes": [
        {
          "duration": 3.0,                                    # seconds, > 0
          "background": {"kind": "solid", "color": "#0D1220"}, # solid|gradient|video
          "overlays": [                                       # optional
            {"text": "SALE", "size": 64, "y": 1560,
             "color": "#FFFFFF", "box": true}
          ]
        },
        {"duration": 2.0,
         "background": {"kind": "gradient", "from": "#0D1220", "to": "#1B2A4A"}}
      ],
      "music": {"file": "bed.mp3", "volume": 0.5,            # optional
                "fade_out": 1.0},
      "out": {"crf": 18, "preset": "medium"}                  # optional
    }

Background kinds:
  - solid:    {"kind": "solid", "color": "#RRGGBB"}
  - gradient: {"kind": "gradient", "from": "#RRGGBB", "to": "#RRGGBB"}
  - video:    {"kind": "video", "file": "clip.mp4"}  (looped/cropped to fill)

Overlay text is Latin-script only in this build: ffmpeg drawtext cannot shape
Persian/Arabic correctly. Persian captions must be pre-rendered to PNG with a
proper shaping pipeline and burned in with the "image" overlay kind:

  {"image": "fa_caption.png", "x": "(W-w)/2", "y": "H-h-120"}

validate() raises SpecError on the first problem it finds.
"""

from __future__ import annotations

import re

HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")

DEFAULT_CANVAS = {"width": 1080, "height": 1920, "fps": 30}


class SpecError(ValueError):
    """Raised when a video spec document is invalid."""


def _need(cond: bool, msg: str) -> None:
    if not cond:
        raise SpecError(msg)


def _check_color(value, where: str) -> str:
    _need(isinstance(value, str) and HEX_COLOR.match(value),
          f"{where}: color must be #RRGGBB, got {value!r}")
    return value


def _check_scene(scene: dict, idx: int, canvas: dict) -> dict:
    tag = f"scenes[{idx}]"
    _need(isinstance(scene, dict), f"{tag}: scene must be an object")
    dur = scene.get("duration")
    _need(isinstance(dur, (int, float)) and dur > 0,
          f"{tag}: duration must be a positive number, got {dur!r}")
    _need(dur <= 600, f"{tag}: duration {dur}s exceeds 600s cap")

    bg = scene.get("background", {"kind": "solid", "color": "#0D1220"})
    _need(isinstance(bg, dict), f"{tag}: background must be an object")
    kind = bg.get("kind", "solid")
    _need(kind in ("solid", "gradient", "video"),
          f"{tag}: background.kind must be solid|gradient|video, got {kind!r}")
    if kind == "solid":
        _check_color(bg.get("color", "#000000"), f"{tag}.background")
    elif kind == "gradient":
        _check_color(bg.get("from", "#000000"), f"{tag}.background.from")
        _check_color(bg.get("to", "#000000"), f"{tag}.background.to")
    else:
        _need(isinstance(bg.get("file"), str) and bg["file"],
              f"{tag}: background.file must be a non-empty path")

    overlays = scene.get("overlays", [])
    _need(isinstance(overlays, list), f"{tag}: overlays must be a list")
    for j, ov in enumerate(overlays):
        otag = f"{tag}.overlays[{j}]"
        _need(isinstance(ov, dict), f"{otag}: overlay must be an object")
        if "image" in ov:
            _need(isinstance(ov["image"], str) and ov["image"],
                  f"{otag}: image must be a non-empty path")
            continue
        text = ov.get("text")
        _need(isinstance(text, str) and text.strip(),
              f"{otag}: text must be a non-empty string")
        size = ov.get("size", 64)
        _need(isinstance(size, int) and 8 <= size <= 400,
              f"{otag}: size must be an int 8..400, got {size!r}")
        y = ov.get("y", canvas["height"] - 360)
        _need(isinstance(y, (int, float)) and 0 <= y < canvas["height"],
              f"{otag}: y must be inside the canvas, got {y!r}")
    return scene


def validate(spec: dict) -> dict:
    """Validate a spec document; return it unchanged on success."""
    _need(isinstance(spec, dict), "spec must be a JSON object")

    canvas = dict(DEFAULT_CANVAS)
    if "canvas" in spec:
        _need(isinstance(spec["canvas"], dict), "canvas must be an object")
        for key in ("width", "height", "fps"):
            if key in spec["canvas"]:
                v = spec["canvas"][key]
                _need(isinstance(v, int) and v > 0,
                      f"canvas.{key} must be a positive int, got {v!r}")
                canvas[key] = v
    _need(canvas["width"] <= 4096 and canvas["height"] <= 4096,
          "canvas dimensions exceed 4096px cap")

    scenes = spec.get("scenes")
    _need(isinstance(scenes, list) and scenes,
          "scenes must be a non-empty list")
    _need(len(scenes) <= 64, "too many scenes (max 64)")
    for i, scene in enumerate(scenes):
        _check_scene(scene, i, canvas)

    if "music" in spec:
        music = spec["music"]
        _need(isinstance(music, dict), "music must be an object")
        _need(isinstance(music.get("file"), str) and music["file"],
              "music.file must be a non-empty path")
        vol = music.get("volume", 0.5)
        _need(isinstance(vol, (int, float)) and 0 < vol <= 1.0,
              f"music.volume must be in (0, 1], got {vol!r}")

    if "out" in spec:
        out = spec["out"]
        _need(isinstance(out, dict), "out must be an object")
        crf = out.get("crf", 18)
        _need(isinstance(crf, int) and 0 <= crf <= 51,
              f"out.crf must be 0..51, got {crf!r}")

    return spec


def total_duration(spec: dict) -> float:
    """Sum of scene durations in seconds."""
    return float(sum(s["duration"] for s in spec["scenes"]))
