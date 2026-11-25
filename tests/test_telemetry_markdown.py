import unittest
import customtkinter as ctk
from functions import telemetry


SAMPLE_RELEASE_NOTES = """\
Resumen inicial del lanzamiento.

---

## Novedades Principales desde v1.0.39-beta

### Almacenamiento, Discos y Recuperación
- **Escáner de Superficie y Sectores (HDD / SSD / USB):** Acceso directo Win32 para clasificar bloques por latencia (`<50 ms` Excelente, `<200 ms` Normal, `<1000 ms` Lento, `>1000 ms` Crítico y sectores dañados). Incluye *Muestreo Rápido*, *Escaneo Completo* (0 escritura) y *Reasignación de Sectores Pendientes (Remap)* con bloqueo automático en discos del sistema y SSD/NVMe.
  - Subpunto con `ai_settings.json` y enlace [Ver guía](https://github.com/GoldenFenix92/gui-cmd-advance).
1. Primer paso ordenado
2. Segundo paso con ~~texto tachado~~

> Nota importante de soporte técnico.

```powershell
Get-Disk | Format-Table -AutoSize
```
"""


class TestTelemetryMarkdown(unittest.TestCase):
    def test_parse_inline_markdown_tokens_and_edge_cases(self):
        tokens = telemetry.parse_inline_markdown(
            "**Negrita**, *cursiva*, ***ambos***, `codigo_x`, ~~tachado~~ y [Repo](https://example.com)"
        )
        types = [t[0] for t in tokens]
        self.assertIn("bold", types)
        self.assertIn("italic", types)
        self.assertIn("bold_italic", types)
        self.assertIn("code", types)
        self.assertIn("strike", types)
        self.assertIn("link", types)

        # Snake_case and math expressions must not trigger italic
        safe_tokens = telemetry.parse_inline_markdown("archivo ai_settings_json y 2 * 3 * 4")
        self.assertEqual(safe_tokens, [("text", "archivo ai_settings_json y 2 * 3 * 4", None)])

    def test_parse_markdown_blocks_structures(self):
        blocks = telemetry.parse_markdown_blocks(SAMPLE_RELEASE_NOTES.replace("\n", "\r\n"))
        block_types = [b[0] for b in blocks]
        self.assertIn("hr", block_types)
        self.assertIn("h2", block_types)
        self.assertIn("h3", block_types)
        self.assertIn("bullet", block_types)
        self.assertIn("ordered", block_types)
        self.assertIn("quote", block_types)
        self.assertIn("code_block", block_types)

        # Empty notes fallback
        empty_blocks = telemetry.parse_markdown_blocks("   \r\n  ")
        self.assertEqual(empty_blocks, [("paragraph", "No se incluyeron notas de la versión.")])

    def test_render_markdown_to_textbox_strips_raw_syntax_and_applies_tags(self):
        root = ctk.CTk()
        root.withdraw()
        try:
            tb = ctk.CTkTextbox(root, wrap="word")
            telemetry.render_markdown_to_textbox(tb, SAMPLE_RELEASE_NOTES, appearance_mode="Dark")

            tk_text = tb._textbox
            rendered = tk_text.get("1.0", "end-1c")
            self.assertNotIn("## ", rendered)
            self.assertNotIn("### ", rendered)
            self.assertNotIn("**", rendered)
            self.assertNotIn("`", rendered)
            self.assertNotIn("```", rendered)
            self.assertIn("Novedades Principales desde v1.0.39-beta", rendered)
            self.assertIn("• Escáner de Superficie y Sectores", rendered)
            self.assertIn("◦ Subpunto con", rendered)
            self.assertIn("Ver guía", rendered)

            # Verify tags were actually applied
            self.assertTrue(tk_text.tag_ranges("h2"))
            self.assertTrue(tk_text.tag_ranges("h3"))
            self.assertTrue(tk_text.tag_ranges("bold"))
            self.assertTrue(tk_text.tag_ranges("italic"))
            self.assertTrue(tk_text.tag_ranges("inline_code"))
            self.assertTrue(tk_text.tag_ranges("bullet_mark"))
            self.assertTrue(tk_text.tag_ranges("hr"))
            self.assertTrue(tk_text.tag_ranges("code_block"))
            self.assertTrue(tk_text.tag_ranges("md_link_1"))
            self.assertEqual(str(tk_text.cget("state")), "disabled")

            # Also verify Light mode palette renders without error
            telemetry.render_markdown_to_textbox(tb, SAMPLE_RELEASE_NOTES, appearance_mode="Light")
            self.assertTrue(tk_text.tag_ranges("h2"))
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
