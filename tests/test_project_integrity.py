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

    def test_report_generator_profiles_and_html_output(self):
        from functions import report_generator

        self.assertEqual(report_generator.detect_report_profile("Multimedia", "Compresor de Multimedia", "--run-compressor"), "multimedia")
        self.assertEqual(report_generator.detect_report_profile("Almacenamiento", "Gestor de Atributos", "--run-disk-attributes"), "storage")
        self.assertEqual(report_generator.detect_report_profile("Redes", "ping", "ping 8.8.8.8"), "network")
        self.assertEqual(report_generator.detect_report_profile("Seguridad y Privacidad", "Credenciales", "--run-vault"), "security")
        self.assertEqual(report_generator.detect_report_profile("Sistema", "sfc", "sfc /scannow"), "system")

        sample_media = (
            "Tiempo total: 5 minutos y 10 segundos.\n"
            "Imágenes        | 100             | 2               | 102\n"
            "Videos          | 10              | 1               | 11\n"
            "Peso Original : 10.0 GB\n"
            "Peso Final    : 2.0 GB\n"
            "Espacio Ahorrado: 8.0 GB (80.0%)\n"
            "[ ARCHIVOS CON ERRORES (ORIGINALES CONSERVADOS INTACTOS) ]\n"
            "bad.mp4 | Invalid data </script><script>alert(1)</script>\n"
        )
        out_html = report_generator.generate_html_report(
            sample_media,
            title="Compresor de Multimedia",
            command="--run-compressor",
            category="Multimedia",
        )
        self.assertIn('data-profile="multimedia"', out_html)
        self.assertIn("80.0% ahorrado", out_html)
        self.assertIn("bad.mp4", out_html)
        self.assertNotIn("</script><script>alert(1)", out_html)

        # Verificar que convert_old_report fue eliminado de gui_app.py
        with open(os.path.join(PROJECT_ROOT, "gui_app.py"), "r", encoding="utf-8") as f:
            gui_src = f.read()
        self.assertNotIn("def convert_old_report", gui_src)
        self.assertNotIn("Convertir Reporte Antiguo", gui_src)

    def test_disk_formatting_commands_syntax_and_safety(self):
        import subprocess

        cfg_path = os.path.join(PROJECT_ROOT, "resources", "commands_config.json")
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        target_names = {
            "Initialize-Disk",
            "New-Partition & Format",
            "Clear-Disk (Formateo Completo)",
            "Formatear Disco (Avanzado estilo Rufus)",
        }
        found = {}
        for cat in cfg["categories"]:
            for cmd in cat["commands"]:
                if cmd["name"] in target_names:
                    found[cmd["name"]] = cmd["command"]

        self.assertEqual(set(found.keys()), target_names)

        for name, cmd_str in found.items():
            self.assertIn("IsSystem", cmd_str, f"{name} debe proteger discos de sistema")
            self.assertIn("IsBoot", cmd_str, f"{name} debe proteger discos de arranque")
            self.assertIn("exit 1", cmd_str, f"{name} debe retornar exit 1 en errores")
            self.assertIn("Update-Disk", cmd_str, f"{name} debe refrescar estado del disco")

            m = re.search(r'powershell -Command "(.*)"$', cmd_str)
            self.assertIsNotNone(m, f"Formato de comando PowerShell inesperado en {name}")
            ps_script = m.group(1)

            # Validar sintaxis PowerShell usando el AST parser oficial (sin ejecutar nada)
            check_ps = (
                "$errs = $null; "
                "$code = [Console]::In.ReadToEnd(); "
                "[void][System.Management.Automation.Language.Parser]::ParseInput($code, [ref]$null, [ref]$errs); "
                "if ($errs.Count -gt 0) { $errs | ForEach-Object { Write-Error $_.Message }; exit 1 }"
            )
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-Command", check_ps],
                input=ps_script,
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertEqual(proc.returncode, 0, f"Error de sintaxis PowerShell en {name}: {proc.stderr}")

        rufus_cmd = found["Formatear Disco (Avanzado estilo Rufus)"]
        self.assertIn("PartitionStyle -eq 'RAW'", rufus_cmd)
        self.assertIn("Set-Disk -Number $num -PartitionStyle $style", rufus_cmd)
        self.assertIn("diskpart", rufus_cmd)
        self.assertIn("FAT32", rufus_cmd)

    def test_categories_no_duplicates_profiles_and_all_powershell_syntax(self):
        import subprocess
        from functions import report_generator

        cfg_path = os.path.join(PROJECT_ROOT, "resources", "commands_config.json")
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        expected_profiles = {
            "Redes y Conectividad": "network",
            "Sistema y Procesos": "system",
            "Reparación y Mantenimiento": "system",
            "Seguridad y Permisos": "security",
            "Archivos y Compresión": "system",
            "Almacenamiento: Formateo y Gestión": "storage",
            "Almacenamiento: Diagnóstico y Salud": "storage",
            "Recuperación de Datos": "storage",
            "Multimedia": "multimedia",
            "Instaladores Oficiales (Microsoft)": "system",
        }
        cat_names = [cat["name"] for cat in cfg["categories"]]
        self.assertEqual(cat_names, list(expected_profiles.keys()))

        seen_names = set()
        ps_scripts = []
        for cat in cfg["categories"]:
            cname = cat["name"]
            self.assertEqual(
                report_generator.detect_report_profile(category=cname),
                expected_profiles[cname],
                f"Perfil de reporte incorrecto para categoría {cname}",
            )
            self.assertGreater(len(cat["commands"]), 0, f"Categoría vacía: {cname}")
            for cmd in cat["commands"]:
                name = cmd["name"]
                self.assertNotIn(name, seen_names, f"Comando duplicado: {name}")
                seen_names.add(name)
                m = re.search(r'powershell -Command "(.*)"$', cmd["command"])
                if m:
                    # En JSON/cmd.exe, \" dentro de -Command "..." representa " en PowerShell
                    ps_scripts.append((name, m.group(1).replace('\\"', '"')))

        # Validar sintaxis AST de TODOS los comandos PowerShell en un solo proceso
        payload = json.dumps(ps_scripts)
        check_all_ps = (
            "$items = [Console]::In.ReadToEnd() | ConvertFrom-Json; "
            "$failed = @(); "
            "foreach ($it in $items) { "
            "  $errs = $null; "
            "  [void][System.Management.Automation.Language.Parser]::ParseInput([string]$it[1], [ref]$null, [ref]$errs); "
            "  if ($errs.Count -gt 0) { $failed += ($it[0] + ': ' + (($errs | ForEach-Object { $_.Message }) -join '; ')) } "
            "}; "
            "if ($failed.Count -gt 0) { $failed | ForEach-Object { Write-Error $_ }; exit 1 }"
        )
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", check_all_ps],
            input=payload,
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(proc.returncode, 0, f"Errores de sintaxis PowerShell:\n{proc.stderr}")

    def test_warnings_shutdown_presets_and_power_manager(self):
        from unittest.mock import patch, MagicMock
        from functions import power_manager
        from gui_app import App

        # 1. power_manager usa ES_CONTINUOUS | ES_SYSTEM_REQUIRED (sin ES_DISPLAY_REQUIRED por defecto)
        mock_kernel32 = MagicMock()
        mock_kernel32.SetThreadExecutionState.return_value = 1
        with patch.object(power_manager.ctypes, "windll", create=True) as mock_windll:
            mock_windll.kernel32 = mock_kernel32
            self.assertTrue(power_manager.prevent_sleep(keep_display=False))
            mock_kernel32.SetThreadExecutionState.assert_called_with(
                power_manager.ES_CONTINUOUS | power_manager.ES_SYSTEM_REQUIRED
            )
            self.assertTrue(power_manager.allow_sleep())
            mock_kernel32.SetThreadExecutionState.assert_called_with(power_manager.ES_CONTINUOUS)

        desktop = power_manager.get_desktop_path()
        self.assertTrue(isinstance(desktop, str) and len(desktop) > 0)

        # 2. Validar advertencias en commands_config.json y skip_if_flag_in
        cfg_path = os.path.join(PROJECT_ROOT, "resources", "commands_config.json")
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        all_cmds = {
            cmd["name"]: cmd
            for cat in cfg["categories"]
            for cmd in cat["commands"]
        }
        warned = {n: c["warning"] for n, c in all_cmds.items() if "warning" in c}
        self.assertGreaterEqual(len(warned), 30)

        for name, w in warned.items():
            self.assertIn(w.get("level"), ("danger", "caution"), f"Nivel inválido en {name}")
            self.assertTrue(w.get("title"), f"Título vacío en {name}")
            self.assertTrue(w.get("message"), f"Mensaje vacío en {name}")

        # Comandos críticos obligatorios con warning danger
        for critical in (
            "Formatear Disco (Avanzado estilo Rufus)",
            "Clear-Disk (Formateo Completo)",
            "Limpieza Selectiva de Temporales",
            "Administrador de Apagado Programado",
        ):
            self.assertEqual(warned[critical]["level"], "danger")

        # Comandos de solo consulta sin warning
        for readonly in ("ipconfig", "Get-Disk", "systeminfo", "Estado de Salud SMART Avanzado"):
            self.assertNotIn(readonly, warned)

        # skip_if_flag_in funciona en modos de solo lectura
        attr_cmd = all_cmds["Gestor de Atributos de Discos (HDD/SSD/USB)"]
        self.assertIsNone(App.get_active_warning(attr_cmd, "__INTERNAL__ --run-disk-attributes --disk 1 --action inspect"))
        self.assertIsNotNone(App.get_active_warning(attr_cmd, "__INTERNAL__ --run-disk-attributes --disk 1 --action clear"))

        usb_cmd = all_cmds["Auditor de Autenticidad de Unidades (USB / SSD / HDD)"]
        self.assertIsNone(App.get_active_warning(usb_cmd, "__INTERNAL__ --run-usb-audit --disk 1 --mode hardware"))
        self.assertIsNotNone(App.get_active_warning(usb_cmd, "__INTERNAL__ --run-usb-audit --disk 1 --mode quick"))

        # 3. Administrador de Apagado Programado tiene dropdown con presets hasta 10 horas (36000s)
        sd_cmd = all_cmds["Administrador de Apagado Programado"]
        time_arg = next((a for a in sd_cmd["args"] if a.get("flag") == "/t"), None)
        self.assertIsNotNone(time_arg)
        self.assertEqual(time_arg["type"], "dropdown")
        values = [opt["value"] for opt in time_arg["options"]]
        self.assertIn("0", values)
        self.assertIn("3600", values)
        self.assertIn("36000", values)


if __name__ == "__main__":
    unittest.main()
