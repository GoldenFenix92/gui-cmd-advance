import json
import os
import unittest
from unittest.mock import patch

from functions import disk_attributes


SAMPLE_DISKPART_EN = """
Microsoft DiskPart version 10.0.22621.1

DISKPART> Current Read-only State : Yes
Read-only  : Yes
Boot Disk  : No
Pagefile Disk  : No
Hibernation File Disk  : No
Crashdump Disk  : No
Clustered Disk  : No
"""

SAMPLE_VOLUME_ATTRS_EN_WITH_PROMPT = """
DISKPART> Read-only              : No
Hidden                 : No
No Default Drive Letter: No
Shadow Copy            : No
"""

SAMPLE_DISKPART_ES_HW_LOCK = """
Microsoft DiskPart versión 10.0.22621.1

Estado actual de solo lectura : Sí
Solo lectura  : No
Disco de arranque  : No
Disco de archivo de paginación  : No
Disco de archivo de hibernación  : No
Disco de volcado de memoria  : No
Disco en clúster  : No
"""

SAMPLE_VOLUME_ATTRS_ES = """
Solo lectura                              : Sí
Oculto                                    : No
Sin letra de unidad predeterminada        : Sí
Instantánea                               : No
"""

SAMPLE_DETAIL_DISK_ES = """
Kingston DataTraveler 3.0 USB Device
Id. de disco: 1234ABCD
Tipo        : USB

  Volumen ###  Ltr  Etiqueta     Fs     Tipo        Tamaño   Estado     Info
  -----------  ---  -----------  -----  ----------  -------  ---------  --------
  Volumen 3     E   MI_USB       FAT32  Extraíble     28 GB  Correcto
  Volumen 4         OCULTO       NTFS   Partición    500 MB  Correcto   Oculto
"""


class TestDiskAttributes(unittest.TestCase):
    def test_parse_disk_attributes_english(self):
        parsed = disk_attributes.parse_disk_attributes(SAMPLE_DISKPART_EN)
        self.assertTrue(parsed["current_readonly"])
        self.assertTrue(parsed["readonly"])
        self.assertFalse(parsed["boot_disk"])
        self.assertFalse(parsed["hardware_write_protected"])

    def test_parse_disk_attributes_spanish_hardware_lock(self):
        parsed = disk_attributes.parse_disk_attributes(SAMPLE_DISKPART_ES_HW_LOCK)
        self.assertTrue(parsed["current_readonly"])
        self.assertFalse(parsed["readonly"])
        self.assertTrue(parsed["hardware_write_protected"])

    def test_parse_volume_attributes_spanish(self):
        parsed = disk_attributes.parse_volume_attributes(SAMPLE_VOLUME_ATTRS_ES)
        self.assertTrue(parsed["readonly"])
        self.assertFalse(parsed["hidden"])
        self.assertTrue(parsed["nodefaultdriveletter"])
        self.assertFalse(parsed["shadowcopy"])

    def test_parse_volume_attributes_english_with_diskpart_prompt(self):
        parsed = disk_attributes.parse_volume_attributes(SAMPLE_VOLUME_ATTRS_EN_WITH_PROMPT)
        self.assertFalse(parsed["readonly"])
        self.assertFalse(parsed["hidden"])
        self.assertFalse(parsed["nodefaultdriveletter"])
        self.assertFalse(parsed["shadowcopy"])

    def test_parse_detail_disk_volumes(self):
        vols = disk_attributes.parse_detail_disk_volumes(SAMPLE_DETAIL_DISK_ES)
        self.assertEqual(len(vols), 2)
        self.assertEqual(vols[0]["volume_number"], 3)
        self.assertEqual(vols[0]["drive_letter"], "E")
        self.assertEqual(vols[1]["volume_number"], 4)
        self.assertEqual(vols[1]["drive_letter"], "")

    def test_build_diskpart_commands_clear_readonly_disk(self):
        cmds = disk_attributes.build_diskpart_commands(
            disk_number=2,
            action="clear",
            scope="disk",
            attribute="readonly",
        )
        self.assertEqual(cmds, ["select disk 2", "attributes disk clear readonly"])

    def test_build_diskpart_commands_both_disk_and_volumes(self):
        cmds = disk_attributes.build_diskpart_commands(
            disk_number=1,
            action="clear",
            scope="both",
            attribute="readonly",
            target_volumes=[3, 4],
        )
        self.assertEqual(
            cmds,
            [
                "select disk 1",
                "attributes disk clear readonly",
                "select volume 3",
                "attributes volume clear readonly",
                "select volume 4",
                "attributes volume clear readonly",
            ],
        )

    def test_classify_drive_type(self):
        self.assertEqual(disk_attributes.classify_drive_type("USB", "Unspecified"), "Memoria USB / Disco USB")
        self.assertEqual(disk_attributes.classify_drive_type("NVMe", "SSD"), "SSD (NVMe)")
        self.assertEqual(disk_attributes.classify_drive_type("SATA", "HDD"), "HDD (SATA)")

    @patch("functions.disk_attributes.run_diskpart_script")
    def test_system_disk_blocks_set_operation(self, mock_dp):
        sys_meta = {
            "Number": 0,
            "FriendlyName": "Samsung SSD 980",
            "IsSystem": True,
            "IsBoot": True,
        }
        rc = disk_attributes.modify_attributes(
            disk_number=0,
            action="set",
            scope="disk",
            attribute="readonly",
            metadata=sys_meta,
        )
        self.assertEqual(rc, 1)
        mock_dp.assert_not_called()

    @patch("functions.disk_attributes.run_diskpart_script")
    def test_incompatible_disk_scope_with_hidden_attr(self, mock_dp):
        rc = disk_attributes.modify_attributes(
            disk_number=1,
            action="set",
            scope="disk",
            attribute="hidden",
            metadata={"Number": 1, "FriendlyName": "USB", "IsSystem": False, "IsBoot": False},
        )
        self.assertEqual(rc, 1)
        mock_dp.assert_not_called()

    @patch("functions.disk_attributes.inspect_disk", return_value=0)
    @patch("functions.disk_attributes.get_disk_metadata")
    @patch("functions.disk_attributes.run_diskpart_script", return_value=(0, "Disk attributes cleared successfully."))
    def test_modify_attributes_clear_readonly_executes_diskpart(self, mock_dp, mock_meta, mock_inspect):
        usb_meta = {"Number": 2, "FriendlyName": "Kingston USB", "IsSystem": False, "IsBoot": False}
        mock_meta.return_value = usb_meta

        rc = disk_attributes.modify_attributes(
            disk_number=2,
            action="clear",
            scope="disk",
            attribute="readonly",
            metadata=usb_meta,
        )
        self.assertEqual(rc, 0)
        mock_dp.assert_called_once_with(["select disk 2", "attributes disk clear readonly"])
        mock_inspect.assert_called_once()

    def test_commands_config_json_is_valid_and_contains_command(self):
        cfg_path = os.path.join(os.path.dirname(__file__), "..", "resources", "commands_config.json")
        with open(cfg_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        storage_cat = next(
            (c for c in data["categories"] if c["name"] == "Almacenamiento: Formateo y Gestión"),
            None,
        )
        self.assertIsNotNone(storage_cat)
        cmd = next(
            (c for c in storage_cat["commands"] if c["command"] == "__INTERNAL__ --run-disk-attributes"),
            None,
        )
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd["name"], "Gestor de Atributos de Discos (HDD/SSD/USB)")


if __name__ == "__main__":
    unittest.main()
