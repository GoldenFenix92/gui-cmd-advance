import json
import os
import shutil
import threading
import tkinter as tk
import urllib.request
import zipfile
import ttkbootstrap as tb
from ttkbootstrap.widgets.floodgauge import Floodgauge
from ttkbootstrap.widgets.scrolled import ScrolledFrame
from functions.utils import get_user_data_path
from functions import ui_theme

PLUGINS = {
    "ai_vault": {
        "id": "ai_vault",
        "name": "Bóveda IA (Configuración Premium)",
        "filename": "ai_settings.json",
        "desc": "Archivo local para configurar y guardar de manera confidencial tus claves API y configuración de modelos de IA.",
        "url": "",
        "is_zip": False,
        "is_local_config": True,
        "size_str": "~1KB",
        "cmds": [],
    },
    "ffmpeg": {
        "id": "ffmpeg",
        "name": "FFmpeg (Motor Multimedia)",
        "filename": "ffmpeg.exe",
        "desc": "Habilita: Compresor, Reparador, Estudio de Video/Audio y Buscador de duplicados (incluye ffmpeg.exe y ffprobe.exe).",
        "url": "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip",
        "is_zip": True,
        "zip_target": "ffmpeg.exe",
        "zip_targets": ["ffmpeg.exe", "ffprobe.exe"],
        "size_str": "~35MB",
        "cmds": [
            "__INTERNAL__ --run-compressor",
            "__INTERNAL__ --run-duplicate-finder",
            "__INTERNAL__ --run-media-repair",
            "__INTERNAL__ --run-media-studio",
            "__INTERNAL__ --run-video-trimmer",
        ],
    },
    "ffmpeg_skill": {
        "id": "ffmpeg_skill",
        "name": "FFmpeg Skill (42 Herramientas Avanzadas)",
        "filename": os.path.join("ffmpeg-skill", "scripts", "_contract.py"),
        "desc": "Complemento avanzado bajo demanda (kajisho5/ffmpeg-skill, MIT): quitar silencios, estabilizar video, quemar subtítulos SRT y exportar por plantillas (TikTok, Reels, Shorts, YouTube).",
        "url": "https://github.com/kajisho5/ffmpeg-skill/archive/refs/heads/main.zip",
        "is_zip": True,
        "is_zip_bundle": True,
        "bundle_dir": "ffmpeg-skill",
        "bundle_include": ("scripts/", "templates/", "references/", "SKILL.md", "LICENSE"),
        "size_str": "~3MB",
        "cmds": ["__INTERNAL__ --run-ffmpeg-skill"],
    },
    "odt": {
        "id": "odt",
        "name": "Office Deployment Tool (ODT)",
        "filename": "setup.exe",
        "desc": "Habilita: Descarga e instalación de Microsoft Office.",
        "url": "https://github.com/GoldenFenix92/gui-cmd-advance/raw/main/tools/setup.exe",
        "is_zip": False,
        "size_str": "~7MB",
        "cmds": ["__INTERNAL__ --run-office-deploy"],
    },
    "7zip": {
        "id": "7zip",
        "name": "7-Zip (Motor Avanzado)",
        "filename": "7za.exe",
        "desc": "Habilita: Compresión/Descompresión ultra-rápida y formato .7z.",
        "url": "https://github.com/GoldenFenix92/gui-cmd-advance/raw/main/tools/7za.exe",
        "is_zip": False,
        "size_str": "~1MB",
        "cmds": ["__INTERNAL__ --run-7z"],
    },
    "sdelete": {
        "id": "sdelete",
        "name": "Sysinternals SDelete (Borrado Seguro)",
        "filename": "sdelete64.exe",
        "desc": "Habilita: Borrado seguro irreversible de archivos/carpetas y sanitización de espacio libre (Microsoft Sysinternals).",
        "url": "https://download.sysinternals.com/files/SDelete.zip",
        "is_zip": True,
        "zip_target": "sdelete64.exe",
        "size_str": "~500KB",
        "cmds": ["__INTERNAL__ --run-sdelete"],
    },
}


