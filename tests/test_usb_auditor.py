import os
import tempfile
import unittest
from unittest.mock import patch

from functions import report_generator, usb_auditor


class TestUsbAuditor(unittest.TestCase):
    def test_parse_vid_pid(self):
        self.assertEqual(usb_auditor.parse_vid_pid(r"USB\VID_0951&PID_1666\E0D55E6A"), ("0951", "1666"))
        self.assertEqual(usb_auditor.parse_vid_pid(r"USB\vid_0781&pid_5581\1234"), ("0781", "5581"))
        self.assertEqual(usb_auditor.parse_vid_pid(r"SCSI\DISK&VEN_NVME"), (None, None))

    def test_suspicious_serial_detection(self):
        self.assertTrue(usb_auditor.is_suspicious_serial("")[0])
        self.assertTrue(usb_auditor.is_suspicious_serial("000000000000")[0])
        self.assertTrue(usb_auditor.is_suspicious_serial("AA00000000000489")[0])
        self.assertFalse(usb_auditor.is_suspicious_serial("E0D55E6A1234F98B")[0])

    def test_evaluate_original_usb(self):
        info = {
            "FriendlyName": "SanDisk Ultra USB 3.0",
            "BusType": "USB",
            "MediaType": "Unspecified",
            "Size": 64 * (1000 ** 3),
            "SerialNumber": "4C530001240519112233",
            "VID": "0781",
            "PID": "5581",
            "IsOffline": False,
            "IsReadOnly": False,
        }
        res = usb_auditor.evaluate_hardware_authenticity(info)
        self.assertEqual(res["verdict"], "ORIGINAL / CONSISTENTE")
        self.assertEqual(res["critical"], [])

    def test_evaluate_spoofed_fake_usb(self):
        info = {
            "FriendlyName": "SanDisk Extreme Pro 2TB",
            "BusType": "USB",
            "MediaType": "Unspecified",
            "Size": 2 * (1000 ** 4),
            "SerialNumber": "000000000000",
            "VID": "1E3D",
            "PID": "2095",
            "IsOffline": False,
            "IsReadOnly": False,
        }
        res = usb_auditor.evaluate_hardware_authenticity(info)
        self.assertEqual(res["verdict"], "ALTA PROBABILIDAD DE FALSIFICACIÓN")
        self.assertGreaterEqual(len(res["critical"]), 2)

    def test_capacity_test_verified_and_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            res = usb_auditor.run_capacity_test(tmp, mode="quick", max_mb_override=4, block_size=64 * 1024)
            self.assertEqual(res["status"], "verified")
            self.assertEqual(res["verified_mb"], 4)
            self.assertGreater(res["write_mb_s"], 0)
            self.assertFalse(os.path.exists(os.path.join(tmp, "_usb_audit_tmp")))

    def test_capacity_test_detects_corrupted_fake_wraparound(self):
        nonce = b"\x01\x02\x03\x04"
        blk0 = usb_auditor._make_signed_block(0, nonce, block_size=4096)
        blk1 = usb_auditor._make_signed_block(1, nonce, block_size=4096)

        # Bloque 0 válido
        ok0, _ = usb_auditor._verify_signed_block(blk0, 0, nonce)
        self.assertTrue(ok0)

        # Simular wrap-around: donde debía estar bloque 0 ahora está bloque 1
        ok_wrap, reason_wrap = usb_auditor._verify_signed_block(blk1, 0, nonce)
        self.assertFalse(ok_wrap)
        self.assertIn("CAPACIDAD INFLADA", reason_wrap)

        # Simular bytes corruptos en el payload
        corrupted = blk0[:100] + b"\xFF\x00\xFF" + blk0[103:]
        ok_crc, reason_crc = usb_auditor._verify_signed_block(corrupted, 0, nonce)
        self.assertFalse(ok_crc)
        self.assertIn("CRC32", reason_crc)

    def test_report_generator_uses_storage_template_for_usb_audit(self):
        sample = (
            "  Modelo             : Kingston DataTraveler 3.0\n"
            "  Tipo de Unidad     : Unspecified (USB)\n"
            "  Capacidad          : 57.70 GiB (62.0 GB comerciales)\n"
            "  VID / PID USB      : VID_0951 & PID_1666 (Kingston Technology)\n"
            "  Velocidad Medida   : Escritura 28.4 MB/s | Lectura 112.6 MB/s\n"
            "  Veredicto de Autenticidad : ORIGINAL / CONSISTENTE\n"
        )
        html_out = report_generator.generate_html_report(
            sample,
            title="Auditor de Autenticidad de Unidades (USB / SSD / HDD)",
            command="__INTERNAL__ --run-usb-audit --disk 3 --mode quick",
            category="Almacenamiento",
        )
        self.assertIn('data-profile="storage"', html_out)
        self.assertIn("ORIGINAL / CONSISTENTE", html_out)
        self.assertIn("VID_0951", html_out)
        self.assertIn("28.4 MB/s", html_out)


if __name__ == "__main__":
    unittest.main()
