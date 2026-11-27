import os
import tempfile
import unittest
import zipfile

from functions import ffmpeg_skill_runner, setup_manager


class TestFfmpegSkillPlugin(unittest.TestCase):
    def test_plugins_registry_includes_ffmpeg_skill_and_ffprobe(self):
        self.assertIn("ffmpeg_skill", setup_manager.PLUGINS)
        skill_plugin = setup_manager.PLUGINS["ffmpeg_skill"]
        self.assertTrue(skill_plugin.get("is_zip_bundle"))
        self.assertEqual(skill_plugin.get("bundle_dir"), "ffmpeg-skill")
        self.assertIn("scripts/", skill_plugin.get("bundle_include", ()))

        ffmpeg_plugin = setup_manager.PLUGINS["ffmpeg"]
        self.assertIn("ffmpeg.exe", ffmpeg_plugin.get("zip_targets", []))
        self.assertIn("ffprobe.exe", ffmpeg_plugin.get("zip_targets", []))
        self.assertIn("__INTERNAL__ --run-media-studio", ffmpeg_plugin.get("cmds", []))

    def test_extract_plugin_zip_bundle_filters_files_and_blocks_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = os.path.join(tmp, "bundle.zip")
            tools_dir = os.path.join(tmp, "tools")

            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("ffmpeg-skill-main/SKILL.md", "# skill")
                zf.writestr("ffmpeg-skill-main/LICENSE", "MIT")
                zf.writestr("ffmpeg-skill-main/scripts/_contract.py", "print('ok')")
                zf.writestr("ffmpeg-skill-main/templates/tiktok.json", "{}")
                zf.writestr("ffmpeg-skill-main/references/flags.md", "# flags")
                # Deben excluirse por peso innecesario
                zf.writestr("ffmpeg-skill-main/demos/big.mp4", "0" * 1024)
                zf.writestr("ffmpeg-skill-main/site/index.html", "<html></html>")
                # Intento de path traversal debe bloquearse
                zf.writestr("ffmpeg-skill-main/scripts/../../evil.txt", "pwn")

            count = setup_manager.extract_plugin_zip(zip_path, setup_manager.PLUGINS["ffmpeg_skill"], tools_dir)
            self.assertEqual(count, 5)
            self.assertTrue(os.path.isfile(os.path.join(tools_dir, "ffmpeg-skill", "scripts", "_contract.py")))
            self.assertTrue(os.path.isfile(os.path.join(tools_dir, "ffmpeg-skill", "templates", "tiktok.json")))
            self.assertFalse(os.path.exists(os.path.join(tools_dir, "ffmpeg-skill", "demos")))
            self.assertFalse(os.path.exists(os.path.join(tools_dir, "ffmpeg-skill", "site")))
            self.assertFalse(os.path.exists(os.path.join(tools_dir, "evil.txt")))

    def test_extract_plugin_zip_multi_targets_extracts_ffmpeg_and_ffprobe(self):
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = os.path.join(tmp, "ffmpeg.zip")
            tools_dir = os.path.join(tmp, "tools")

            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("ffmpeg-master/bin/ffmpeg.exe", b"FFMPEG")
                zf.writestr("ffmpeg-master/bin/ffprobe.exe", b"FFPROBE")
                zf.writestr("ffmpeg-master/bin/ffplay.exe", b"FFPLAY")

            count = setup_manager.extract_plugin_zip(zip_path, setup_manager.PLUGINS["ffmpeg"], tools_dir)
            self.assertEqual(count, 2)
            self.assertTrue(os.path.isfile(os.path.join(tools_dir, "ffmpeg.exe")))
            self.assertTrue(os.path.isfile(os.path.join(tools_dir, "ffprobe.exe")))
            self.assertFalse(os.path.exists(os.path.join(tools_dir, "ffplay.exe")))

    def test_run_skill_script_executes_portable_via_runpy(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = os.path.join(tmp, "ffmpeg-skill")
            scripts_dir = os.path.join(skill_dir, "scripts")
            os.makedirs(scripts_dir)

            with open(os.path.join(scripts_dir, "_contract.py"), "w", encoding="utf-8") as f:
                f.write("import sys\nsys.exit(0)\n")

            marker = os.path.join(tmp, "ran.txt")
            with open(os.path.join(scripts_dir, "hello.py"), "w", encoding="utf-8") as f:
                f.write(
                    "import sys\n"
                    "with open(sys.argv[1], 'w', encoding='utf-8') as out:\n"
                    "    out.write(sys.argv[2])\n"
                )

            rc = ffmpeg_skill_runner.run_skill_script("hello", [marker, "ok-from-skill"], skill_dir=skill_dir)
            self.assertEqual(rc, 0)
            with open(marker, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), "ok-from-skill")

            # Bloqueo de traversal en nombre de script
            self.assertIsNone(ffmpeg_skill_runner.resolve_skill_script("../evil", skill_dir=skill_dir))


if __name__ == "__main__":
    unittest.main()
