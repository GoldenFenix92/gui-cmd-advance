import os
import threading
import urllib.request
import zipfile
import shutil
import json
import customtkinter as ctk
from tkinter import messagebox
from functions.utils import get_user_data_path, apply_window_theme

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
        "cmds": []
    },
    "ffmpeg": {
        "id": "ffmpeg",
        "name": "FFmpeg (Motor Multimedia)",
        "filename": "ffmpeg.exe",
        "desc": "Habilita: Compresor, Reparador y Buscador de duplicados (video).",
        "url": "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip",
        "is_zip": True,
        "zip_target": "ffmpeg.exe",
        "size_str": "~35MB",
        "cmds": ["__INTERNAL__ --run-compressor", "__INTERNAL__ --run-duplicate-finder", "__INTERNAL__ --run-media-repair"]
    },
    "odt": {
        "id": "odt",
        "name": "Office Deployment Tool (ODT)",
        "filename": "setup.exe",
        "desc": "Habilita: Descarga e instalación de Microsoft Office.",
        "url": "https://github.com/GoldenFenix92/gui-cmd-advance/raw/main/tools/setup.exe",
        "is_zip": False,
        "size_str": "~7MB",
        "cmds": ["__INTERNAL__ --run-office-deploy"]
    },
    "7zip": {
        "id": "7zip",
        "name": "7-Zip (Motor Avanzado)",
        "filename": "7za.exe",
        "desc": "Habilita: Compresión/Descompresión ultra-rápida y formato .7z.",
        "url": "https://github.com/GoldenFenix92/gui-cmd-advance/raw/main/tools/7za.exe",
        "is_zip": False,
        "size_str": "~1MB",
        "cmds": []
    },
    "winrar": {
        "id": "winrar",
        "name": "WinRAR (CLI)",
        "filename": "rar.exe",
        "desc": "Habilita: Formato .rar y reparación avanzada con volúmenes de recuperación. Descarga e instala WinRAR normalmente.",
        "url": "https://www.win-rar.com/download.html",
        "is_zip": False,
        "is_browser_link": True,
        "size_str": "~3MB",
        "cmds": [],
        "check_paths": [
            r"C:\Program Files\WinRAR\WinRAR.exe",
            r"C:\Program Files (x86)\WinRAR\WinRAR.exe"
        ]
    }
}

class PluginInstaller(ctk.CTkToplevel):
    def __init__(self, master, plugin_id, on_complete_callback=None):
        super().__init__(master)
        self.plugin = PLUGINS[plugin_id]
        self.title(f"Instalando {self.plugin['name']}")
        self.geometry("500x350")
        self.transient(master)
        self.grab_set()
        self.on_complete_callback = on_complete_callback
        
        self.update_idletasks()
        x = int(master.winfo_x() + (master.winfo_width() / 2) - (500 / 2))
        y = int(master.winfo_y() + (master.winfo_height() / 2) - (350 / 2))
        self.geometry(f"+{x}+{y}")
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        
        apply_window_theme(self)
        lbl_title = ctk.CTkLabel(self, text=f"Descargando {self.plugin['name']}", font=("Arial", 16, "bold"))
        lbl_title.pack(pady=(20, 10))
        
        self.progress_var = ctk.DoubleVar(value=0)
        self.progress_bar = ctk.CTkProgressBar(self, variable=self.progress_var)
        self.progress_bar.pack(pady=(10, 0), padx=20, fill="x")
        
        self.lbl_status = ctk.CTkLabel(self, text="Iniciando descarga...")
        self.lbl_status.pack(pady=10)
        
        self.btn_cancel = ctk.CTkButton(self, text="Cancelar", fg_color="gray", command=self.cancel)
        self.btn_cancel.pack(pady=10)
        
        self.is_cancelled = False
        threading.Thread(target=self._download_and_extract, daemon=True).start()

    def cancel(self):
        self.is_cancelled = True
        if self.on_complete_callback:
            self.on_complete_callback(False)
        self.destroy()

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
                self.lbl_status.configure(text="¡Bóveda creada exitosamente!")
                self.btn_cancel.configure(text="Cerrar", command=self.finish_success)
                self.after(1000, self.finish_success)
                return
                
            if self.plugin.get("is_browser_link"):
                import webbrowser
                webbrowser.open(url)
                self.lbl_status.configure(text="Instala el programa desde tu navegador.")
                self.btn_cancel.configure(text="Entendido", command=self.finish_success)
                return

            def report(blocknum, blocksize, totalsize):
                if self.is_cancelled:
                    raise Exception("Cancelado por el usuario")
                readsofar = blocknum * blocksize
                if totalsize > 0:
                    percent = readsofar / totalsize
                    self.progress_var.set(percent)
            
            urllib.request.urlretrieve(url, temp_file, reporthook=report)
            
            if self.plugin["is_zip"]:
                self.lbl_status.configure(text="Extrayendo archivos...")
                self.progress_var.set(0)
                with zipfile.ZipFile(temp_file, 'r') as zip_ref:
                    for file_info in zip_ref.infolist():
                        if file_info.filename.endswith(self.plugin["zip_target"]):
                            file_info.filename = self.plugin["filename"]
                            zip_ref.extract(file_info, tools_dir)
                            break
                os.remove(temp_file)
            else:
                shutil.move(temp_file, final_file)
            
            self.lbl_status.configure(text="¡Instalación completada!")
            self.btn_cancel.configure(text="Cerrar", command=self.finish_success)
            self.after(1000, self.finish_success)
            
        except Exception as e:
            if not self.is_cancelled:
                self.lbl_status.configure(text=f"Error: {str(e)}")

    def finish_success(self):
        if self.on_complete_callback:
            self.on_complete_callback(True)
        self.destroy()

