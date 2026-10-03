import os
import threading
import urllib.request
import zipfile
import shutil
import customtkinter as ctk
from functions.utils import get_user_data_path

class SetupManager(ctk.CTkToplevel):
    def __init__(self, master, on_complete_callback=None):
        super().__init__(master)
        self.title("Complemento Faltante")
        self.geometry("500x350")
        self.transient(master)
        self.grab_set()
        self.on_complete_callback = on_complete_callback
        
        # Centrar
        self.update_idletasks()
        x = int(master.winfo_x() + (master.winfo_width() / 2) - (500 / 2))
        y = int(master.winfo_y() + (master.winfo_height() / 2) - (350 / 2))
        self.geometry(f"+{x}+{y}")
        self.protocol("WM_DELETE_WINDOW", self.use_lite_mode)
        
        lbl_title = ctk.CTkLabel(self, text="Falta el Motor Multimedia (FFmpeg)", font=("Arial", 16, "bold"))
        lbl_title.pack(pady=(20, 10))
        
        desc = ("Para mantener la aplicación ligera, el motor multimedia no viene incluido.\n\n"
                "Sin este complemento, las siguientes funciones estarán BLOQUEADAS:\n"
                "❌ Compresor de Multimedia\n"
                "❌ Reparador de Multimedia\n"
                "❌ Buscador de Duplicados (Escaneo de video)\n\n"
                "¿Qué deseas hacer?")
                
        lbl_desc = ctk.CTkLabel(self, text=desc, justify="left", wraplength=450)
        lbl_desc.pack(padx=20, pady=10)
        
        self.progress_var = ctk.DoubleVar(value=0)
        self.progress_bar = ctk.CTkProgressBar(self, variable=self.progress_var)
        self.lbl_status = ctk.CTkLabel(self, text="Esperando...")
        
        self.btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_frame.pack(pady=20)
        
        self.btn_lite = ctk.CTkButton(self.btn_frame, text="Usar Modo Lite", fg_color="gray", command=self.use_lite_mode)
        self.btn_lite.pack(side="left", padx=10)
        
        self.btn_full = ctk.CTkButton(self.btn_frame, text="Descargar Modo Full (~35MB)", fg_color="#F39C12", hover_color="#D68910", command=self.start_download)
        self.btn_full.pack(side="left", padx=10)

    def use_lite_mode(self):
        if self.on_complete_callback:
            self.on_complete_callback(False)
        self.destroy()

    def start_download(self):
        self.btn_lite.configure(state="disabled")
        self.btn_full.configure(state="disabled")
        
        self.progress_bar.pack(pady=(10, 0), padx=20, fill="x")
        self.lbl_status.pack()
        
        threading.Thread(target=self._download_and_extract, daemon=True).start()

    def _download_and_extract(self):
        url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
        # Usamos gpl-shared o un binario más pequeño si fuera posible, pero este sirve.
        temp_zip = get_user_data_path("ffmpeg_temp.zip")
        tools_dir = get_user_data_path("tools")
        os.makedirs(tools_dir, exist_ok=True)
        
        try:
            # Descargar
            self.lbl_status.configure(text="Descargando FFmpeg (esto puede tardar unos minutos)...")
            def report(blocknum, blocksize, totalsize):
                readsofar = blocknum * blocksize
                if totalsize > 0:
                    percent = readsofar / totalsize
                    self.progress_var.set(percent)
            
            urllib.request.urlretrieve(url, temp_zip, reporthook=report)
            
            # Extraer
            self.lbl_status.configure(text="Extrayendo archivos...")
            self.progress_var.set(0) # Indeterminate like
            
            with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
                for file_info in zip_ref.infolist():
                    if file_info.filename.endswith('ffmpeg.exe'):
                        file_info.filename = 'ffmpeg.exe'
                        zip_ref.extract(file_info, tools_dir)
                        break
            
            os.remove(temp_zip)
            
            self.lbl_status.configure(text="¡Instalación completada!")
            self.after(1000, self._finish_success)
            
        except Exception as e:
            self.lbl_status.configure(text=f"Error: {str(e)}")
            self.btn_lite.configure(state="normal")
            self.btn_full.configure(state="normal")
            
    def _finish_success(self):
        if self.on_complete_callback:
            self.on_complete_callback(True)
        self.destroy()

def check_dependencies(app):
    ffmpeg_path = get_user_data_path(os.path.join("tools", "ffmpeg.exe"))
    if not os.path.exists(ffmpeg_path):
        def on_done(success):
            if not success:
                app.disable_multimedia_features()
        SetupManager(app, on_done)
