import json
import re
import customtkinter as ctk
from functions import cmd_executor
import os
from tkinter import filedialog
from tkinter import messagebox

import sys
import webbrowser
import gc
import subprocess

try:
    from CTkToolTip import CTkToolTip
except ImportError:
    CTkToolTip = None

try:
    from version import __version__
except ImportError:
    __version__ = "1.0.0"

from functions.setup_manager import check_dependencies

def get_base_path():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    else:
        return os.path.dirname(os.path.abspath(__file__))

def get_user_data_path(filename):
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, filename)

def get_resource_path(relative_path):
    return os.path.join(get_base_path(), relative_path)

def center_window(window, width, height):
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    x = int((screen_width / 2) - (width / 2))
    y = int((screen_height / 2) - (height / 2))
    window.geometry(f"{width}x{height}+{x}+{y}")

try:
    ctk.set_default_color_theme(get_resource_path("resources/custom_github_theme.json"))
except Exception as e:
    print(f"No se pudo cargar el tema, usando blue: {e}")
    ctk.set_default_color_theme("blue")

ctk.set_appearance_mode("Dark")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("CMD GUI Advance")
        center_window(self, 1400, 800)
        
        try:
            self.iconbitmap(get_resource_path("resources/app_icon.ico"))
        except:
            pass

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)

        self.commands_config = self.load_config()
        self.is_running = False

        # ---------- FRAME IZQUIERDO: Panel de Control ----------
        self.left_frame = ctk.CTkFrame(self)
        self.left_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        self.left_frame.grid_rowconfigure(6, weight=1)
        self.left_frame.grid_rowconfigure(7, weight=0)
        self.left_frame.grid_columnconfigure(0, weight=1)

        self.top_bar = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        self.top_bar.grid(row=0, column=0, padx=15, pady=15, sticky="ew")

        self.theme_switch = ctk.CTkSwitch(self.top_bar, text="Oscuro", command=self.toggle_theme)
        self.theme_switch.pack(side="left")
        self.theme_switch.select()

        self.credits_btn = ctk.CTkButton(self.top_bar, text="ℹ️ Créditos", width=80, height=25, fg_color="transparent", text_color=("black", "white"), command=self.show_credits)
        self.credits_btn.pack(side="right")

        self.plugins_btn = ctk.CTkButton(self.top_bar, text="🧩 Complementos", width=100, height=25, fg_color="#27AE60", hover_color="#2ECC71", command=self.show_plugins)
        self.plugins_btn.pack(side="right", padx=(0, 10))

        self.proc_btn = ctk.CTkButton(self.top_bar, text="⚙️ Procesos", width=80, height=25, fg_color="#3498DB", hover_color="#2980B9", command=self.open_process_manager)
        self.proc_btn.pack(side="right", padx=(0, 10))
        if CTkToolTip: CTkToolTip(self.proc_btn, message="Gestor de Procesos y Servicios")

        self.ram_btn = ctk.CTkButton(self.top_bar, text="🚀 RAM", width=60, height=25, fg_color="#E67E22", hover_color="#D35400", command=self.optimize_ram)

        self.ram_btn.pack(side="right", padx=(0, 10))
        if CTkToolTip: CTkToolTip(self.ram_btn, message="Liberar memoria inactiva (RAM)")

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self.on_search)
        self.search_entry = ctk.CTkEntry(self.left_frame, textvariable=self.search_var, placeholder_text="🔍 Buscar comando...", border_width=0)
        self.search_entry.grid(row=1, column=0, padx=15, pady=(15, 5), sticky="ew")

        self.lbl_cat = ctk.CTkLabel(self.left_frame, text="Categoría:", font=("Arial", 12, "bold"))
        self.lbl_cat.grid(row=2, column=0, padx=15, pady=(5, 0), sticky="w")

        categories = [cat.get("name", "Unknown") for cat in self.commands_config.get("categories", [])]
        self.cat_var = ctk.StringVar(value=categories[0] if categories else "")
        self.cat_menu = ctk.CTkOptionMenu(self.left_frame, values=categories, variable=self.cat_var, command=self.on_category_change)
        self.cat_menu.grid(row=3, column=0, padx=15, pady=5, sticky="ew")

        # Frame Comando (Label + Info + Help)
        self.cmd_label_frame = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        self.cmd_label_frame.grid(row=4, column=0, padx=15, pady=(10, 0), sticky="ew")
        
        self.lbl_cmd = ctk.CTkLabel(self.cmd_label_frame, text="Comando:", font=("Arial", 12, "bold"))
        self.lbl_cmd.pack(side="left")

        # Info button
        self.cmd_info_btn = ctk.CTkButton(self.cmd_label_frame, text="ℹ", width=25, height=25, command=self.show_command_info)
        self.cmd_info_btn.pack(side="right", padx=(5, 0))
        if CTkToolTip: CTkToolTip(self.cmd_info_btn, message="Información detallada del comando")

        # Help button
        self.cmd_help_btn = ctk.CTkButton(self.cmd_label_frame, text="❔", width=25, height=25, command=self.run_help)
        self.cmd_help_btn.pack(side="right")
        if CTkToolTip: CTkToolTip(self.cmd_help_btn, message="Ejecutar la ayuda oficial del comando (/? o --help)")

        self.cmd_var = ctk.StringVar(value="")
        self.cmd_menu = ctk.CTkOptionMenu(self.left_frame, variable=self.cmd_var, command=self.on_command_change)
        self.cmd_menu.grid(row=5, column=0, padx=15, pady=5, sticky="ew")

        self.args_frame = ctk.CTkScrollableFrame(self.left_frame, fg_color="transparent", bg_color="transparent")
        self.args_frame.grid(row=6, column=0, padx=10, pady=10, sticky="nsew")
        
        self.current_args_vars = {}

        self.btn_frame = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        self.btn_frame.grid(row=7, column=0, padx=15, pady=15, sticky="ew")

        self.execute_btn = ctk.CTkButton(self.btn_frame, text="Ejecutar Comando", command=self.toggle_execution)
        self.execute_btn.pack(side="left", fill="x", expand=True, padx=(0, 5))
        if CTkToolTip: CTkToolTip(self.execute_btn, message="Ejecutar el comando en segundo plano (Ctrl+Enter)")
        
        self.fav_btn = ctk.CTkButton(self.btn_frame, text="⭐", width=40, font=("Segoe UI Emoji", 15), anchor="center", command=self.save_favorite, fg_color="#F39C12", hover_color="#D68910")
        self.fav_btn.pack(side="right")
        if CTkToolTip: CTkToolTip(self.fav_btn, message="Guardar o remover de Favoritos")

        # ---------- FRAME DERECHO: Consola y Exportar ----------
        self.right_frame = ctk.CTkFrame(self)
        self.right_frame.grid(row=0, column=1, padx=(0, 10), pady=10, sticky="nsew")
        self.right_frame.grid_rowconfigure(1, weight=1)
        self.right_frame.grid_columnconfigure(0, weight=1)
        self.right_frame.grid_columnconfigure(1, weight=0)

        # Preview de comando en vivo
        self.preview_var = ctk.StringVar(value="")
        self.preview_entry = ctk.CTkEntry(self.right_frame, textvariable=self.preview_var, state="disabled", font=("Consolas", 14, "bold"), text_color=("#1f6aa5", "#3B8ED0"), border_width=0)
        self.preview_entry.grid(row=0, column=0, columnspan=2, padx=10, pady=(10, 0), sticky="ew")

        # Consola
        self.output_textbox = ctk.CTkTextbox(self.right_frame, font=("Consolas", 13), wrap="none", border_width=0)
        self.output_textbox.grid(row=1, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")
        self.output_textbox.configure(state="disabled")

        self.progress_frame = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        self.progress_frame.grid(row=2, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="ew")
        self.progress_frame.grid_columnconfigure(0, weight=1)
        
        self.progressbar = ctk.CTkProgressBar(self.progress_frame)
        self.progressbar.grid(row=0, column=0, sticky="ew")
        self.progressbar.set(0)
        
        self.lbl_progress = ctk.CTkLabel(self.progress_frame, text="0%", width=40, font=("Consolas", 12, "bold"))
        self.lbl_progress.grid(row=0, column=1, padx=(10, 0))

        # Export Buttons
        self.btn_frame = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        self.btn_frame.grid(row=3, column=0, padx=10, pady=(0, 5), sticky="sw")
        
        self.export_btn = ctk.CTkButton(self.btn_frame, text="Exportar Actual", width=100, command=self.export_output)
        self.export_btn.pack(side="left", padx=(0, 10))

        self.table_btn = ctk.CTkButton(self.btn_frame, text="Ver como Tabla", width=100, fg_color="#2E86C1", hover_color="#21618C", command=self.show_table_view)
        self.table_btn.pack(side="left", padx=(0, 10))
        if CTkToolTip: CTkToolTip(self.table_btn, message="Ver resultados en una tabla interactiva (ideal para CSV)")
        
        self.convert_btn = ctk.CTkButton(self.btn_frame, text="Convertir Reporte Antiguo", width=150, command=self.convert_old_report, fg_color="#475569", hover_color="#334155")
        self.convert_btn.pack(side="left")

        self.interpreter_btn = ctk.CTkButton(self.btn_frame, text="✨ Interpretar Resultados", width=150, command=self.run_interpreter, fg_color="#8E44AD", hover_color="#9B59B6")
        self.interpreter_btn.pack(side="left", padx=(10, 0))
        if CTkToolTip: CTkToolTip(self.interpreter_btn, message="Analiza el reporte con Inteligencia Artificial o de manera local")
        
        # Dashboard (Status Bar)
        self.status_bar = ctk.CTkFrame(self.right_frame, height=25, fg_color="transparent")
        self.status_bar.grid(row=4, column=0, columnspan=2, sticky="ew")
        
        self.lbl_ram = ctk.CTkLabel(self.status_bar, text="🧠 RAM: --%", font=("Consolas", 12, "bold"))
        self.lbl_ram.pack(side="right", padx=10)
        
        self.lbl_cpu = ctk.CTkLabel(self.status_bar, text="💻 CPU: --%", font=("Consolas", 12, "bold"))
        self.lbl_cpu.pack(side="right", padx=10)
        
        self.update_console_tags()

        self.update_status_dashboard()

        self.clear_frame = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        self.clear_frame.grid(row=3, column=1, padx=10, pady=(0, 10), sticky="se")

        self.auto_clear_var = ctk.BooleanVar(value=True)
        self.auto_clear_cb = ctk.CTkCheckBox(self.clear_frame, text="Auto-Limpiar", variable=self.auto_clear_var, width=100)
        self.auto_clear_cb.pack(side="left", padx=(0, 10))
        if CTkToolTip: CTkToolTip(self.auto_clear_cb, message="Limpiar la consola antes de ejecutar un nuevo comando")

        self.clear_btn = ctk.CTkButton(self.clear_frame, text="Limpiar", width=100, fg_color="transparent", text_color=("#24292F", "#C9D1D9"), command=self.clear_output)
        self.clear_btn.pack(side="left")
        if CTkToolTip: CTkToolTip(self.clear_btn, message="Limpiar la consola manualmente (Ctrl+L)")

        # Keyboard shortcuts
        self.bind("<Control-Return>", lambda e: self.toggle_execution())
        self.bind("<Control-l>", lambda e: self.clear_output())
        self.bind("<Control-L>", lambda e: self.clear_output())

        self.on_category_change(self.cat_var.get())
        
        # Check multimedia dependencies
        self.after(500, lambda: check_dependencies(self))
        
        # Telemetry and Updates
        from functions.telemetry import check_for_crashes, check_for_updates
        self.after(1500, lambda: check_for_crashes(self))
        self.after(3000, lambda: check_for_updates(self))

    def disable_missing_features(self):
        self.on_category_change(self.cat_var.get())

    def load_config(self):
        config = {"categories": []}
        try:
            with open(get_resource_path("resources/commands_config.json"), "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception as e:
            pass
            
        try:
            with open(get_user_data_path("favorites.json"), "r", encoding="utf-8") as f:
                favs = json.load(f)
                if favs:
                    config["categories"].insert(0, {
                        "name": "⭐ Favoritos",
                        "commands": favs
                    })
        except:
            pass
            
        return config

    def update_status_dashboard(self):
        import psutil
        try:
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().percent
            
            def get_color(val):
                if val < 25: return "#28a745" # Verde
                elif val < 50: return "#ffc107" # Amarillo
                elif val < 75: return "#fd7e14" # Naranja
                else: return "#dc3545" # Rojo
                
            self.lbl_cpu.configure(text=f"💻 CPU: {cpu}%", text_color=get_color(cpu))
            self.lbl_ram.configure(text=f"🧠 RAM: {ram}%", text_color=get_color(ram))
        except:
            self.lbl_cpu.configure(text="💻 CPU: --%")
            self.lbl_ram.configure(text="🧠 RAM: --%")
        self.after(2000, self.update_status_dashboard)

    def get_windows_drives(self):
        import subprocess
        drives = []
        try:
            output = subprocess.check_output(
                ["powershell", "-Command", "Get-CimInstance Win32_LogicalDisk | Where-Object DriveType -eq 3 | ForEach-Object { $n = $_.VolumeName; if(-not $n){ $n = $_.Description }; $_.DeviceID + ' (' + $n + ')' }"],
                creationflags=subprocess.CREATE_NO_WINDOW
            ).decode('mbcs', errors='ignore').strip().split('\n')
            for line in output:
                if line.strip():
                    drives.append(line.strip())
        except:
            pass
        if not drives:
            import string
            from ctypes import windll
            bitmask = windll.kernel32.GetLogicalDrives()
            for letter in string.ascii_uppercase:
                if bitmask & 1:
                    drives.append(f"{letter}:")
                bitmask >>= 1
        return drives if drives else ["C:"]

    def get_physical_disks(self):
        import subprocess
        disks = []
        try:
            cmd = "Get-PhysicalDisk | ForEach-Object { $num = $_.DeviceId; $friendly = $_.FriendlyName; $vStr=''; try{ $v=Get-Partition -DiskNumber $num -ErrorAction SilentlyContinue | Where-Object DriveLetter | Select-Object -ExpandProperty DriveLetter; if($v){$vStr = ' (' + ($v -join ', ') + ':)'} }catch{}; $num + ' - ' + $friendly + $vStr }"
            output = subprocess.check_output(
                ["powershell", "-Command", cmd],
                creationflags=subprocess.CREATE_NO_WINDOW
            ).decode('mbcs', errors='ignore').strip().split('\n')
            for line in output:
                if line.strip():
                    disks.append(line.strip())
        except:
            pass
        if not disks:
            disks = ["0", "1", "2"]
        return disks

    def get_wifi_profiles(self):
        import subprocess
        profiles = []
        try:
            output = subprocess.check_output(
                "netsh wlan show profiles", shell=True, creationflags=subprocess.CREATE_NO_WINDOW
            ).decode('mbcs', errors='ignore').split('\n')
            for line in output:
                if "Perfil de todos los usuarios" in line or "All User Profile" in line:
                    profile_name = line.split(":", 1)[1].strip()
                    if profile_name:
                        profiles.append(profile_name)
        except:
            pass
        return profiles if profiles else ["(Ninguna red encontrada)"]

    def get_network_adapters(self):
        import subprocess
        adapters = []
        try:
            output = subprocess.check_output(
                ["powershell", "-Command", "Get-NetAdapter | Select-Object -ExpandProperty Name"],
                creationflags=subprocess.CREATE_NO_WINDOW
            ).decode('mbcs', errors='ignore').strip().split('\n')
            for line in output:
                if line.strip():
                    adapters.append(line.strip())
        except:
            pass
        return adapters if adapters else ["(Ninguno)"]

    def get_cpu_threads_list(self):
        import os
        try:
            threads = os.cpu_count() or 4
        except:
            threads = 4
            
        options = ["0 (Auto - Todos)"]
        for i in range(1, threads + 1):
            options.append(str(i))
            
        return options

    def toggle_theme(self):
        if self.theme_switch.get() == 1:
            ctk.set_appearance_mode("Dark")
            self.theme_switch.configure(text="Modo Oscuro")
        else:
            ctk.set_appearance_mode("Light")
            self.theme_switch.configure(text="Modo Claro")
        self.update_console_tags()

    def update_console_tags(self):
        is_dark = ctk.get_appearance_mode().lower() == "dark"
        self.output_textbox.tag_config("error", foreground="#FF4C4C" if is_dark else "#D32F2F")
        self.output_textbox.tag_config("success", foreground="#4CFF4C" if is_dark else "#2E7D32")
        self.output_textbox.tag_config("ip", foreground="#42A5F5" if is_dark else "#1565C0")
        self.output_textbox.tag_config("path", foreground="#FFCA28" if is_dark else "#E65100")
        self.output_textbox.tag_config("highlight", foreground="#FF4081" if is_dark else "#C2185B")

    def get_category_data(self, cat_name):
        for cat in self.commands_config.get("categories", []):
            if cat.get("name") == cat_name:
                return cat
        return None

    def get_command_data(self, cmd_name):
        for cat in self.commands_config.get("categories", []):
            for cmd in cat.get("commands", []):
                if cmd.get("name") == cmd_name:
                    return cmd
        return None

    def show_custom_info(self, title, message):
        info_win = ctk.CTkToplevel(self)
        info_win.title(title)
        center_window(info_win, 450, 250)
        info_win.resizable(False, False)
        
        def set_icon():
            try:
                info_win.iconbitmap(get_resource_path("resources/app_icon.ico"))
            except:
                pass
        
        info_win.after(200, set_icon)
        
        info_win.transient(self)
        info_win.grab_set()
        
        lbl_title = ctk.CTkLabel(info_win, text=title, font=("Arial", 16, "bold"), text_color=("#1f6aa5", "#F39C12"))
        lbl_title.pack(pady=(20, 10))
        
        lbl_msg = ctk.CTkLabel(info_win, text=message, font=("Arial", 13), justify="center", wraplength=400, text_color=("black", "white"))
        lbl_msg.pack(pady=10, fill="both", expand=True, padx=20)
        
        close_btn = ctk.CTkButton(info_win, text="Entendido", command=info_win.destroy, fg_color=("#1f6aa5", "#24292F"), hover_color=("#144870", "#40464d"), text_color="white")
        close_btn.pack(pady=(10, 20))

    def show_command_info(self):
        cmd_data = self.get_command_data(self.cmd_var.get())
        if cmd_data:
            self.show_custom_info(f"Info: {cmd_data.get('name')}", cmd_data.get("description", ""))

    def show_arg_info(self, arg_name, arg_desc):
        self.show_custom_info(f"Info: {arg_name}", arg_desc)

    def on_search(self, *args):
        query = self.search_var.get().lower()
        if not query:
            self.cat_menu.configure(state="normal")
            self.on_category_change(self.cat_var.get())
            return
            
        self.cat_menu.configure(state="disabled")
        matched_commands = []
        for cat in self.commands_config.get("categories", []):
            for cmd in cat.get("commands", []):
                if query in cmd.get("name", "").lower() or query in cmd.get("description", "").lower() or query in cmd.get("command", "").lower():
                    matched_commands.append(cmd.get("name"))
                    
        if matched_commands:
            self.cmd_menu.configure(values=matched_commands)
            self.cmd_var.set(matched_commands[0])
            self.on_command_change(matched_commands[0])
        else:
            self.cmd_menu.configure(values=[])
            self.cmd_var.set("")
            self.on_command_change("")

    def on_category_change(self, selected_category):
        cat_data = self.get_category_data(selected_category)
        if cat_data:
            commands = [cmd.get("name") for cmd in cat_data.get("commands", [])]
            self.cmd_menu.configure(values=commands)
            if commands:
                self.cmd_var.set(commands[0])
                self.on_command_change(commands[0])
            else:
                self.cmd_var.set("")
                self.on_command_change("")
        else:
            self.cmd_menu.configure(values=[])
            self.cmd_var.set("")
            self.on_command_change("")

    def on_command_change(self, selected_command):
        if self.cat_var.get() == "⭐ Favoritos":
            self.fav_btn.configure(text="🗑️", font=("Segoe UI Emoji", 15), anchor="center", fg_color="#E74C3C", hover_color="#C0392B", command=self.remove_favorite)
        else:
            self.fav_btn.configure(text="⭐", font=("Segoe UI Emoji", 15), anchor="center", fg_color="#F39C12", hover_color="#D68910", command=self.save_favorite)
            
        for widget in self.args_frame.winfo_children():
            widget.destroy()
        self.current_args_vars.clear()
        gc.collect()

        cmd_data = self.get_command_data(selected_command)
        if cmd_data:
            from functions.setup_manager import get_missing_commands, PLUGINS
            missing = get_missing_commands()
            if cmd_data.get("command") in missing:
                plugin_needed = None
                for pid, p in PLUGINS.items():
                    if cmd_data.get("command") in p["cmds"]:
                        plugin_needed = pid
                        break
                        
                lbl = ctk.CTkLabel(self.args_frame, text=f"⚠️ Falta {PLUGINS[plugin_needed]['name']}.", text_color="#E74C3C", font=("Arial", 14, "bold"))
                lbl.pack(pady=20)
                
                def install_it():
                    from functions.setup_manager import PluginInstaller
                    def on_done(success):
                        if success:
                            self.on_command_change(selected_command)
                    PluginInstaller(self, plugin_needed, on_done)
                
                btn = ctk.CTkButton(self.args_frame, text="Instalar Complemento", fg_color="#F39C12", hover_color="#D68910", command=install_it)
                btn.pack(pady=10)
                self.execute_btn.configure(state="disabled")
                return
            else:
                self.execute_btn.configure(state="normal")
                
            if cmd_data.get("name") == "Compresor de Multimedia":
                self.update_hardware_options(cmd_data)
                
            args = cmd_data.get("args", [])
            for arg in args:
                arg_name = arg.get("name")
                arg_type = arg.get("type")
                arg_flag = arg.get("flag", "")
                arg_desc = arg.get("description", "")
                
                row_frame = ctk.CTkFrame(self.args_frame, fg_color="transparent")
                row_frame.pack(fill="x", pady=10)
                
                var = ctk.StringVar(value=arg.get("value", ""))
                var.trace_add("write", lambda *args: self.update_preview())
                
                if arg_type == "checkbox":
                    chk = ctk.CTkCheckBox(row_frame, text=arg_name, variable=var, onvalue=arg_flag, offvalue="")
                    chk.pack(side="left", padx=(0, 10))
                elif arg_type in ["entry", "directory_entry", "file_entry", "save_file_entry"]:
                    lbl = ctk.CTkLabel(row_frame, text=f"{arg_name}:", wraplength=180, justify="left")
                    lbl.pack(side="left", padx=(0, 5))
                    
                    if arg_type in ["directory_entry", "file_entry", "save_file_entry"]:
                        def browse_folder(v=var):
                            folder = filedialog.askdirectory()
                            if folder:
                                folder = folder.replace("/", "\\")
                                if " " in folder and not folder.startswith('"'):
                                    folder = f'"{folder}"'
                                v.set(folder)
                                
                        def browse_file(v=var):
                            file_path = filedialog.askopenfilename()
                            if file_path:
                                file_path = file_path.replace("/", "\\")
                                if " " in file_path and not file_path.startswith('"'):
                                    file_path = f'"{file_path}"'
                                v.set(file_path)

                        def browse_save_file(v=var):
                            file_path = filedialog.asksaveasfilename(defaultextension="*.*", filetypes=[("Todos los archivos", "*.*")])
                            if file_path:
                                file_path = file_path.replace("/", "\\")
                                if " " in file_path and not file_path.startswith('"'):
                                    file_path = f'"{file_path}"'
                                v.set(file_path)
                                
                        btn_frame_paths = ctk.CTkFrame(row_frame, fg_color="transparent")
                        btn_frame_paths.pack(side="right", padx=(0, 10))
                        
                        if arg_type == "save_file_entry":
                            btn_browse_save = ctk.CTkButton(btn_frame_paths, text="💾 Guardar Como...", width=60, command=browse_save_file)
                            btn_browse_save.pack(side="left", padx=(0, 5))
                        elif arg_type == "file_entry":
                            btn_browse_file = ctk.CTkButton(btn_frame_paths, text="📄 Archivo", width=60, command=browse_file)
                            btn_browse_file.pack(side="left", padx=(0, 5))
                        
                        if arg_type in ["directory_entry", "file_entry"]:
                            btn_browse_folder = ctk.CTkButton(btn_frame_paths, text="📁 Carpeta", width=60, command=browse_folder)
                            btn_browse_folder.pack(side="left")
                        
                    ent = ctk.CTkEntry(row_frame, textvariable=var, placeholder_text="Escribir...", border_width=0)
                    ent.pack(side="left", fill="x", expand=True, padx=(0, 10))
                    
                    # The browse buttons and entry were already handled above
                        
                elif arg_type == "radio_group":
                    lbl = ctk.CTkLabel(row_frame, text=f"{arg_name}:")
                    lbl.pack(side="top", anchor="w", padx=(0, 5))
                    
                    rb_frame = ctk.CTkFrame(row_frame, fg_color="transparent")
                    rb_frame.pack(side="top", fill="x", expand=True, padx=(10, 0))
                    
                    options = arg.get("options", [])
                    for opt in options:
                        opt_name = opt.get("name")
                        opt_flag = opt.get("flag", "")
                        rb = ctk.CTkRadioButton(rb_frame, text=opt_name, variable=var, value=opt_flag)
                        rb.pack(side="top", anchor="w", pady=(0, 5))
                        
                elif arg_type == "drive_dropdown":
                    lbl = ctk.CTkLabel(row_frame, text=f"{arg_name}:")
                    lbl.pack(side="left", padx=(0, 5))
                    drives = self.get_windows_drives()
                    if drives:
                        var.set(drives[0])
                    dropdown = ctk.CTkOptionMenu(row_frame, variable=var, values=drives)
                    dropdown.pack(side="left", fill="x", expand=True, padx=(0, 10))
                    
                elif arg_type == "disk_dropdown":
                    lbl = ctk.CTkLabel(row_frame, text=f"{arg_name}:")
                    lbl.pack(side="left", padx=(0, 5))
                    pdisks = self.get_physical_disks()
                    if pdisks:
                        var.set(pdisks[0])
                    dropdown = ctk.CTkOptionMenu(row_frame, variable=var, values=pdisks)
                    dropdown.pack(side="left", fill="x", expand=True, padx=(0, 10))
                    
                elif arg_type == "netadapter_dropdown":
                    lbl = ctk.CTkLabel(row_frame, text=f"{arg_name}:")
                    lbl.pack(side="left", padx=(0, 5))
                    adapters = self.get_network_adapters()
                    if adapters:
                        var.set(adapters[0])
                    dropdown = ctk.CTkOptionMenu(row_frame, variable=var, values=adapters)
                    dropdown.pack(side="left", fill="x", expand=True, padx=(0, 10))
                    
                elif arg_type == "wifi_radio_group":
                    lbl = ctk.CTkLabel(row_frame, text=f"{arg_name}:")
                    lbl.pack(side="top", anchor="w", padx=(0, 5))
                    
                    rb_frame = ctk.CTkFrame(row_frame, fg_color="transparent")
                    rb_frame.pack(side="top", fill="x", expand=True, padx=(10, 0))
                    
                    profiles = self.get_wifi_profiles()
                    if profiles:
                        var.set(profiles[0])
                    for prof in profiles:
                        rb = ctk.CTkRadioButton(rb_frame, text=prof, variable=var, value=prof)
                        rb.pack(side="top", anchor="w", pady=(0, 5))
                    
                elif arg_type == "threads_dropdown":
                    lbl = ctk.CTkLabel(row_frame, text=f"{arg_name}:")
                    lbl.pack(side="left", padx=(0, 5))
                    threads_options = self.get_cpu_threads_list()
                    if threads_options:
                        var.set(threads_options[0])
                    dropdown = ctk.CTkOptionMenu(row_frame, variable=var, values=threads_options)
                    dropdown.pack(side="left", fill="x", expand=True, padx=(0, 10))
                    
                elif arg_type == "password_single":
                    lbl = ctk.CTkLabel(row_frame, text=f"{arg_name}:")
                    lbl.pack(side="left", padx=(0, 5))
                    
                    ent = ctk.CTkEntry(row_frame, textvariable=var, show="*", placeholder_text="Contraseña...", border_width=0)
                    ent.pack(side="left", fill="x", expand=True, padx=(0, 5))
                    
                    btn_show_s = ctk.CTkButton(row_frame, text="👁️", width=30, fg_color="transparent", text_color=("black", "white"), hover_color=("#E5E5E5", "#333333"))
                    def toggle_show_s(b=btn_show_s, e=ent):
                        if e.cget("show") == "*":
                            e.configure(show="")
                            b.configure(text="🙈")
                        else:
                            e.configure(show="*")
                            b.configure(text="👁️")
                    btn_show_s.configure(command=toggle_show_s)
                    btn_show_s.pack(side="left", padx=(0, 10))
                    
                elif arg_type == "password_double":
                    lbl = ctk.CTkLabel(row_frame, text=f"{arg_name}:")
                    lbl.pack(side="top", anchor="w", padx=(0, 5))
                    
                    pw_frame = ctk.CTkFrame(row_frame, fg_color="transparent")
                    pw_frame.pack(side="top", fill="x", expand=True)
                    
                    var1 = ctk.StringVar()
                    var2 = ctk.StringVar()
                    var.set("") # var is the main one used for command
                    
                    ent1 = ctk.CTkEntry(pw_frame, textvariable=var1, show="*", placeholder_text="Contraseña...", border_width=0)
                    ent1.pack(side="left", fill="x", expand=True, padx=(0, 5))
                    
                    ent2 = ctk.CTkEntry(pw_frame, textvariable=var2, show="*", placeholder_text="Confirmar Contraseña...", border_width=0)
                    ent2.pack(side="left", fill="x", expand=True, padx=(5, 5))
                    
                    btn_show = ctk.CTkButton(pw_frame, text="👁️", width=30, fg_color="transparent", text_color=("black", "white"), hover_color=("#E5E5E5", "#333333"))
                    def toggle_show(b=btn_show, e1=ent1, e2=ent2):
                        if e1.cget("show") == "*":
                            e1.configure(show="")
                            e2.configure(show="")
                            b.configure(text="🙈")
                        else:
                            e1.configure(show="*")
                            e2.configure(show="*")
                            b.configure(text="👁️")
                    btn_show.configure(command=toggle_show)
                    btn_show.pack(side="left")
                    
                    def check_match(*args_cb, v=var, e2=ent2, v1_var=var1, v2_var=var2):
                        v1 = v1_var.get()
                        v2 = v2_var.get()
                        if v1 != v2 or not v1:
                            e2.configure(border_color="red", border_width=2)
                            v.set("")
                        else:
                            e2.configure(border_color="green", border_width=2)
                            v.set(v1)
                    var1.trace_add("write", check_match)
                    var2.trace_add("write", check_match)
                
                self.current_args_vars[arg_name] = {"var": var, "type": arg_type, "flag": arg_flag}
                
                btn_info = ctk.CTkButton(
                    row_frame, text="ℹ", width=25, height=25, fg_color="transparent",
                    text_color=("black", "white"), command=lambda n=arg_name, d=arg_desc: self.show_arg_info(n, d)
                )
                btn_info.pack(side="right")
        
        self.update_preview()

    def update_hardware_options(self, cmd_data):
        import subprocess
        
        has_nvenc = False
        has_amf = False
        has_qsv = False

        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            output = subprocess.check_output(['powershell', '-Command', 'Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name'], text=True, startupinfo=startupinfo)
            out_upper = output.upper()
            if 'NVIDIA' in out_upper:
                has_nvenc = True
            if 'AMD' in out_upper or 'RADEON' in out_upper:
                has_amf = True
            if 'INTEL' in out_upper:
                has_qsv = True
        except Exception:
            pass

        options = [
            {'name': 'Auto-Detectar (Prioriza Dedicada)', 'flag': '--hw auto'}
        ]
        
        if has_nvenc:
            options.append({'name': 'NVIDIA (NVENC) - Dedicada', 'flag': '--hw nvenc'})
        if has_amf:
            options.append({'name': 'AMD (AMF)', 'flag': '--hw amf'})
        if has_qsv:
            options.append({'name': 'Intel (QSV) - Integrada', 'flag': '--hw qsv'})
            
        options.append({'name': 'Solo CPU (Lento pero seguro)', 'flag': '--hw cpu'})

        for arg in cmd_data.get("args", []):
            if arg.get("name") == "Motor de Aceleracion de Hardware":
                arg["options"] = options
                # Pre-seleccionar Auto
                arg["value"] = "--hw auto"
                break

    def update_preview(self):
        selected_command = self.cmd_var.get()
        if not selected_command:
            self.preview_var.set("")
            return

        cmd_data = self.get_command_data(selected_command)
        if not cmd_data:
            return

        command_list = [cmd_data.get("command", "")]
        for arg_name, arg_data in self.current_args_vars.items():
            val = arg_data["var"].get().strip()
            if val:
                if arg_data["type"] in ["checkbox", "radio_group"]:
                    if arg_data["type"] == "checkbox" and val != arg_data["flag"]:
                        continue
                    command_list.append(val)
                elif arg_data["type"] in ["entry", "directory_entry", "file_entry", "save_file_entry", "wifi_radio_group", "netadapter_dropdown"]:
                    if arg_data["type"] in ["directory_entry", "file_entry", "save_file_entry"]:
                        val = val.replace("/", "\\")
                    if any(c in val for c in [" ", ",", ";", "&", "|", "(", ")", "'"]) and not val.startswith('"'):
                        if "powershell" in command_list[0].lower():
                            val = f"'\"{val}\"'"
                        else:
                            val = f'"{val}"'
                    if arg_data["flag"]:
                        command_list.append(arg_data["flag"])
                    command_list.append(val)
                elif arg_data["type"] in ["drive_dropdown", "disk_dropdown", "threads_dropdown"]:
                    val_to_use = val.split(" ")[0]
                    if arg_data["flag"]:
                        command_list.append(arg_data["flag"])
                    command_list.append(val_to_use)
        
        full_command_str = " ".join(command_list)
        self.preview_var.set(full_command_str)

    def run_help(self):
        if self.is_running:
            return
        cmd_data = self.get_command_data(self.cmd_var.get())
        if cmd_data:
            help_cmd = f"{cmd_data.get('command')} /?"
            self.execute_external(help_cmd)

    def toggle_execution(self):
        if self.is_running:
            cmd_executor.stop_command()
        else:
            self.check_drives_and_run()

    def check_drives_and_run(self):
        cmd_str = self.preview_var.get()
        if not cmd_str: return
        
        # Extraer posibles letras de unidad (ej. C:\ o E:\)
        import re, threading, subprocess
        drives = set(re.findall(r'([A-Za-z]):[\\/]', cmd_str))
        
        # Si no hay unidades evidentes, ejecutamos normal
        if not drives:
            self.run_command()
            return
            
        self.execute_btn.configure(text="Analizando disco...", state="disabled")
        
        def _check():
            warnings = []
            try:
                for d in drives:
                    script = f"""
                    $vol = Get-Partition -DriveLetter '{d}' -ErrorAction SilentlyContinue | Get-Disk -ErrorAction SilentlyContinue
                    if ($vol) {{
                        Write-Output "$($vol.MediaType)|$($vol.IsReadOnly)|$($vol.HealthStatus)"
                    }}
                    """
                    out = subprocess.check_output(["powershell", "-NoProfile", "-Command", script], creationflags=subprocess.CREATE_NO_WINDOW, text=True).strip()
                    if out:
                        parts = out.split('|')
                        if len(parts) >= 3:
                            media_type, is_ro, health = parts[0], parts[1], parts[2]
                            
                            if is_ro.lower() == 'true':
                                warnings.append(f"• El disco {d}: está bloqueado en modo Solo Lectura (Hardware). Cualquier comando de escritura o borrado fallará. Si es un SSD, es probable que haya fallado permanentemente.")
                            if health.lower() not in ['healthy', 'unknown', '']:
                                warnings.append(f"• El estado de salud del disco {d}: es '{health}'. Proceder con precaución.")
                            
                            if media_type.lower() == 'ssd':
                                cmd_lower = cmd_str.lower()
                                if "chkdsk" in cmd_lower and "/r" in cmd_lower:
                                    warnings.append(f"• Vas a ejecutar CHKDSK /R en un SSD ({d}:). Esto causa desgaste y escrituras masivas innecesarias. En SSDs, los sectores se reasignan automáticamente por firmware.")
                                if "clear-disk" in cmd_lower:
                                    warnings.append(f"• CUIDADO: Clear-Disk borrará TODA la información y particiones del SSD ({d}:) de forma irrecuperable.")
            except Exception as e:
                pass
                
            self.after(0, self._on_check_done, warnings)
            
        threading.Thread(target=_check, daemon=True).start()

    def _on_check_done(self, warnings):
        self.execute_btn.configure(text="Ejecutar Comando", state="normal")
        if warnings:
            from tkinter import messagebox
            msg = "Resultados del Análisis de Unidad:\n\n" + "\n\n".join(warnings) + "\n\n¿Estás completamente seguro de continuar con la ejecución?"
            if not messagebox.askyesno("Advertencia de Hardware", msg):
                return
        self.run_command()

    def remove_favorite(self):
        cmd_name = self.cmd_var.get()
        favs = []
        try:
            if os.path.exists(get_user_data_path("favorites.json")):
                with open(get_user_data_path("favorites.json"), "r", encoding="utf-8") as f:
                    favs = json.load(f)
        except:
            return
            
        new_favs = [f for f in favs if f.get("name") != cmd_name]
        
        with open(get_user_data_path("favorites.json"), "w", encoding="utf-8") as f:
            json.dump(new_favs, f, indent=4)
            
        self.output_textbox.configure(state="normal")
        self.output_textbox.insert("end", f"\n[!] Comando '{cmd_name}' eliminado de Favoritos.\n(Reinicia la app para actualizar la lista)\n", "error")
        self.output_textbox.see("end")
        self.output_textbox.configure(state="disabled")

    def save_favorite(self):
        cmd_data = self.get_command_data(self.cmd_var.get())
        if not cmd_data: return
        
        import copy
        fav_cmd = copy.deepcopy(cmd_data)
        
        for arg in fav_cmd.get("args", []):
            arg_name = arg.get("name")
            if arg_name in self.current_args_vars:
                arg["value"] = self.current_args_vars[arg_name]["var"].get()
                
        favs = []
        try:
            if os.path.exists(get_user_data_path("favorites.json")):
                with open(get_user_data_path("favorites.json"), "r", encoding="utf-8") as f:
                    favs = json.load(f)
        except:
            pass
            
        base_name = f"{fav_cmd['name']} (Fav)"
        fav_name = base_name
        counter = 1
        
        # Check for exact duplicates or generate a unique name
        while any(f.get("name") == fav_name for f in favs):
            existing = next((f for f in favs if f.get("name") == fav_name), None)
            if existing:
                # Compare args
                if existing.get("args") == fav_cmd.get("args"):
                    self.output_textbox.configure(state="normal")
                    self.output_textbox.insert("end", "\n[!] Este comando con los mismos parámetros ya existe en Favoritos.\n", "error")
                    self.output_textbox.see("end")
                    self.output_textbox.configure(state="disabled")
                    return
            counter += 1
            fav_name = f"{base_name} {counter}"
            
        fav_cmd["name"] = fav_name
            
        favs.append(fav_cmd)
        with open(get_user_data_path("favorites.json"), "w", encoding="utf-8") as f:
            json.dump(favs, f, indent=4)
            
        self.output_textbox.configure(state="normal")
        self.output_textbox.insert("end", f"\n[⭐] Comando '{fav_name}' guardado en Favoritos.\n(Reinicia la app para verlo en la lista)\n", "success")
        self.output_textbox.see("end")
        self.output_textbox.configure(state="disabled")

    def run_command(self):
        if not self.preview_var.get():
            return
        self.execute_external(self.preview_var.get())

    def execute_external(self, command_str):
        if hasattr(self, 'auto_clear_var') and self.auto_clear_var.get():
            self.clear_output()
            
        if hasattr(self, 'progressbar'):
            self.progressbar.set(0)
            if hasattr(self, 'lbl_progress'):
                self.lbl_progress.configure(text="0%")
        self.append_output(f"\n> {command_str}\n")
        self.is_running = True
        self.execute_btn.configure(text="Detener ejecución", fg_color="red", hover_color="#8B0000")
        self.cat_menu.configure(state="disabled")
        self.cmd_menu.configure(state="disabled")
        
        def on_finish():
            self.is_running = False
            self.execute_btn.configure(text="Ejecutar Comando", fg_color=["#1F883D", "#238636"], hover_color=["#1A7F37", "#2EA043"])
            self.cat_menu.configure(state="normal")
            self.cmd_menu.configure(state="normal")

        cmd_executor.execute_command_async(
            command_string=command_str,
            output_callback=self.append_output,
            finished_callback=lambda: self.after(0, on_finish)
        )

    def append_output(self, text):
        def _append():
            nonlocal text
            self.output_textbox.configure(state="normal")
            
            if not hasattr(self, '_last_was_cr'):
                self._last_was_cr = False
                
            # Limpiar lineas normales de Windows
            if text.endswith('\r\n'):
                text = text[:-2] + '\n'
                
            if self._last_was_cr:
                if text == '\n':
                    self._last_was_cr = False
                    self.output_textbox.insert("end", "\n")
                    self.output_textbox.see("end")
                    self.output_textbox.configure(state="disabled")
                    return
                else:
                    self.output_textbox.delete("end-1c linestart", "end-1c")
                    self._last_was_cr = False

            if text.endswith('\r'):
                self._last_was_cr = True
                text = text[:-1]
                
            if text:
                pattern = re.compile(r'(\b\d{1,3}(?:\.\d{1,3}){3}\b)|(\b(?:error|failed|denied|fallo|denegado|acceso denegado)\b)|(\b(?:success|exitoso|completado|100%|correcto)\b)|([A-Za-z]:\\[^\s]*)', re.IGNORECASE)
                
                last_end = 0
                for match in pattern.finditer(text):
                    start, end = match.span()
                    if start > last_end:
                        self.output_textbox.insert("end", text[last_end:start])
                    
                    matched_text = match.group(0)
                    if match.group(1): # IP
                        self.output_textbox.insert("end", matched_text, "ip")
                    elif match.group(2): # Error
                        self.output_textbox.insert("end", matched_text, "error")
                    elif match.group(3): # Success
                        self.output_textbox.insert("end", matched_text, "success")
                    elif match.group(4): # Path
                        self.output_textbox.insert("end", matched_text, "path")
                        
                    last_end = end
                
                if last_end < len(text):
                    self.output_textbox.insert("end", text[last_end:])

                self.output_textbox.see("end")
                
                match = re.search(r'\b(\d{1,3})%', text)
                if match and hasattr(self, 'progressbar'):
                    try:
                        val = int(match.group(1))
                        if 0 <= val <= 100:
                            self.progressbar.set(val / 100.0)
                            if hasattr(self, 'lbl_progress'):
                                self.lbl_progress.configure(text=f"{val}%")
                    except:
                        pass
                        
            self.output_textbox.configure(state="disabled")
        self.after(0, _append)

    def clear_output(self):
        self.output_textbox.configure(state="normal")
        self.output_textbox.delete("1.0", "end")
        self.output_textbox.configure(state="disabled")

    def get_html_template(self, content, title="Reporte de Ejecución", command="Desconocido"):
        import datetime, os
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        template_path = os.path.join(os.path.dirname(__file__), "resources/templates", "base_report.html")
        
        if os.path.exists(template_path):
            with open(template_path, "r", encoding="utf-8") as tf:
                html = tf.read()
                # Escapar contenido
                safe_content = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                html = html.replace("{{TITLE}}", title)
                html = html.replace("{{COMMAND}}", command)
                html = html.replace("{{TIMESTAMP}}", timestamp)
                html = html.replace("{{CONTENT}}", safe_content)
                return html
        else:
            # Fallback simple
            return f"<html><body><h1>{title}</h1><pre>{content}</pre></body></html>"

    def show_plugins(self):
        from functions.utils import get_user_data_path, apply_window_theme
        from functions.setup_manager import PLUGINS, PluginInstaller, is_plugin_installed
        import os
        import subprocess
        import sys
        
        win = ctk.CTkToplevel(self)
        win.title("Gestor de Complementos")
        win.geometry("550x450")
        win.transient(self)
        win.grab_set()
        
        win.update_idletasks()
        x = int(self.winfo_x() + (self.winfo_width() / 2) - (550 / 2))
        y = int(self.winfo_y() + (self.winfo_height() / 2) - (450 / 2))
        win.geometry(f"+{x}+{y}")
        
        apply_window_theme(win)
        
        lbl_title = ctk.CTkLabel(win, text="Complementos Disponibles", font=("Arial", 16, "bold"))
        lbl_title.pack(pady=15)


        
        self.backup_vars = {}
        
        frame = ctk.CTkScrollableFrame(win)
        frame.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        
        for pid, p in PLUGINS.items():
            path = get_user_data_path(os.path.join("tools", p["filename"]))
            is_installed = is_plugin_installed(p)
            
            row = ctk.CTkFrame(frame)
            row.pack(fill="x", padx=10, pady=10)
            
            name_lbl = ctk.CTkLabel(row, text=f"{p['name']} ({p['size_str']})", font=("Arial", 14, "bold"))
            name_lbl.pack(side="top", anchor="w", padx=10, pady=(10, 0))
            
            desc_lbl = ctk.CTkLabel(row, text=p['desc'], text_color="gray", wraplength=400, justify="left")
            desc_lbl.pack(side="top", anchor="w", padx=10)
            
            status_text = "🟢 Instalado" if is_installed else "🔴 No Instalado"
            status_lbl = ctk.CTkLabel(row, text=status_text)
            status_lbl.pack(side="top", anchor="w", padx=10, pady=(5, 10))
            
            btn_frame = ctk.CTkFrame(row, fg_color="transparent")
            btn_frame.pack(side="top", fill="x", padx=10, pady=(0, 10))
            
            def open_folder(fpath=path):
                tools_dir = os.path.dirname(fpath)
                os.makedirs(tools_dir, exist_ok=True)
                subprocess.Popen(f'explorer "{tools_dir}"')
                
            def delete_plugin(fpath=path):
                try:
                    os.remove(fpath)
                    from tkinter import messagebox
                    messagebox.showinfo("Éxito", "Complemento eliminado. El programa se reiniciará.")
                    win.destroy()
                    self.quit()
                    import ctypes
                    if getattr(sys, 'frozen', False):
                        ctypes.windll.shell32.ShellExecuteW(None, "open", sys.executable, "", None, 1)
                    else:
                        ctypes.windll.shell32.ShellExecuteW(None, "open", sys.executable, f'"{os.path.abspath(sys.argv[0])}"', None, 1)
                    os._exit(0)
                except Exception as e:
                    from tkinter import messagebox
                    messagebox.showerror("Error", f"No se pudo eliminar: {e}")
                    
            def install_plugin(plug_id=pid):
                def on_done(success):
                    if success:
                        win.destroy()
                        self.show_plugins()
                        self.on_category_change(self.cat_var.get())
                PluginInstaller(win, plug_id, on_done)
            
            if is_installed:
                btn_open = ctk.CTkButton(btn_frame, text="Abrir Ubicación", width=120, command=open_folder)
                btn_open.pack(side="left", padx=(0, 10))
                
                btn_del = ctk.CTkButton(btn_frame, text="Eliminar", width=80, fg_color="#E74C3C", hover_color="#C0392B", command=delete_plugin)
                btn_del.pack(side="left")
                
                if pid == "ai_vault":
                    def open_ai_config():
                        from functions.interpreter_addon import ConfigAPIWindow
                        ConfigAPIWindow(self)
                    btn_ai = ctk.CTkButton(btn_frame, text="⚙️ Configurar Bóveda IA", width=120, fg_color="#8E44AD", hover_color="#9B59B6", command=open_ai_config)
                    btn_ai.pack(side="left", padx=(10, 0))

                self.backup_vars[pid] = ctk.IntVar(value=0)
                chk_backup = ctk.CTkCheckBox(row, text="Respaldar", variable=self.backup_vars[pid])
                chk_backup.pack(side="right", padx=10, pady=10)
            else:
                btn_inst = ctk.CTkButton(btn_frame, text="Instalar", width=80, fg_color="#F39C12", hover_color="#D68910", command=install_plugin)
                btn_inst.pack(side="left")

        def export_plugins():
            to_export = [pid for pid, var in self.backup_vars.items() if var.get() == 1]
            if not to_export:
                from tkinter import messagebox
                messagebox.showwarning("Aviso", "Selecciona al menos un complemento instalado para respaldar.")
                return
            from tkinter import filedialog
            zip_path = filedialog.asksaveasfilename(defaultextension=".zip", filetypes=[("Archivos ZIP", "*.zip")], title="Respaldar Complementos")
            if zip_path:
                import zipfile
                try:
                    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        for pid in to_export:
                            filename = PLUGINS[pid]["filename"]
                            filepath = get_user_data_path(os.path.join("tools", filename))
                            if os.path.exists(filepath):
                                zipf.write(filepath, arcname=filename)
                    from tkinter import messagebox
                    messagebox.showinfo("Éxito", f"Complementos respaldados en:\n{zip_path}")
                except Exception as e:
                    from tkinter import messagebox
                    messagebox.showerror("Error", f"Fallo al respaldar: {e}")

        def import_plugins():
            from tkinter import filedialog
            zip_path = filedialog.askopenfilename(filetypes=[("Archivos ZIP", "*.zip")], title="Importar Complementos")
            if zip_path:
                import zipfile
                try:
                    with zipfile.ZipFile(zip_path, 'r') as zipf:
                        tools_dir = get_user_data_path("tools")
                        os.makedirs(tools_dir, exist_ok=True)
                        for filename in zipf.namelist():
                            if ".." in filename or filename.startswith("/"): continue
                            zipf.extract(filename, path=tools_dir)
                    from tkinter import messagebox
                    messagebox.showinfo("Éxito", "Complementos importados correctamente. El gestor se recargará.")
                    win.destroy()
                    self.show_plugins()
                except Exception as e:
                    from tkinter import messagebox
                    messagebox.showerror("Error", f"Fallo al importar: {e}")

        btn_action_frame = ctk.CTkFrame(win, fg_color="transparent")
        btn_action_frame.pack(fill="x", padx=20, pady=(0, 20))
        
        btn_export = ctk.CTkButton(btn_action_frame, text="📦 Exportar ZIP", fg_color="#2E86C1", hover_color="#2874A6", command=export_plugins)
        btn_export.pack(side="left", expand=True, padx=5)

        btn_import = ctk.CTkButton(btn_action_frame, text="📥 Importar ZIP", fg_color="#27AE60", hover_color="#229954", command=import_plugins)
        btn_import.pack(side="right", expand=True, padx=5)

    def show_table_view(self):
        content = self.output_textbox.get("1.0", "end-1c").strip()
        if not content:
            messagebox.showinfo("Información", "No hay resultados para mostrar en la tabla.")
            return
        # Intentar normalizar salidas de powershell
        lines = content.split('\n')
        # Filter purely decorative lines
        clean_lines = [l for l in lines if not l.startswith('---')]
        
        from functions.tabular_viewer import show_tabular_data
        show_tabular_data(self, self.cmd_var.get(), '\n'.join(clean_lines))

    def export_output(self):
        content = self.output_textbox.get("1.0", "end-1c")
        if not content.strip(): return
        
        from tkinter import messagebox
        import re
        
        # Preguntar si desea exportar completo o solo resumen
        ans = messagebox.askyesnocancel(
            "Tipo de Exportación", 
            "¿Deseas exportar TODO el historial de la consola?\n\n"
            "• SÍ: Exporta toda la salida (útil para ver procesos detalle a detalle).\n"
            "• NO: Exporta SOLO el resumen final (recomendado para no sobrecargar archivos HTML).\n"
            "• CANCELAR: Aborta la exportación."
        )
        
        if ans is None:
            return
            
        if not ans:
            # Extraer solo el resumen
            lines = content.split('\n')
            summary_start = 0
            for i in range(len(lines)-1, -1, -1):
                if "ARCHIVOS COMPLETADOS" in lines[i] or "ARCHIVOS CON ERRORES" in lines[i] or "RESUMEN DE" in lines[i]:
                    # Buscar la línea divisoria '===' justo arriba del resumen
                    for j in range(i, max(-1, i-5), -1):
                        if "===" in lines[j]:
                            summary_start = j
                            break
                    else:
                        summary_start = max(0, i-2)
                    break
            
            if summary_start > 0:
                content = "\n... (Salida larga de proceso omitida) ...\n\n" + "\n".join(lines[summary_start:])
            elif len(lines) > 300:
                content = "\n... (Salida larga omitida, marcador de resumen no detectado) ...\n\n" + "\n".join(lines[-300:])
        
        file_path = filedialog.asksaveasfilename(defaultextension=".html", filetypes=[("HTML Interactivo", "*.html"), ("Text file", "*.txt")], title="Exportar Consola a Plantilla")
        if file_path:
            with open(file_path, "w", encoding="utf-8") as f:
                if file_path.endswith(".html"):
                    cmd = self.cmd_var.get()
                    f.write(self.get_html_template(content, title=cmd, command=self.preview_var.get() or cmd))
                else:
                    f.write(content)
            self.output_textbox.configure(state="normal")
            self.output_textbox.insert("end", f"\n[!] Reporte Exportado con Plantilla a: {file_path}\n", "success")
            self.output_textbox.see("end")
            self.output_textbox.configure(state="disabled")


    def run_interpreter(self):
        text_content = self.output_textbox.get("1.0", "end")
        from functions.interpreter_addon import InterpreterApp
        InterpreterApp(self, initial_text=text_content)

    def convert_old_report(self):
        # Abre un archivo antiguo (.txt o .html basico) y lo convierte al nuevo formato
        input_path = filedialog.askopenfilename(filetypes=[("Archivos de texto/HTML", "*.txt *.html *.log"), ("Todos los archivos", "*.*")], title="Selecciona un reporte antiguo para convertir")
        if not input_path: return
        
        try:
            with open(input_path, "r", encoding="utf-8") as f:
                content = f.read()
        except:
            # Fallback for ANSI encoding
            with open(input_path, "r", encoding="latin-1") as f:
                content = f.read()
                
        # Limpiar si el archivo viejo ya era un HTML (muy básico, extraemos el body text si es posible, o lo metemos crudo)
        import re
        if "<body" in content.lower():
            match = re.search(r'<div class="console">(.*?)</div>', content, re.IGNORECASE | re.DOTALL)
            if match:
                content = match.group(1).replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
            else:
                # Si no encontramos consola, quitamos las etiquetas html basicas
                content = re.sub(r'<[^>]+>', '', content)

        from tkinter import messagebox
        ans = messagebox.askyesnocancel(
            "Tipo de Conversión", 
            "¿Deseas mantener TODO el historial del reporte antiguo?\n\n"
            "• SÍ: Convierte todo el texto íntegro.\n"
            "• NO: Extrae y convierte SOLO el resumen final (más ligero).\n"
            "• CANCELAR: Aborta la conversión."
        )
        
        if ans is None:
            return
            
        if not ans:
            # Extraer solo el resumen
            lines = content.split('\n')
            summary_start = 0
            for i in range(len(lines)-1, -1, -1):
                if "ARCHIVOS COMPLETADOS" in lines[i] or "ARCHIVOS CON ERRORES" in lines[i] or "RESUMEN DE" in lines[i]:
                    for j in range(i, max(-1, i-5), -1):
                        if "===" in lines[j]:
                            summary_start = j
                            break
                    else:
                        summary_start = max(0, i-2)
                    break
            
            if summary_start > 0:
                content = "\n... (Salida larga de proceso omitida durante la conversión) ...\n\n" + "\n".join(lines[summary_start:])
            elif len(lines) > 300:
                content = "\n... (Salida larga omitida, marcador no detectado) ...\n\n" + "\n".join(lines[-300:])

        output_path = filedialog.asksaveasfilename(defaultextension=".html", filetypes=[("HTML Interactivo", "*.html")], title="Guardar Nuevo Reporte Interactivo", initialfile=os.path.basename(input_path).split('.')[0] + "_interactivo.html")
        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(self.get_html_template(content, title="Reporte Convertido", command="Importado desde " + os.path.basename(input_path)))
            
            self.output_textbox.configure(state="normal")
            self.output_textbox.insert("end", f"\n[!] Reporte antiguo convertido con éxito a HTML interactivo: {output_path}\n", "success")
            self.output_textbox.see("end")
            self.output_textbox.configure(state="disabled")

    def show_credits(self):
        credits_win = ctk.CTkToplevel(self)
        credits_win.title("Acerca de GUI CMD ADVANCE")
        center_window(credits_win, 400, 450)
        credits_win.resizable(False, False)
        
        def set_credits_icon():
            try:
                credits_win.iconbitmap(get_resource_path("resources/app_icon.ico"))
            except:
                pass
                
        credits_win.after(200, set_credits_icon)
            
        credits_win.transient(self)
        credits_win.grab_set()
        
        # Icono o Título Principal
        lbl_title = ctk.CTkLabel(credits_win, text="GUI CMD ADVANCE", font=("Arial", 20, "bold"), text_color="#F39C12")
        lbl_title.pack(pady=(20, 5))
        
        lbl_version = ctk.CTkLabel(credits_win, text=f"Versión {__version__}", font=("Arial", 12))
        lbl_version.pack(pady=(0, 15))
        
        # Descripción
        desc = ("Herramienta gráfica avanzada para comandos de sistema.\n"
                "Diseñada para simplificar y optimizar tareas de\n"
                "mantenimiento, red y gestión de archivos en Windows.")
        lbl_desc = ctk.CTkLabel(credits_win, text=desc, font=("Arial", 12), justify="center")
        lbl_desc.pack(pady=10)
        
        # Autor y Copyright
        lbl_author = ctk.CTkLabel(credits_win, text="Desarrollador: GOLDEN FENIX", font=("Arial", 12, "bold"))
        lbl_author.pack(pady=(15, 5))
        
        lbl_copy = ctk.CTkLabel(credits_win, text="© 2026 GoldenFenix. Todos los derechos reservados.", font=("Arial", 10))
        lbl_copy.pack(pady=5)
        
        # Link GitHub
        def open_repo():
            webbrowser.open("https://github.com/GoldenFenix92/gui-cmd-advance")
            
        link_btn = ctk.CTkButton(credits_win, text="Ver Repositorio en GitHub", fg_color="#24292F", hover_color="#40464d", command=open_repo)
        link_btn.pack(pady=15)
        
        close_btn = ctk.CTkButton(credits_win, text="Cerrar", command=credits_win.destroy)
        close_btn.pack(pady=(10, 20))

    def open_process_manager(self):
        try:
            subprocess.Popen([sys.executable, sys.argv[0], "--run-process-manager"], creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir el Gestor de Procesos:\n{e}")

    def optimize_ram(self):
        try:
            import gc
            gc.collect()
            
            vbs_path = os.path.join(get_base_path(), "liberar_ram.vbs")
            with open(vbs_path, "w") as f:
                f.write('FreeMem=Space(100000000)')
                
            subprocess.run(["cscript", "//nologo", vbs_path], creationflags=subprocess.CREATE_NO_WINDOW)
            
            if os.path.exists(vbs_path):
                os.remove(vbs_path)
                
            messagebox.showinfo("RAM Optimizada", "Memoria inactiva liberada y procesos de fondo limpios correctamente.")
        except Exception as e:
            messagebox.showerror("Error", f"Ocurrió un error al intentar optimizar la RAM:\n{e}")
