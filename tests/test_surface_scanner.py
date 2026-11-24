import unittest

from functions import surface_scanner


class FakeDiskHandle:
    """Disco simulado en memoria para probar escaneo y remap sin tocar hardware real."""

    def __init__(self, bad_offsets=None, recoverable_offsets=None):
        self.bad_offsets = set(bad_offsets or [])
        self.recoverable_offsets = set(recoverable_offsets or [])
        self.written_offsets = []

    def read_block(self, offset, size):
        if offset in self.bad_offsets:
            raise OSError(f"Simulated I/O error at {offset}")
        return size

    def write_zeros(self, offset, size):
        self.written_offsets.append(offset)
        if offset in self.recoverable_offsets:
            self.bad_offsets.discard(offset)
            return size
        raise OSError(f"Permanent bad sector at {offset}")


class TestSurfaceScanner(unittest.TestCase):
    def test_classify_block_thresholds(self):
        self.assertEqual(surface_scanner.classify_block(10.0), "excellent")
        self.assertEqual(surface_scanner.classify_block(120.0), "normal")
        self.assertEqual(surface_scanner.classify_block(450.0), "slow")
        self.assertEqual(surface_scanner.classify_block(1500.0), "critical")
        self.assertEqual(surface_scanner.classify_block(5.0, io_error=True), "bad")

    def test_remap_safety_blocks_system_and_ssd_allows_hdd(self):
        ok, msg = surface_scanner.check_remap_safety(
            {"IsSystem": True, "IsBoot": False, "MediaType": "HDD", "BusType": "SATA"}
        )
        self.assertFalse(ok)
        self.assertIn("BLOQUEADO", msg)

        ok, msg = surface_scanner.check_remap_safety(
            {"IsSystem": False, "IsBoot": False, "MediaType": "SSD", "BusType": "NVMe"}
        )
        self.assertFalse(ok)
        self.assertIn("SSD", msg)

        ok, msg = surface_scanner.check_remap_safety(
            {"IsSystem": False, "IsBoot": False, "MediaType": "HDD", "BusType": "USB"}
        )
        self.assertTrue(ok)
        self.assertEqual(msg, "")

    def test_scan_surface_map_and_largest_healthy_range(self):
        block = 1024 * 1024  # 1 MB
        total = 10 * block
        # Bloque en 7 MB (70%) dañado
        fake = FakeDiskHandle(bad_offsets={7 * block})
        summary = surface_scanner.run_surface_scan(
            fake, total_size=total, mode="scan", block_size=block, log_cb=lambda *a, **k: None
        )
        self.assertEqual(summary["total_blocks"], 10)
        self.assertEqual(summary["counts"]["bad"], 1)

        smap = surface_scanner.build_surface_map(summary["results"], total, cells=10)
        self.assertEqual(len(smap), 10)
        self.assertEqual(smap[7], "X")
        self.assertEqual(smap[0], ".")

        start, end = surface_scanner.find_largest_healthy_range(summary["results"], total)
        self.assertEqual((start, end), (0, 7 * block))

    def test_remap_recovers_pending_and_flags_permanent_bad(self):
        block = 1024 * 1024
        total = 6 * block
        fake = FakeDiskHandle(bad_offsets={2 * block, 4 * block}, recoverable_offsets={2 * block})
        summary = surface_scanner.run_surface_scan(
            fake, total_size=total, mode="remap", block_size=block, log_cb=lambda *a, **k: None
        )
        self.assertEqual(summary["remapped_ok"], 1)
        self.assertEqual(summary["remapped_fail"], 1)
        self.assertEqual(summary["counts"]["bad"], 1)
        self.assertIn(2 * block, fake.written_offsets)
        self.assertIn(4 * block, fake.written_offsets)

    def test_quick_mode_sampling_aligned_to_512(self):
        offsets = surface_scanner.compute_offsets(
            total_size=500 * 1024 * 1024 * 1024,
            block_size=4 * 1024 * 1024,
            mode="quick",
            quick_samples=100,
        )
        self.assertEqual(len(offsets), 100)
        self.assertTrue(all(o % 512 == 0 for o in offsets))
        self.assertEqual(offsets[0], 0)


if __name__ == "__main__":
    unittest.main()
