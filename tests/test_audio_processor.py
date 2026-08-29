import unittest
import os
import tempfile
import cv2
import numpy as np
import subprocess
import imageio_ffmpeg
from core.audio_processor import (
    AUDIO_EQUALIZER_PRESETS,
    build_audio_filter_string,
    equalize_video_audio,
    generate_audio_preview_sample
)

FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()


class TestAudioProcessor(unittest.TestCase):

    def test_presets_exist(self):
        self.assertIn("anti_clipping_crowd", AUDIO_EQUALIZER_PRESETS)
        self.assertIn("speech_clarity_podcast", AUDIO_EQUALIZER_PRESETS)
        self.assertIn("declip_gentle", AUDIO_EQUALIZER_PRESETS)
        self.assertIn("aggressive_leveler", AUDIO_EQUALIZER_PRESETS)
        self.assertIn("social_loudnorm", AUDIO_EQUALIZER_PRESETS)

    def test_build_audio_filter_string(self):
        f_anti = build_audio_filter_string({"preset_key": "anti_clipping_crowd"})
        self.assertIn("highpass", f_anti)
        self.assertIn("dynaudnorm", f_anti)
        self.assertIn("alimiter", f_anti)

        f_social = build_audio_filter_string({"preset_key": "social_loudnorm"})
        self.assertIn("loudnorm", f_social)

    def test_equalize_video_audio_and_preview(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            dummy_video = os.path.join(tmp_dir, "test_audio_v.mp4")
            # Create a 2-second video with tone audio
            cmd = [
                FFMPEG_EXE, "-y",
                "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=30",
                "-f", "lavfi", "-i", "sine=frequency=1000:duration=2",
                "-c:v", "libx264", "-preset", "ultrafast",
                "-c:a", "aac",
                dummy_video
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.assertTrue(os.path.exists(dummy_video))

            # Test preview generation
            prev_audio = generate_audio_preview_sample(dummy_video, {"preset_key": "anti_clipping_crowd"})
            self.assertIsNotNone(prev_audio)
            self.assertTrue(os.path.exists(prev_audio))

            # Test video audio equalization
            out_eq = os.path.join(tmp_dir, "out_eq.mp4")
            res = equalize_video_audio(dummy_video, {"preset_key": "anti_clipping_crowd"}, output_path=out_eq)
            self.assertIsNone(res.get("error"))
            self.assertTrue(os.path.exists(out_eq))
            self.assertGreater(os.path.getsize(out_eq), 0)


if __name__ == '__main__':
    unittest.main()
