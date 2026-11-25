import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image

from functions import combo_engine, health_analyzer, media_repair


class TestMultimediaPipeline(unittest.TestCase):
    def _create_valid_jpg(self, path):
        img = Image.new("RGB", (32, 32), color=(40, 120, 200))
        img.save(path, "JPEG")

    def _create_corrupt_jpg(self, path):
        with open(path, "wb") as f:
            f.write(b"\xff\xd8\xff\xe0CORRUPT_DATA_NOT_A_VALID_JPEG")

    def test_health_analyzer_writes_manifest_with_only_corrupt_files_including_subfolders(self):
        with tempfile.TemporaryDirectory() as tmp:
            root_ok = os.path.join(tmp, "sana_raiz.jpg")
            root_bad = os.path.join(tmp, "rota_raiz.jpg")
            sub_clean = os.path.join(tmp, "sub_sana")
            sub_dirty = os.path.join(tmp, "sub_con_error")
            os.makedirs(sub_clean)
            os.makedirs(sub_dirty)

            sub_ok = os.path.join(sub_clean, "sana_sub.jpg")
            sub_bad = os.path.join(sub_dirty, "rota_sub.jpg")

            self._create_valid_jpg(root_ok)
            self._create_corrupt_jpg(root_bad)
            self._create_valid_jpg(sub_ok)
            self._create_corrupt_jpg(sub_bad)

            manifest_nonrec = os.path.join(tmp, "m_nonrec.json")
            health_analyzer.main(tmp, recursive=False, media_type="images", manifest_out=manifest_nonrec)
            data_nr = json.load(open(manifest_nonrec, encoding="utf-8"))
            paths_nr = [os.path.abspath(x["path"]) for x in data_nr["corrupt_files"]]
            self.assertEqual(paths_nr, [os.path.abspath(root_bad)])

            manifest_rec = os.path.join(tmp, "m_rec.json")
            health_analyzer.main(tmp, recursive=True, media_type="images", manifest_out=manifest_rec)
            data_r = json.load(open(manifest_rec, encoding="utf-8"))
            paths_r = sorted(os.path.abspath(x["path"]) for x in data_r["corrupt_files"])
            self.assertEqual(paths_r, sorted([os.path.abspath(root_bad), os.path.abspath(sub_bad)]))

    def test_media_repair_from_manifest_processes_only_corrupt_and_respects_media_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            ok_img = os.path.join(tmp, "sana.jpg")
            bad_img = os.path.join(tmp, "danada.jpg")
            bad_vid = os.path.join(tmp, "danado.mp4")
            self._create_valid_jpg(ok_img)
            self._create_valid_jpg(bad_img)
            Path(bad_vid).write_bytes(b"fake_mp4")

            manifest = os.path.join(tmp, "manifest.json")
            health_analyzer.write_corrupt_manifest(
                manifest,
                tmp,
                True,
                "all",
                [
                    {"path": bad_img, "type": "image", "error": "truncated"},
                    {"path": bad_vid, "type": "video", "error": "invalid moov"},
                ],
            )

            # Filtro solo imágenes: solo carga bad_img y nunca ok_img ni bad_vid
            imgs, _ = media_repair.load_corrupt_files_from_manifest(manifest, media_type="images")
            self.assertEqual([str(p) for p in imgs], [bad_img])

            # Filtro solo videos: solo carga bad_vid
            vids, _ = media_repair.load_corrupt_files_from_manifest(manifest, media_type="videos")
            self.assertEqual([str(p) for p in vids], [bad_vid])

            # Enrutamiento de --ref-video y --ref-image al ejecutar main() con --manifest
            calls = []
            with patch.object(media_repair, "repair_image", side_effect=lambda i, o, r=None: calls.append(("img", i, r)) or True), \
                 patch.object(media_repair, "repair_video", side_effect=lambda i, o, r=None: calls.append(("vid", i, r)) or True):
                media_repair.main([
                    "--manifest", manifest,
                    "--media-type", "all",
                    "--ref-video", "C:\\ref_sano.mp4",
                    "--ref-image", "C:\\ref_sano.jpg",
                ])

            self.assertEqual(
                calls,
                [
                    ("img", bad_img, "C:\\ref_sano.jpg"),
                    ("vid", bad_vid, "C:\\ref_sano.mp4"),
                ],
            )
            # El manifiesto debe eliminarse automáticamente al concluir la reparación
            self.assertFalse(os.path.exists(manifest))

            # Manifiesto vacío sale con código 0 limpiamente y también se elimina
            empty_manifest = os.path.join(tmp, "empty.json")
            health_analyzer.write_corrupt_manifest(empty_manifest, tmp, False, "all", [])
            with self.assertRaises(SystemExit) as cm:
                media_repair.main(["--manifest", empty_manifest])
            self.assertEqual(cm.exception.code, 0)
            self.assertFalse(os.path.exists(empty_manifest))

    def test_media_repair_direct_is_non_recursive_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root_img = os.path.join(tmp, "a.jpg")
            sub = os.path.join(tmp, "sub")
            os.makedirs(sub)
            sub_img = os.path.join(sub, "b.jpg")
            self._create_valid_jpg(root_img)
            self._create_valid_jpg(sub_img)

            non_rec = media_repair.collect_target_files([tmp], media_type="images", recursive=False)
            self.assertEqual([str(p) for p in non_rec], [root_img])

            rec = media_repair.collect_target_files([tmp], media_type="images", recursive=True)
            self.assertEqual(sorted(str(p) for p in rec), sorted([root_img, sub_img]))

    def test_media_repair_direct_folder_without_combo_isolates_only_corrupt_via_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            ok_img = os.path.join(tmp, "sana.jpg")
            bad_img = os.path.join(tmp, "rota.jpg")
            self._create_valid_jpg(ok_img)
            self._create_corrupt_jpg(bad_img)

            repaired_inputs = []
            fake_manifest = os.path.join(tmp, "auto_manifest.json")
            with patch.object(media_repair, "get_user_data_path", return_value=fake_manifest), \
                 patch.object(media_repair, "repair_image", side_effect=lambda i, o, r=None: repaired_inputs.append(i) or True):
                media_repair.main(["--input", tmp, "--media-type", "images"])

            # Solo intentó reparar la corrupta, jamás la sana, y eliminó el manifiesto temporal al terminar
            self.assertEqual(repaired_inputs, [bad_img])
            self.assertFalse(os.path.exists(fake_manifest))

    def test_incremental_manifest_removal_and_resume_after_interruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            ok_img = os.path.join(tmp, "sana.jpg")
            bad1 = os.path.join(tmp, "rota1.jpg")
            bad2 = os.path.join(tmp, "rota2.jpg")
            self._create_valid_jpg(ok_img)
            self._create_corrupt_jpg(bad1)
            self._create_corrupt_jpg(bad2)

            fake_manifest = os.path.join(tmp, "resume_manifest.json")

            # Simular interrupción (pausa) justo después de reparar bad1
            repaired_run1 = []
            pause_states = [True, False]

            def fake_pause():
                return pause_states.pop(0) if pause_states else False

            with patch.object(media_repair, "get_user_data_path", return_value=fake_manifest), \
                 patch.object(media_repair, "repair_image", side_effect=lambda i, o, r=None: repaired_run1.append(i) or True), \
                 patch.object(media_repair.TaskMemory, "check_pause_signal", side_effect=fake_pause):
                with self.assertRaises(SystemExit) as cm:
                    media_repair.main(["--input", tmp, "--media-type", "images"])
                self.assertEqual(cm.exception.code, 0)

            self.assertEqual(len(repaired_run1), 1)
            first_repaired = repaired_run1[0]
            remaining_expected = bad2 if first_repaired == bad1 else bad1

            # El manifiesto debe seguir existiendo con SOLO el archivo pendiente
            self.assertTrue(os.path.exists(fake_manifest))
            mdata = json.load(open(fake_manifest, encoding="utf-8"))
            self.assertEqual([x["path"] for x in mdata["corrupt_files"]], [os.path.abspath(remaining_expected)])

            # Al reanudar sobre la misma carpeta, NO vuelve a escanear ni a reparar el primero: solo repara el faltante
            repaired_run2 = []
            with patch.object(media_repair, "get_user_data_path", return_value=fake_manifest), \
                 patch.object(media_repair, "repair_image", side_effect=lambda i, o, r=None: repaired_run2.append(i) or True), \
                 patch.object(media_repair.TaskMemory, "check_pause_signal", return_value=False):
                media_repair.main(["--input", tmp, "--media-type", "images"])

            self.assertEqual(repaired_run2, [remaining_expected])
            # Y al terminar todo, el manifiesto se elimina automáticamente
            self.assertFalse(os.path.exists(fake_manifest))

    def test_combo_engine_injects_from_manifest_and_inherits_media_context(self):
        main_cmd = '__INTERNAL__ --run-media-repair --input "C:\\Fotos" --media-type videos --recursive --ref-video "C:\\sano.mp4"'
        ctx = combo_engine.extract_command_context(main_cmd)
        self.assertEqual(ctx["path"], "C:\\Fotos")
        self.assertEqual(ctx["media_type"], "videos")
        self.assertEqual(ctx["recursive_flag"], "--recursive")

        before_item = {
            "command": "Analizador de Salud Multimedia",
            "when": "before",
            "auto_command": '__INTERNAL__ --run-health-analyzer "{path}" {recursive_flag} --media-type {media_type}',
        }
        queue = combo_engine.build_execution_queue(
            "Reparador de Multimedia",
            main_cmd,
            selected_before=[before_item],
            selected_after=[],
            auto_execute=True,
            context=ctx,
        )
        self.assertEqual(len(queue), 2)
        self.assertIn("--run-health-analyzer", queue[0]["cmd_str"])
        self.assertIn("--recursive", queue[0]["cmd_str"])
        self.assertIn("--media-type videos", queue[0]["cmd_str"])
        self.assertIn("--from-manifest", queue[1]["cmd_str"])


if __name__ == "__main__":
    unittest.main()
