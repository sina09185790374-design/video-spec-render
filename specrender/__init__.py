"""video-spec-render: declarative JSON spec -> rendered MP4, via ffmpeg."""

from .spec import SpecError, total_duration, validate
from .render import build_command, check_ffmpeg, describe_command, render
from .audio import check_audio, has_audio_stream, mean_volume

__all__ = [
    "SpecError", "total_duration", "validate",
    "build_command", "check_ffmpeg", "describe_command", "render",
    "check_audio", "has_audio_stream", "mean_volume",
]
