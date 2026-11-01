"""Unit tests for spec validation — no ffmpeg needed."""

import unittest

from specrender import SpecError, total_duration, validate


def base_spec(**over):
    spec = {
        "scenes": [
            {"duration": 2.0,
             "background": {"kind": "solid", "color": "#0D1220"},
             "overlays": [{"text": "HELLO", "size": 64, "y": 1560}]},
            {"duration": 1.5,
             "background": {"kind": "gradient", "from": "#000000",
                            "to": "#FFFFFF"}},
        ]
    }
    spec.update(over)
    return spec


class TestValidate(unittest.TestCase):
    def test_valid(self):
        spec = validate(base_spec())
        self.assertEqual(len(spec["scenes"]), 2)

    def test_total_duration(self):
        self.assertAlmostEqual(total_duration(validate(base_spec())), 3.5)

    def test_defaults_canvas(self):
        spec = validate({"scenes": [{"duration": 1.0}]})
        self.assertEqual(spec["scenes"][0]["duration"], 1.0)

    def test_bad_duration(self):
        s = base_spec()
        s["scenes"][0]["duration"] = 0
        with self.assertRaises(SpecError):
            validate(s)

    def test_empty_scenes(self):
        with self.assertRaises(SpecError):
            validate({"scenes": []})

    def test_bad_color(self):
        s = base_spec()
        s["scenes"][0]["background"] = {"kind": "solid", "color": "red"}
        with self.assertRaises(SpecError):
            validate(s)

    def test_bad_kind(self):
        s = base_spec()
        s["scenes"][0]["background"] = {"kind": "plasma"}
        with self.assertRaises(SpecError):
            validate(s)

    def test_video_bg_needs_file(self):
        s = base_spec()
        s["scenes"][0]["background"] = {"kind": "video"}
        with self.assertRaises(SpecError):
            validate(s)

    def test_overlay_y_out_of_canvas(self):
        s = base_spec()
        s["scenes"][0]["overlays"][0]["y"] = 5000
        with self.assertRaises(SpecError):
            validate(s)

    def test_empty_text(self):
        s = base_spec()
        s["scenes"][0]["overlays"][0]["text"] = "   "
        with self.assertRaises(SpecError):
            validate(s)

    def test_image_overlay(self):
        s = base_spec()
        s["scenes"][0]["overlays"] = [{"image": "fa_caption.png", "y": 1500}]
        validate(s)  # must not raise

    def test_music_validation(self):
        s = base_spec()
        s["music"] = {"file": "bed.mp3", "volume": 1.5}
        with self.assertRaises(SpecError):
            validate(s)
        s["music"] = {"file": "bed.mp3", "volume": 0.5}
        validate(s)

    def test_too_many_scenes(self):
        s = base_spec()
        s["scenes"] = [{"duration": 0.1}] * 65
        with self.assertRaises(SpecError):
            validate(s)


if __name__ == "__main__":
    unittest.main()
