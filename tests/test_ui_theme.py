import os
import tempfile
import unittest
from unittest.mock import patch
import ttkbootstrap as tb
from functions import ui_theme


class TestUITheme(unittest.TestCase):
    def test_available_themes_and_dark_light_classification(self):
        themes = ui_theme.get_available_themes()
        self.assertEqual(len(themes), 30)
        self.assertIn("bootstrap-dark", themes)
        self.assertIn("tokyo-night-dark", themes)
        self.assertIn("bootstrap-light", themes)
        self.assertTrue(ui_theme.is_dark_theme("bootstrap-dark"))
        self.assertTrue(ui_theme.is_dark_theme("tokyo-night-dark"))
        self.assertFalse(ui_theme.is_dark_theme("bootstrap-light"))
        self.assertFalse(ui_theme.is_dark_theme("catppuccin-light"))

    def test_save_and_load_theme_persistence(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_path = os.path.join(tmp, "ui_settings.json")
            with patch.object(ui_theme, "_settings_path", return_value=fake_path):
                self.assertEqual(ui_theme.get_saved_theme(), ui_theme.DEFAULT_THEME)
                saved = ui_theme.set_saved_theme("tokyo-night-dark")
                self.assertEqual(saved, "tokyo-night-dark")
                self.assertEqual(ui_theme.get_saved_theme(), "tokyo-night-dark")
                # Tema inválido cae al default
                fallback = ui_theme.set_saved_theme("tema_inexistente")
                self.assertEqual(fallback, ui_theme.DEFAULT_THEME)

    def test_placeholder_entry_and_bootstrap_icons(self):
        win = tb.Window(themename="bootstrap-dark")
        win.withdraw()
        try:
            entry = ui_theme.PlaceholderEntry(win, placeholder="Buscar comando...")
            self.assertTrue(entry.is_placeholder_active())
            self.assertEqual(entry.get_value(), "")

            entry.set_value("ipconfig")
            self.assertFalse(entry.is_placeholder_active())
            self.assertEqual(entry.get_value(), "ipconfig")

            entry.set_value("")
            self.assertTrue(entry.is_placeholder_active())
            self.assertEqual(entry.get_value(), "")

            for icon_name in ("info", "help", "star", "star_filled", "trash", "eye", "eye_off", "play", "stop", "pause", "search", "copy", "refresh", "table", "ai"):
                icon = ui_theme.get_bootstrap_icon(icon_name, size=16, color="#FFFFFF", master=win)
                self.assertEqual(icon.width(), 16)
                self.assertEqual(icon.height(), 16)
        finally:
            win.destroy()


if __name__ == "__main__":
    unittest.main()