def extract_plugin_zip(zip_path, plugin, tools_dir):
    """Extrae uno o varios binarios o un paquete filtrado (zip_bundle) de forma segura sin path traversal."""
    os.makedirs(tools_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        if plugin.get("is_zip_bundle"):
            bundle_root = os.path.abspath(os.path.join(tools_dir, plugin["bundle_dir"]))
            if os.path.isdir(bundle_root):
                shutil.rmtree(bundle_root, ignore_errors=True)
            os.makedirs(bundle_root, exist_ok=True)
            allowed = tuple(plugin.get("bundle_include") or ())
            extracted = 0

            for info in zip_ref.infolist():
                if info.is_dir():
                    continue
                norm_name = info.filename.replace("\\", "/").lstrip("/")
                # Quitar la carpeta raíz del archivo ZIP de GitHub (ej. ffmpeg-skill-main/)
                parts = norm_name.split("/", 1)
                rel = parts[1] if len(parts) == 2 else parts[0]
                if not rel or ".." in rel.split("/"):
                    continue
                if allowed and not any(rel == item or rel.startswith(item) for item in allowed):
                    continue

                dest_path = os.path.abspath(os.path.join(bundle_root, *rel.split("/")))
                if not dest_path.startswith(bundle_root + os.sep):
                    continue
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                with zip_ref.open(info, "r") as src_f, open(dest_path, "wb") as dst_f:
                    shutil.copyfileobj(src_f, dst_f)
                extracted += 1
            return extracted

        targets = list(plugin.get("zip_targets") or [])
        if not targets and plugin.get("zip_target"):
            targets = [plugin["zip_target"]]

        extracted = 0
        remaining = set(targets)
        for info in zip_ref.infolist():
            if info.is_dir():
                continue
            base = os.path.basename(info.filename.replace("\\", "/"))
            if base in remaining:
                out_name = plugin["filename"] if len(targets) == 1 else base
                dest_path = os.path.join(tools_dir, out_name)
                with zip_ref.open(info, "r") as src_f, open(dest_path, "wb") as dst_f:
                    shutil.copyfileobj(src_f, dst_f)
                remaining.discard(base)
                extracted += 1
                if not remaining:
                    break
        return extracted


class PluginInstaller(tb.Toplevel):
    def __init__(self, master, plugin_id, on_complete_callback=None):
        super().__init__(master)
        self.plugin = PLUGINS[plugin_id]
        self.title(f"Instalando {self.plugin['name']}")
        self.geometry("500x300")
        self.transient(master)
        self.grab_set()
        self.on_complete_callback = on_complete_callback

        self.update_idletasks()
        x = int(master.winfo_x() + (master.winfo_width() / 2) - 250)
        y = int(master.winfo_y() + (master.winfo_height() / 2) - 150)
        self.geometry(f"+{x}+{y}")
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        ui_theme.apply_window_chrome(self)

        lbl_title = tb.Label(self, text=f"Descargando {self.plugin['name']}", font=("Segoe UI", 13, "bold"), bootstyle="primary")
        lbl_title.pack(pady=(22, 12))

        self.progress_bar = Floodgauge(self, maximum=100, value=0, mask="{}%", bootstyle="info")
        self.progress_bar.pack(pady=(8, 4), padx=24, fill="x")

        self.lbl_status = tb.Label(self, text="Iniciando descarga...", font=("Segoe UI", 10))
        self.lbl_status.pack(pady=10)

        self.btn_cancel = tb.Button(self, text="Cancelar", bootstyle="secondary", command=self.cancel, width=16)
        self.btn_cancel.pack(pady=10)

        self.is_cancelled = False
        ui_theme.bring_to_front(self)
        threading.Thread(target=self._download_and_extract, daemon=True).start()

    def cancel(self):
        self.is_cancelled = True
        if self.on_complete_callback:
            self.on_complete_callback(False)
        self.destroy()

    def _safe_ui(self, fn):
        try:
            if self.winfo_exists():
                self.after(0, fn)
        except Exception:
            pass

    def _download_and_extract(self):
        url = self.plugin["url"]
        tools_dir = get_user_data_path("tools")
        os.makedirs(tools_dir, exist_ok=True)
        temp_file = get_user_data_path(f"temp_{self.plugin['id']}.tmp")
        final_file = os.path.join(tools_dir, self.plugin["filename"])

        try:
            if self.plugin.get("is_local_config"):
                with open(final_file, "w", encoding="utf-8") as f:
                    f.write("{}")
                self._safe_ui(lambda: self.progress_bar.configure(value=100, bootstyle="success"))
                self._safe_ui(lambda: self.lbl_status.configure(text="Bóveda creada exitosamente."))
                self._safe_ui(lambda: self.btn_cancel.configure(text="Cerrar", command=self.finish_success, bootstyle="success"))
                self.after(900, self.finish_success)
                return

            if self.plugin.get("is_browser_link"):
                import webbrowser
                webbrowser.open(url)
                self._safe_ui(lambda: self.lbl_status.configure(text="Instala el programa desde tu navegador."))
                self._safe_ui(lambda: self.btn_cancel.configure(text="Entendido", command=self.finish_success))
                return

            def report(blocknum, blocksize, totalsize):
                if self.is_cancelled:
                    raise Exception("Cancelado por el usuario")
                readsofar = blocknum * blocksize
                if totalsize > 0:
                    pct = min(100, int((readsofar / totalsize) * 100))
                    self._safe_ui(lambda p=pct: self.progress_bar.configure(value=p))

            urllib.request.urlretrieve(url, temp_file, reporthook=report)

            if self.plugin["is_zip"]:
                self._safe_ui(lambda: self.lbl_status.configure(text="Extrayendo archivos..."))
                count = extract_plugin_zip(temp_file, self.plugin, tools_dir)
                os.remove(temp_file)
                if count <= 0:
                    raise RuntimeError("No se encontraron los archivos esperados dentro del paquete ZIP.")
            else:
                shutil.move(temp_file, final_file)

            self._safe_ui(lambda: self.progress_bar.configure(value=100, bootstyle="success"))
            self._safe_ui(lambda: self.lbl_status.configure(text="Instalación completada."))
            self._safe_ui(lambda: self.btn_cancel.configure(text="Cerrar", command=self.finish_success, bootstyle="success"))
            self.after(900, self.finish_success)

        except Exception as e:
            if not self.is_cancelled:
                err_txt = f"Error: {str(e)}"
                self._safe_ui(lambda m=err_txt: self.lbl_status.configure(text=m, bootstyle="danger"))

    def finish_success(self):
        if self.on_complete_callback:
            self.on_complete_callback(True)
        self.destroy()


class StartupCheck(tb.Toplevel):
    def __init__(self, master, missing_plugins, on_complete):
        super().__init__(master)
        self.title("Complementos Faltantes")
        self.geometry("560x440")
        self.transient(master)
        self.grab_set()
        self.on_complete = on_complete

        self.update_idletasks()
        x = int(master.winfo_x() + (master.winfo_width() / 2) - 280)
        y = int(master.winfo_y() + (master.winfo_height() / 2) - 220)
        self.geometry(f"+{x}+{y}")
        self.protocol("WM_DELETE_WINDOW", self.close)
        ui_theme.apply_window_chrome(self)

        lbl = tb.Label(
            self,
            text="Para mantener la app ligera, algunos componentes se descargan bajo demanda. Algunas funciones estarán bloqueadas hasta que los instales.",
            wraplength=510,
            justify="left",
        )
        lbl.pack(pady=(14, 8), padx=18)

        frame = ScrolledFrame(self, auto_hide=True, padding=6)
        frame.pack(fill="both", expand=True, padx=16, pady=6)

        for pid in missing_plugins:
            p = PLUGINS[pid]
            row = tb.Labelframe(frame, text=f"{p['name']} ({p['size_str']})", padding=8, bootstyle="secondary")
            row.pack(fill="x", pady=5, padx=2)
            tb.Label(row, text=p["desc"], wraplength=420, bootstyle="secondary").pack(side="left", fill="x", expand=True)

            def install_p(plugin_id=pid):
                def on_done(success):
                    if success:
                        self.close()
                PluginInstaller(self, plugin_id, on_done)

            tb.Button(row, text="Instalar", bootstyle="success", command=install_p, width=10).pack(side="right", padx=(8, 0))

        self.dont_show_var = tk.BooleanVar(value=False)
        tb.Checkbutton(self, text="No volver a mostrar en el inicio", variable=self.dont_show_var, bootstyle="round-toggle").pack(pady=8)

        tb.Button(self, text="Continuar en Modo Lite", command=self.close, bootstyle="primary", width=22).pack(pady=(0, 14))
        ui_theme.bring_to_front(self)

    def close(self):
        if self.dont_show_var.get():
            with open(get_user_data_path("hide_startup_plugins.json"), "w", encoding="utf-8") as f:
                json.dump({"hide": True}, f)
        self.on_complete()
        self.destroy()


def is_plugin_installed(p):
    if "check_paths" in p:
        for path in p["check_paths"]:
            if os.path.exists(path):
                return True
        return False
    return os.path.exists(get_user_data_path(os.path.join("tools", p["filename"])))


def check_dependencies(app):
    hide_path = get_user_data_path("hide_startup_plugins.json")
    missing = [pid for pid, p in PLUGINS.items() if not is_plugin_installed(p)]

    if os.path.exists(hide_path):
        app.disable_missing_features()
        return

    if missing:
        StartupCheck(app, missing, lambda: app.disable_missing_features())
    else:
        app.disable_missing_features()


def get_missing_commands():
    missing_cmds = []
    for _pid, p in PLUGINS.items():
        if not is_plugin_installed(p):
            missing_cmds.extend(p["cmds"])
    return missing_cmds
