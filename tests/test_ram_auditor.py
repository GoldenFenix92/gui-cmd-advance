import json
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from functions import ram_auditor


class TestRamAuditor(unittest.TestCase):
    def test_memory_snapshot_and_process_grouping(self):
        snap = ram_auditor.get_memory_snapshot()
        self.assertGreater(snap["total_bytes"], 0)
        self.assertGreaterEqual(snap["percent"], 0.0)
        self.assertLessEqual(snap["percent"], 100.0)

        fake_procs = [
            SimpleNamespace(info={"pid": 101, "name": "chrome.exe", "memory_info": SimpleNamespace(rss=200 * 1024**2, private=180 * 1024**2)}),
            SimpleNamespace(info={"pid": 102, "name": "Chrome.exe", "memory_info": SimpleNamespace(rss=300 * 1024**2, private=260 * 1024**2)}),
            SimpleNamespace(info={"pid": 4, "name": "System", "memory_info": SimpleNamespace(rss=50 * 1024**2, private=10 * 1024**2)}),
        ]
        with patch("functions.ram_auditor.psutil.process_iter", return_value=fake_procs):
            audit = ram_auditor.get_process_memory_audit(limit=10)

        self.assertEqual(audit["total_processes"], 3)
        self.assertEqual(audit["grouped"][0]["name"].lower(), "chrome.exe")
        self.assertEqual(audit["grouped"][0]["instances"], 2)
        self.assertAlmostEqual(audit["grouped"][0]["rss_mb"], 500.0, places=1)
        self.assertEqual(audit["grouped"][0]["category"], "Navegador")

    def test_evaluate_ram_health_detects_warnings(self):
        snap = {
            "total_bytes": 16 * 1024**3,
            "used_bytes": 14 * 1024**3,
            "available_bytes": 2 * 1024**3,
            "percent": 88.5,
            "commit_percent": 90.0,
            "kernel_nonpaged_bytes": 2 * 1024**3,
        }
        hw = {
            "total_slots": 2,
            "used_slots": 1,
            "max_capacity_gb": 64.0,
            "modules": [
                {"slot": "DIMM_A1", "speed_mhz": 3200, "configured_mhz": 2400, "capacity_gb": 16.0}
            ],
        }
        pa = {
            "grouped": [
                {"name": "chrome.exe", "rss_mb": 4200.0, "percent": 25.6, "instances": 18}
            ]
        }
        health = ram_auditor.evaluate_ram_health(snap, hw, pa)
        self.assertEqual(health["status"], "CRÍTICO")
        self.assertLess(health["score"], 55)
        titles = " ".join(f["title"] for f in health["findings"])
        self.assertIn("Presión crítica", titles)
        self.assertIn("Commit", titles)
        self.assertIn("Non-Paged Pool", titles)
        self.assertIn("Single-Channel", titles)

    def test_protected_kernel_processes_are_never_trimmed(self):
        my_pid = os.getpid()
        fake_procs = [
            SimpleNamespace(info={"pid": 4, "name": "System"}),
            SimpleNamespace(info={"pid": 500, "name": "csrss.exe"}),
            SimpleNamespace(info={"pid": 600, "name": "lsass.exe"}),
            SimpleNamespace(info={"pid": my_pid, "name": "python.exe"}),
            SimpleNamespace(info={"pid": 9999, "name": "notepad.exe"}),
        ]
        mock_k32 = MagicMock()
        mock_k32.OpenProcess.return_value = 12345
        mock_psapi = MagicMock()
        mock_psapi.EmptyWorkingSet.return_value = True

        def fake_windll(name, use_last_error=True):
            return mock_k32 if name == "kernel32" else mock_psapi

        with patch("functions.ram_auditor.psutil.process_iter", return_value=fake_procs), \
             patch("functions.ram_auditor.ctypes.WinDLL", side_effect=fake_windll):
            stats = ram_auditor.trim_process_working_sets()

        self.assertEqual(stats["trimmed"], 1)
        self.assertEqual(stats["trimmed_pids"], [9999])
        self.assertEqual(stats["skipped"], 4)

    def test_optimize_ram_safe_and_deep_modes_report_delta_and_export_html(self):
        before = {
            "timestamp": "2026-11-26 20:55:00",
            "total_bytes": 16 * 1024**3,
            "used_bytes": 10 * 1024**3,
            "available_bytes": 6 * 1024**3,
            "percent": 62.5,
            "system_cache_bytes": 3 * 1024**3,
            "commit_total_bytes": 11 * 1024**3,
            "commit_limit_bytes": 24 * 1024**3,
            "commit_percent": 45.8,
            "kernel_nonpaged_bytes": 400 * 1024**2,
        }
        after = dict(before)
        after["used_bytes"] = 9 * 1024**3
        after["available_bytes"] = 7 * 1024**3
        after["percent"] = 56.2
        after["system_cache_bytes"] = 2 * 1024**3

        with tempfile.TemporaryDirectory() as tmp:
            hist_file = os.path.join(tmp, "hist.json")
            with patch("functions.ram_auditor.get_memory_snapshot", side_effect=[before, after]), \
                 patch("functions.ram_auditor.enable_memory_privileges", return_value={"SeProfileSingleProcessPrivilege": True}), \
                 patch("functions.ram_auditor.trim_process_working_sets", return_value={"trimmed": 12, "skipped": 8, "failed": 0, "trimmed_pids": []}), \
                 patch("functions.ram_auditor.purge_standby_list", return_value={"ok": True, "commands_ok": ["PurgeStandbyList"], "commands_failed": []}), \
                 patch("functions.ram_auditor.flush_system_file_cache", return_value=True), \
                 patch("functions.ram_auditor.time.sleep"):
                res = ram_auditor.optimize_ram(mode="deep", history_path=hist_file)

            self.assertAlmostEqual(res["freed_mb"], 1024.0, places=1)
            self.assertEqual(res["processes_trimmed"], 12)
            self.assertTrue(os.path.exists(hist_file))
            with open(hist_file, "r", encoding="utf-8") as f:
                saved_hist = json.load(f)
            self.assertEqual(len(saved_hist), 1)

            html_path = os.path.join(tmp, "reporte.html")
            out = ram_auditor.export_ram_audit_html(
                after,
                {"total_slots": 2, "used_slots": 2, "max_capacity_gb": 64.0, "modules": []},
                {"grouped": []},
                {"status": "ÓPTIMO", "score": 95, "findings": []},
                last_opt=res,
                output_path=html_path,
            )
            self.assertTrue(os.path.exists(out))
            with open(out, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("1024.0 MB", content)

    def test_cli_audit_mode_runs_cleanly(self):
        with patch("functions.ram_auditor.get_physical_ram_hardware", return_value={
            "total_slots": 2, "used_slots": 2, "max_capacity_gb": 64.0, "modules": [], "error": None
        }):
            rc = ram_auditor.main(["--mode", "audit"])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
