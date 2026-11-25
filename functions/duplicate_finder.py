import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from tkinter import filedialog, messagebox
from PIL import Image, ImageFile, ImageTk
import pymupdf
import ttkbootstrap as tb
from ttkbootstrap.widgets.scrolled import ScrolledFrame
from ttkbootstrap.widgets.floodgauge import Floodgauge

ImageFile.LOAD_TRUNCATED_IMAGES = True

from functions.utils import center_window, get_resource_path, safe_print
from functions import ui_theme

for _stream in (sys.stdout, sys.stderr):
    if _stream is not None and hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


class DuplicateFinderApp(tb.Window):
    def __init__(self, folder=None, hw="cpu", mode="both", threads=0):
        theme = ui_theme.get_saved_theme()
        super().__init__(themename=theme)
        self.title("Buscador de Duplicados y Multimedia Dañada")
        center_window(self, 940, 700)
        ui_theme.apply_window_chrome(self, theme)

        self.selected_folder = folder or ""
        self.hw_mode = hw
        self.search_mode = mode
        self.max_threads = threads if threads > 0 else (os.cpu_count() or 4)

        self.results = []
        self.checkboxes = []
        self.all_suspects = []
        self.rendered_count = 0
        self.is_scanning = False

        self.setup_ui()

        if self.selected_folder:
            self.lbl_folder.configure(text=self.selected_folder)
            self.btn_select.configure(state="disabled")
            self.after(100, self.start_scan)

    def setup_ui(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        top_frame = tb.Labelframe(self, text="Carpeta de Escaneo", padding=10, bootstyle="info")
        top_frame.grid(row=0, column=0, padx=12, pady=(12, 6), sticky="ew")

        self.btn_select = tb.Button(top_frame, text="Seleccionar Carpeta", command=self.select_folder, bootstyle="primary")
        self.btn_select.pack(side="left", padx=(0, 10))

        self.lbl_folder = tb.Label(top_frame, text="Ninguna carpeta seleccionada")
        self.lbl_folder.pack(side="left", padx=6)

        self.btn_scan = tb.Button(top_frame, text="Escanear", command=self.start_scan, state="disabled", bootstyle="success")
        self.btn_scan.pack(side="right", padx=(6, 0))

        self.btn_stop = tb.Button(top_frame, text="Detener", command=self.stop_scan, state="disabled", bootstyle="danger")
        self.btn_stop.pack(side="right", padx=6)

        self.scroll_frame = ScrolledFrame(self, autohide=True, padding=8)
        self.scroll_frame.grid(row=1, column=0, padx=12, pady=6, sticky="nsew")

        bottom_frame = tb.Frame(self, padding=(12, 8))
        bottom_frame.grid(row=2, column=0, sticky="ew")

        controls_row = tb.Frame(bottom_frame)
        controls_row.pack(fill="x")

        self.lbl_status = tb.Label(controls_row, text="Listo.")
        self.lbl_status.pack(side="left")

        self.btn_move_all = tb.Button(controls_row, text="Mover TODOS (Rápido)", command=self.move_all, state="disabled", bootstyle="danger")
        self.btn_move_all.pack(side="right", padx=(6, 0))

        self.btn_move = tb.Button(controls_row, text="Mover Visibles", command=self.move_selected, state="disabled", bootstyle="warning")
        self.btn_move.pack(side="right", padx=6)

        self.select_all_var = tk.IntVar(value=0)
        self.chk_select_all = tb.Checkbutton(
            controls_row, text="Seleccionar Visibles", variable=self.select_all_var,
            command=self.toggle_all_visible, state="disabled", bootstyle="primary",
        )
        self.chk_select_all.pack(side="right", padx=14)

        self.progress_bar = Floodgauge(bottom_frame, maximum=100, value=0, mask="{}%", bootstyle="info")
        self.progress_bar.pack(fill="x", pady=(8, 0))
        self.progress_bar.pack_forget()

        self.btn_load_more = tb.Button(self.scroll_frame, text="Cargar 100 más...", command=self.load_more, bootstyle="secondary-outline")

    def select_folder(self):
        folder = filedialog.askdirectory(parent=self)
        if folder:
            self.selected_folder = folder
            self.lbl_folder.configure(text=folder)
            self.btn_scan.configure(state="normal")

    def start_scan(self):
        self.is_scanning = True
        self.btn_scan.configure(state="disabled")
        self.btn_select.configure(state="disabled")
        self.btn_move.configure(state="disabled")
        self.btn_move_all.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.lbl_status.configure(text="Escaneando... esto puede tomar un tiempo.")
        self.progress_bar.pack(fill="x", pady=(8, 0))
        self.progress_bar.configure(value=0)

        for widget in self.scroll_frame.winfo_children():
            if widget != self.btn_load_more:
                widget.destroy()
        self.btn_load_more.pack_forget()

        self.results = []
        self.checkboxes = []
        self.all_suspects = []
        self.rendered_count = 0

        thread = threading.Thread(target=self.scan_process, daemon=True)
        thread.start()

    def stop_scan(self):
        self.is_scanning = False
        self.btn_stop.configure(state="disabled")
        self.lbl_status.configure(text="Deteniendo el escaneo... por favor espere.")

    def update_progress(self, current, total, msg):
        percent = int((current / total) * 100) if total > 0 else 0
        self.progress_bar.configure(value=percent)
        self.lbl_status.configure(text=msg)
        safe_print(f"{percent}%")

    def get_hash(self, filepath):
        sha256 = hashlib.sha256()
        try:
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except Exception:
            return None

    def get_base_name(self, filepath):
        stem = filepath.stem
        pattern = r"([-_ ]+(copia|copy)\b[-_ ]*\d*|[-_ ]+\(\d{1,2}\))+$"
        base = re.sub(pattern, "", stem, flags=re.IGNORECASE).strip()
        return base if base else stem

    def toggle_all_visible(self):
        new_val = self.select_all_var.get()
        for item in self.all_suspects[:max(100, self.rendered_count)]:
            if "checkbox_var" in item:
                item["checkbox_var"].set(new_val)

    def check_corruption(self, filepath):
        ext = filepath.suffix.lower()
        if ext in [".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"]:
            try:
                img = Image.open(filepath)
                img.verify()
                return False
            except Exception:
                return True
        elif ext == ".pdf":
            try:
                doc = pymupdf.open(filepath)
                if doc.page_count < 1:
                    return True
                doc.close()
                return False
            except Exception:
                return True
        elif ext in [".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv", ".webm", ".m4v"]:
            try:
                ffmpeg_exe = Path(get_resource_path(os.path.join("tools", "ffmpeg.exe")))
                if not ffmpeg_exe.exists():
                    return False

                cmd = [str(ffmpeg_exe), "-v", "error"]
                if self.hw_mode == "nvenc":
                    cmd.extend(["-hwaccel", "cuda"])
                elif self.hw_mode == "amf":
                    cmd.extend(["-hwaccel", "dxva2"])
                elif self.hw_mode == "auto":
                    cmd.extend(["-hwaccel", "auto"])

                cmd.extend(["-i", str(filepath), "-f", "null", "-"])
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                if result.returncode != 0:
                    if self.hw_mode in ["nvenc", "amf", "auto"]:
                        fallback_cmd = [str(ffmpeg_exe), "-v", "error", "-i", str(filepath), "-f", "null", "-"]
                        result_fb = subprocess.run(fallback_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                        return result_fb.returncode != 0
                    return True
                return False
            except Exception:
                return False
        return False

    def extract_thumbnail(self, filepath):
        ext = filepath.suffix.lower()
        size = (96, 96)
        try:
            if ext in [".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"]:
                img = Image.open(filepath).copy()
                img.thumbnail(size)
                return img
            elif ext == ".pdf":
                doc = pymupdf.open(filepath)
                page = doc.load_page(0)
                pix = page.get_pixmap(matrix=pymupdf.Matrix(0.2, 0.2))
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                img.thumbnail(size)
                doc.close()
                return img
            elif ext in [".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv", ".webm", ".m4v"]:
                ffmpeg_exe = Path(get_resource_path(os.path.join("tools", "ffmpeg.exe")))
                if ffmpeg_exe.exists():
                    out_jpg = filepath.with_suffix(f".thumb_{threading.get_ident()}.jpg")
                    cmd = [str(ffmpeg_exe), "-y", "-ss", "1", "-i", str(filepath), "-vframes", "1", "-vf", "scale=100:-1", str(out_jpg)]
                    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                    if out_jpg.exists():
                        img = Image.open(out_jpg).copy()
                        img.thumbnail(size)
                        out_jpg.unlink()
                        return img
        except Exception:
            pass
        return None

    def scan_process(self):
        folder = Path(self.selected_folder)
        all_files = []
        for root, dirs, files in os.walk(folder):
            dirs[:] = [d for d in dirs if d.lower() not in ("archivos_duplicados", "archivos_dañados")]
            for f in files:
                all_files.append(Path(root) / f)

        total_files = len(all_files)
        if total_files == 0:
            self.after(0, self._finish_scan_ui, 0)
            return

        size_dict = {}
        name_dict = {}

        for i, f in enumerate(all_files):
            if not self.is_scanning:
                break
            if i % 100 == 0:
                self.after(0, self.update_progress, i, total_files, f"Fase 1/2: Buscando archivos... ({i}/{total_files})")
            try:
                s = f.stat().st_size
                size_dict.setdefault(s, []).append(f)
                if self.search_mode in ["both", "name"]:
                    base_name = self.get_base_name(f)
                    name_key = (base_name, f.suffix.lower())
                    name_dict.setdefault(name_key, []).append(f)
            except Exception:
                pass

        name_duplicates = set()
        name_originals = set()
        if self.search_mode in ["both", "name"]:
            for g in name_dict.values():
                if len(g) > 1:
                    g_sorted = sorted(g, key=lambda x: len(x.name))
                    name_originals.add(g_sorted[0])
                    for d in g_sorted[1:]:
                        name_duplicates.add(d)

        groups = list(size_dict.values())

        def process_group(files_in_group):
            if not self.is_scanning:
                return 0, []

            needs_hash = len(files_in_group) > 1 and self.search_mode in ["both", "hash"]
            hash_dict = {}
            corrupt_files = []

            for fpath in files_in_group:
                if not self.is_scanning:
                    return 0, []
                h = self.get_hash(fpath) if needs_hash else None
                is_corrupt = self.check_corruption(fpath)

                if is_corrupt:
                    corrupt_files.append((fpath, h))
                if h:
                    hash_dict.setdefault(h, []).append(fpath)

            suspects = []
            for h, h_files in hash_dict.items():
                if len(h_files) > 1:
                    h_files = sorted(h_files, key=lambda x: len(x.name))
                    is_c = any(f == h_files[0] for f, _ in corrupt_files)
                    suspects.append({"path": h_files[0], "status": "Original (Dañado)" if is_c else "Original", "hash": h, "group_key": h})
                    for d_file in h_files[1:]:
                        is_c_d = any(f == d_file for f, _ in corrupt_files)
                        suspects.append({"path": d_file, "status": "Duplicado (Dañado)" if is_c_d else "Duplicado", "hash": h, "group_key": h})

            processed_paths = set(s["path"] for s in suspects)
            for fpath in files_in_group:
                if fpath in processed_paths:
                    continue
                is_c = any(f == fpath for f, _ in corrupt_files)
                if fpath in name_duplicates:
                    suspects.append({"path": fpath, "status": "Duplicado por Nombre (Dañado)" if is_c else "Duplicado por Nombre", "hash": None, "group_key": self.get_base_name(fpath)})
                    processed_paths.add(fpath)
                elif fpath in name_originals:
                    suspects.append({"path": fpath, "status": "Original por Nombre (Dañado)" if is_c else "Original por Nombre", "hash": None, "group_key": self.get_base_name(fpath)})
                    processed_paths.add(fpath)
                elif is_c:
                    suspects.append({"path": fpath, "status": "Dañado", "hash": None, "group_key": str(fpath)})
                    processed_paths.add(fpath)

            for s in suspects:
                if not self.is_scanning:
                    break
                s["thumb"] = self.extract_thumbnail(s["path"])

            return len(files_in_group), suspects

        processed = 0
        found_suspects_count = 0

        with ThreadPoolExecutor(max_workers=self.max_threads) as executor:
            futures = {executor.submit(process_group, g): g for g in groups}
            for future in as_completed(futures):
                if not self.is_scanning:
                    continue
                count_processed, suspects = future.result()
                processed += count_processed
                self.after(0, self.update_progress, processed, total_files, f"Fase 2/2: Analizando y extrayendo miniaturas... ({processed}/{total_files})")
                if suspects:
                    found_suspects_count += len(suspects)
                    self.after(0, self._render_suspects_chunk, suspects)

        self.is_scanning = False
        self.after(0, self._finish_scan_ui, found_suspects_count)

    def _render_suspects_chunk(self, suspects):
        self.btn_load_more.pack_forget()
        for item in suspects:
            self.all_suspects.append(item)
            if self.rendered_count < 100:
                self._render_single_item(item)
        if len(self.all_suspects) > self.rendered_count:
            self.btn_load_more.pack(side="bottom", pady=10)

    def load_more(self):
        self.btn_load_more.pack_forget()
        start = self.rendered_count
        end = min(start + 100, len(self.all_suspects))
        for i in range(start, end):
            self._render_single_item(self.all_suspects[i])
        if len(self.all_suspects) > self.rendered_count:
            self.btn_load_more.pack(side="bottom", pady=10)

    def _render_single_item(self, item):
        self.rendered_count += 1
        is_bad = "Dañado" in item["status"]
        is_dup = "Duplicado" in item["status"]
        card_style = "danger" if is_bad else ("warning" if is_dup else "secondary")

        frame = tb.Labelframe(self.scroll_frame, text=item["status"], padding=6, bootstyle=card_style)
        frame.pack(fill="x", pady=4, padx=4)

        var = tk.IntVar(value=1 if (is_dup or is_bad) else 0)
        cb = tb.Checkbutton(frame, text="", variable=var, bootstyle="primary")
        cb.pack(side="left", padx=6)

        item["checkbox_var"] = var
        self.checkboxes.append((var, item["path"]))

        pil_img = item.get("thumb")
        if pil_img:
            photo = ImageTk.PhotoImage(pil_img, master=self)
            lbl_img = tb.Label(frame, image=photo)
            lbl_img.image = photo
            lbl_img.pack(side="left", padx=6)
        else:
            lbl_img = tb.Label(frame, text="Sin vista", width=12, bootstyle="secondary")
            lbl_img.pack(side="left", padx=6)

        info_text = f"{item['path'].name}\nRuta: {item['path']}"
        tb.Label(frame, text=info_text, justify="left", anchor="w").pack(side="left", fill="x", expand=True, padx=10)

    def _finish_scan_ui(self, count):
        self.progress_bar.pack_forget()
        self.btn_stop.configure(state="disabled")
        self.all_suspects.sort(key=lambda x: (str(x.get("group_key", "")), not x["status"].startswith("Original"), x["path"].name))

        self.lbl_status.configure(text=f"Escaneo finalizado. {len(self.all_suspects)} archivos sospechosos/duplicados encontrados.")
        self.btn_select.configure(state="normal")
        self.btn_scan.configure(state="normal")

        if len(self.all_suspects) > 0:
            self.btn_move.configure(state="normal")
            self.btn_move_all.configure(state="normal")
            self.chk_select_all.configure(state="normal")
            self.select_all_var.set(0)
            self._refresh_ui()
        else:
            self.chk_select_all.configure(state="disabled")
            self._refresh_ui()

    def move_all(self):
        dest_dupes = Path(self.selected_folder) / "Archivos_Duplicados"
        dest_damaged = Path(self.selected_folder) / "Archivos_Dañados"
        moved_count = 0

        safe_print("=== REPORTE DE ARCHIVOS MULTIMEDIA MOVIDOS ===")
        items_to_keep = []
        for item in self.all_suspects:
            if "checkbox_var" in item:
                is_selected = item["checkbox_var"].get() == 1
            else:
                is_selected = "Duplicado" in item["status"] or "Dañado" in item["status"]

            if is_selected:
                filepath = item["path"]
                is_damaged = "Dañado" in item["status"]
                dest_folder = dest_damaged if is_damaged else dest_dupes
                try:
                    dest_folder.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(filepath), str(dest_folder / filepath.name))
                    moved_count += 1
                except Exception as e:
                    safe_print(f"ERROR al mover {filepath.name}: {e}")
                    items_to_keep.append(item)
                else:
                    safe_print(f"MOVIDO: [{item['status']}] {filepath.name} -> {dest_folder.name}")
            else:
                items_to_keep.append(item)

        safe_print(f"=== TOTAL MOVIDO: {moved_count} archivos ===\n")
        self.all_suspects = items_to_keep
        messagebox.showinfo("Completado", f"Se han movido {moved_count} archivos en total.", parent=self)
        self._refresh_ui()

    def move_selected(self):
        dest_dupes = Path(self.selected_folder) / "Archivos_Duplicados"
        dest_damaged = Path(self.selected_folder) / "Archivos_Dañados"
        moved_count = 0

        safe_print("=== REPORTE DE ARCHIVOS MULTIMEDIA VISIBLES MOVIDOS ===")
        items_to_keep = []

        for item in self.all_suspects:
            if "checkbox_var" in item and item["checkbox_var"].get() == 1:
                filepath = item["path"]
                is_damaged = "Dañado" in item["status"]
                dest_folder = dest_damaged if is_damaged else dest_dupes
                try:
                    dest_folder.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(filepath), str(dest_folder / filepath.name))
                    moved_count += 1
                except Exception as e:
                    safe_print(f"ERROR al mover {filepath.name}: {e}")
                    items_to_keep.append(item)
                else:
                    safe_print(f"MOVIDO: [{item['status']}] {filepath.name} -> {dest_folder.name}")
            else:
                items_to_keep.append(item)

        safe_print(f"=== TOTAL MOVIDO: {moved_count} archivos ===\n")
        self.all_suspects = items_to_keep
        messagebox.showinfo("Completado", f"Se han movido {moved_count} archivos.", parent=self)
        self._refresh_ui()

    def _refresh_ui(self):
        for widget in self.scroll_frame.winfo_children():
            if widget != self.btn_load_more:
                widget.destroy()

        self.checkboxes = []
        self.btn_load_more.pack_forget()

        target_render_count = max(100, self.rendered_count)
        self.rendered_count = 0

        for item in self.all_suspects[:target_render_count]:
            item.pop("checkbox_var", None)
            self._render_single_item(item)

        if len(self.all_suspects) > self.rendered_count:
            self.btn_load_more.pack(side="bottom", pady=10)

        self.btn_move.configure(text=f"Mover Visibles ({self.rendered_count})")
        self.lbl_status.configure(text=f"Archivos restantes por revisar: {len(self.all_suspects)}")

        if len(self.all_suspects) == 0:
            self.lbl_status.configure(text="Revisión completada. No hay más archivos sospechosos.")
            self.btn_move.configure(state="disabled")
            self.btn_move_all.configure(state="disabled")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", nargs="?", default="")
    parser.add_argument("--hw", default="cpu")
    parser.add_argument("--mode", default="both")
    parser.add_argument("--threads", type=int, default=0)
    args = parser.parse_args()

    app = DuplicateFinderApp(folder=args.folder, hw=args.hw, mode=args.mode, threads=args.threads)
    app.mainloop()
