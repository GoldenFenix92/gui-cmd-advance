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
from functions.utils import get_user_data_path, get_resource_path, center_window

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
        except Exception:
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

        self.credits_btn = ctk.CTkButton(self.top_bar, text="Créditos", width=80, height=25, fg_color="transparent", text_color=("black", "white"), command=self.show_credits)
        self.credits_btn.pack(side="right")

        self.plugins_btn = ctk.CTkButton(self.top_bar, text="Complementos", width=100, height=25, fg_color="#27AE60", hover_color="#2ECC71", command=self.show_plugins)
        self.plugins_btn.pack(side="right", padx=(0, 10))

        self.proc_btn = ctk.CTkButton(self.top_bar, text="Procesos", width=80, height=25, fg_color="#3498DB", hover_color="#2980B9", command=self.open_process_manager)
        self.proc_btn.pack(side="right", padx=(0, 10))
        if CTkToolTip: CTkToolTip(self.proc_btn, message="Gestor de Procesos y Servicios")

        self.ram_btn = ctk.CTkButton(self.top_bar, text="RAM", width=60, height=25, fg_color="#E67E22", hover_color="#D35400", command=self.optimize_ram)

        self.ram_btn.pack(side="right", padx=(0, 10))
        if CTkToolTip: CTkToolTip(self.ram_btn, message="Liberar memoria inactiva (RAM)")

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self.on_search)
        self.search_entry = ctk.CTkEntry(self.left_frame, textvariable=self.search_var, placeholder_text="Buscar comando...", border_width=0)
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
        
        self.pause_btn = ctk.CTkButton(self.btn_frame, text="Posponer", width=80, fg_color="#F39C12", hover_color="#D68910", command=self.pause_execution)
        # self.pause_btn.pack(side="left", padx=(0, 5)) # Se oculta por defecto
        
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
        
        self.lbl_progress = ctk.CTkLabel(self.progress_frame, text="Listo (0%)", font=("Consolas", 12, "bold"), anchor="e")
        self.lbl_progress.grid(row=0, column=1, padx=(10, 0), sticky="e")

        self.lbl_eta = ctk.CTkLabel(self.progress_frame, text="ETA: --:--", font=("Consolas", 12, "bold"), anchor="e")
        self.lbl_eta.grid(row=0, column=2, padx=(10, 0), sticky="e")

        # Export Buttons
        self.btn_frame = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        self.btn_frame.grid(row=3, column=0, padx=10, pady=(0, 5), sticky="sw")
        
        self.export_btn = ctk.CTkButton(self.btn_frame, text="Exportar Actual", width=100, command=self.export_output)
        self.export_btn.pack(side="left", padx=(0, 10))

        self.table_btn = ctk.CTkButton(self.btn_frame, text="Ver como Tabla", width=100, fg_color="#2E86C1", hover_color="#21618C", command=self.show_table_view)
        self.table_btn.pack(side="left", padx=(0, 10))
        if CTkToolTip: CTkToolTip(self.table_btn, message="Ver resultados en una tabla interactiva (ideal para CSV)")

        self.interpreter_btn = ctk.CTkButton(self.btn_frame, text="Interpretar Resultados", width=150, command=self.run_interpreter, fg_color="#8E44AD", hover_color="#9B59B6")
        self.interpreter_btn.pack(side="left")
        if CTkToolTip: CTkToolTip(self.interpreter_btn, message="Analiza el reporte con Inteligencia Artificial o de manera local")
        
        # Controles de energía debajo de la consola
        self.power_frame = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        self.power_frame.grid(row=4, column=0, columnspan=2, padx=10, pady=(2, 4), sticky="ew")

        self.keep_awake_var = ctk.BooleanVar(value=False)
        self.keep_awake_cb = ctk.CTkCheckBox(
            self.power_frame,
            text="Evitar suspensión / hibernación",
            variable=self.keep_awake_var,
        )
        self.keep_awake_cb.pack(side="left", padx=(0, 18))
        if CTkToolTip:
            CTkToolTip(
                self.keep_awake_cb,
                message="Evita que Windows suspenda o hiberne mientras se ejecuta un comando (la pantalla puede apagarse normalmente).",
            )

        self.shutdown_after_var = ctk.BooleanVar(value=False)
        self.shutdown_after_cb = ctk.CTkCheckBox(
            self.power_frame,
            text="Apagar PC al finalizar",
            variable=self.shutdown_after_var,
        )
        self.shutdown_after_cb.pack(side="left", padx=(0, 18))
        if CTkToolTip:
            CTkToolTip(
                self.shutdown_after_cb,
                message="Al terminar la ejecución, inicia una cuenta regresiva cancelable de 60s para apagar el equipo. Si ocurre un error, guarda un reporte HTML en el Escritorio antes de apagar.",
            )

        self.combo_suggestions_var = ctk.BooleanVar(value=True)
        self.combo_suggestions_cb = ctk.CTkCheckBox(
            self.power_frame,
            text="Sugerencias de combos",
            variable=self.combo_suggestions_var,
        )
        self.combo_suggestions_cb.pack(side="left")
        if CTkToolTip:
            CTkToolTip(
                self.combo_suggestions_cb,
                message="Muestra un modal con funciones recomendadas antes (Protocolo Seguro) o después del comando actual para encadenarlas automáticamente.",
            )

        # Dashboard (Status Bar)
        self.status_bar = ctk.CTkFrame(self.right_frame, height=25, fg_color="transparent")
        self.status_bar.grid(row=5, column=0, columnspan=2, sticky="ew")
        
        self.lbl_ram = ctk.CTkLabel(self.status_bar, text="RAM: --%", font=("Consolas", 12, "bold"))
        self.lbl_ram.pack(side="right", padx=10)
        
        self.lbl_cpu = ctk.CTkLabel(self.status_bar, text="CPU: --%", font=("Consolas", 12, "bold"))
        self.lbl_cpu.pack(side="right", padx=10)
        
        self.update_console_tags()

        self.update_status_dashboard()
        self.protocol("WM_DELETE_WINDOW", self._on_app_close)

        self.clear_frame = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        self.clear_frame.grid(row=3, column=1, padx=10, pady=(0, 10), sticky="se")

        self.auto_clear_var = ctk.BooleanVar(value=True)
        self.auto_clear_cb = ctk.CTkCheckBox(self.clear_frame, text="Auto-Limpiar", variable=self.auto_clear_var, width=100)
        self.auto_clear_cb.pack(side="left", padx=(0, 10))
        if CTkToolTip: CTkToolTip(self.auto_clear_cb, message="Limpiar la consola antes de ejecutar un nuevo comando")

        self.clear_btn = ctk.CTkButton(
            self.clear_frame,
            text="Limpiar",
            width=100,
            fg_color="#D97706",
            hover_color="#B45309",
            text_color="#FFFFFF",
            command=self.clear_output,
        )
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
        except Exception:
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
                
            self.lbl_cpu.configure(text=f"CPU: {cpu}%", text_color=get_color(cpu))
            self.lbl_ram.configure(text=f"RAM: {ram}%", text_color=get_color(ram))
        except Exception:
            self.lbl_cpu.configure(text="CPU: --%")
            self.lbl_ram.configure(text="RAM: --%")
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
        except Exception:
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

    def get_physical_disks(self, filter_status=None):
        import subprocess
        disks = []
        try:
            filter_mode = filter_status or "All"
            cmd = (
                f"$filter = '{filter_mode}'; "
                "$pDisks = @{}; "
                "try { Get-PhysicalDisk -ErrorAction SilentlyContinue | ForEach-Object { $pDisks[[string]$_.DeviceId] = $_ } } catch {}; "
                "$msftDisks = @{}; "
                "try { Get-Disk -ErrorAction SilentlyContinue | ForEach-Object { $msftDisks[[string]$_.Number] = $_ } } catch {}; "
                "$wmiDisks = @{}; "
                "try { Get-CimInstance Win32_DiskDrive -ErrorAction SilentlyContinue | ForEach-Object { $wmiDisks[[string]$_.Index] = $_ } } catch {}; "
                "$allIds = @($pDisks.Keys + $msftDisks.Keys + $wmiDisks.Keys) | Sort-Object { [int]$_ } -Unique; "
                "foreach ($id in $allIds) { "
                "  $d = $msftDisks[$id]; $pd = $pDisks[$id]; $wmi = $wmiDisks[$id]; "
                "  $isOffline = if ($d) { [bool]$d.IsOffline -or ($d.OperationalStatus -match 'Offline') } else { $false }; "
                "  if ($filter -eq 'Online' -and $isOffline) { continue }; "
                "  if ($filter -eq 'Offline' -and -not $isOffline) { continue }; "
                "  $friendly = if ($d -and $d.FriendlyName) { [string]$d.FriendlyName } elseif ($pd -and $pd.FriendlyName) { [string]$pd.FriendlyName } elseif ($wmi -and $wmi.Model) { [string]$wmi.Model } else { 'Disco ' + $id }; "
                "  $bus = if ($d -and $d.BusType) { [string]$d.BusType } elseif ($pd -and $pd.BusType) { [string]$pd.BusType } elseif ($wmi -and $wmi.InterfaceType) { [string]$wmi.InterfaceType } else { '' }; "
                "  $media = if ($pd -and $pd.MediaType) { [string]$pd.MediaType } else { '' }; "
                "  if ($bus -eq 'USB') { $kind = 'USB' } elseif ($media -eq 'SSD' -or $media -eq 'HDD') { $kind = $media } elseif ($bus -and $bus -ne 'Unspecified') { $kind = $bus } else { $kind = 'Disco' }; "
                "  $sizeVal = if ($d -and $d.Size) { $d.Size } elseif ($pd -and $pd.Size) { $pd.Size } elseif ($wmi -and $wmi.Size) { $wmi.Size } else { 0 }; "
                "  $gb = [math]::Round($sizeVal / 1GB, 1); "
                "  $stTag = if ($isOffline) { ' | Offline' } else { ' | Online' }; "
                "  $dynTag = if (-not $d) { ' | Dinamico' } else { '' }; "
                "  $tag = ' [' + $kind + ' | ' + $gb + ' GB' + $stTag + $dynTag + ']'; "
                "  $vStr = ''; "
                "  try { "
                "    $vols = Get-Partition -DiskNumber ([int]$id) -ErrorAction SilentlyContinue | Get-Volume -ErrorAction SilentlyContinue | Where-Object DriveLetter; "
                "    if ($vols) { "
                "      $lbls = $vols | ForEach-Object { $_.DriveLetter + ':\\ [' + $_.FileSystemLabel + ']' }; "
                "      $vStr = ' (' + ($lbls -join ', ') + ')' "
                "    } "
                "  } catch {}; "
                "  $id + ' - ' + $friendly + $tag + $vStr "
                "}"
            )
            output = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", cmd],
                creationflags=subprocess.CREATE_NO_WINDOW
            ).decode('mbcs', errors='ignore').strip().split('\n')
            for line in output:
                if line.strip():
                    disks.append(line.strip())
        except Exception:
            pass
        if not disks:
            disks = ["(Ningun disco)"]
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
        except Exception:
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
        except Exception:
            pass
        return adapters if adapters else ["(Ninguno)"]

    def get_cpu_threads_list(self):
        import os
        try:
            threads = os.cpu_count() or 4
        except Exception:
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
            except Exception:
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
                        
                lbl = ctk.CTkLabel(self.args_frame, text=f"[AVISO] Falta {PLUGINS[plugin_needed]['name']}.", text_color="#E74C3C", font=("Arial", 14, "bold"))
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
                
                option_map = None
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
                            btn_browse_save = ctk.CTkButton(btn_frame_paths, text="Guardar Como...", width=60, command=browse_save_file)
                            btn_browse_save.pack(side="left", padx=(0, 5))
                        elif arg_type == "file_entry":
                            btn_browse_file = ctk.CTkButton(btn_frame_paths, text="Archivo", width=60, command=browse_file)
                            btn_browse_file.pack(side="left", padx=(0, 5))
                        
                        if arg_type in ["directory_entry", "file_entry"]:
                            btn_browse_folder = ctk.CTkButton(btn_frame_paths, text="Carpeta", width=60, command=browse_folder)
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
                    
                elif arg_type in ["disk_dropdown", "disk_online_dropdown", "disk_offline_dropdown"]:
                    lbl = ctk.CTkLabel(row_frame, text=f"{arg_name}:")
                    lbl.pack(side="left", padx=(0, 5))
                    
                    if arg_type == "disk_online_dropdown":
                        pdisks = self.get_physical_disks(filter_status="Online")
                    elif arg_type == "disk_offline_dropdown":
                        pdisks = self.get_physical_disks(filter_status="Offline")
                    else:
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
                    
                elif arg_type == "dropdown":
                    lbl = ctk.CTkLabel(row_frame, text=f"{arg_name}:")
                    lbl.pack(side="left", padx=(0, 5))
                    raw_opts = arg.get("options", [])
                    if raw_opts and isinstance(raw_opts[0], dict):
                        display_opts = [o.get("name", "") for o in raw_opts]
                        option_map = {o.get("name", ""): str(o.get("value", "")) for o in raw_opts}
                    else:
                        display_opts = raw_opts
                    dropdown = ctk.CTkOptionMenu(row_frame, variable=var, values=display_opts)
                    dropdown.pack(side="left", fill="x", expand=True, padx=(0, 10))
                    if display_opts and (not var.get() or var.get() not in display_opts):
                        var.set(display_opts[0])
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
                
                self.current_args_vars[arg_name] = {
                    "var": var,
                    "type": arg_type,
                    "flag": arg_flag,
                    "option_map": option_map,
                }
                
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
                elif arg_data["type"] in ["drive_dropdown", "disk_dropdown", "disk_online_dropdown", "disk_offline_dropdown", "threads_dropdown", "dropdown"]:
                    opt_map = arg_data.get("option_map")
                    if opt_map and val in opt_map:
                        val_to_use = opt_map[val]
                    else:
                        val_to_use = val.split(" ")[0]
                    if arg_data["type"] in ["disk_dropdown", "disk_online_dropdown", "disk_offline_dropdown"] and val_to_use == "(Ningun":
                        continue
                    if command_list[0].strip().lower() == "shutdown" and "/a" in command_list and arg_data["flag"] in ("/t", "/f"):
                        continue
                    if arg_data["flag"]:
                        command_list.append(arg_data["flag"])
                    command_list.append(val_to_use)
        if command_list[0].strip().lower() == "shutdown" and "/a" in command_list:
            command_list = ["shutdown", "/a"]
        full_command_str = " ".join(command_list)
        self.preview_var.set(full_command_str)

        # Validación para Compresor de Multimedia
        if selected_command == "Compresor de Multimedia":
            args_map = {}
            for arg_name, arg_data in self.current_args_vars.items():
                args_map[arg_name] = arg_data["var"].get().strip()
                
            input_val = args_map.get("Seleccionar Carpeta (Lote)", "")
            if not input_val:
                input_val = args_map.get("Seleccionar Archivo (Individual)", "")
                
            out_val = args_map.get("Salida (Carpeta opcional)", "")
            suffix = args_map.get("Sufijo de archivo", "")
            
            # Limpiar comillas
            input_val = input_val.strip('"\'')
            out_val = out_val.strip('"\'')
            
            # Si no hay ruta de salida definida, la salida es la misma carpeta que la de entrada
            if not out_val and input_val:
                import os
                if os.path.isfile(input_val):
                    out_val = os.path.dirname(input_val)
                else:
                    out_val = input_val
            
            if input_val and out_val and input_val.lower() == out_val.lower() and not suffix:
                self.execute_btn.configure(state="disabled", text="Falta sufijo (Evitará sobrescribir originales)")
            else:
                if not self.is_running:
                    self.execute_btn.configure(state="normal", text="Ejecutar Comando")

    def pause_execution(self):
        if not self.is_running: return
        import os
        appdata = os.environ.get('APPDATA', '')
        flag_file = os.path.join(appdata, "cmd_gui_advance", "pause.flag")
        try:
            with open(flag_file, "w") as f: f.write("1")
            self.append_output("\n[SISTEMA] Señal de pausa enviada. El proceso se detendrá al terminar su tarea actual...\n")
            self.pause_btn.configure(state="disabled", text="Pausando...")
        except Exception as e:
            self.append_output(f"\nError enviando señal de pausa: {e}\n")

    def run_help(self):
        if self.is_running:
            return
        cmd_data = self.get_command_data(self.cmd_var.get())
        if cmd_data:
            help_cmd = f"{cmd_data.get('command')} /?"
            self.execute_external(help_cmd)

    @staticmethod
    def get_active_warning(cmd_data, cmd_str):
        """Devuelve el diccionario de advertencia si el comando requiere confirmación previa."""
        if not cmd_data:
            return None
        warning = cmd_data.get("warning")
        if not warning or not isinstance(warning, dict):
            return None
        skip_flags = warning.get("skip_if_flag_in") or []
        cmd_lower = (cmd_str or "").lower()
        for flag in skip_flags:
            if flag and flag.lower() in cmd_lower:
                return None
        return warning

    def show_execution_warning_dialog(self, warning, cmd_str):
        """Muestra un diálogo modal de advertencia antes de ejecutar un comando modificador/destructivo."""
        from functions.utils import apply_window_theme

        level = warning.get("level", "caution")
        title = warning.get("title", "Confirmación de Ejecución")
        message = warning.get("message", "Esta operación realizará cambios en el sistema o en tus archivos.")
        is_danger = level == "danger"

        accent = "#D73A49" if is_danger else "#D29922"
        accent_hover = "#B62324" if is_danger else "#B07C14"
        badge_text = "ACCIÓN CRÍTICA" if is_danger else "CONFIRMACIÓN DE CAMBIO"

        result = {"proceed": False}

        win = ctk.CTkToplevel(self)
        win.title(f"Advertencia — {title}")
        win.geometry("540x360")
        win.resizable(False, False)
        win.transient(self)
        win.grab_set()

        win.update_idletasks()
        x = int(self.winfo_x() + (self.winfo_width() / 2) - 270)
        y = int(self.winfo_y() + (self.winfo_height() / 2) - 180)
        win.geometry(f"+{x}+{y}")
        apply_window_theme(win)

        header = ctk.CTkFrame(win, fg_color=accent, corner_radius=6)
        header.pack(fill="x", padx=18, pady=(16, 10))
        ctk.CTkLabel(
            header,
            text=f"{badge_text}  —  {title}",
            font=("Segoe UI", 14, "bold"),
            text_color="#FFFFFF",
            wraplength=480,
            justify="left",
        ).pack(padx=12, pady=10, anchor="w")

        ctk.CTkLabel(
            win,
            text=message,
            font=("Segoe UI", 13),
            wraplength=495,
            justify="left",
            anchor="w",
        ).pack(fill="x", padx=20, pady=(4, 10))

        preview_text = cmd_str if len(cmd_str) <= 220 else cmd_str[:217] + "..."
        preview_box = ctk.CTkTextbox(win, height=78, font=("Consolas", 11), wrap="word")
        preview_box.pack(fill="x", padx=20, pady=(0, 12))
        preview_box.insert("1.0", f"Comando a ejecutar:\n{preview_text}")
        preview_box.configure(state="disabled")

        btn_row = ctk.CTkFrame(win, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(4, 16))

        def on_cancel():
            result["proceed"] = False
            win.destroy()

        def on_continue():
            result["proceed"] = True
            win.destroy()

        cancel_btn = ctk.CTkButton(
            btn_row,
            text="Cancelar",
            width=140,
            fg_color="transparent",
            border_width=1,
            text_color=("#24292F", "#C9D1D9"),
            command=on_cancel,
        )
        cancel_btn.pack(side="left")

        proceed_btn = ctk.CTkButton(
            btn_row,
            text="Continuar y Ejecutar",
            width=190,
            fg_color=accent,
            hover_color=accent_hover,
            text_color="#FFFFFF",
            font=("Segoe UI", 13, "bold"),
            command=on_continue,
        )
        proceed_btn.pack(side="right")

        win.bind("<Escape>", lambda e: on_cancel())
        win.protocol("WM_DELETE_WINDOW", on_cancel)
        cancel_btn.focus_set()
        self.wait_window(win)
        return result["proceed"]

    def _on_app_close(self):
        try:
            from functions import power_manager
            power_manager.allow_sleep()
        except Exception:
            pass
        if self.is_running:
            try:
                cmd_executor.stop_command()
            except Exception:
                pass
        self.destroy()

    def _save_error_report_to_desktop(self, cmd_name, command_str):
        """Genera y guarda automáticamente un reporte HTML en el Escritorio cuando ocurre un error antes de apagar."""
        import datetime
        import os
        import re
        from functions import power_manager

        try:
            content = self.output_textbox.get("1.0", "end-1c")
            html_doc = self.get_html_template(
                content=content,
                title=f"{cmd_name} (Error antes de apagar)",
                command=command_str,
                category=self.cat_var.get() if hasattr(self, "cat_var") else "",
            )
            desktop = power_manager.get_desktop_path()
            os.makedirs(desktop, exist_ok=True)
            safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", cmd_name or "comando").strip("_")[:40]
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path = os.path.join(desktop, f"Reporte_Error_{safe_name}_{ts}.html")
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(html_doc)
            return out_path
        except Exception:
            return None

    def show_shutdown_countdown_dialog(self, seconds=60, had_error=False, report_path=None):
        """Ventana de cuenta regresiva cancelable antes de apagar el PC al finalizar una tarea."""
        from functions import power_manager
        from functions.utils import apply_window_theme

        state = {"remaining": int(seconds), "cancelled": False, "timer_id": None}

        win = ctk.CTkToplevel(self)
        win.title("Apagado Automático Programado")
        win.geometry("500x290")
        win.resizable(False, False)
        win.transient(self)
        win.grab_set()

        win.update_idletasks()
        x = int(self.winfo_x() + (self.winfo_width() / 2) - 250)
        y = int(self.winfo_y() + (self.winfo_height() / 2) - 145)
        win.geometry(f"+{x}+{y}")
        apply_window_theme(win)

        header_color = "#D29922" if had_error else "#1F6AA5"
        header_txt = "Tarea finalizada con error — Apagado en curso" if had_error else "Tarea finalizada — Apagado automático"
        header = ctk.CTkFrame(win, fg_color=header_color, corner_radius=6)
        header.pack(fill="x", padx=18, pady=(16, 10))
        ctk.CTkLabel(header, text=header_txt, font=("Segoe UI", 14, "bold"), text_color="#FFFFFF").pack(padx=12, pady=10, anchor="w")

        countdown_lbl = ctk.CTkLabel(
            win,
            text=f"El equipo se apagará en {state['remaining']} segundos.",
            font=("Segoe UI", 16, "bold"),
        )
        countdown_lbl.pack(pady=(8, 6))

        extra_msg = ""
        if had_error and report_path:
            extra_msg = f"Se guardó automáticamente el reporte HTML de errores en tu Escritorio:\n{report_path}"
        elif had_error:
            extra_msg = "El comando finalizó con errores. Puedes cancelar el apagado para revisar la consola."
        else:
            extra_msg = "Puedes cancelar el apagado en cualquier momento antes de que termine el conteo."

        ctk.CTkLabel(win, text=extra_msg, font=("Segoe UI", 12), wraplength=460, justify="center").pack(padx=18, pady=(0, 14))

        btn_row = ctk.CTkFrame(win, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(4, 16))

        def cancel_shutdown():
            state["cancelled"] = True
            if state["timer_id"]:
                try:
                    win.after_cancel(state["timer_id"])
                except Exception:
                    pass
            self.append_output("\n[ENERGÍA] Apagado automático cancelado por el usuario.\n")
            win.destroy()

        def shutdown_now():
            state["cancelled"] = True
            if state["timer_id"]:
                try:
                    win.after_cancel(state["timer_id"])
                except Exception:
                    pass
            win.destroy()
            power_manager.execute_shutdown_now()

        cancel_btn = ctk.CTkButton(
            btn_row,
            text="Cancelar Apagado",
            width=190,
            fg_color="#D73A49",
            hover_color="#B62324",
            text_color="#FFFFFF",
            font=("Segoe UI", 13, "bold"),
            command=cancel_shutdown,
        )
        cancel_btn.pack(side="left")

        now_btn = ctk.CTkButton(
            btn_row,
            text="Apagar Ahora",
            width=150,
            fg_color="#2E86C1",
            hover_color="#21618C",
            text_color="#FFFFFF",
            command=shutdown_now,
        )
        now_btn.pack(side="right")

        def tick():
            if state["cancelled"]:
                return
            state["remaining"] -= 1
            if state["remaining"] <= 0:
                win.destroy()
                power_manager.execute_shutdown_now()
                return
            countdown_lbl.configure(text=f"El equipo se apagará en {state['remaining']} segundos.")
            state["timer_id"] = win.after(1000, tick)

        win.bind("<Escape>", lambda e: cancel_shutdown())
        win.protocol("WM_DELETE_WINDOW", cancel_shutdown)
        cancel_btn.focus_set()
        state["timer_id"] = win.after(1000, tick)

    def navigate_to_command(self, target_cmd_name):
        """Navega automáticamente a la categoría y comando indicado."""
        if hasattr(self, "search_var") and self.search_var.get():
            self.search_var.set("")
        for cat in self.commands_config.get("categories", []):
            cname = cat.get("name", "")
            for cmd in cat.get("commands", []):
                if cmd.get("name") == target_cmd_name:
                    self.cat_var.set(cname)
                    self.on_category_change(cname)
                    self.cmd_var.set(target_cmd_name)
                    self.on_command_change(target_cmd_name)
                    return True
        return False

    def show_combo_suggestions_dialog(self, main_cmd_name, before_list, after_list):
        """Muestra un modal con sugerencias de combo (Protocolo Seguro ANTES y Continuación DESPUÉS)
        y checkbox para autoejecutar la cola completa en un solo clic.

        Retorna None si el usuario cancela, o (selected_before, selected_after, auto_execute).
        """
        from functions.utils import apply_window_theme

        result = {"action": None, "before": [], "after": [], "auto_execute": True}
        before_vars = []
        after_vars = []
        auto_exec_var = ctk.BooleanVar(value=True)

        win = ctk.CTkToplevel(self)
        win.title(f"Sugerencias de Combo — {main_cmd_name}")
        win.geometry("640x510")
        win.resizable(False, False)
        win.transient(self)
        win.grab_set()

        win.update_idletasks()
        x = int(self.winfo_x() + (self.winfo_width() / 2) - 320)
        y = int(self.winfo_y() + (self.winfo_height() / 2) - 255)
        win.geometry(f"+{x}+{y}")
        apply_window_theme(win)

        header = ctk.CTkFrame(win, fg_color="#1F6AA5", corner_radius=6)
        header.pack(fill="x", padx=18, pady=(16, 10))
        ctk.CTkLabel(
            header,
            text=f"Combos Recomendados para: {main_cmd_name}",
            font=("Segoe UI", 14, "bold"),
            text_color="#FFFFFF",
            wraplength=580,
            justify="left",
        ).pack(padx=12, pady=10, anchor="w")

        scroll = ctk.CTkScrollableFrame(win, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        confirm_btn_ref = {"btn": None}

        def refresh_confirm_label(*_args):
            btn = confirm_btn_ref["btn"]
            if not btn:
                return
            sel_count = sum(1 for v, _ in before_vars if v.get()) + sum(1 for v, _ in after_vars if v.get())
            total_steps = 1 + sel_count
            if sel_count > 0 and auto_exec_var.get():
                btn.configure(text=f"Ejecutar Servicio ({total_steps} pasos)")
            else:
                btn.configure(text="Aceptar y Continuar")

        def add_section(title_txt, accent_color, items, target_vars):
            ctk.CTkLabel(
                scroll,
                text=title_txt,
                font=("Segoe UI", 13, "bold"),
                text_color=accent_color,
                anchor="w",
            ).pack(fill="x", pady=(6, 4))
            for item in items:
                var = ctk.BooleanVar(value=False)
                var.trace_add("write", refresh_confirm_label)
                target_vars.append((var, item))
                mode_tag = "[Automático en cola]" if item["mode"] == "auto" else "[Abrir para configurar]"
                row = ctk.CTkFrame(scroll, corner_radius=6)
                row.pack(fill="x", pady=4)
                cb = ctk.CTkCheckBox(
                    row,
                    text=f"{item['command']}  {mode_tag}",
                    variable=var,
                    font=("Segoe UI", 12, "bold"),
                )
                cb.pack(anchor="w", padx=10, pady=(8, 2))
                if item.get("reason"):
                    ctk.CTkLabel(
                        row,
                        text=item["reason"],
                        font=("Segoe UI", 11),
                        wraplength=550,
                        justify="left",
                        anchor="w",
                    ).pack(fill="x", padx=34, pady=(0, 8))

        if before_list:
            add_section(
                "PROTOCOLO SEGURO — Ejecutar ANTES de tu comando (tu comando esperará al terminar):",
                ("#B45309", "#F39C12"),
                before_list,
                before_vars,
            )
        if after_list:
            add_section(
                "CONTINUACIÓN — Ejecutar o abrir DESPUÉS de tu comando:",
                ("#1F883D", "#2EA043"),
                after_list,
                after_vars,
            )

        opt_bar = ctk.CTkFrame(win, corner_radius=6)
        opt_bar.pack(fill="x", padx=18, pady=(2, 10))
        auto_cb = ctk.CTkCheckBox(
            opt_bar,
            text="Autoejecutar cola completa en un solo clic (servicio continuo sin pausas)",
            variable=auto_exec_var,
            font=("Segoe UI", 12, "bold"),
        )
        auto_cb.pack(anchor="w", padx=10, pady=8)
        auto_exec_var.trace_add("write", refresh_confirm_label)
        if CTkToolTip:
            CTkToolTip(
                auto_cb,
                message="Activo: ejecuta de corrido todos los pasos automáticos seleccionados. Desactivado: abre el siguiente paso al terminar para que lo revises antes de ejecutar.",
            )

        btn_row = ctk.CTkFrame(win, fg_color="transparent")
        btn_row.pack(fill="x", padx=18, pady=(2, 14))

        def on_cancel():
            result["action"] = None
            win.destroy()

        def on_only_main():
            result["action"] = "run"
            result["before"] = []
            result["after"] = []
            result["auto_execute"] = False
            win.destroy()

        def on_confirm():
            result["action"] = "run"
            result["before"] = [it for v, it in before_vars if v.get()]
            result["after"] = [it for v, it in after_vars if v.get()]
            result["auto_execute"] = bool(auto_exec_var.get())
            win.destroy()

        ctk.CTkButton(
            btn_row,
            text="Cancelar",
            width=110,
            fg_color="transparent",
            border_width=1,
            text_color=("#24292F", "#C9D1D9"),
            command=on_cancel,
        ).pack(side="left")

        ctk.CTkButton(
            btn_row,
            text="Solo mi comando",
            width=145,
            fg_color="#64748B",
            hover_color="#475569",
            text_color="#FFFFFF",
            command=on_only_main,
        ).pack(side="right", padx=(8, 0))

        confirm_btn = ctk.CTkButton(
            btn_row,
            text="Aceptar y Continuar",
            width=215,
            fg_color="#1F883D",
            hover_color="#1A7F37",
            text_color="#FFFFFF",
            font=("Segoe UI", 13, "bold"),
            command=on_confirm,
        )
        confirm_btn.pack(side="right")
        confirm_btn_ref["btn"] = confirm_btn

        win.bind("<Escape>", lambda e: on_cancel())
        win.protocol("WM_DELETE_WINDOW", on_cancel)
        self.wait_window(win)
        if result["action"] != "run":
            return None
        return result["before"], result["after"], result["auto_execute"]

    def toggle_execution(self):
        if self.is_running:
            self._stopped_by_user = True
            self._execution_queue = []
            cmd_executor.stop_command()
        else:
            cmd_str = self.preview_var.get()
            if not cmd_str:
                return
            cmd_name = self.cmd_var.get()
            cmd_data = self.get_command_data(cmd_name)
            self._pending_queue = None
            unified_warning = None

            if getattr(self, "combo_suggestions_var", None) and self.combo_suggestions_var.get():
                from functions import combo_engine
                ctx = combo_engine.extract_command_context(cmd_str)
                before_list, after_list = combo_engine.get_command_combos(cmd_data, context=ctx)
                if before_list or after_list:
                    choice = self.show_combo_suggestions_dialog(cmd_name, before_list, after_list)
                    if choice is None:
                        return
                    sel_before, sel_after, auto_exec = choice
                    queue = combo_engine.build_execution_queue(
                        cmd_name,
                        cmd_str,
                        sel_before,
                        sel_after,
                        auto_execute=auto_exec,
                        context=ctx,
                    )
                    nav_before = [s for s in queue if s["role"] == "before" and s["mode"] == "navigate"]
                    if nav_before:
                        prereq_name = nav_before[0]["name"]
                        self.navigate_to_command(prereq_name)
                        self.append_output(
                            f"\n[COMBO - PROTOCOLO SEGURO] Configura y ejecuta primero '{prereq_name}' antes de continuar con '{cmd_name}'.\n"
                        )
                        return
                    if len(queue) > 1:
                        self._pending_queue = queue
                        all_cmds = {
                            c["name"]: c
                            for cat in self.commands_config.get("categories", [])
                            for c in cat.get("commands", [])
                        }
                        unified_warning = combo_engine.build_unified_warning(queue, all_cmds)

            warning = unified_warning if unified_warning else self.get_active_warning(cmd_data, cmd_str)
            if warning:
                if not self.show_execution_warning_dialog(warning, cmd_str):
                    self._pending_queue = None
                    return
            self.check_drives_and_run()

    def check_drives_and_run(self):
        cmd_str = self.preview_var.get()
        if not cmd_str: return
        
        # Extraer posibles letras de unidad (ej. C:\, E:\ o --drive E:)
        import re, threading, subprocess
        drives = set(re.findall(r'([A-Za-z]):[\\/]', cmd_str))
        drives.update(re.findall(r'--drive\s+([A-Za-z]):?', cmd_str, flags=re.IGNORECASE))
        
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
                                if "--run-sdelete" in cmd_lower:
                                    warnings.append(
                                        f"• ADVERTENCIA SSD ({d}:): Vas a ejecutar SDelete sobre un SSD. Debido al wear leveling (nivelación de desgaste), "
                                        "sobrescribir espacio o usar múltiples pasadas desgasta los ciclos de vida (TBW) sin garantizar el borrado de bloques reasignados.\n"
                                        "  Modo seguro recomendado en SSD: utiliza 1 sola pasada (-p 1), ejecuta Optimizar/TRIM o utiliza cifrado BitLocker."
                                    )
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
        except Exception:
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
        except Exception:
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
        self.output_textbox.insert("end", f"\n[OK] Comando '{fav_name}' guardado en Favoritos.\n(Reinicia la app para verlo en la lista)\n", "success")
        self.output_textbox.see("end")
        self.output_textbox.configure(state="disabled")

    def run_command(self):
        if not self.preview_var.get():
            return
        self.execute_external(self.preview_var.get())

    @staticmethod
    def extract_progress_from_text(text):
        """Extrae porcentaje (0-100) desde salida de consola (enteros, decimales o fracciones [i/total])."""
        if not text:
            return None
        lower = text.lower()
        # Ignorar porcentajes de reportes de resumen que no representan progreso
        if any(k in lower for k in ("espacio ahorrado", "incremento de peso", "ram:", "cpu:")):
            return None

        # 1. Porcentaje explícito: 45%, 12.5%, 12,5%
        m_pct = re.search(r'(?<!\d)(\d{1,3}(?:[.,]\d+)?)\s*%', text)
        if m_pct:
            try:
                val = float(m_pct.group(1).replace(',', '.'))
                if 0.0 <= val <= 100.0:
                    return val
            except ValueError:
                pass

        # 2. Fracción de avance tipo [15/200] o (15/200)
        m_frac = re.search(r'[\[\(](\d+)\s*/\s*(\d+)[\]\)]', text)
        if m_frac:
            try:
                cur, tot = int(m_frac.group(1)), int(m_frac.group(2))
                if tot > 0 and 0 <= cur <= tot:
                    return (cur / tot) * 100.0
            except ValueError:
                pass

        return None

    @staticmethod
    def parse_storage_job_json(raw_json):
        """Parsea la salida JSON de Get-StorageJob y retorna (nombre, porcentaje) del trabajo activo."""
        if not raw_json or not raw_json.strip():
            return None
        try:
            data = json.loads(raw_json)
            jobs = data if isinstance(data, list) else [data]
            for job in jobs:
                if not isinstance(job, dict):
                    continue
                state = str(job.get("JobState", "")).lower()
                if state in ("running", "starting", "new", "4"):
                    pct = job.get("PercentComplete")
                    name = str(job.get("Name") or "Almacenamiento")
                    if pct is not None:
                        return name, max(0.0, min(100.0, float(pct)))
        except Exception:
            pass
        return None

    @staticmethod
    def format_duration(seconds):
        sec = int(max(0, seconds))
        h, rem = divmod(sec, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"

    @staticmethod
    def estimate_remaining_seconds(elapsed_sec, pct):
        """Estima segundos restantes según tiempo transcurrido y porcentaje completado."""
        try:
            p = float(pct)
            e = float(elapsed_sec)
        except Exception:
            return None
        if p >= 100.0:
            return 0
        if p < 1.0 or e < 1.0:
            return None
        return int(max(0.0, e * (100.0 - p) / p))

    @staticmethod
    def get_progress_color(pct):
        """Escala de avance (0% -> 100%): Rojo -> Naranja -> Amarillo/Ámbar -> Verde."""
        p = max(0.0, min(100.0, float(pct)))
        if p < 25.0:
            return "#dc3545"  # Rojo
        if p < 50.0:
            return "#fd7e14"  # Naranja
        if p < 75.0:
            return ("#B45309", "#ffc107")  # Ámbar en claro / Amarillo en oscuro
        return "#28a745"  # Verde

    @staticmethod
    def get_eta_color(pct):
        """Escala inversa para el ETA: Verde al inicio -> Amarillo -> Naranja -> Rojo cerca del final (Verde al completar)."""
        p = max(0.0, min(100.0, float(pct)))
        if p >= 100.0:
            return "#28a745"  # Completado (00:00)
        if p < 25.0:
            return "#28a745"  # Verde
        if p < 50.0:
            return ("#B45309", "#ffc107")  # Amarillo/Ámbar
        if p < 75.0:
            return "#fd7e14"  # Naranja
        return "#dc3545"  # Rojo

    def _get_elapsed_seconds(self):
        import time
        return max(0.0, time.time() - getattr(self, "_cmd_start_time", time.time()))

    def _format_elapsed(self):
        return self.format_duration(self._get_elapsed_seconds())

    def _refresh_progress_labels(self, pct, detail=None):
        elapsed_sec = self._get_elapsed_seconds()
        elapsed_str = self.format_duration(elapsed_sec)
        if hasattr(self, 'lbl_progress'):
            prefix = f"{detail}: " if detail else ""
            self.lbl_progress.configure(
                text=f"{prefix}{pct:.0f}% ({elapsed_str})",
                text_color=self.get_progress_color(pct),
            )
        if hasattr(self, 'lbl_eta'):
            rem = self.estimate_remaining_seconds(elapsed_sec, pct)
            eta_str = self.format_duration(rem) if rem is not None else "--:--"
            self.lbl_eta.configure(
                text=f"ETA: {eta_str}",
                text_color=self.get_eta_color(pct),
            )

    def _set_determinate_progress(self, pct, detail=None):
        if not hasattr(self, 'progressbar'):
            return
        pct_clamped = max(0.0, min(100.0, float(pct)))
        if not getattr(self, "_has_determinate_progress", False):
            self._has_determinate_progress = True
            try:
                self.progressbar.stop()
                self.progressbar.configure(mode="determinate")
            except Exception:
                pass
        self._last_progress_pct = pct_clamped
        self._last_progress_detail = detail
        self.progressbar.set(pct_clamped / 100.0)
        self._refresh_progress_labels(pct_clamped, detail=detail)

    def _tick_progress_timer(self):
        if not getattr(self, "is_running", False):
            return
        if getattr(self, "_has_determinate_progress", False):
            pct = getattr(self, "_last_progress_pct", 0.0)
            detail = getattr(self, "_last_progress_detail", None)
            self._refresh_progress_labels(pct, detail=detail)
        else:
            elapsed = self._format_elapsed()
            if hasattr(self, 'lbl_progress'):
                self.lbl_progress.configure(text=f"Ejecutando... ({elapsed})", text_color="#dc3545")
            if hasattr(self, 'lbl_eta'):
                self.lbl_eta.configure(text="ETA: --:--", text_color="#28a745")
        self._progress_timer_id = self.after(1000, self._tick_progress_timer)

    def _start_storage_job_monitor(self, command_str):
        """Monitorea Get-StorageJob en segundo plano para comandos de formateo/disco de PowerShell."""
        storage_keywords = ("Format-Volume", "Clear-Disk", "Optimize-Volume", "Initialize-Disk", "New-Partition")
        if not any(k.lower() in command_str.lower() for k in storage_keywords):
            return

        import threading, time

        def _poll():
            ps_cmd = (
                "Get-StorageJob -ErrorAction SilentlyContinue | "
                "Select-Object Name, @{N='JobState';E={[string]$_.JobState}}, PercentComplete | "
                "ConvertTo-Json -Compress"
            )
            while getattr(self, "is_running", False):
                try:
                    proc = subprocess.run(
                        ["powershell", "-NoProfile", "-Command", ps_cmd],
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                        timeout=8,
                    )
                    parsed = self.parse_storage_job_json(proc.stdout)
                    if parsed and getattr(self, "is_running", False):
                        job_name, pct = parsed
                        self.after(0, lambda n=job_name, p=pct: self._set_determinate_progress(p, detail=n))
                except Exception:
                    pass
                for _ in range(6):
                    if not getattr(self, "is_running", False):
                        return
                    time.sleep(0.5)

        threading.Thread(target=_poll, daemon=True).start()

    def execute_external(self, command_str):
        import time
        if hasattr(self, 'auto_clear_var') and self.auto_clear_var.get():
            self.clear_output()

        current_cmd_name = self.cmd_var.get()
        pending = getattr(self, "_pending_queue", None)
        self._pending_queue = None
        if pending:
            self._execution_queue = list(pending)
        else:
            self._execution_queue = [{"name": current_cmd_name, "cmd_str": command_str, "mode": "auto", "role": "main"}]
        self._queue_total = len(self._execution_queue)
        self._queue_step_idx = 0
        self._queue_had_error = False

        self.is_running = True
        self._stopped_by_user = False
        self._active_keep_awake = bool(getattr(self, "keep_awake_var", None) and self.keep_awake_var.get())
        if self._active_keep_awake:
            from functions import power_manager
            if power_manager.prevent_sleep(keep_display=False):
                self.append_output("[ENERGÍA] Anti-suspensión/hibernación activo durante la ejecución (la pantalla podrá apagarse normalmente).\n")
        self.execute_btn.configure(text="Detener ejecución", fg_color="red", hover_color="#8B0000")
        self.cat_menu.configure(state="disabled")
        self.cmd_menu.configure(state="disabled")
        self.pause_btn.pack(side="left", padx=(0, 5), before=self.fav_btn)

        # Limpiar archivo de pausa viejo si existe
        appdata = os.environ.get('APPDATA', '')
        flag_file = os.path.join(appdata, "cmd_gui_advance", "pause.flag")
        if os.path.exists(flag_file):
            try: os.remove(flag_file)
            except Exception: pass

        def finalize_all(last_rc, last_step_name, last_cmd_str, next_navigate_name=None):
            self.is_running = False
            self._execution_queue = []
            if getattr(self, "_active_keep_awake", False):
                try:
                    from functions import power_manager
                    power_manager.allow_sleep()
                except Exception:
                    pass
                self._active_keep_awake = False

            if getattr(self, "_progress_timer_id", None):
                try:
                    self.after_cancel(self._progress_timer_id)
                except Exception:
                    pass
                self._progress_timer_id = None

            elapsed = self._format_elapsed()
            if hasattr(self, 'progressbar'):
                try:
                    self.progressbar.stop()
                    self.progressbar.configure(mode="determinate")
                except Exception:
                    pass
                if last_rc == 0 and not self._queue_had_error:
                    self.progressbar.set(1.0)
                    if hasattr(self, 'lbl_progress'):
                        self.lbl_progress.configure(text=f"100% Completado ({elapsed})", text_color="#28a745")
                    if hasattr(self, 'lbl_eta'):
                        self.lbl_eta.configure(text="ETA: 00:00", text_color="#28a745")
                else:
                    last_pct = getattr(self, "_last_progress_pct", 0.0) if getattr(self, "_has_determinate_progress", False) else 0.0
                    self.progressbar.set(last_pct / 100.0)
                    if hasattr(self, 'lbl_progress'):
                        self.lbl_progress.configure(text=f"Detenido / Error ({elapsed})", text_color="#dc3545")
                    if hasattr(self, 'lbl_eta'):
                        self.lbl_eta.configure(text="ETA: --:--", text_color="#dc3545")

            self.execute_btn.configure(text="Ejecutar Comando", fg_color=["#1F883D", "#238636"], hover_color=["#1A7F37", "#2EA043"])
            self.cat_menu.configure(state="normal")
            self.cmd_menu.configure(state="normal")
            self.pause_btn.pack_forget()

            if next_navigate_name and not getattr(self, "_stopped_by_user", False):
                self.navigate_to_command(next_navigate_name)
                self.append_output(
                    f"\n[COMBO] Siguiente paso listo para configurar y ejecutar: '{next_navigate_name}'.\n"
                )

            should_shutdown = bool(getattr(self, "shutdown_after_var", None) and self.shutdown_after_var.get())
            if should_shutdown and not getattr(self, "_stopped_by_user", False):
                self.shutdown_after_var.set(False)
                had_error = (last_rc != 0) or self._queue_had_error
                report_path = None
                if had_error:
                    report_path = self._save_error_report_to_desktop(last_step_name, last_cmd_str)
                    if report_path:
                        self.append_output(f"\n[ENERGÍA] Error detectado: reporte HTML guardado en Escritorio -> {report_path}\n")
                self.show_shutdown_countdown_dialog(seconds=60, had_error=had_error, report_path=report_path)

        def run_next_step():
            if not self._execution_queue or getattr(self, "_stopped_by_user", False):
                finalize_all(0, current_cmd_name, command_str)
                return

            step = self._execution_queue.pop(0)
            self._queue_step_idx += 1

            if step["mode"] == "navigate":
                finalize_all(0, step["name"], command_str, next_navigate_name=step["name"])
                return

            self._cmd_start_time = time.time()
            self._has_determinate_progress = False
            self._last_progress_pct = 0.0
            self._last_progress_detail = None

            if hasattr(self, 'progressbar'):
                try:
                    self.progressbar.configure(mode="indeterminate")
                    self.progressbar.start()
                except Exception:
                    self.progressbar.set(0)
                step_prefix = f"[{self._queue_step_idx}/{self._queue_total}] " if self._queue_total > 1 else ""
                if hasattr(self, 'lbl_progress'):
                    self.lbl_progress.configure(text=f"{step_prefix}Ejecutando... (00:00)", text_color="#dc3545")
                if hasattr(self, 'lbl_eta'):
                    self.lbl_eta.configure(text="ETA: --:--", text_color="#28a745")

            if self._queue_total > 1:
                role_label = "PROTOCOLO SEGURO" if step["role"] == "before" else ("PRINCIPAL" if step["role"] == "main" else "CONTINUACIÓN")
                self.append_output(f"\n================ [COMBO {self._queue_step_idx}/{self._queue_total} — {role_label}] {step['name']} ================\n")
            self.append_output(f"\n> {step['cmd_str']}\n")

            if getattr(self, "_progress_timer_id", None):
                try:
                    self.after_cancel(self._progress_timer_id)
                except Exception:
                    pass
                self._progress_timer_id = None
            self._tick_progress_timer()
            self._start_storage_job_monitor(step["cmd_str"])

            def on_step_finish():
                rc = cmd_executor.get_last_returncode()
                if rc != 0:
                    self._queue_had_error = True
                if getattr(self, "_stopped_by_user", False):
                    finalize_all(rc, step["name"], step["cmd_str"])
                    return
                if step["role"] == "before" and rc != 0:
                    self.append_output(
                        f"\n[COMBO] El paso de Protocolo Seguro '{step['name']}' finalizó con error (código {rc}). Cola detenida por seguridad.\n"
                    )
                    finalize_all(rc, step["name"], step["cmd_str"])
                    return
                if self._execution_queue:
                    run_next_step()
                else:
                    finalize_all(rc, step["name"], step["cmd_str"])

            cmd_executor.execute_command_async(
                command_string=step["cmd_str"],
                output_callback=self.append_output,
                finished_callback=lambda: self.after(0, on_step_finish),
            )

        run_next_step()

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
                
                pct = self.extract_progress_from_text(text)
                if pct is not None and hasattr(self, 'progressbar'):
                    self._set_determinate_progress(pct)
                        
            self.output_textbox.configure(state="disabled")
        self.after(0, _append)

    def clear_output(self):
        self.output_textbox.configure(state="normal")
        self.output_textbox.delete("1.0", "end")
        self.output_textbox.configure(state="disabled")

    def get_html_template(self, content, title="Reporte de Ejecución", command="Desconocido", category=""):
        from functions.report_generator import generate_html_report
        return generate_html_report(
            content=content,
            title=title,
            command=command,
            category=category or (self.cat_var.get() if hasattr(self, "cat_var") else ""),
        )

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
            
            status_text = "Instalado" if is_installed else "No Instalado"
            status_lbl = ctk.CTkLabel(row, text=status_text)
            status_lbl.pack(side="top", anchor="w", padx=10, pady=(5, 10))
            
            btn_frame = ctk.CTkFrame(row, fg_color="transparent")
            btn_frame.pack(side="top", fill="x", padx=10, pady=(0, 10))
            
            def open_folder(fpath=path):
                tools_dir = os.path.dirname(fpath)
                os.makedirs(tools_dir, exist_ok=True)
                subprocess.Popen(
                    f'explorer "{tools_dir}"',
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                
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
                    btn_ai = ctk.CTkButton(btn_frame, text="Configurar Bóveda IA", width=120, fg_color="#8E44AD", hover_color="#9B59B6", command=open_ai_config)
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
        
        btn_export = ctk.CTkButton(btn_action_frame, text="Exportar ZIP", fg_color="#2E86C1", hover_color="#2874A6", command=export_plugins)
        btn_export.pack(side="left", expand=True, padx=5)

        btn_import = ctk.CTkButton(btn_action_frame, text="Importar ZIP", fg_color="#27AE60", hover_color="#229954", command=import_plugins)
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

    def show_credits(self):
        credits_win = ctk.CTkToplevel(self)
        credits_win.title("Acerca de GUI CMD ADVANCE")
        center_window(credits_win, 400, 450)
        credits_win.resizable(False, False)
        
        def set_credits_icon():
            try:
                credits_win.iconbitmap(get_resource_path("resources/app_icon.ico"))
            except Exception:
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
            env = os.environ.copy()
            if getattr(sys, "frozen", False):
                cmd = [sys.executable, "--run-process-manager"]
                env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
                env.pop("_MEIPASS2", None)
            else:
                cmd = [sys.executable, os.path.abspath(sys.argv[0]), "--run-process-manager"]
            subprocess.Popen(cmd, env=env, creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir el Gestor de Procesos:\n{e}")

    def optimize_ram(self):
        vbs_path = None
        try:
            import gc
            gc.collect()
            
            vbs_path = get_user_data_path("liberar_ram.vbs")
            with open(vbs_path, "w", encoding="utf-8") as f:
                f.write('FreeMem=Space(100000000)')
                
            subprocess.run(["cscript", "//nologo", vbs_path], creationflags=subprocess.CREATE_NO_WINDOW)
            messagebox.showinfo("RAM Optimizada", "Memoria inactiva liberada y procesos de fondo limpios correctamente.")
        except Exception as e:
            messagebox.showerror("Error", f"Ocurrió un error al intentar optimizar la RAM:\n{e}")
        finally:
            if vbs_path and os.path.exists(vbs_path):
                try:
                    os.remove(vbs_path)
                except Exception:
                    pass
