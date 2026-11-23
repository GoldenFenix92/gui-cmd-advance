import glob
import importlib
import json
import os
import re
import tempfile
import unittest

from PIL import Image

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestProjectIntegrity(unittest.TestCase):
    def test_all_function_modules_import_cleanly(self):
        func_files = sorted(glob.glob(os.path.join(PROJECT_ROOT, "functions", "*.py")))
        self.assertGreater(len(func_files), 10)
        for path in func_files:
            mod_name = os.path.splitext(os.path.basename(path))[0]
            if mod_name == "__init__":
                continue
            mod = importlib.import_module(f"functions.{mod_name}")
            self.assertIsNotNone(mod)

    def test_commands_config_internal_flags_exist_in_main(self):
        cfg_path = os.path.join(PROJECT_ROOT, "resources", "commands_config.json")
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        main_path = os.path.join(PROJECT_ROOT, "main.py")
        with open(main_path, "r", encoding="utf-8") as f:
            main_src = f.read()

        main_flags = set(re.findall(r'"(--run-[a-z0-9-]+)"', main_src))
        for cat in cfg["categories"]:
            for cmd in cat["commands"]:
                if "__INTERNAL__" in cmd["command"]:
                    m = re.search(r"(--run-[a-z0-9-]+)", cmd["command"])
                    self.assertIsNotNone(m, f"Comando __INTERNAL__ sin flag: {cmd['command']}")
                    self.assertIn(m.group(1), main_flags, f"Flag faltante en main.py: {m.group(1)}")

    def test_build_exe_covers_all_function_modules_and_valid_paths(self):
        build_mod = importlib.import_module("scripts.build_exe")
        func_mods = {
            f"functions.{os.path.splitext(os.path.basename(p))[0]}"
            for p in glob.glob(os.path.join(PROJECT_ROOT, "functions", "*.py"))
            if not p.endswith("__init__.py")
        }
        hidden_set = set(build_mod.HIDDEN_IMPORTS)
        missing = sorted(func_mods - hidden_set)
        self.assertEqual(missing, [], f"Módulos faltantes en scripts/build_exe.py HIDDEN_IMPORTS: {missing}")

        cmd = build_mod.build_pyinstaller_command("TestApp", "version_info.txt")
        self.assertIn("main.py", cmd)
        self.assertTrue(os.path.exists(os.path.join(PROJECT_ROOT, "main.py")))
        self.assertTrue(os.path.exists(os.path.join(PROJECT_ROOT, "resources", "app_icon.ico")))
        self.assertTrue(os.path.exists(os.path.join(PROJECT_ROOT, "resources", "commands_config.json")))

    def test_media_repair_image_works(self):
        from functions import media_repair

        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "sample.jpg")
            im = Image.new("RGB", (40, 20), (255, 0, 0))
            ex = im.getexif()
            ex[274] = 6  # Rotado 90° CW
            im.save(src, "JPEG", exif=ex.tobytes())
            out = media_repair.get_output_path(src, tmp, suffix="_reparado")
            ok = media_repair.repair_image(src, out)
            self.assertTrue(ok)
            self.assertTrue(os.path.exists(out))
            with Image.open(out) as check:
                self.assertEqual(check.size, (20, 40))

    def test_credentials_vault_cli_parses_english_and_spanish(self):
        from functions import credentials_vault_cli

        en_sample = """
        Currently stored credentials:

            Target: LegacyGeneric:target=git:https://github.com
            Type: Generic
            User: GoldenFenix92
        """
        es_sample = """
        Credenciales almacenadas actualmente:

            Destino: MicrosoftAccount:user=test@outlook.com
            Tipo: Genérico
            Nombre de usuario: test@outlook.com
        """
        en_creds = credentials_vault_cli.parse_cmdkey_output(en_sample)
        es_creds = credentials_vault_cli.parse_cmdkey_output(es_sample)
        self.assertEqual(len(en_creds), 1)
        self.assertEqual(en_creds[0]["usuario"], "GoldenFenix92")
        self.assertEqual(len(es_creds), 1)
        self.assertEqual(es_creds[0]["usuario"], "test@outlook.com")

    def test_office_deploy_channels_match_version(self):
        from functions import office_deploy

        xml_2024 = office_deploy.build_office_xml("ProPlus2024Volume", "64", "es-mx", True, True)
        xml_2021 = office_deploy.build_office_xml("ProPlus2021Volume", "64", "es-es")
        xml_2019 = office_deploy.build_office_xml("ProPlus2019Volume", "32", "en-us")

        self.assertIn('Channel="PerpetualVL2024"', xml_2024)
        self.assertIn('Product ID="VisioPro2024Volume"', xml_2024)
        self.assertIn('Product ID="ProjectPro2024Volume"', xml_2024)
        self.assertIn('Channel="PerpetualVL2021"', xml_2021)
        self.assertIn('Channel="PerpetualVL2019"', xml_2019)

    def test_task_memory_batched_persistence(self):
        from functions.task_memory import TaskMemory

        mem = TaskMemory("unit_test_task", "ctx_123", batch_size=3)
        mem.clear()
        try:
            mem.mark_processed("a")
            mem.mark_processed("b")
            self.assertTrue(mem.is_processed("a"))
            self.assertEqual(mem.get_processed_count(), 2)
            mem.flush()
            self.assertTrue(os.path.exists(mem.memory_file))

            mem2 = TaskMemory("unit_test_task", "ctx_123", batch_size=3)
            self.assertTrue(mem2.is_processed("a"))
            self.assertTrue(mem2.is_processed("b"))
        finally:
            mem.clear()

    def test_telemetry_has_no_hardcoded_discord_webhook(self):
        tel_path = os.path.join(PROJECT_ROOT, "functions", "telemetry.py")
        with open(tel_path, "r", encoding="utf-8") as f:
            src = f.read()
        self.assertNotIn("https://discord.com/api/webhooks/", src)

    def test_safe_print_and_windowed_stdout_none(self):
        import sys
        from unittest.mock import patch
        from functions import utils, disk_attributes, duplicate_finder, health_analyzer, name_sanitizer

        with patch.object(sys, "stdout", None):
            utils.safe_print("hola \U0001f451")
            disk_attributes.safe_print("hola \U0001f451")
            duplicate_finder.safe_print("hola \U0001f451")
            self.assertEqual(health_analyzer.safe_str("test"), "test")
            self.assertEqual(name_sanitizer.safe_str("test"), "test")

    def test_cmd_executor_resolve_internal_frozen_and_dev(self):
        import sys
        from unittest.mock import patch
        from functions.cmd_executor import resolve_internal_command

        with patch.object(sys, "frozen", True, create=True), patch.object(sys, "executable", r"C:\App\Gui.exe"):
            resolved = resolve_internal_command("__INTERNAL__ --run-vault")
            self.assertEqual(resolved, r'"C:\App\Gui.exe" --run-vault')

        with patch.object(sys, "frozen", False, create=True), patch.object(sys, "executable", r"C:\Py\python.exe"), patch.object(sys, "argv", [r"C:\Proj\main.py"]):
            resolved = resolve_internal_command("__INTERNAL__ --run-vault")
            self.assertEqual(resolved, r'"C:\Py\python.exe" "C:\Proj\main.py" --run-vault')

    def test_no_unprotected_stdout_flush_or_encoding_in_functions(self):
        func_files = sorted(glob.glob(os.path.join(PROJECT_ROOT, "functions", "*.py")))
        for path in func_files:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                src = f.read()
            self.assertNotIn("sys.stdout.flush()", src, f"Uso sin protección de sys.stdout.flush() en {path}")
            self.assertNotIn("sys.stdout.encoding", src, f"Uso sin protección de sys.stdout.encoding en {path}")

    def test_progress_parser_and_storage_job_parser(self):
        from gui_app import App

        self.assertEqual(App.extract_progress_from_text("Progreso Total: 45%"), 45.0)
        self.assertAlmostEqual(App.extract_progress_from_text("[==== 12.5% ====]"), 12.5)
        self.assertAlmostEqual(App.extract_progress_from_text("Analizando [25/100]: video.mp4"), 25.0)
        self.assertIsNone(App.extract_progress_from_text("Espacio Ahorrado: 10 MB (39.3%)"))
        self.assertIsNone(App.extract_progress_from_text("Incremento de Peso: +6.88 KB (+47.5%)"))

        job_json = '{"Name":"Format Volume","JobState":"Running","PercentComplete":18}'
        self.assertEqual(App.parse_storage_job_json(job_json), ("Format Volume", 18.0))
        self.assertIsNone(App.parse_storage_job_json('{"Name":"Format Volume","JobState":"Completed","PercentComplete":100}'))


if __name__ == "__main__":
    unittest.main()
