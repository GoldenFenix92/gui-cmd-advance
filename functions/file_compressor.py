import customtkinter as ctk
import os
import sys
import threading
import subprocess
import zipfile
import shutil
import urllib.request
from tkinter import filedialog

class CustomMessageBox(ctk.CTkToplevel):
    def __init__(self, master, title, message, is_error=False):
        super().__init__(master)
        self.title(title)
        self.geometry("400x200")
        self.transient(master)
        self.grab_set()
        
        try:
            from functions.utils import apply_window_theme
            apply_window_theme(self)
        except: pass
        
        self.update_idletasks()
        x = int(master.winfo_x() + (master.winfo_width() / 2) - (400 / 2))
        y = int(master.winfo_y() + (master.winfo_height() / 2) - (200 / 2))
        self.geometry(f"+{x}+{y}")
        
        icon = "❌" if is_error else "✅"
        color = "#E74C3C" if is_error else "#2ECC71"
        
        lbl_icon = ctk.CTkLabel(self, text=icon, font=("Arial", 40), text_color=color)
        lbl_icon.pack(pady=(20, 0))
        
        lbl_msg = ctk.CTkLabel(self, text=message, font=("Arial", 14), wraplength=350, justify="center")
        lbl_msg.pack(pady=10, padx=20, fill="both", expand=True)
        
        btn_ok = ctk.CTkButton(self, text="Aceptar", command=self.destroy, width=100)
        btn_ok.pack(pady=(0, 20))

# Fallback basic zip repair
def repair_zip(input_file, output_file):
    try:
        with open(input_file, 'rb') as f:
            data = f.read()
        
        # Search for PK\x03\x04 (local file header signature)
        idx = data.find(b'PK\x03\x04')
        if idx == -1:
            return False, "No se encontraron firmas ZIP válidas."
        
        with open(output_file, 'wb') as f:
            f.write(data[idx:])
        
        # Try to test the repaired file
        with zipfile.ZipFile(output_file, 'r') as zf:
            bad = zf.testzip()
            if bad:
                return True, f"Reparación parcial (algunos archivos corruptos: {bad})"
        return True, "Reparado exitosamente (cabeceras corregidas)."
    except Exception as e:
        return False, str(e)

class FileCompressorApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Gestor Avanzado de Archivos (ZIP, RAR, 7Z)")
        self.geometry("800x600")
        
        try:
            from functions.utils import apply_window_theme
            apply_window_theme(self)
        except: pass
        
        self.seven_z_path = self.check_7z()
        
        # Tabs
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.tab_comp = self.tabview.add("Comprimir")
        self.tab_ext = self.tabview.add("Descomprimir")
        self.tab_rep = self.tabview.add("Reparar")
        
        self.setup_comp_tab()
        self.setup_ext_tab()
        self.setup_rep_tab()
        
    def check_7z(self):
        from functions.utils import get_user_data_path
        p = get_user_data_path(r"tools\7za.exe")
        if os.path.exists(p): return p
        return None
        
    def setup_comp_tab(self):
        frame = self.tab_comp
        
        ctk.CTkLabel(frame, text="Ruta de Origen (Carpeta o Archivo):").pack(pady=(10,0))
        self.comp_src = ctk.CTkEntry(frame, width=500)
        self.comp_src.pack(pady=5)
        
        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(pady=5)
        ctk.CTkButton(btn_frame, text="Elegir Archivo", command=lambda: self.comp_src.insert(0, filedialog.askopenfilename())).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Elegir Carpeta", command=lambda: self.comp_src.insert(0, filedialog.askdirectory())).pack(side="left", padx=5)
        
        ctk.CTkLabel(frame, text="Destino (Ej. C:\\ruta\\archivo.zip):").pack(pady=(10,0))
        
        dest_frame = ctk.CTkFrame(frame, fg_color="transparent")
        dest_frame.pack(pady=5)
        
        self.comp_dest = ctk.CTkEntry(dest_frame, width=400)
        self.comp_dest.pack(side="left", padx=5)
        
        def pick_dest():
            f = filedialog.asksaveasfilename(defaultextension=".zip", filetypes=[("Archivo ZIP", "*.zip"), ("Archivo 7Z", "*.7z"), ("Todos los archivos", "*.*")])
            if f:
                self.comp_dest.delete(0, ctk.END)
                self.comp_dest.insert(0, f)
                
        ctk.CTkButton(dest_frame, text="Guardar Como...", command=pick_dest, width=100).pack(side="left", padx=5)
        
        ctk.CTkLabel(frame, text="Contraseña (Opcional):").pack(pady=(10,0))
        self.comp_pwd = ctk.CTkEntry(frame, show="*")
        self.comp_pwd.pack(pady=5)
        
        # Tool selector
        self.comp_tool_var = ctk.StringVar(value="nativo")
        tools_frame = ctk.CTkFrame(frame)
        tools_frame.pack(pady=15, padx=20, fill="x")
        ctk.CTkLabel(tools_frame, text="Herramienta a usar:").pack(side="left", padx=10)
        
        r_nat = ctk.CTkRadioButton(tools_frame, text="Nativo (ZIP Básico)", variable=self.comp_tool_var, value="nativo")
        r_nat.pack(side="left", padx=10)
        
        r_7z = ctk.CTkRadioButton(tools_frame, text="7-Zip (Soporta .7z, Contraseña segura)", variable=self.comp_tool_var, value="7z")
        r_7z.pack(side="left", padx=10)
        if not self.seven_z_path:
            r_7z.configure(state="disabled")
            
        self.comp_btn = ctk.CTkButton(frame, text="▶ Comenzar Compresión", fg_color="#27AE60", hover_color="#2ECC71", command=self.do_compress)
        self.comp_btn.pack(pady=20)
        
        self.comp_status = ctk.CTkLabel(frame, text="", text_color="gray")
        self.comp_status.pack()
        
    def setup_ext_tab(self):
        frame = self.tab_ext
        
        ctk.CTkLabel(frame, text="Archivo Comprimido:").pack(pady=(10,0))
        self.ext_src = ctk.CTkEntry(frame, width=500)
        self.ext_src.pack(pady=5)
        ctk.CTkButton(frame, text="Buscar", command=lambda: self.ext_src.insert(0, filedialog.askopenfilename())).pack()
        
        ctk.CTkLabel(frame, text="Carpeta de Destino:").pack(pady=(10,0))
        self.ext_dest = ctk.CTkEntry(frame, width=500)
        self.ext_dest.pack(pady=5)
        ctk.CTkButton(frame, text="Buscar", command=lambda: self.ext_dest.insert(0, filedialog.askdirectory())).pack()
        
        ctk.CTkLabel(frame, text="Contraseña (Si la tiene):").pack(pady=(10,0))
        self.ext_pwd = ctk.CTkEntry(frame, show="*")
        self.ext_pwd.pack(pady=5)
        
        self.ext_btn = ctk.CTkButton(frame, text="▶ Extraer Ahora", command=self.do_extract)
        self.ext_btn.pack(pady=20)
        
        self.ext_status = ctk.CTkLabel(frame, text="", text_color="gray")
        self.ext_status.pack()
        
    def setup_rep_tab(self):
        frame = self.tab_rep
        
        ctk.CTkLabel(frame, text="Herramienta de Reparación de Archivos Dañados", font=("Arial", 16, "bold")).pack(pady=10)
        
        ctk.CTkLabel(frame, text="Archivo Dañado (.zip, .rar):").pack(pady=(10,0))
        self.rep_src = ctk.CTkEntry(frame, width=500)
        self.rep_src.pack(pady=5)
        ctk.CTkButton(frame, text="Buscar", command=lambda: self.rep_src.insert(0, filedialog.askopenfilename())).pack()
        
        self.rep_tool_var = ctk.StringVar(value="nativo")
        tools_frame = ctk.CTkFrame(frame)
        tools_frame.pack(pady=15, padx=20, fill="x")
        
        ctk.CTkRadioButton(tools_frame, text="Nativo (Reparador de Cabeceras ZIP)", variable=self.rep_tool_var, value="nativo").pack(side="left", padx=10)
        
        if self.seven_z_path:
            ctk.CTkRadioButton(tools_frame, text="7-Zip (Extraer ignorando errores)", variable=self.rep_tool_var, value="7z_force").pack(side="left", padx=10)
            
        ctk.CTkLabel(frame, text="Contraseña (Si la tiene):").pack(pady=(10,0))
        self.rep_pwd = ctk.CTkEntry(frame, show="*")
        self.rep_pwd.pack(pady=5)
            
        buttons_frame = ctk.CTkFrame(frame, fg_color="transparent")
        buttons_frame.pack(pady=20)
        
        self.analyze_btn = ctk.CTkButton(buttons_frame, text="🔍 Analizar Archivo (7-Zip)", fg_color="#F39C12", hover_color="#D68910", command=self.do_analyze)
        self.analyze_btn.pack(side="left", padx=10)
        if not self.seven_z_path:
            self.analyze_btn.configure(state="disabled")
            
        self.rep_btn = ctk.CTkButton(buttons_frame, text="🛠️ Intentar Reparar", command=self.do_repair)
        self.rep_btn.pack(side="left", padx=10)
        
        self.rep_status = ctk.CTkLabel(frame, text="", text_color="gray")
        self.rep_status.pack()
        


    def do_compress(self):
        src = self.comp_src.get().strip()
        dest = self.comp_dest.get().strip()
        pwd = self.comp_pwd.get().strip()
        tool = self.comp_tool_var.get()
        
        if not src or not dest:
            CustomMessageBox(self, "Error", "Debes especificar origen y destino.", is_error=True)
            return
            
        self.comp_btn.configure(state="disabled")
        self.comp_status.configure(text="Comprimiendo...")
        
        def _task():
            success = False
            err = ""
            try:
                if tool == "nativo":
                    if pwd:
                        # Fallback to powershell if pyzipper is not present, though native PS doesn't support password easily in Compress-Archive.
                        # Using basic zipfile without password if pyzipper fails
                        err = "La librería nativa actual no soporta contraseña. Usa 7-Zip o WinRAR."
                    else:
                        if os.path.isdir(src):
                            shutil.make_archive(dest.replace('.zip', ''), 'zip', src)
                        else:
                            with zipfile.ZipFile(dest, 'w') as zf:
                                zf.write(src, os.path.basename(src))
                        success = True
                elif tool == "7z":
                    cmd = [self.seven_z_path, "a", dest, src]
                    if pwd: cmd.append(f"-p{pwd}")
                    subprocess.run(cmd, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
                    success = True
            except Exception as e:
                err = str(e)
                
            self.after(0, self.comp_done, success, err)
            
        threading.Thread(target=_task, daemon=True).start()
        
    def comp_done(self, success, err):
        self.comp_btn.configure(state="normal")
        if success:
            self.comp_status.configure(text="¡Compresión Finalizada!")
            CustomMessageBox(self, "Éxito", "Archivo comprimido correctamente.")
        else:
            self.comp_status.configure(text=f"Error: {err}")
            CustomMessageBox(self, "Error", f"Falló la compresión: {err}", is_error=True)

    def do_extract(self):
        src = self.ext_src.get().strip()
        dest = self.ext_dest.get().strip()
        pwd = self.ext_pwd.get().strip()
        
        if not src or not dest:
            CustomMessageBox(self, "Error", "Debes especificar origen y destino.", is_error=True)
            return
            
        self.ext_btn.configure(state="disabled")
        self.ext_status.configure(text="Extrayendo...")
        
        def _task():
            success = False
            err = ""
            try:
                # Try 7z first if available
                if self.seven_z_path:
                    cmd = [self.seven_z_path, "x", src, f"-o{dest}", "-y"]
                    if pwd: cmd.append(f"-p{pwd}")
                    subprocess.run(cmd, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
                    success = True
                else:
                    # Native extraction
                    import zipfile
                    with zipfile.ZipFile(src, 'r') as zf:
                        if pwd:
                            zf.extractall(dest, pwd=pwd.encode())
                        else:
                            zf.extractall(dest)
                    success = True
            except Exception as e:
                err = str(e)
                
            self.after(0, self.ext_done, success, err)
            
        threading.Thread(target=_task, daemon=True).start()
        
    def ext_done(self, success, err):
        self.ext_btn.configure(state="normal")
        if success:
            self.ext_status.configure(text="¡Extracción Finalizada!")
            CustomMessageBox(self, "Éxito", "Archivo extraído correctamente.")
        else:
            self.ext_status.configure(text=f"Error: {err}")
            CustomMessageBox(self, "Error", f"Falló la extracción: {err}", is_error=True)

    def do_repair(self):
        src = self.rep_src.get().strip()
        tool = self.rep_tool_var.get()
        pwd = self.rep_pwd.get().strip()
        
        if not src:
            return
            
        self.rep_btn.configure(state="disabled")
        self.rep_status.configure(text="Reparando...")
        
        dest = src + "_reparado.zip"
        
        def _task():
            success = False
            msg = ""
            try:
                if tool == "nativo":
                    success, msg = repair_zip(src, dest)
                elif tool == "7z_force":
                    # 7-Zip no tiene función "repair" pero puede forzar la extracción de lo recuperable ignorando errores
                    dest_folder = src + "_recuperado"
                    os.makedirs(dest_folder, exist_ok=True)
                    cmd = [self.seven_z_path, "x", src, f"-o{dest_folder}", "-y"]
                    if pwd: cmd.append(f"-p{pwd}")
                    # Usamos run sin check porque 7-Zip devolverá > 0 si hay errores, pero extraerá lo que pueda.
                    subprocess.run(cmd, creationflags=subprocess.CREATE_NO_WINDOW)
                    success = True
                    msg = f"Se forzó la extracción de archivos recuperables usando 7-Zip. Revisa la carpeta:\n{dest_folder}"
            except Exception as e:
                msg = str(e)
                
            self.after(0, self.rep_done, success, msg)
            
        threading.Thread(target=_task, daemon=True).start()
        
    def rep_done(self, success, msg):
        self.rep_btn.configure(state="normal")
        if success:
            self.rep_status.configure(text=f"Resultado: {msg}")
            CustomMessageBox(self, "Reparación", msg)
        else:
            self.rep_status.configure(text=f"Error: {msg}")
            CustomMessageBox(self, "Error", f"Falló la reparación: {msg}", is_error=True)

    def do_analyze(self):
        src = self.rep_src.get().strip()
        pwd = self.rep_pwd.get().strip()
        
        if not src:
            CustomMessageBox(self, "Error", "Selecciona un archivo para analizar.", is_error=True)
            return
            
        self.analyze_btn.configure(state="disabled")
        self.rep_status.configure(text="Analizando integridad con 7-Zip...")
        
        def _task():
            success = False
            msg = ""
            try:
                cmd = [self.seven_z_path, "t", src]
                if pwd: cmd.append(f"-p{pwd}")
                
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                
                if result.returncode == 0:
                    success = True
                    msg = "El archivo está en perfectas condiciones. No se encontraron errores."
                else:
                    success = False
                    # Extract last lines of 7z output to show the error
                    out_lines = result.stdout.strip().split('\n')
                    err_summary = "\n".join(out_lines[-5:]) if len(out_lines) > 5 else result.stdout
                    msg = f"El archivo contiene errores o está corrupto:\n\n{err_summary}"
            except Exception as e:
                msg = str(e)
                
            self.after(0, self.analyze_done, success, msg)
            
        threading.Thread(target=_task, daemon=True).start()

    def analyze_done(self, success, msg):
        self.analyze_btn.configure(state="normal")
        if success:
            self.rep_status.configure(text="Análisis completado: Todo OK")
            CustomMessageBox(self, "Análisis 7-Zip", msg)
        else:
            self.rep_status.configure(text="Análisis completado: Archivo dañado")
            CustomMessageBox(self, "Análisis 7-Zip", msg, is_error=True)

def main():
    app = FileCompressorApp()
    app.mainloop()

if __name__ == "__main__":
    main()
