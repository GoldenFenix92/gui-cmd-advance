import customtkinter as ctk
import subprocess
import threading
import os
from tkinter import filedialog
from gui_app import center_window, get_resource_path

class MultiSelectDropdown(ctk.CTkButton):
    def __init__(self, master, options, **kwargs):
        super().__init__(master, text="Extensiones", command=self.toggle_dropdown, **kwargs)
        self.options = options
        self.vars = {opt: ctk.BooleanVar(value=True if opt == "*.*" else False) for opt in options}
        self.dropdown_window = None

    def toggle_dropdown(self):
        if self.dropdown_window is None or not self.dropdown_window.winfo_exists():
            self.dropdown_window = ctk.CTkToplevel(self)
            self.dropdown_window.title("Seleccionar Extensiones")
            # Hacer que sea una ventana modal pequeña
            self.dropdown_window.attributes('-topmost', True)
            self.dropdown_window.resizable(False, False)
            
            # Position relative to button
            x = self.winfo_rootx()
            y = self.winfo_rooty() + self.winfo_height()
            self.dropdown_window.geometry(f"200x250+{x}+{y}")
            self.dropdown_window.overrideredirect(True) # Sin bordes de windows

            frame = ctk.CTkFrame(self.dropdown_window, border_width=2, border_color="#1f6aa5")
            frame.pack(fill="both", expand=True)

            scroll = ctk.CTkScrollableFrame(frame, fg_color="transparent")
            scroll.pack(fill="both", expand=True, padx=5, pady=5)

            for opt in self.options:
                cb = ctk.CTkCheckBox(scroll, text=opt, variable=self.vars[opt], command=self.update_text)
                cb.pack(anchor="w", pady=2)
                
            btn_close = ctk.CTkButton(frame, text="Cerrar", command=self.dropdown_window.destroy, fg_color="#E74C3C", hover_color="#C0392B", height=24)
            btn_close.pack(pady=5)
        else:
            self.dropdown_window.destroy()

    def update_text(self):
        selected = [opt for opt, var in self.vars.items() if var.get()]
        if not selected:
            self.configure(text="Ninguna")
        elif "*.*" in selected:
            self.configure(text="Todas (*.*)")
        else:
            self.configure(text=f"{len(selected)} seleccionadas")

    def get_selected(self):
        selected = [opt for opt, var in self.vars.items() if var.get()]
        if "*.*" in selected or not selected:
            return ["*.*"]
        return selected

class AdvancedSearchApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Búsqueda Avanzada de Texto (FindStr Ultra)")
        center_window(self, 900, 600)
        try: self.iconbitmap(get_resource_path("resources/app_icon.ico"))
        except: pass
        
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # Filtros (sin border_width=0 para mantener los bordes predeterminados de CTk)
        top_frame = ctk.CTkFrame(self, fg_color="transparent")
        top_frame.grid(row=0, column=0, padx=20, pady=10, sticky="ew")
        
        ctk.CTkLabel(top_frame, text="Directorio:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.dir_var = ctk.StringVar()
        ctk.CTkEntry(top_frame, textvariable=self.dir_var, width=250).grid(row=0, column=1, padx=5, pady=5)
        
        # Botón Secundario (Azul)
        self.btn_browse = ctk.CTkButton(top_frame, text="Examinar", width=80, command=self.browse, fg_color="#2980B9", hover_color="#1F618D")
        self.btn_browse.grid(row=0, column=2, padx=5, pady=5)
        
        ctk.CTkLabel(top_frame, text="Texto a buscar:").grid(row=0, column=3, padx=15, pady=5, sticky="w")
        self.term_var = ctk.StringVar()
        ctk.CTkEntry(top_frame, textvariable=self.term_var, width=200).grid(row=0, column=4, padx=5, pady=5)
        
        ctk.CTkLabel(top_frame, text="Extensiones:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        exts = ["*.*", "*.txt", "*.log", "*.json", "*.py", "*.csv", "*.xml", "*.md", "*.ini", "*.cfg", "*.html", "*.css", "*.js", "*.php", "*.cpp", "*.java", "*.bat", "*.pdf"]
        
        # Terciario (Gris Oscuro)
        self.ext_dropdown = MultiSelectDropdown(top_frame, options=exts, fg_color="#34495E", hover_color="#2C3E50", width=150)
        self.ext_dropdown.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        
        self.ignore_case_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(top_frame, text="Ignorar Mayúsculas (/i)", variable=self.ignore_case_var).grid(row=1, column=3, padx=5, pady=5)
        
        self.regex_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(top_frame, text="Expresión Regular (/r)", variable=self.regex_var).grid(row=1, column=4, padx=5, pady=5)
        
        # Botón Primario (Verde)
        self.btn_search = ctk.CTkButton(self, text="🔍 Buscar Ahora", command=self.run_search, fg_color="#27AE60", hover_color="#1E8449", font=("Arial", 14, "bold"))
        self.btn_search.grid(row=1, column=0, padx=20, pady=5)
        
        self.results_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.results_frame.grid(row=2, column=0, padx=20, pady=10, sticky="nsew")

    def browse(self):
        f = filedialog.askdirectory()
        if f: self.dir_var.set(f.replace("/", "\\"))

    def run_search(self):
        if not self.dir_var.get() or not self.term_var.get(): return
        self.btn_search.configure(state="disabled")
        
        for w in self.results_frame.winfo_children(): w.destroy()
        
        ctk.CTkLabel(self.results_frame, text="Buscando...", font=("Arial", 14)).pack(pady=20)
        
        def task():
            d = self.dir_var.get()
            t = self.term_var.get()
            exts = self.ext_dropdown.get_selected()
            
            flags = "/s /n "
            if self.ignore_case_var.get(): flags += "/i "
            if self.regex_var.get(): flags += "/r "
            else: flags += "/c:"
            
            # Formatear multiples extensiones para findstr
            paths = " ".join([f'"{d}\\{ext}"' for ext in exts])
            cmd = f'findstr {flags}"{t}" {paths}'
            
            try:
                out = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
                text = out.decode('mbcs', 'ignore')
            except subprocess.CalledProcessError as err:
                text = err.output.decode('mbcs', 'ignore') if err.output else ""
                
            self.after(0, self.done, text)
            
        threading.Thread(target=task, daemon=True).start()

    def done(self, text):
        for w in self.results_frame.winfo_children(): w.destroy()
        self.btn_search.configure(state="normal")
        
        if not text.strip():
            ctk.CTkLabel(self.results_frame, text="No se encontraron coincidencias.", font=("Arial", 14)).pack(pady=20)
            return

        lines = text.strip().split('\n')
        grouped = {}
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith("FINDSTR:"): continue
            
            parts = line.split(":", 2)
            if len(parts) >= 3:
                # Si contiene letra de unidad (ej. C:\...)
                if len(parts[0]) == 1 and parts[0].isalpha() and "\\" in parts[1]:
                    path = parts[0] + ":" + parts[1]
                    rem = parts[2].split(":", 1)
                    if len(rem) == 2:
                        line_num = rem[0]
                        content = rem[1]
                    else:
                        line_num = "?"
                        content = parts[2]
                else:
                    # En caso de que devuelva ruta relativa (no debería por cómo armamos el comando)
                    path = parts[0]
                    line_num = parts[1]
                    content = parts[2]
                    
                if path not in grouped:
                    grouped[path] = []
                grouped[path].append((line_num, content))

        for path, matches in grouped.items():
            # Contenedor sin fondo visible para evitar cuadros feos
            file_frame = ctk.CTkFrame(self.results_frame, fg_color="transparent")
            file_frame.pack(fill="x", pady=15, padx=5)
            
            header = ctk.CTkFrame(file_frame, fg_color="transparent")
            header.pack(fill="x", padx=5, pady=2)
            header.grid_columnconfigure(0, weight=1)
            
            # Nombre de archivo truncado pero visible
            lbl_path = ctk.CTkLabel(header, text=f"📄 {path}", font=("Arial", 14, "bold"), text_color="#F39C12", anchor="w", justify="left")
            lbl_path.grid(row=0, column=0, sticky="w")
            
            # Botón Primario para Abrir Archivo, alineado a la derecha
            btn_open = ctk.CTkButton(header, text="Abrir Archivo", width=120, height=28, command=lambda p=path: self.open_file(p), fg_color="#2980B9", hover_color="#1F618D")
            btn_open.grid(row=0, column=1, sticky="e", padx=(10, 0))
            
            # Separador visual
            ctk.CTkFrame(file_frame, height=1, fg_color="#333333").pack(fill="x", pady=(2, 8))
            
            # Caja de texto grande en lugar de múltiples labels individuales
            # Esto soluciona los contenedores feos y emula un bloque de código
            matches_text = ""
            for line_num, content in matches:
                matches_text += f"Línea {line_num:>5} |  {content}\n"
                
            tb = ctk.CTkTextbox(file_frame, font=("Consolas", 13), height=min(200, len(matches)*20 + 10), fg_color="#1E1E1E", text_color="#A9CCE3")
            tb.pack(fill="x", padx=10)
            tb.insert("1.0", matches_text)
            tb.configure(state="disabled")

    def open_file(self, path):
        import os
        from tkinter import messagebox
        import subprocess
        
        # Limpiar la ruta por si tiene espacios residuales
        clean_path = path.strip()
        
        if not os.path.exists(clean_path):
            messagebox.showerror("Error", f"Windows no puede encontrar la ruta:\n{clean_path}")
            return
            
        try:
            # Dado que la aplicación principal se ejecuta como Administrador (elevada),
            # algunos programas (como Edge, Chrome o Adobe) bloquean la apertura de archivos
            # por motivos de seguridad (UIPI).
            # Para evitarlo, le pedimos a 'explorer.exe' (que corre como usuario normal) que lo abra.
            subprocess.Popen(['explorer.exe', clean_path])
        except Exception as e:
            try:
                os.startfile(clean_path)
            except Exception as e2:
                messagebox.showerror("Error Crítico", f"No se pudo abrir el archivo.\n{e2}")

if __name__ == "__main__":
    app = AdvancedSearchApp()
    app.mainloop()