class StartupCheck(ctk.CTkToplevel):
    def __init__(self, master, missing_plugins, on_complete):
        super().__init__(master)
        self.title("Complementos Faltantes")
        self.geometry("500x400")
        self.transient(master)
        self.grab_set()
        self.on_complete = on_complete
        
        self.update_idletasks()
        x = int(master.winfo_x() + (master.winfo_width() / 2) - (500 / 2))
        y = int(master.winfo_y() + (master.winfo_height() / 2) - (400 / 2))
        self.geometry(f"+{x}+{y}")
        self.protocol("WM_DELETE_WINDOW", self.close)
        
        apply_window_theme(self)
        lbl = ctk.CTkLabel(self, text="Para mantener la app ligera, algunos componentes no vienen incluidos. Algunas funciones estarán bloqueadas hasta que los instales.", wraplength=450, justify="left")
        lbl.pack(pady=10, padx=20)
        
        frame = ctk.CTkScrollableFrame(self)
        frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        for pid in missing_plugins:
            p = PLUGINS[pid]
            row = ctk.CTkFrame(frame)
            row.pack(fill="x", pady=5)
            ctk.CTkLabel(row, text=f"{p['name']} ({p['size_str']})", font=("Arial", 12, "bold")).pack(anchor="w", padx=10, pady=(5,0))
            ctk.CTkLabel(row, text=p['desc'], text_color="gray").pack(anchor="w", padx=10)
            
            def install_p(plugin_id=pid):
                def on_done(success):
                    if success:
                        self.close()
                PluginInstaller(self, plugin_id, on_done)
                
            ctk.CTkButton(row, text="Instalar", width=80, command=install_p).pack(anchor="e", padx=10, pady=5)
            
        self.dont_show_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(self, text="No volver a mostrar en el inicio", variable=self.dont_show_var).pack(pady=10)
        
        ctk.CTkButton(self, text="Continuar en Modo Lite", command=self.close).pack(pady=(0, 20))

    def close(self):
        if self.dont_show_var.get():
            with open(get_user_data_path("hide_startup_plugins.json"), "w") as f:
                json.dump({"hide": True}, f)
        self.on_complete()
        self.destroy()

def is_plugin_installed(p):
    if "check_paths" in p:
        for path in p["check_paths"]:
            if os.path.exists(path):
                return True
        return False
    else:
        return os.path.exists(get_user_data_path(os.path.join("tools", p["filename"])))

def check_dependencies(app):
    hide_path = get_user_data_path("hide_startup_plugins.json")
    missing = []
    for pid, p in PLUGINS.items():
        if not is_plugin_installed(p):
            missing.append(pid)
            
    if os.path.exists(hide_path):
        app.disable_missing_features()
        return
        
    if missing:
        StartupCheck(app, missing, lambda: app.disable_missing_features())
    else:
        app.disable_missing_features()

def get_missing_commands():
    missing_cmds = []
    for pid, p in PLUGINS.items():
        if not is_plugin_installed(p):
            missing_cmds.extend(p["cmds"])
    return missing_cmds
