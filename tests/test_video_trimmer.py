import os
import subprocess
import tempfile
import unittest

from functions import media_studio, video_trimmer


class TestVideoTrimmer(unittest.TestCase):
    def test_format_and_parse_timestamp_roundtrip(self):
        self.assertEqual(video_trimmer.format_timestamp(0), "00:00:00.00")
        self.assertEqual(video_trimmer.format_timestamp(65.5), "00:01:05.50")
        self.assertEqual(video_trimmer.format_timestamp(3661.25), "01:01:01.25")

        self.assertAlmostEqual(video_trimmer.parse_timestamp("12.5"), 12.5, places=2)
        self.assertAlmostEqual(video_trimmer.parse_timestamp("01:05.50"), 65.5, places=2)
        self.assertAlmostEqual(video_trimmer.parse_timestamp("01:01:01.25"), 3661.25, places=2)
        self.assertIsNone(video_trimmer.parse_timestamp("invalid"))

    def test_build_trim_export_command_modes(self):
        cmd_copy = video_trimmer.build_trim_export_command("in.mp4", "out.mp4", 2.0, 7.5, mode="copy", output_format="mp4")
        self.assertIn("-c", cmd_copy)
        self.assertIn("copy", cmd_copy)
        self.assertIn("2.000", cmd_copy)
        self.assertIn("5.500", cmd_copy)

        cmd_acc = video_trimmer.build_trim_export_command("in.mp4", "out.mp4", 1.0, 4.0, mode="accurate", output_format="mp4")
        self.assertIn("libx264", cmd_acc)
        self.assertIn("scale=trunc(iw/2)*2:trunc(ih/2)*2", cmd_acc)

        cmd_gif = video_trimmer.build_trim_export_command("in.mp4", "out.gif", 0.5, 2.5, output_format="gif")
        self.assertIn("palettegen", " ".join(cmd_gif))

    def test_real_ffmpeg_frame_filmstrip_trim_and_gui_smoke(self):
        ffmpeg = media_studio.get_ffmpeg_path()
        with tempfile.TemporaryDirectory() as tmp:
            sample = os.path.join(tmp, "clip.mp4")
            out_mp4 = os.path.join(tmp, "clip_recortado.mp4")

            gen = subprocess.run(
                [
                    ffmpeg, "-y", "-nostdin",
                    "-f", "lavfi", "-i", "testsrc=duration=3:size=160x120:rate=24",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                    sample,
                ],
                capture_output=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            self.assertEqual(gen.returncode, 0)

            # 1) Extraer fotograma en memoria
            frame = video_trimmer.extract_frame_pil(sample, 1.0, max_size=(160, 120))
            self.assertIsNotNone(frame)
            self.assertGreater(frame.size[0], 0)

            # 2) Extraer tira de miniaturas (filmstrip)
            strip = video_trimmer.extract_filmstrip_pil(sample, 3.0, count=5, thumb_w=48, thumb_h=36)
            self.assertIsNotNone(strip)
            self.assertEqual(strip.size[1], 36)

            # 3) Exportar recorte preciso [0.5s .. 2.0s]
            cmd = video_trimmer.build_trim_export_command(sample, out_mp4, 0.5, 2.0, mode="accurate", output_format="mp4")
            res = subprocess.run(cmd, capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self.assertEqual(res.returncode, 0)
            self.assertTrue(os.path.isfile(out_mp4))
            trimmed_info = media_studio.probe_media(out_mp4)
            self.assertIsNotNone(trimmed_info)
            self.assertGreaterEqual(trimmed_info["duration_s"], 1.2)
            self.assertLessEqual(trimmed_info["duration_s"], 1.8)

            # 4) Smoke test GUI de VideoTrimmerApp
            app = video_trimmer.VideoTrimmerApp(video_path=sample)
            app.win.withdraw()
            try:
                app.win.update_idletasks()
                self.assertAlmostEqual(app.timeline.duration, 3.0, delta=0.2)
                app.timeline.set_range(start_s=0.5, end_s=2.0, playhead_s=1.0, notify=False)
                self.assertAlmostEqual(app.timeline.start_s, 0.5, places=2)
                self.assertAlmostEqual(app.timeline.end_s, 2.0, places=2)
            finally:
                app._on_close()


if __name__ == "__main__":
    unittest.main()
