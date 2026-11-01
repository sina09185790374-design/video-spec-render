"""Integration tests — render real video with ffmpeg and verify it.

Renders a tiny 2-scene clip (360x640, 1s scenes, ultrafast) so the suite
stays fast, then checks dimensions, duration and the audio gate with
ffprobe/volumedetect.
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest

from specrender import build_command, check_audio, render, validate

TINY = {"canvas": {"width": 360, "height": 640, "fps": 30},
        "out": {"crf": 28, "preset": "ultrafast"},
        "scenes": [
            {"duration": 1.0,
             "background": {"kind": "gradient", "from": "#0D1220",
                            "to": "#1B2A4A"},
             "overlays": [{"text": "TEST ONE", "size": 40, "y": 480}]},
            {"duration": 1.0,
             "background": {"kind": "solid", "color": "#101828"},
             "overlays": [{"text": "TEST TWO", "size": 40, "y": 480}]},
        ]}

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")


def probe(path):
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,duration",
         "-of", "json", path],
        capture_output=True, text=True, timeout=60)
    return json.loads(out.stdout)["streams"][0]


@unittest.skipUnless(FFMPEG and FFPROBE, "ffmpeg/ffprobe required")
class TestRender(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="vsr_test_")
        self.out = os.path.join(self.tmp, "clip.mp4")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_render_clip(self):
        spec = validate(dict(TINY))
        render(spec, self.out)
        self.assertTrue(os.path.exists(self.out))
        self.assertGreater(os.path.getsize(self.out), 1000)
        info = probe(self.out)
        self.assertEqual((info["width"], info["height"]), (360, 640))
        self.assertAlmostEqual(float(info["duration"]), 2.0, delta=0.3)

    def test_build_command_shape(self):
        argv = build_command(validate(dict(TINY)), "x.mp4")
        self.assertEqual(argv[0], "ffmpeg")
        self.assertIn("-filter_complex", argv)
        self.assertIn("+faststart", argv)
        joined = " ".join(argv)
        self.assertIn("drawtext", joined)
        self.assertIn("concat=n=2", joined)

    def test_audio_gate_rejects_silence(self):
        # silent aac track must fail the -50 dB gate, not slip through
        spec = validate(dict(TINY))
        render(spec, self.out)
        silent = os.path.join(self.tmp, "silent.mp4")
        subprocess.run(
            [FFMPEG, "-y", "-i", self.out, "-f", "lavfi",
             "-i", "anullsrc=r=44100:cl=stereo:d=2",
             "-c:v", "copy", "-c:a", "aac", "-shortest", silent],
            capture_output=True, timeout=120, check=True)
        with self.assertRaises(RuntimeError):
            check_audio(silent, require_audio=True)

    def test_audio_gate_passes_real_bed(self):
        spec = validate(dict(TINY))
        bed = os.path.join(self.tmp, "bed.wav")
        subprocess.run(
            [FFMPEG, "-y", "-f", "lavfi", "-i", "sine=frequency=440:d=2",
             "-ar", "44100", "-ac", "2", bed],
            capture_output=True, timeout=60, check=True)
        spec = dict(spec)
        spec["music"] = {"file": bed, "volume": 0.8, "fade_out": 0.5}
        render(spec, self.out)
        db = check_audio(self.out, require_audio=True)
        self.assertGreater(db, -50.0)


if __name__ == "__main__":
    unittest.main()
