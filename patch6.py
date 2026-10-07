import os

gui_path = r"f:\Proyectos\gui-cmd-advance\gui_app.py"
with open(gui_path, "r", encoding="utf-8") as f:
    gui_code = f.read()

# 1. Add pause button creation
old_execute_btn = '''        self.execute_btn = ctk.CTkButton(self.btn_frame, text="Ejecutar Comando", command=self.toggle_execution)
        self.execute_btn.pack(side="left", fill="x", expand=True, padx=(0, 5))
        if CTkToolTip: CTkToolTip(self.execute_btn, message="Ejecutar el comando en segundo plano (Ctrl+Enter)")'''

new_execute_btn = '''        self.execute_btn = ctk.CTkButton(self.btn_frame, text="Ejecutar Comando", command=self.toggle_execution)
        self.execute_btn.pack(side="left", fill="x", expand=True, padx=(0, 5))
        if CTkToolTip: CTkToolTip(self.execute_btn, message="Ejecutar el comando en segundo plano (Ctrl+Enter)")
        
        self.pause_btn = ctk.CTkButton(self.btn_frame, text="⏸️ Posponer", width=80, fg_color="#F39C12", hover_color="#D68910", command=self.pause_execution)
        # self.pause_btn.pack(side="left", padx=(0, 5)) # Se oculta por defecto'''

gui_code = gui_code.replace(old_execute_btn, new_execute_btn)

# 2. Add pause logic and show/hide button
old_execute_ext = '''        self.execute_btn.configure(text="Detener ejecución", fg_color="red", hover_color="#8B0000")
        self.cat_menu.configure(state="disabled")
        self.cmd_menu.configure(state="disabled")
        
        def on_finish():
            self.is_running = False
            self.execute_btn.configure(text="Ejecutar Comando", fg_color=["#1F883D", "#238636"], hover_color=["#1A7F37", "#2EA043"])
            self.cat_menu.configure(state="normal")
            self.cmd_menu.configure(state="normal")'''

new_execute_ext = '''        self.execute_btn.configure(text="Detener ejecución", fg_color="red", hover_color="#8B0000")
        self.cat_menu.configure(state="disabled")
        self.cmd_menu.configure(state="disabled")
        self.pause_btn.pack(side="left", padx=(0, 5), before=self.fav_btn)
        
        # Limpiar archivo de pausa viejo si existe
        appdata = os.environ.get('APPDATA', '')
        flag_file = os.path.join(appdata, "cmd_gui_advance", "pause.flag")
        if os.path.exists(flag_file):
            try: os.remove(flag_file)
            except: pass
        
        def on_finish():
            self.is_running = False
            self.execute_btn.configure(text="Ejecutar Comando", fg_color=["#1F883D", "#238636"], hover_color=["#1A7F37", "#2EA043"])
            self.cat_menu.configure(state="normal")
            self.cmd_menu.configure(state="normal")
            self.pause_btn.pack_forget()'''

gui_code = gui_code.replace(old_execute_ext, new_execute_ext)

# 3. Add pause_execution method
if "def pause_execution" not in gui_code:
    old_run_help = "    def run_help(self):"
    new_pause_method = '''    def pause_execution(self):
        if not self.is_running: return
        import os
        appdata = os.environ.get('APPDATA', '')
        flag_file = os.path.join(appdata, "cmd_gui_advance", "pause.flag")
        try:
            with open(flag_file, "w") as f: f.write("1")
            self.append_output("\\n[SISTEMA] Señal de pausa enviada. El proceso se detendrá al terminar su tarea actual...\\n")
            self.pause_btn.configure(state="disabled", text="Pausando...")
        except Exception as e:
            self.append_output(f"\\nError enviando señal de pausa: {e}\\n")

    def run_help(self):'''
    gui_code = gui_code.replace(old_run_help, new_pause_method)

with open(gui_path, "w", encoding="utf-8") as f:
    f.write(gui_code)

print("gui_app.py patched for Pause button.")
