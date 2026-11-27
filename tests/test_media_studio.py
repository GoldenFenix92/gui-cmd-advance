import os
import subprocess
import tempfile
import unittest

from functions import compressor, media_studio


class TestMediaStudio(unittest.TestCase):
    def test_build_atempo_chain_handles_normal_and_extreme_speeds(self):
        self.assertEqual(media_studio.build_atempo_chain(1.5), "atempo=1.5")
        self.assertEqual(media_studio.build_atempo_chain(4.0), "atempo=2.0,atempo=2")
        self.assertEqual(media_studio.build_atempo_chain(0.25), "atempo=0.5,atempo=0.5")

    def test_build_studio_command_variants(self):
        cmd_trim = media_studio.build_studio_command("trim", "in.mp4", "out.mp4", start="00:00:01", end="00:00:05")
        self.assertIn("-c", cmd_trim)
        self.assertIn("copy", cmd_trim)

        cmd_reframe = media_studio.build_studio_command("reframe", "in.mp4", "out.mp4", aspect="9:16", fit="blur", height="720")
        self.assertIn("-filter_complex", cmd_reframe)
        self.assertIn("boxblur=20:5", " ".join(cmd_reframe))

        cmd_norm = media_studio.build_studio_command("audio-normalize", "in.mp4", "out.mp4")
        self.assertIn("loudnorm=I=-14:TP=-1.5:LRA=11", " ".join(cmd_norm))

        cmd_hdr = media_studio.build_studio_command("hdr-to-sdr", "in.mov", "out.mp4")
        self.assertIn("bt709", cmd_hdr)

    def test_real_ffmpeg_probe_mute_audio_extract_and_target_bitrate(self):
        ffmpeg = media_studio.get_ffmpeg_path()
        with tempfile.TemporaryDirectory() as tmp:
            sample = os.path.join(tmp, "sample.mp4")
            out_dir = os.path.join(tmp, "out")
            os.makedirs(out_dir)

            # Generar clip sintético corto (2s) con video + audio real
            gen = subprocess.run(
                [
                    ffmpeg, "-y", "-nostdin",
                    "-f", "lavfi", "-i", "color=c=blue:s=160x120:d=2:r=24",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                    sample,
                ],
                capture_output=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            self.assertEqual(gen.returncode, 0, "FFmpeg local no pudo generar clip sintético de prueba.")

            # 1) Probe
            info = media_studio.probe_media(sample)
            self.assertIsNotNone(info)
            self.assertTrue(info["has_video"])
            self.assertTrue(info["has_audio"])
            self.assertEqual(info["width"], 160)
            self.assertEqual(info["height"], 120)

            # 2) Bitrate objetivo en compressor.py (--max-mb)
            kbps = compressor._calculate_target_video_bitrate_kbps(sample, max_mb=5)
            self.assertIsNotNone(kbps)
            self.assertGreater(kbps, 250)

            # 3) Mute sin pérdida vía CLI
            rc_mute = media_studio.main(["--input", sample, "--op", "mute", "--output", out_dir])
            self.assertEqual(rc_mute, 0)
            muted_file = os.path.join(out_dir, "sample_sin_audio.mp4")
            self.assertTrue(os.path.exists(muted_file))
            muted_info = media_studio.probe_media(muted_file)
            self.assertFalse(muted_info["has_audio"])

            # 4) Extraer audio a WAV vía CLI
            rc_aud = media_studio.main(["--input", sample, "--op", "audio-extract", "--audio-format", "wav", "--output", out_dir])
            self.assertEqual(rc_aud, 0)
            self.assertTrue(os.path.exists(os.path.join(out_dir, "sample_audio.wav")))

    def test_gui_media_studio_dropdown_and_visible_when(self):
        import gui_app

        app = gui_app.App()
        app.withdraw()
        try:
            app.cat_var.set("Multimedia")
            app.on_category_change("Multimedia")
            app.cmd_var.set("Estudio de Video y Audio (FFmpeg)")
            app.on_command_change("Estudio de Video y Audio (FFmpeg)")
            app.update_idletasks()

            self.assertIn("--op probe", app.preview_var.get())
            self.assertFalse(app.current_args_vars["Tiempo Inicio (ej. 00:00:05)"]["is_visible"])

            app.current_args_vars["Operación"]["var"].set("Recortar Video (Inicio / Fin)")
            app.update_preview()
            self.assertIn("--op trim", app.preview_var.get())
            self.assertTrue(app.current_args_vars["Tiempo Inicio (ej. 00:00:05)"]["is_visible"])
            self.assertFalse(app.current_args_vars["Formato de Audio"]["is_visible"])

            app.current_args_vars["Operación"]["var"].set("Adaptar Formato / Redes (9:16, 16:9, 1:1)")
            app.update_preview()
            self.assertIn("--op reframe", app.preview_var.get())
            self.assertIn("--aspect 9:16", app.preview_var.get())
            self.assertTrue(app.current_args_vars["Relación de Aspecto"]["is_visible"])
        finally:
            app._on_app_close()


if __name__ == "__main__":
    unittest.main()
