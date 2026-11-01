"""Audio gates for rendered video.

Mirrors the publishing rule we dogfood ourselves: a render without audible
audio (or with a digital-silence track) must not ship. mean_volume must be
above -50 dB or the render is rejected.
"""

from __future__ import annotations

import re
import shutil
import subprocess

MIN_MEAN_DB = -50.0


def mean_volume(path: str, ffmpeg: str = "ffmpeg") -> float:
    """Return the mean_volume (dB) of *path*'s audio, or -inf if none."""
    exe = shutil.which(ffmpeg)
    if not exe:
        raise RuntimeError("ffmpeg not found")
    proc = subprocess.run(
        [exe, "-i", path, "-af", "volumedetect", "-vn", "-sn", "-dn",
         "-f", "null", "-"],
        capture_output=True, text=True, timeout=120)
    m = re.search(r"mean_volume:\s*(-?[\d.]+)\s*dB", proc.stderr or "")
    if not m:
        return float("-inf")
    return float(m.group(1))


def check_audio(path: str, require_audio: bool = False) -> float:
    """Validate the audio track; raise RuntimeError on silence.

    Returns the measured mean_volume. If the file has no audio track and
    require_audio is True, raises. If audio exists but is quieter than
    MIN_MEAN_DB (digital silence), raises.
    """
    db = mean_volume(path)
    if db == float("-inf"):
        if require_audio:
            raise RuntimeError(f"{path}: no audio track, but audio required")
        return db
    if db < MIN_MEAN_DB:
        raise RuntimeError(
            f"{path}: audio is effectively silent (mean_volume {db:.1f} dB "
            f"< {MIN_MEAN_DB:.0f} dB gate) — mux a real music bed, never silence")
    return db


def has_audio_stream(path: str, ffprobe: str = "ffprobe") -> bool:
    exe = shutil.which(ffprobe)
    if not exe:
        return False
    proc = subprocess.run(
        [exe, "-v", "error", "-select_streams", "a",
         "-show_entries", "stream=index", "-of", "csv=p=0", path],
        capture_output=True, text=True, timeout=60)
    return bool(proc.stdout.strip())
