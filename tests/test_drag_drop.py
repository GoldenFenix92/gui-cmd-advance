import os
import tempfile
import unittest

from PIL import Image

from functions import compressor, drag_drop, media_repair


class TestDragAndDrop(unittest.TestCase):
    def test_single_video_and_image_detection_and_presets(self):
        with tempfile.TemporaryDirectory() as tmp:
            vid = os.path.join(tmp, "clip_prueba.mp4")
            img = os.path.join(tmp, "foto_prueba.png")
            with open(vid, "wb") as f:
                f.write(b"\x00" * 2048)
            Image.new("RGB", (32, 32), (10, 120, 200)).save(img, "PNG")

            vid_batch = drag_drop.inspect_dropped_batch([vid])
            self.assertEqual(vid_batch["total_count"], 1)
            self.assertEqual(vid_batch["compatible_count"], 1)
            self.assertEqual(vid_batch["video_count"], 1)
            self.assertEqual(vid_batch["image_count"], 0)
            self.assertEqual(vid_batch["detected_media_type"], "videos")
            self.assertIn("MP4", vid_batch["items"][0]["file_type_label"])

            vid_services = drag_drop.get_compatible_services(vid_batch)
            self.assertEqual(
                [s["command_name"] for s in vid_services],
                [
                    "Compresor de Multimedia",
                    "Reparador de Multimedia",
                    "Recortador Visual de Video (Línea de Tiempo)",
                    "Estudio de Video y Audio (FFmpeg)",
                ],
            )
            self.assertTrue(vid_services[2].get("video_only"))
            self.assertEqual(vid_services[2].get("launch_direct"), "video_trimmer")
            self.assertTrue(vid_services[3].get("video_only"))
            repair_svc = vid_services[1]
            self.assertEqual(repair_svc["presets"]["Tipo de Archivos a Reparar"], "Solo Videos")

            img_batch = drag_drop.inspect_dropped_batch([img])
            self.assertEqual(img_batch["detected_media_type"], "images")
            img_services = drag_drop.get_compatible_services(img_batch)
            self.assertEqual(
                [s["command_name"] for s in img_services],
                ["Compresor de Multimedia", "Reparador de Multimedia"],
            )
            self.assertEqual(img_services[1]["presets"]["Tipo de Archivos a Reparar"], "Solo Imágenes")

    def test_multi_file_mixed_batch_filters_non_media(self):
        with tempfile.TemporaryDirectory() as tmp:
            vid = os.path.join(tmp, "video1.mkv")
            img = os.path.join(tmp, "imagen1.jpg")
            txt = os.path.join(tmp, "notas.txt")
            sub = os.path.join(tmp, "carpeta_extra")
            os.makedirs(sub)
            for p in (vid, img, txt):
                with open(p, "wb") as f:
                    f.write(b"data")

            # Incluye duplicado intencional para validar deduplicación
            batch = drag_drop.inspect_dropped_batch([vid, img, txt, sub, vid])
            self.assertEqual(batch["total_count"], 4)
            self.assertEqual(batch["compatible_count"], 2)
            self.assertEqual(batch["unsupported_count"], 2)
            self.assertEqual(batch["video_count"], 1)
            self.assertEqual(batch["image_count"], 1)
            self.assertEqual(batch["detected_media_type"], "all")

            services = drag_drop.get_compatible_services(batch)
            self.assertEqual(len(services), 4)
            self.assertEqual(
                services[1]["presets"]["Tipo de Archivos a Reparar"],
                "Videos e Imágenes (Todos)",
            )

    def test_folder_and_unsupported_files_return_no_services(self):
        with tempfile.TemporaryDirectory() as tmp:
            txt = os.path.join(tmp, "doc.txt")
            pdf = os.path.join(tmp, "manual.pdf")
            mp3 = os.path.join(tmp, "audio.mp3")
            no_ext = os.path.join(tmp, "README")
            for p in (txt, pdf, mp3, no_ext):
                with open(p, "wb") as f:
                    f.write(b"abc")

            for candidate in (tmp, txt, pdf, mp3, no_ext):
                batch = drag_drop.inspect_dropped_batch([candidate])
                self.assertEqual(batch["compatible_count"], 0)
                self.assertEqual(drag_drop.get_compatible_services(batch), [])
                self.assertTrue(batch["items"][0]["file_type_label"])

    def test_batch_file_roundtrip_and_input_list_in_compressor_and_repair(self):
        with tempfile.TemporaryDirectory() as tmp:
            img1 = os.path.join(tmp, "foto1.jpg")
            img2 = os.path.join(tmp, "foto2.png")
            out_comp = os.path.join(tmp, "out_comp")
            out_rep = os.path.join(tmp, "out_rep")
            os.makedirs(out_comp)
            os.makedirs(out_rep)

            Image.new("RGB", (60, 40), (220, 40, 40)).save(img1, "JPEG")
            Image.new("RGB", (50, 50), (40, 200, 60)).save(img2, "PNG")

            list_file = os.path.join(tmp, "lote.json")
            saved = drag_drop.save_dropped_batch_file([img1, img2], target_path=list_file)
            loaded = drag_drop.load_input_list_file(saved)
            self.assertEqual(len(loaded), 2)

            # Validar --input-list en Compresor de Multimedia
            compressor.main([
                "--input-list", saved,
                "--output", out_comp,
                "--suffix", "_opt",
                "--quality", "80",
            ])
            self.assertTrue(os.path.exists(os.path.join(out_comp, "foto1_opt.jpg")))
            self.assertTrue(os.path.exists(os.path.join(out_comp, "foto2_opt.png")))

            # Validar --input-list en Reparador de Multimedia (imágenes reparadas se guardan como .jpg)
            media_repair.main([
                "--input-list", saved,
                "--output", out_rep,
                "--media-type", "images",
                "--suffix", "_rep",
            ])
            self.assertTrue(os.path.exists(os.path.join(out_rep, "foto1_rep.jpg")))
            self.assertTrue(os.path.exists(os.path.join(out_rep, "foto2_rep.jpg")))

    def test_gui_drop_modal_and_apply_service_smoke(self):
        import gui_app

        with tempfile.TemporaryDirectory() as tmp:
            v1 = os.path.join(tmp, "video_a.mp4")
            v2 = os.path.join(tmp, "video_b.mkv")
            doc = os.path.join(tmp, "archivo.txt")
            for p in (v1, v2, doc):
                with open(p, "wb") as f:
                    f.write(b"0123456789")

            app = gui_app.App()
            app.withdraw()
            try:
                app.update()
                # 1) Attach nativo Win32
                app._init_drag_and_drop()
                self.assertIsNotNone(app._drop_handler)
                self.assertTrue(app._drop_handler._attached)

                # 2) Modal con archivo no compatible
                b_unsup = drag_drop.inspect_dropped_batch([doc])
                win_u = app._open_dropped_file_modal(b_unsup, drag_drop.get_compatible_services(b_unsup))
                app.update()
                win_u.destroy()

                # 3) Aplicar servicio sobre 1 video -> Reparador con Solo Videos y ruta cargada
                b_single = drag_drop.inspect_dropped_batch([v1])
                svcs_single = drag_drop.get_compatible_services(b_single)
                app._apply_dropped_service(b_single, svcs_single[1])
                self.assertEqual(app.cat_var.get(), "Multimedia")
                self.assertEqual(app.cmd_var.get(), "Reparador de Multimedia")
                self.assertEqual(app.current_args_vars["Tipo de Archivos a Reparar"]["var"].get(), "Solo Videos")
                self.assertIn("video_a.mp4", app.preview_var.get())

                # 4) Aplicar servicio sobre lote multi-archivo -> Compresor con --input-list
                b_multi = drag_drop.inspect_dropped_batch([v1, v2, doc])
                svcs_multi = drag_drop.get_compatible_services(b_multi)
                win_m = app._open_dropped_file_modal(b_multi, svcs_multi)
                app.update()
                win_m.destroy()

                app._apply_dropped_service(b_multi, svcs_multi[0])
                self.assertEqual(app.cmd_var.get(), "Compresor de Multimedia")
                self.assertIn("--input-list", app.preview_var.get())
                self.assertIsNotNone(app._dropped_batch_state)
                self.assertEqual(len(app._dropped_batch_state["paths"]), 2)

                # 5) Limpiar lote quita --input-list de la vista previa
                app._clear_dropped_batch(refresh_preview=True)
                self.assertNotIn("--input-list", app.preview_var.get())
            finally:
                if app._drop_handler is not None:
                    app._drop_handler.detach()
                app.destroy()


if __name__ == "__main__":
    unittest.main()
