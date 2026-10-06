import customtkinter as ctk
import os
import sys
import threading
import subprocess
import zipfile
import shutil
import urllib.request
from tkinter import filedialog, messagebox

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
        self.winrar_path = self.check_winrar()
        
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
        
    def check_winrar(self):
        from functions.utils import get_user_data_path
        p = get_user_data_path(r"tools\rar.exe")
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
        self.comp_dest = ctk.CTkEntry(frame, width=500)
        self.comp_dest.pack(pady=5)
        
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
            
        r_rar = ctk.CTkRadioButton(tools_frame, text="WinRAR (Soporta .rar)", variable=self.comp_tool_var, value="rar")
        r_rar.pack(side="left", padx=10)
        if not self.winrar_path:
            r_rar.configure(state="disabled")
            
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
        r_rar = ctk.CTkRadioButton(tools_frame, text="WinRAR (Reparador Inteligente de RAR/ZIP)", variable=self.rep_tool_var, value="rar")
        r_rar.pack(side="left", padx=10)
        if not self.winrar_path:
            r_rar.configure(state="disabled")
            
        ctk.CTkLabel(frame, text="Contraseña (Si la tiene):").pack(pady=(10,0))
        self.rep_pwd = ctk.CTkEntry(frame, show="*")
        self.rep_pwd.pack(pady=5)
            
        self.rep_btn = ctk.CTkButton(frame, text="🛠️ Intentar Reparar", command=self.do_repair)
        self.rep_btn.pack(pady=20)
        
        self.rep_status = ctk.CTkLabel(frame, text="", text_color="gray")
        self.rep_status.pack()
        


    def do_compress(self):
        src = self.comp_src.get().strip()
        dest = self.comp_dest.get().strip()
        pwd = self.comp_pwd.get().strip()
        tool = self.comp_tool_var.get()
        
        if not src or not dest:
            messagebox.showerror("Error", "Debes especificar origen y destino.")
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
                elif tool == "rar":
                    cmd = [self.winrar_path, "a", dest, src]
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
            messagebox.showinfo("Éxito", "Archivo comprimido correctamente.")
        else:
            self.comp_status.configure(text=f"Error: {err}")
            messagebox.showerror("Error", f"Falló la compresión: {err}")

    def do_extract(self):
        src = self.ext_src.get().strip()
        dest = self.ext_dest.get().strip()
        pwd = self.ext_pwd.get().strip()
        
        if not src or not dest:
            messagebox.showerror("Error", "Debes especificar origen y destino.")
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
                elif self.winrar_path:
                    cmd = [self.winrar_path, "x", "-y"]
                    if pwd: cmd.append(f"-p{pwd}")
                    cmd.extend([src, dest + "\\"])
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
            messagebox.showinfo("Éxito", "Archivo extraído correctamente.")
        else:
            self.ext_status.configure(text=f"Error: {err}")
            messagebox.showerror("Error", f"Falló la extracción: {err}")

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
                elif tool == "rar":
                    cmd = [self.winrar_path, "r"]
                    if pwd:
                        cmd.append(f"-p{pwd}")
                    cmd.append(src)
                    
                    # WinRAR repara en el mismo directorio con prefijo rebuilt. o fixed.
                    subprocess.run(cmd, check=True, cwd=os.path.dirname(src), creationflags=subprocess.CREATE_NO_WINDOW)
                    success = True
                    msg = "WinRAR intentó reparar el archivo. Revisa el directorio original."
            except Exception as e:
                msg = str(e)
                
            self.after(0, self.rep_done, success, msg)
            
        threading.Thread(target=_task, daemon=True).start()
        
    def rep_done(self, success, msg):
        self.rep_btn.configure(state="normal")
        if success:
            self.rep_status.configure(text=f"Resultado: {msg}")
            messagebox.showinfo("Reparación", msg)
        else:
            self.rep_status.configure(text=f"Error: {msg}")
            messagebox.showerror("Error", f"Falló la reparación: {msg}")

def main():
    app = FileCompressorApp()
    app.mainloop()

if __name__ == "__main__":
    main()
