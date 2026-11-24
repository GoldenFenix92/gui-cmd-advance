import unittest

from functions import sdelete_runner, setup_manager


class TestSDeleteRunner(unittest.TestCase):
    def test_plugin_registered_in_setup_manager(self):
        self.assertIn("sdelete", setup_manager.PLUGINS)
        plugin = setup_manager.PLUGINS["sdelete"]
        self.assertEqual(plugin["filename"], "sdelete64.exe")
        self.assertTrue(plugin["is_zip"])
        self.assertEqual(plugin["zip_target"], "sdelete64.exe")
        self.assertIn("__INTERNAL__ --run-sdelete", plugin["cmds"])

    def test_protected_paths_are_blocked(self):
        for bad in (
            "",
            "C:\\",
            "D:\\",
            "C:\\Windows",
            "C:\\Windows\\System32",
            "C:\\Program Files",
            "C:\\Users",
        ):
            self.assertTrue(sdelete_runner.is_protected_path(bad), f"Debio bloquear: {bad}")

        self.assertFalse(sdelete_runner.is_protected_path("C:\\Temp\\secreto.txt"))
        self.assertFalse(sdelete_runner.is_protected_path("D:\\Respaldos\\privado"))

    def test_build_sdelete_command_file_and_free_space_modes(self):
        cmd_file = sdelete_runner.build_sdelete_command(
            exe_path="C:\\GuiCmdAdvance\\tools\\sdelete64.exe",
            mode="file",
            target="D:\\Temp\\confidencial.pdf",
            passes=3,
            recursive=True,
            remove_readonly=True,
        )
        self.assertEqual(
            cmd_file,
            [
                "C:\\GuiCmdAdvance\\tools\\sdelete64.exe",
                "-accepteula",
                "-nobanner",
                "-p",
                "3",
                "-s",
                "-r",
                "D:\\Temp\\confidencial.pdf",
            ],
        )

        cmd_zero = sdelete_runner.build_sdelete_command(
            exe_path="C:\\GuiCmdAdvance\\tools\\sdelete64.exe",
            mode="free-zero",
            drive="E:",
            passes=1,
        )
        self.assertEqual(
            cmd_zero,
            ["C:\\GuiCmdAdvance\\tools\\sdelete64.exe", "-accepteula", "-nobanner", "-p", "1", "-z", "E:"],
        )

        cmd_clean = sdelete_runner.build_sdelete_command(
            exe_path="C:\\GuiCmdAdvance\\tools\\sdelete64.exe",
            mode="free-clean",
            drive="f",
            passes=7,
        )
        self.assertEqual(
            cmd_clean,
            ["C:\\GuiCmdAdvance\\tools\\sdelete64.exe", "-accepteula", "-nobanner", "-p", "7", "-c", "F:"],
        )

    def test_build_sdelete_command_rejects_protected_or_invalid(self):
        with self.assertRaises(ValueError):
            sdelete_runner.build_sdelete_command("sdelete64.exe", mode="file", target="C:\\Windows")
        with self.assertRaises(ValueError):
            sdelete_runner.build_sdelete_command("sdelete64.exe", mode="file", target="")
        with self.assertRaises(ValueError):
            sdelete_runner.build_sdelete_command("sdelete64.exe", mode="free-zero", drive="invalid")

    def test_extract_sdelete_percent(self):
        self.assertEqual(sdelete_runner.extract_sdelete_percent("Zeroing free space on E:\\: 47%"), 47)
        self.assertEqual(sdelete_runner.extract_sdelete_percent("100%"), 100)
        self.assertIsNone(sdelete_runner.extract_sdelete_percent("SDelete is set for 1 pass."))


if __name__ == "__main__":
    unittest.main()
