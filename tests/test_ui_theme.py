import os
import tempfile
import unittest
from unittest.mock import patch
import ttkbootstrap as tb
from functions import ui_theme


class TestUITheme(unittest.TestCase):
    def test_pulse_defaults_and_dark_light_classification(self):
        self.assertEqual(ui_theme.DEFAULT_DARK_THEME, "pulse-dark")
        self.assertEqual(ui_theme.DEFAULT_LIGHT_THEME, "pulse-light")
        self.assertEqual(ui_theme.DEFAULT_THEME, "pulse-dark")
        themes = ui_theme.get_available_themes()
        self.assertEqual(len(themes), 30)
        self.assertIn("pulse-dark", themes)
        self.assertIn("pulse-light", themes)
        self.assertTrue(ui_theme.is_dark_theme("pulse-dark"))
        self.assertFalse(ui_theme.is_dark_theme("pulse-light"))

    def test_save_and_load_theme_persistence(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_path = os.path.join(tmp, "ui_settings.json")
            with patch.object(ui_theme, "_settings_path", return_value=fake_path):
                self.assertEqual(ui_theme.get_saved_theme(), "pulse-dark")
                ui_theme.set_saved_theme("pulse-light")
                self.assertEqual(ui_theme.get_saved_theme(), "pulse-light")
                ui_theme.set_saved_theme("tema_inexistente")
                self.assertEqual(ui_theme.get_saved_theme(), "pulse-dark")

    def test_rounded_components_toggle_and_icons(self):
        win = tb.Window(themename="pulse-dark")
        win.withdraw()
        try:
            ui_theme.apply_rounded_styles(win.style, "pulse-dark")
            card = ui_theme.RoundedCard(win, title="Prueba")
            self.assertIsNotNone(card.body)

            pb = ui_theme.RoundedProgressBar(card.body, maximum=100, value=45, theme_name="pulse-dark")
            pb.set_progress(value=80, bootstyle="success")
            pb.apply_palette("pulse-light")

            toggled = []
            sw = ui_theme.ThemeToggleSwitch(win, is_dark=True, command=lambda d: toggled.append(d))
            sw.set_dark(False, notify=True)
            self.assertEqual(toggled, [False])
            self.assertFalse(sw.is_dark())

            entry = ui_theme.PlaceholderEntry(win, placeholder="Buscar comando...")
            self.assertTrue(entry.is_placeholder_active())
            self.assertEqual(entry.get_value(), "")
            entry.set_value("ipconfig")
            self.assertEqual(entry.get_value(), "ipconfig")

            for icon_name in ("info", "help", "star", "star_filled", "trash", "eye", "eye_off", "play", "stop", "pause", "search", "copy", "refresh", "table", "ai"):
                icon = ui_theme.get_bootstrap_icon(icon_name, size=16, color="#FFFFFF", master=win)
                self.assertEqual(icon.width(), 16)
        finally:
            win.destroy()


if __name__ == "__main__":
    unittest.main()
