import customtkinter as ctk
import os
import shutil
import threading
from gui_app import center_window, get_resource_path
from tkinter import messagebox

class TempCleanerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Limpieza Selectiva de Temporales")
        center_window(self, 800, 600)
        try:
            self.iconbitmap(get_resource_path("resources/app_icon.ico"))
        except: pass
        
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        top_frame = ctk.CTkFrame(self, fg_color="transparent")
        top_frame.grid(row=0, column=0, padx=20, pady=15, sticky="ew")
        ctk.CTkLabel(top_frame, text="🧹 Escáner de Archivos Basura", font=("Arial", 18, "bold")).pack(side="left")
        
        self.btn_scan = ctk.CTkButton(top_frame, text="🔍 Escanear", command=self.scan_temp)
        self.btn_scan.pack(side="right", padx=(10, 0))
        self.btn_clean = ctk.CTkButton(top_frame, text="🗑️ Limpiar Seleccionados", fg_color="#E74C3C", hover_color="#C0392B", command=self.clean_temp)
        self.btn_clean.pack(side="right")
        
        self.scroll_frame = ctk.CTkScrollableFrame(self)
        self.scroll_frame.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        
        self.status_lbl = ctk.CTkLabel(self, text="Listo.", font=("Arial", 12))
        self.status_lbl.grid(row=2, column=0, padx=20, pady=(0, 10), sticky="w")
        
        self.items = []

    def get_targets(self):
        return [
            {"name": "Temp de Usuario", "path": os.environ.get('TEMP', '')},
            {"name": "Temp de Windows", "path": r"C:\Windows\Temp"},
            {"name": "Prefetch", "path": r"C:\Windows\Prefetch"},
            {"name": "SoftwareDistribution (Descargas WinUpdate)", "path": r"C:\Windows\SoftwareDistribution\Download"}
        ]

    def scan_temp(self):
        for w in self.scroll_frame.winfo_children(): w.destroy()
        self.items.clear()
        self.btn_scan.configure(state="disabled")
        self.status_lbl.configure(text="Escaneando...")
        
        def task():
            targets = self.get_targets()
            total_size = 0
            for t in targets:
                size = 0
                count = 0
                path = t["path"]
                if os.path.exists(path):
                    for root, dirs, files in os.walk(path):
                        for f in files:
                            fp = os.path.join(root, f)
                            try:
                                size += os.path.getsize(fp)
                                count += 1
                            except: pass
                
                mb = size / (1024*1024)
                total_size += size
                self.items.append({"name": t["name"], "path": path, "size": size, "mb": mb, "count": count, "var": ctk.BooleanVar(value=True)})
            
            self.after(0, self.update_scan_ui, total_size)
            
        threading.Thread(target=task, daemon=True).start()

    def update_scan_ui(self, total_size):
        for item in self.items:
            row = ctk.CTkFrame(self.scroll_frame, fg_color="#2B2B2B", corner_radius=5)
            row.pack(fill="x", pady=5, padx=5)
            chk = ctk.CTkCheckBox(row, text=f"{item['name']} ({item['count']} archivos) - {item['mb']:.2f} MB", variable=item["var"], font=("Arial", 13))
            chk.pack(side="left", padx=10, pady=10)
            lbl = ctk.CTkLabel(row, text=item["path"], text_color="gray", font=("Consolas", 11))
            lbl.pack(side="right", padx=10)
            
        self.status_lbl.configure(text=f"Escaneo completo. Total basura encontrada: {total_size/(1024*1024):.2f} MB")
        self.btn_scan.configure(state="normal")

    def clean_temp(self):
        selected = [i for i in self.items if i["var"].get() and i["size"] > 0]
        if not selected: return
        
        if not messagebox.askyesno("Confirmar", "¿Eliminar archivos seleccionados?"): return
        
        self.btn_clean.configure(state="disabled")
        self.status_lbl.configure(text="Limpiando...")
        
        def task():
            freed = 0
            for item in selected:
                path = item["path"]
                if os.path.exists(path):
                    for root, dirs, files in os.walk(path, topdown=False):
                        for name in files:
                            fp = os.path.join(root, name)
                            try:
                                size = os.path.getsize(fp)
                                os.remove(fp)
                                freed += size
                            except: pass
                        for name in dirs:
                            dp = os.path.join(root, name)
                            try: os.rmdir(dp)
                            except: pass
            self.after(0, self.clean_done, freed)
            
        threading.Thread(target=task, daemon=True).start()
        
    def clean_done(self, freed):
        self.status_lbl.configure(text=f"Limpieza completa. Espacio liberado: {freed/(1024*1024):.2f} MB")
        self.btn_clean.configure(state="normal")
        messagebox.showinfo("Éxito", f"Se han liberado {freed/(1024*1024):.2f} MB.")
        self.scan_temp()

if __name__ == "__main__":
    app = TempCleanerApp()
    app.mainloop()
