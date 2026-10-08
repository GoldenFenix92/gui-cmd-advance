import os
import re
import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading

class NameSanitizerApp(ctk.CTkToplevel):
    def __init__(self):
        super().__init__()
        self.title("Sanitizador de Nombres (Windows)")
        self.geometry("600x450")
        
        self.folder_path = ctk.StringVar()
        
        # UI Setup
        ctk.CTkLabel(self, text="Sanitizador de Archivos y Carpetas", font=("Arial", 18, "bold")).pack(pady=10)
        ctk.CTkLabel(self, text="Repara nombres importados de Mac/Linux que Windows marca como corruptos.", text_color="gray").pack(pady=5)
        
        frame = ctk.CTkFrame(self)
        frame.pack(pady=10, padx=20, fill="x")
        
        ctk.CTkEntry(frame, textvariable=self.folder_path, width=400, state="readonly").pack(side="left", padx=10, pady=10)
        ctk.CTkButton(frame, text="Examinar", command=self.browse_folder, width=100).pack(side="left", padx=10)
        
        self.log_box = ctk.CTkTextbox(self, width=560, height=200)
        self.log_box.pack(pady=10, padx=20)
        
        self.btn_run = ctk.CTkButton(self, text="Sanitizar Nombres", command=self.start_sanitization, fg_color="green", hover_color="darkgreen")
        self.btn_run.pack(pady=10)
        
    def browse_folder(self):
        folder = filedialog.askdirectory(title="Selecciona la carpeta a sanitizar")
        if folder:
            self.folder_path.set(folder)
            
    def log(self, msg):
        self.log_box.insert("end", msg + "\n")
        self.log_box.see("end")
        
    def sanitize_name(self, name):
        # Caracteres inválidos en Windows: < > : " / \ | ? *
        invalid_chars = r'[<>:"/\\|?*]'
        new_name = re.sub(invalid_chars, '_', name)
        
        # Windows no permite puntos o espacios al final
        new_name = new_name.rstrip(' .')
        
        if not new_name:
            new_name = "Archivo_Renombrado"
            
        return new_name if new_name != name else None

    def start_sanitization(self):
        folder = self.folder_path.get()
        if not folder or not os.path.isdir(folder):
            messagebox.showerror("Error", "Selecciona una carpeta válida.")
            return
            
        self.btn_run.configure(state="disabled")
        self.log_box.delete("1.0", "end")
        self.log("Iniciando escaneo y reparación...")
        
        threading.Thread(target=self._run_process, args=(folder,), daemon=True).start()
        
    def _run_process(self, folder):
        renamed_count = 0
        error_count = 0
        
        # Renombrar desde abajo hacia arriba (bottom-up) para evitar romper rutas
        for root, dirs, files in os.walk(folder, topdown=False):
            # Archivos
            for name in files:
                new_name = self.sanitize_name(name)
                if new_name:
                    old_path = os.path.join(root, name)
                    new_path = os.path.join(root, new_name)
                    
                    # Manejar duplicados si el nuevo nombre ya existe
                    counter = 1
                    base, ext = os.path.splitext(new_name)
                    while os.path.exists(new_path):
                        new_path = os.path.join(root, f"{base}_{counter}{ext}")
                        counter += 1
                        
                    try:
                        os.rename(old_path, new_path)
                        self.log(f"[OK] Archivo renombrado: {name} -> {os.path.basename(new_path)}")
                        renamed_count += 1
                    except Exception as e:
                        self.log(f"[ERROR] No se pudo renombrar el archivo '{name}': {e}")
                        error_count += 1
                        
            # Carpetas
            for name in dirs:
                new_name = self.sanitize_name(name)
                if new_name:
                    old_path = os.path.join(root, name)
                    new_path = os.path.join(root, new_name)
                    
                    counter = 1
                    while os.path.exists(new_path):
                        new_path = os.path.join(root, f"{new_name}_{counter}")
                        counter += 1
                        
                    try:
                        os.rename(old_path, new_path)
                        self.log(f"[OK] Carpeta renombrada: {name} -> {os.path.basename(new_path)}")
                        renamed_count += 1
                    except Exception as e:
                        self.log(f"[ERROR] No se pudo renombrar la carpeta '{name}': {e}")
                        error_count += 1
                        
        self.log(f"\nProceso finalizado. Total renombrados: {renamed_count}, Errores: {error_count}")
        self.btn_run.configure(state="normal")
