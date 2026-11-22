import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from functions import compressor
from functions.utils import get_ffmpeg_path


def _generate_test_video(output_path, duration=1):
    """Genera un video MP4 real con pista de video + audio usando FFmpeg."""
    cmd = [
        get_ffmpeg_path(), "-y",
        "-f", "lavfi", "-i", f"testsrc=duration={duration}:size=320x240:rate=24",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        str(output_path),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def _verify_video_playable(video_path):
    cmd = [
        get_ffmpeg_path(), "-v", "error",
        "-i", str(video_path),
        "-f", "null", "-",
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return proc.returncode == 0 and proc.stderr.strip() == ""


class TestCompressor(unittest.TestCase):
    def test_format_size_handles_zero_positive_and_negative(self):
        self.assertEqual(compressor.format_size(0), "0 B")
        self.assertEqual(compressor.format_size(1024), "1.0 KB")
        self.assertEqual(compressor.format_size(-2048), "-2.0 KB")

    def test_compress_image_preserves_exif_orientation_and_formats(self):
        with tempfile.TemporaryDirectory() as tmp:
            # 1. JPEG con EXIF Orientation = 6 (90° CW -> ancho 100 x alto 50 debe quedar 50 x 100 tras transponer)
            jpg_in = os.path.join(tmp, "foto_\U0001f451_movil.jpg")
            img = Image.new("RGB", (100, 50), (20, 120, 220))
            exif = img.getexif()
            exif[274] = 6  # Orientation: Rotate 90 CW
            img.save(jpg_in, "JPEG", exif=exif.tobytes())

            jpg_out = os.path.join(tmp, "foto_\U0001f451_movil_comprimido.jpg")
            res_jpg = compressor.compress_image(jpg_in, jpg_out, quality=75)
            self.assertEqual(res_jpg["status"], "success")
            with Image.open(jpg_out) as out_img:
                self.assertEqual(out_img.format, "JPEG")
                self.assertEqual(out_img.size, (50, 100))
                self.assertIn(out_img.getexif().get(274), (None, 1))

            # 2. PNG con transparencia RGBA
            png_in = os.path.join(tmp, "logo.png")
            Image.new("RGBA", (64, 64), (255, 0, 0, 128)).save(png_in, "PNG")
            png_out = os.path.join(tmp, "logo_comprimido.png")
            res_png = compressor.compress_image(png_in, png_out)
            self.assertEqual(res_png["status"], "success")
            with Image.open(png_out) as out_png:
                self.assertEqual(out_png.format, "PNG")
                self.assertEqual(out_png.mode, "RGBA")

            # 3. WEBP mantiene formato interno WEBP (no JPEG corrupto)
            webp_in = os.path.join(tmp, "banner.webp")
            Image.new("RGB", (80, 60), (0, 200, 100)).save(webp_in, "WEBP")
            webp_out = os.path.join(tmp, "banner_comprimido.webp")
            res_webp = compressor.compress_image(webp_in, webp_out, quality=75)
            self.assertEqual(res_webp["status"], "success")
            with Image.open(webp_out) as out_webp:
                self.assertEqual(out_webp.format, "WEBP")

    def test_compress_video_real_and_corrupt_safety(self):
        if not compressor.is_ffmpeg_installed():
            self.skipTest("FFmpeg no está instalado en este entorno.")

        with tempfile.TemporaryDirectory() as tmp:
            # 1. Video MP4 real con audio
            vid_in = os.path.join(tmp, "clip_\U0001f3ac.mp4")
            vid_out = os.path.join(tmp, "clip_\U0001f3ac_comprimido.mp4")
            _generate_test_video(vid_in, duration=1)

            res_ok = compressor.compress_video(vid_in, vid_out, crf=26, hw="cpu", preset="fast")
            self.assertEqual(res_ok["status"], "success")
            self.assertTrue(os.path.exists(vid_out))
            self.assertGreater(os.path.getsize(vid_out), 0)
            self.assertTrue(_verify_video_playable(vid_out))

            # 2. Video corrupto: debe fallar sin dejar .part ni .mp4 corrupto
            bad_in = os.path.join(tmp, "corrupto.mp4")
            bad_out = os.path.join(tmp, "corrupto_comprimido.mp4")
            with open(bad_in, "wb") as f:
                f.write(b"esto no es un video valido" * 100)

            res_bad = compressor.compress_video(bad_in, bad_out, crf=26, hw="cpu", preset="fast")
            self.assertEqual(res_bad["status"], "error")
            self.assertFalse(os.path.exists(bad_out))
            self.assertFalse(os.path.exists(compressor._make_temp_output_path(bad_out)))

    def test_main_batch_with_nested_output_no_recompress_and_safe_delete(self):
        if not compressor.is_ffmpeg_installed():
            self.skipTest("FFmpeg no está instalado en este entorno.")

        with tempfile.TemporaryDirectory() as tmp:
            # Crear imagen válida, BMP válido, video válido y video corrupto
            img_ok = Path(tmp) / "foto.jpg"
            Image.new("RGB", (64, 64), (10, 20, 30)).save(img_ok, "JPEG")

            bmp_ok = Path(tmp) / "captura.bmp"
            Image.new("RGB", (64, 64), (40, 50, 60)).save(bmp_ok, "BMP")

            vid_ok = Path(tmp) / "video.mp4"
            _generate_test_video(vid_ok, duration=1)

            vid_bad = Path(tmp) / "roto.mp4"
            vid_bad.write_bytes(b"corrupto" * 50)

            # Carpeta de salida DENTRO de la carpeta de entrada (prueba anti-bucle)
            nested_out = Path(tmp) / "salida"

            compressor.main([
                "--input", tmp,
                "--output", str(nested_out),
                "--suffix", "_comprimido",
                "--hw", "cpu",
                "--preset", "fast",
                "--delete-original",
            ])

            # Los exitosos existen y sus originales se eliminaron
            self.assertTrue((nested_out / "foto_comprimido.jpg").exists())
            self.assertTrue((nested_out / "captura_comprimido.jpg").exists())
            self.assertTrue((nested_out / "video_comprimido.mp4").exists())
            self.assertTrue(_verify_video_playable(nested_out / "video_comprimido.mp4"))

            self.assertFalse(img_ok.exists())
            self.assertFalse(bmp_ok.exists())
            self.assertFalse(vid_ok.exists())

            # El video corrupto NO debe haberse borrado ni haber dejado salida corrupta
            self.assertTrue(vid_bad.exists())
            self.assertFalse((nested_out / "roto_comprimido.mp4").exists())

            # Segunda ejecución sobre la carpeta salida no debe re-comprimir *_comprimido.*
            compressor.main([
                "--input", str(nested_out),
                "--suffix", "_comprimido",
                "--hw", "cpu",
            ])
            self.assertFalse((nested_out / "foto_comprimido_comprimido.jpg").exists())


if __name__ == "__main__":
    unittest.main()
