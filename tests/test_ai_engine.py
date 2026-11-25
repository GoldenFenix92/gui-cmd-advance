import json
import unittest
from unittest.mock import patch

from functions import ai_engine


class TestAIEngine(unittest.TestCase):
    def test_dpapi_roundtrip_and_plaintext_compatibility(self):
        secret = "sk-test-secret-key-12345"
        protected = ai_engine.dpapi_protect(secret)
        self.assertTrue(protected.startswith(ai_engine.DPAPI_PREFIX))
        self.assertNotIn(secret, protected)
        self.assertEqual(ai_engine.dpapi_unprotect(protected), secret)
        # Retrocompatibilidad con texto plano
        self.assertEqual(ai_engine.dpapi_unprotect("plain-key-999"), "plain-key-999")

    def test_encrypted_vault_export_and_import_roundtrip(self):
        sample = {
            "current_provider": "Ollama (Local)",
            "free_only": True,
            "providers": {
                "Google Gemini": {"api_key": "AIzaSyExampleKey123", "model": "gemini-2.0-flash", "cached_models": []},
                "Ollama (Local)": {"api_key": "", "model": "llama3.2", "base_url": "http://localhost:11434/v1/chat/completions", "cached_models": ["llama3.2"]},
            },
            "model_train": [{"provider": "Ollama (Local)", "model": "llama3.2"}],
        }
        blob = ai_engine.export_encrypted_vault(sample, "MiClaveMaestra2026")
        self.assertNotIn("AIzaSyExampleKey123", blob)
        self.assertNotIn("llama3.2", blob)

        restored = ai_engine.import_encrypted_vault(blob, "MiClaveMaestra2026")
        self.assertEqual(restored["providers"]["Google Gemini"]["api_key"], "AIzaSyExampleKey123")
        self.assertEqual(restored["current_provider"], "Ollama (Local)")

        with self.assertRaises(ValueError):
            ai_engine.import_encrypted_vault(blob, "ClaveIncorrecta")

    def test_local_providers_do_not_require_api_key(self):
        self.assertFalse(ai_engine.provider_requires_api_key("Ollama (Local)"))
        self.assertFalse(ai_engine.provider_requires_api_key("LM Studio (Local)"))
        self.assertFalse(ai_engine.provider_requires_api_key("Personalizado", "http://localhost:8080/v1/chat/completions"))
        self.assertFalse(ai_engine.provider_requires_api_key("Personalizado", "http://127.0.0.1:11434/v1/chat/completions"))
        self.assertTrue(ai_engine.provider_requires_api_key("Google Gemini"))
        self.assertTrue(ai_engine.provider_requires_api_key("Personalizado", "https://api.example.com/v1/chat/completions"))

    def test_smart_truncate_log_preserves_head_errors_and_tail(self):
        lines = ["HEADER LINE 1"] + [f"info ok line {i}" for i in range(600)] + ["[ERROR] Disk 3 bad sector LBA 12345"] + [f"tail line {i}" for i in range(70)]
        raw = "\n".join(lines)
        truncated = ai_engine.smart_truncate_log(raw, max_chars=4000)
        self.assertLessEqual(len(truncated), 4000)
        self.assertIn("HEADER LINE 1", truncated)
        self.assertIn("[ERROR] Disk 3 bad sector LBA 12345", truncated)
        self.assertIn("tail line 69", truncated)

    def test_run_model_train_fallbacks_to_next_and_supports_local_without_key(self):
        settings = {
            "current_provider": "Google Gemini",
            "providers": {
                "Google Gemini": {"api_key": "fake-key", "model": "gemini-2.0-flash"},
                "Ollama (Local)": {"api_key": "", "model": "llama3.2", "base_url": "http://localhost:11434/v1/chat/completions"},
            },
            "model_train": [
                {"provider": "Google Gemini", "model": "gemini-2.0-flash"},
                {"provider": "Ollama (Local)", "model": "llama3.2"},
            ],
        }

        def fake_call(provider, model, api_key, prompt, base_url="", timeout=25, max_tokens=2048):
            if provider == "Google Gemini":
                raise TimeoutError("timed out")
            return "Diagnostico completado en local."

        with patch.object(ai_engine, "call_provider", side_effect=fake_call):
            res = ai_engine.run_model_train(settings, "Test prompt", use_train=True)
            self.assertTrue(res["ok"])
            self.assertEqual(res["provider"], "Ollama (Local)")
            self.assertEqual(res["model"], "llama3.2")
            self.assertEqual(len(res["errors"]), 1)

    def test_analyze_offline_covers_multiple_domains(self):
        ping_res = ai_engine.analyze_offline("Haciendo ping a 8.8.8.8 TTL=117 perdidos = 0 media = 18ms")
        self.assertIn("0 paquetes perdidos", ping_res)

        surf_res = ai_engine.analyze_offline("ESCANER DE SUPERFICIE\nDanados (Error I/O) : 3")
        self.assertIn("3 bloques dañados", surf_res)

        usb_res = ai_engine.analyze_offline("AUDITOR DE AUTENTICIDAD\nVEREDICTO: FALSIFICADA")
        self.assertIn("falsificada", usb_res.lower())


if __name__ == "__main__":
    unittest.main()
