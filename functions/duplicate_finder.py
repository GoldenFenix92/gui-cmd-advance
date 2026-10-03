import os
import sys
import hashlib
import threading
import shutil
import argparse
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import subprocess
import customtkinter as ctk
from PIL import Image, ImageFile
import pymupdf  # PyMuPDF
from tkinter import filedialog, messagebox

ImageFile.LOAD_TRUNCATED_IMAGES = True

from functions.utils import get_resource_path

def center_window(window, width, height):
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    x = int((screen_width / 2) - (width / 2))
    y = int((screen_height / 2) - (height / 2))
    window.geometry(f"{width}x{height}+{x}+{y}")

class DuplicateFinderApp(ctk.CTk):
    def __init__(self, folder=None, hw="cpu", mode="both", threads=0):
        super().__init__()
        self.title("Buscador de Duplicados y Multimedia Dañada")
        center_window(self, 900, 700)
        
        def set_icon():
            try:
                self.iconbitmap(get_resource_path("app_icon.ico"))
            except:
                pass
        self.after(200, set_icon)
        
        self.selected_folder = folder or ""
        self.hw_mode = hw
        self.search_mode = mode
        self.max_threads = threads if threads > 0 else (os.cpu_count() or 4)
        
        self.results = []
        self.checkboxes = []
        self.is_scanning = False
        
        # UI Setup
        self.setup_ui()
        
        if self.selected_folder:
            self.lbl_folder.configure(text=self.selected_folder)
            self.btn_select.configure(state="disabled")
            self.after(100, self.start_scan)

    def setup_ui(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # Top Frame
        top_frame = ctk.CTkFrame(self)
        top_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        
        self.btn_select = ctk.CTkButton(top_frame, text="Seleccionar Carpeta", command=self.select_folder)
        self.btn_select.pack(side="left", padx=10, pady=10)
        
        self.lbl_folder = ctk.CTkLabel(top_frame, text="Ninguna carpeta seleccionada")
        self.lbl_folder.pack(side="left", padx=10, pady=10)
        
        self.btn_scan = ctk.CTkButton(top_frame, text="Escanear", command=self.start_scan, state="disabled")
        self.btn_scan.pack(side="right", padx=10, pady=10)
        
        self.btn_stop = ctk.CTkButton(top_frame, text="Detener", command=self.stop_scan, state="disabled", fg_color="darkred", hover_color="red")
        self.btn_stop.pack(side="right", padx=10, pady=10)
        
        # Center Frame - Scrollable Results
        self.scroll_frame = ctk.CTkScrollableFrame(self)
        self.scroll_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        
        # Bottom Frame
        bottom_frame = ctk.CTkFrame(self)
        bottom_frame.grid(row=2, column=0, padx=10, pady=10, sticky="ew")
        
        self.lbl_status = ctk.CTkLabel(bottom_frame, text="Listo.")
        self.lbl_status.pack(side="left", padx=10, pady=10)
        
        self.btn_move_all = ctk.CTkButton(bottom_frame, text="Mover TODOS (Rápido)", command=self.move_all, state="disabled", fg_color="darkred", hover_color="red")
        self.btn_move_all.pack(side="right", padx=10, pady=10)
        
        self.btn_move = ctk.CTkButton(bottom_frame, text="Mover Visibles", command=self.move_selected, state="disabled")
        self.btn_move.pack(side="right", padx=10, pady=10)
        
        self.chk_select_all = ctk.CTkCheckBox(bottom_frame, text="Seleccionar Visibles", command=self.toggle_all_visible, state="disabled")
        self.chk_select_all.pack(side="right", padx=20, pady=10)
        
        self.progress_bar = ctk.CTkProgressBar(bottom_frame, mode="determinate")
        self.progress_bar.pack(side="bottom", fill="x", padx=10, pady=5)
        self.progress_bar.set(0)
        self.progress_bar.pack_forget() # Hide initially

    def select_folder(self):
        folder = filedialog.askdirectory()
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
        self.progress_bar.pack(side="bottom", fill="x", padx=10, pady=5)
        self.progress_bar.set(0)
        
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
            
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
        self.progress_bar.set(current / total if total > 0 else 0)
        self.lbl_status.configure(text=msg)

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
        # Matches suffixes like " - copia", "_copy", " (1)". Limitamos a 2 digitos en parentesis para evitar secuencias largas (ej. 13209)
        pattern = r'([-_ ]+(copia|copy)\b[-_ ]*\d*|[-_ ]+\(\d{1,2}\))+$'
        base = re.sub(pattern, '', stem, flags=re.IGNORECASE).strip()
        return base if base else stem

    def toggle_all_visible(self):
        new_val = self.chk_select_all.get()
        # Only toggle those that are rendered
        for item in self.all_suspects[:max(100, self.rendered_count)]:
            if "checkbox_var" in item:
                item["checkbox_var"].set(new_val)

    def check_corruption(self, filepath):
        ext = filepath.suffix.lower()
        if ext in [".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"]:
            try:
                img = Image.open(filepath)
                img.verify() # verify integrity
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
            # Check with ffprobe if ffmpeg is available
            try:
                ffmpeg_exe = Path(get_resource_path(os.path.join("tools", "ffmpeg.exe")))
                if not ffmpeg_exe.exists():
                    return False # Can't check
                
                cmd = [str(ffmpeg_exe), "-v", "error"]
                if self.hw_mode == "nvenc":
                    cmd.extend(["-hwaccel", "cuda"])
                elif self.hw_mode == "amf":
                    cmd.extend(["-hwaccel", "dxva2"])
                elif self.hw_mode == "auto":
                    cmd.extend(["-hwaccel", "auto"])
                    
                cmd.extend(["-i", str(filepath), "-f", "null", "-"])
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
                if result.returncode != 0:
                    if self.hw_mode in ["nvenc", "amf", "auto"]:
                        fallback_cmd = [str(ffmpeg_exe), "-v", "error", "-i", str(filepath), "-f", "null", "-"]
                        result_fb = subprocess.run(fallback_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
                        if result_fb.returncode != 0:
                            return True
                        return False
                    return True
                return False
            except Exception:
                return False
        return False

    def extract_thumbnail(self, filepath):
        ext = filepath.suffix.lower()
        size = (100, 100)
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
                    # Usamos CPU y saltamos 1 segundo para evitar fotogramas negros
                    cmd = [str(ffmpeg_exe), "-y", "-ss", "1", "-i", str(filepath), "-vframes", "1", "-vf", "scale=100:-1", str(out_jpg)]
                    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
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
            # Ignorar carpetas de destino para que no se re-escaneen de forma insensible a mayúsculas
            dirs[:] = [d for d in dirs if d.lower() not in ("archivos_duplicados", "archivos_dañados")]
                
            for f in files:
                all_files.append(Path(root) / f)
        
        total_files = len(all_files)
        if total_files == 0:
            self.after(0, self.finish_scan, [])
            return

        # Fase 1: Agrupar por tamaño (muy rápido) y por nombre base
        size_dict = {}
        name_dict = {}
        
        for i, f in enumerate(all_files):
            if not self.is_scanning:
                break
            if i % 100 == 0:
                self.after(0, self.update_progress, i, total_files, f"Fase 1/2: Buscando archivos... ({i}/{total_files})")
            try:
                s = f.stat().st_size
                if s not in size_dict:
                    size_dict[s] = []
                size_dict[s].append(f)
                
                if self.search_mode in ["both", "name"]:
                    base_name = self.get_base_name(f)
                    name_key = (base_name, f.suffix.lower())
                    if name_key not in name_dict:
                        name_dict[name_key] = []
                    name_dict[name_key].append(f)
            except Exception:
                pass
                
        # Procesar duplicados por nombre
        name_duplicates = set()
        name_originals = set()
        if self.search_mode in ["both", "name"]:
            for g in name_dict.values():
                if len(g) > 1:
                    g_sorted = sorted(g, key=lambda x: len(x.name))
                    name_originals.add(g_sorted[0])
                    for d in g_sorted[1:]:
                        name_duplicates.add(d)
                
        # Preparar grupos para la Fase 2
        groups = list(size_dict.values())
        
        # Helper function para procesar un grupo entero (por tamaño)
        def process_group(files_in_group):
            if not self.is_scanning:
                return 0, []
                
            needs_hash = len(files_in_group) > 1 and self.search_mode in ["both", "hash"]
            group_results = []
            
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
                    if h not in hash_dict:
                        hash_dict[h] = []
                    hash_dict[h].append(fpath)
            
            # Identificar sospechosos en este grupo
            suspects = []
            for h, h_files in hash_dict.items():
                if len(h_files) > 1:
                    h_files = sorted(h_files, key=lambda x: len(x.name))
                    is_c = any(f == h_files[0] for f, _ in corrupt_files)
                    suspects.append({"path": h_files[0], "status": "Original (Dañado)" if is_c else "Original", "hash": h, "group_key": h})
                    for d_file in h_files[1:]:
                        is_c_d = any(f == d_file for f, _ in corrupt_files)
                        suspects.append({"path": d_file, "status": "Duplicado (Dañado)" if is_c_d else "Duplicado", "hash": h, "group_key": h})
                        
            # Añadir duplicados por nombre y archivos dañados
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
                    
            # Extraer miniaturas de los sospechosos encontrados
            for s in suspects:
                if not self.is_scanning:
                    break
                s["thumb"] = self.extract_thumbnail(s["path"])
                
            return len(files_in_group), suspects

        processed = 0
        found_suspects_count = 0
        self.btn_load_more = ctk.CTkButton(self.scroll_frame, text="Cargar 100 más...", command=self.load_more)
        
        # Iniciar Pool para procesar los grupos en paralelo
        with ThreadPoolExecutor(max_workers=self.max_threads) as executor:
            futures = {executor.submit(process_group, g): g for g in groups}
            for future in as_completed(futures):
                if not self.is_scanning:
                    continue # Skip processing remaining results if stopped
                    
                count_processed, suspects = future.result()
                processed += count_processed
                
                # Actualizar barra de progreso
                self.after(0, self.update_progress, processed, total_files, f"Fase 2/2: Analizando y extrayendo miniaturas... ({processed}/{total_files})")
                
                # Si hay sospechosos, los renderizamos de inmediato en la UI
                if suspects:
                    found_suspects_count += len(suspects)
                    self.after(0, self._render_suspects_chunk, suspects)

        self.is_scanning = False
        self.after(0, self._finish_scan_ui, found_suspects_count)

    def _render_suspects_chunk(self, suspects):
        self.btn_load_more.pack_forget() # Ocultar temporalmente si estaba visible
        
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
        frame = ctk.CTkFrame(self.scroll_frame)
        frame.pack(fill="x", pady=2, padx=5)
        
        var = ctk.IntVar(value=1 if "Duplicado" in item["status"] or "Dañado" in item["status"] else 0)
        cb = ctk.CTkCheckBox(frame, text="", variable=var, width=30)
        cb.pack(side="left", padx=5)
        
        # Guardar referencia global en all_suspects para poder moverlos después
        item["checkbox_var"] = var 
        self.checkboxes.append((var, item["path"]))
        
        pil_img = item.get("thumb")
        if pil_img:
            # Mantener referencia a CTkImage en el widget
            ctk_img = ctk.CTkImage(light_image=pil_img, size=(100, 100))
            lbl_img = ctk.CTkLabel(frame, image=ctk_img, text="")
            lbl_img.image = ctk_img # Referencia fuerte
            lbl_img.pack(side="left", padx=5)
        else:
            lbl_img = ctk.CTkLabel(frame, text="Sin vista", width=100)
            lbl_img.pack(side="left", padx=5)
            
        info_text = f"[{item['status']}] {item['path'].name}\nRuta: {item['path']}"
        lbl_info = ctk.CTkLabel(frame, text=info_text, justify="left", anchor="w")
        lbl_info.pack(side="left", fill="x", expand=True, padx=10)

    def _finish_scan_ui(self, count):
        self.progress_bar.pack_forget()
        self.btn_stop.configure(state="disabled")
        
        # Ordenar all_suspects para agrupar Originales con sus Duplicados correspondientes
        # Ordenamos por: group_key, y luego si es Original (para que queden arriba del grupo)
        self.all_suspects.sort(key=lambda x: (str(x.get("group_key", "")), not x["status"].startswith("Original"), x["path"].name))
        
        self.lbl_status.configure(text=f"Escaneo finalizado. {len(self.all_suspects)} archivos sospechosos/duplicados encontrados.")
        self.btn_select.configure(state="normal")
        self.btn_scan.configure(state="normal")
        
        if len(self.all_suspects) > 0:
            self.btn_move.configure(state="normal")
            self.btn_move_all.configure(state="normal")
            self.chk_select_all.configure(state="normal")
            self.chk_select_all.deselect()
            self._refresh_ui()
        else:
            # Refresh to show empty UI
            self.chk_select_all.configure(state="disabled")
            self._refresh_ui()

    def move_all(self):
        dest_dupes = Path(self.selected_folder) / "Archivos_Duplicados"
        dest_damaged = Path(self.selected_folder) / "Archivos_Dañados"
        moved_count = 0
        
        print("=== REPORTE DE ARCHIVOS MULTIMEDIA MOVIDOS ===")
        
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
                    if not dest_folder.exists():
                        dest_folder.mkdir(parents=True)
                    shutil.move(str(filepath), str(dest_folder / filepath.name))
                    moved_count += 1
                    print(f"MOVIDO: [{item['status']}] {filepath.name} -> {dest_folder.name}")
                except Exception as e:
                    print(f"ERROR al mover {filepath.name}: {e}")
                    items_to_keep.append(item)
            else:
                items_to_keep.append(item)
                
        print(f"=== TOTAL MOVIDO: {moved_count} archivos ===\n")
                
        self.all_suspects = items_to_keep
        messagebox.showinfo("Completado", f"Se han movido {moved_count} archivos en total.")
        self._refresh_ui()

    def move_selected(self):
        dest_dupes = Path(self.selected_folder) / "Archivos_Duplicados"
        dest_damaged = Path(self.selected_folder) / "Archivos_Dañados"
        moved_count = 0
        
        print("=== REPORTE DE ARCHIVOS MULTIMEDIA VISIBLES MOVIDOS ===")
        items_to_keep = []
        
        # Mover SOLO los archivos que están renderizados y marcados
        for item in self.all_suspects:
            if "checkbox_var" in item:
                if item["checkbox_var"].get() == 1:
                    filepath = item["path"]
                    is_damaged = "Dañado" in item["status"]
                    dest_folder = dest_damaged if is_damaged else dest_dupes
                    
                    try:
                        if not dest_folder.exists():
                            dest_folder.mkdir(parents=True)
                        shutil.move(str(filepath), str(dest_folder / filepath.name))
                        moved_count += 1
                        print(f"MOVIDO: [{item['status']}] {filepath.name} -> {dest_folder.name}")
                    except Exception as e:
                        print(f"ERROR al mover {filepath.name}: {e}")
                        items_to_keep.append(item) 
            else:
                items_to_keep.append(item)
                
        print(f"=== TOTAL MOVIDO: {moved_count} archivos ===\n")
        
        self.all_suspects = items_to_keep
        messagebox.showinfo("Completado", f"Se han movido {moved_count} archivos.")
        self._refresh_ui()
        
    def _refresh_ui(self):
        # Limpiar la ventana actual (excepto el botón de cargar más)
        for widget in self.scroll_frame.winfo_children():
            if widget != self.btn_load_more:
                widget.destroy()
            
        self.checkboxes = []
        self.btn_load_more.pack_forget()
        
        # Mantener el ritmo de carga (si había 200 cargados, cargamos 200 de los nuevos)
        target_render_count = max(100, self.rendered_count)
        self.rendered_count = 0
        
        # Cargar los siguientes elementos
        for item in self.all_suspects[:target_render_count]:
            item.pop("checkbox_var", None) # Limpiar variable vieja por si acaso
            self._render_single_item(item)
            
        if len(self.all_suspects) > self.rendered_count:
            self.btn_load_more.pack(side="bottom", pady=10)
            
        # Actualizar botón inferior
        self.btn_move.configure(text=f"Mover Visibles ({self.rendered_count})")
        self.lbl_status.configure(text=f"Archivos restantes por revisar: {len(self.all_suspects)}")
        
        if len(self.all_suspects) == 0:
            self.lbl_status.configure(text="¡Revisión completada! No hay más archivos sospechosos.")
            self.btn_move.configure(state="disabled")
            self.btn_move_all.configure(state="disabled")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", nargs="?", default="")
    parser.add_argument("--hw", default="cpu")
    parser.add_argument("--mode", default="both")
    parser.add_argument("--threads", type=int, default=0)
    args = parser.parse_args()

    ctk.set_appearance_mode("Dark")
    app = DuplicateFinderApp(folder=args.folder, hw=args.hw, mode=args.mode, threads=args.threads)
    app.mainloop()
