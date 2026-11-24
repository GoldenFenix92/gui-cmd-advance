import json
import os
import unittest

from functions import combo_engine

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestComboEngine(unittest.TestCase):
    def test_get_command_combos_splits_before_and_after(self):
        sample = {
            "name": "Reparar Archivos de Sistema Windows (sfc)",
            "combos": [
                {
                    "command": "Reparar Imagen del Sistema Windows (DISM)",
                    "when": "before",
                    "reason": "Protocolo seguro",
                    "auto_command": "DISM /Online /Cleanup-Image /RestoreHealth",
                },
                {
                    "command": "Reparar Windows Update",
                    "when": "after",
                    "reason": "Limpiar caché WU",
                },
            ],
        }
        before, after = combo_engine.get_command_combos(sample)
        self.assertEqual(len(before), 1)
        self.assertEqual(before[0]["mode"], "auto")
        self.assertEqual(len(after), 1)
        self.assertEqual(after[0]["mode"], "navigate")

    def test_build_execution_queue_orders_before_main_after(self):
        before = [{"command": "DISM", "auto_command": "DISM /RestoreHealth"}]
        after = [{"command": "WU", "auto_command": ""}]
        q = combo_engine.build_execution_queue("SFC", "sfc /scannow", before, after)
        self.assertEqual([s["role"] for s in q], ["before", "main", "after"])
        self.assertEqual([s["mode"] for s in q], ["auto", "auto", "navigate"])
        self.assertEqual(q[0]["cmd_str"], "DISM /RestoreHealth")
        self.assertEqual(q[1]["cmd_str"], "sfc /scannow")

    def test_all_combos_in_commands_config_have_valid_targets(self):
        cfg_path = os.path.join(PROJECT_ROOT, "resources", "commands_config.json")
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        all_names = {
            c["name"]
            for cat in cfg["categories"]
            for c in cat["commands"]
        }

        combo_cmd_count = 0
        has_before = False
        has_after = False
        for cat in cfg["categories"]:
            for cmd in cat["commands"]:
                if "combos" not in cmd:
                    continue
                combo_cmd_count += 1
                before, after = combo_engine.get_command_combos(cmd)
                if before:
                    has_before = True
                if after:
                    has_after = True
                for item in before + after:
                    self.assertIn(item["command"], all_names, f"Combo roto en {cmd['name']}: {item['command']}")
                    self.assertNotEqual(item["command"], cmd["name"], f"Auto-referencia en {cmd['name']}")
                    self.assertTrue(item["reason"], f"Falta reason en combo de {cmd['name']}")

        self.assertGreaterEqual(combo_cmd_count, 25)
        self.assertTrue(has_before, "Debe existir al menos un combo Protocolo Seguro (before)")
        self.assertTrue(has_after, "Debe existir al menos un combo de Continuación (after)")

    def test_context_extraction_auto_execute_and_unified_warning(self):
        ctx_disk = combo_engine.extract_command_context("powershell -Command \"...\" -num 3 -style GPT")
        self.assertEqual(ctx_disk["disk"], "3")

        ctx_path = combo_engine.extract_command_context('icacls "D:\\Mis Documentos\\Proyecto" /grant Administrators:F')
        self.assertEqual(ctx_path["path"], "D:\\Mis Documentos\\Proyecto")

        step_tpl = {"command": "Tomar Posesión (takeown)", "auto_command": 'takeown /f "{path}" /r /d y'}
        # Con auto_execute=True resuelve {path} y corre automático
        q_auto = combo_engine.build_execution_queue(
            "Conceder Control Total (icacls)",
            'icacls "D:\\Mis Documentos\\Proyecto" /grant Administrators:F',
            selected_before=[step_tpl],
            auto_execute=True,
        )
        self.assertEqual(q_auto[0]["mode"], "auto")
        self.assertEqual(q_auto[0]["cmd_str"], 'takeown /f "D:\\Mis Documentos\\Proyecto" /r /d y')

        # Con auto_execute=False pasa a modo guiado (navigate)
        q_guided = combo_engine.build_execution_queue(
            "Conceder Control Total (icacls)",
            'icacls "D:\\Mis Documentos\\Proyecto" /grant Administrators:F',
            selected_before=[step_tpl],
            auto_execute=False,
        )
        self.assertEqual(q_guided[0]["mode"], "navigate")
        self.assertEqual(q_guided[0]["cmd_str"], "")

        # Advertencia unificada escala a danger si cualquier paso es danger
        cmds_map = {
            "Tomar Posesión (takeown)": {"warning": {"level": "caution"}},
            "Formatear": {"warning": {"level": "danger"}},
        }
        q_mix = [
            {"name": "Tomar Posesión (takeown)", "role": "before", "mode": "auto"},
            {"name": "Formatear", "role": "main", "mode": "auto"},
        ]
        uw = combo_engine.build_unified_warning(q_mix, cmds_map)
        self.assertIsNotNone(uw)
        self.assertEqual(uw["level"], "danger")
        self.assertIn("2 pasos", uw["title"])


if __name__ == "__main__":
    unittest.main()
