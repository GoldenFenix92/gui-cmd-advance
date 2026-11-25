import copy
import ctypes
import datetime
import gc
import json
import os
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
import webbrowser
import zipfile
from tkinter import filedialog, messagebox

import psutil
import ttkbootstrap as tb
from ttkbootstrap.widgets.meter import Meter
from ttkbootstrap.widgets.scrolled import ScrolledFrame, ScrolledText

from functions import cmd_executor, ui_theme
from functions.setup_manager import check_dependencies
from functions.utils import center_window, get_resource_path, get_user_data_path

from functions.versioning import get_app_version

__version__ = get_app_version()

FAVORITES_CATEGORY_NAME = "Favoritos"


class App(tb.Window):
    def __init__(self):
        self.current_theme = ui_theme.get_saved_theme()
        super().__init__(themename=self.current_theme)

        self.title("CMD GUI Advance")
        center_window(self, 1420, 840)
        self.minsize(1120, 700)
        ui_theme.apply_window_chrome(self, self.current_theme)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1, uniform="main_cols")
        self.grid_columnconfigure(1, weight=2, uniform="main_cols")

        self.commands_config = self.load_config()
        self.is_running = False
        self.current_args_vars = {}
        self._last_was_cr = False

        # Íconos vectoriales estilo Bootstrap (cero emojis hardcodeados)
        self._icons = {
            "info": ui_theme.get_bootstrap_icon("info", size=14, color="#FFFFFF", master=self),
            "help": ui_theme.get_bootstrap_icon("help", size=14, color="#FFFFFF", master=self),
            "star": ui_theme.get_bootstrap_icon("star_filled", size=15, color="#FFFFFF", master=self),
            "trash": ui_theme.get_bootstrap_icon("trash", size=15, color="#FFFFFF", master=self),
            "eye": ui_theme.get_bootstrap_icon("eye", size=14, color="#FFFFFF", master=self),
            "eye_off": ui_theme.get_bootstrap_icon("eye_off", size=14, color="#FFFFFF", master=self),
            "play": ui_theme.get_bootstrap_icon("play", size=14, color="#FFFFFF", master=self),
            "stop": ui_theme.get_bootstrap_icon("stop", size=14, color="#FFFFFF", master=self),
            "pause": ui_theme.get_bootstrap_icon("pause", size=14, color="#FFFFFF", master=self),
            "table": ui_theme.get_bootstrap_icon("table", size=14, color="#FFFFFF", master=self),
            "ai": ui_theme.get_bootstrap_icon("ai", size=14, color="#FFFFFF", master=self),
        }

        # ---------- PANEL IZQUIERDO: Control y Parámetros ----------
        self.left_frame = tb.Frame(self, padding=(12, 10, 6, 10))
        self.left_frame.grid(row=0, column=0, sticky="nsew")
        self.left_frame.grid_rowconfigure(2, weight=1)
        self.left_frame.grid_columnconfigure(0, weight=1)

        # Barra superior: interruptor nativo instantáneo Oscuro/Claro (pulse-dark <-> pulse-light)
        self.top_bar = tb.Frame(self.left_frame)
        self.top_bar.grid(row=0, column=0, pady=(0, 10), sticky="ew")

        self.dark_mode_var = tk.BooleanVar(value=ui_theme.is_dark_theme(self.current_theme))
        self.theme_switch = tb.Checkbutton(
            self.top_bar,
            text="Modo Oscuro" if self.dark_mode_var.get() else "Modo Claro",
            variable=self.dark_mode_var,
            bootstyle="primary-round-toggle",
            command=lambda: self.on_theme_toggle(self.dark_mode_var.get()),
        )
        self.theme_switch.pack(side="left", padx=(0, 8))
        ui_theme.add_tooltip(self.theme_switch, "Alternar al instante entre Pulse Oscuro y Pulse Claro")

        self.credits_btn = tb.Button(self.top_bar, text="Créditos", bootstyle="secondary-outline", command=self.show_credits)
        self.credits_btn.pack(side="right")

        self.plugins_btn = tb.Button(self.top_bar, text="Complementos", bootstyle="success", command=self.show_plugins)
        self.plugins_btn.pack(side="right", padx=(0, 6))

        self.proc_btn = tb.Button(self.top_bar, text="Procesos", bootstyle="info", command=self.open_process_manager)
        self.proc_btn.pack(side="right", padx=(0, 6))
        ui_theme.add_tooltip(self.proc_btn, "Gestor de Procesos y Servicios")

        self.ram_btn = tb.Button(self.top_bar, text="RAM", bootstyle="warning", command=self.optimize_ram)
        self.ram_btn.pack(side="right", padx=(0, 6))
        ui_theme.add_tooltip(self.ram_btn, "Liberar memoria inactiva (RAM)")

        # Tarjeta redondeada (12px): Selección de Comando
        cmd_card_wrap = ui_theme.RoundedCard(self.left_frame, title="Selección de Comando", padding=(4, 2))
        cmd_card_wrap.grid(row=1, column=0, pady=(0, 10), sticky="ew")
        cmd_card = cmd_card_wrap.body
        cmd_card.grid_columnconfigure(0, weight=1)

        self.search_var = tk.StringVar()
        self.search_entry = ui_theme.PlaceholderEntry(cmd_card, textvariable=self.search_var, placeholder="Buscar comando...")
        self.search_entry.grid(row=0, column=0, pady=(0, 8), sticky="ew")
        self.search_var.trace_add("write", self.on_search)

        tb.Label(cmd_card, text="Categoría:", style="PulseCard.TLabel", font=("Segoe UI", 9, "bold")).grid(row=1, column=0, sticky="w")
        categories = [cat.get("name", "Unknown") for cat in self.commands_config.get("categories", [])]
        self.cat_var = tk.StringVar(value=categories[0] if categories else "")
        self.cat_menu = tb.Combobox(cmd_card, values=categories, textvariable=self.cat_var, state="readonly")
        self.cat_menu.grid(row=2, column=0, pady=(2, 8), sticky="ew")
        self.cat_menu.bind("<<ComboboxSelected>>", lambda _e: self.on_category_change(self.cat_var.get()))

        cmd_label_frame = tb.Frame(cmd_card, style="PulseCardInner.TFrame")
        cmd_label_frame.grid(row=3, column=0, sticky="ew")

        tb.Label(cmd_label_frame, text="Comando:", style="PulseCard.TLabel", font=("Segoe UI", 9, "bold")).pack(side="left")

        self.cmd_info_btn = tb.Button(
            cmd_label_frame, image=self._icons["info"], bootstyle="info", command=self.show_command_info
        )
        self.cmd_info_btn.pack(side="right", padx=(4, 0))
        ui_theme.add_tooltip(self.cmd_info_btn, "Información detallada del comando")

        self.cmd_help_btn = tb.Button(
            cmd_label_frame, image=self._icons["help"], bootstyle="secondary", command=self.run_help
        )
        self.cmd_help_btn.pack(side="right")
        ui_theme.add_tooltip(self.cmd_help_btn, "Ejecutar la ayuda oficial del comando (/? o --help)")

        self.cmd_var = tk.StringVar(value="")
        self.cmd_menu = tb.Combobox(cmd_card, textvariable=self.cmd_var, state="readonly")
        self.cmd_menu.grid(row=4, column=0, pady=(4, 0), sticky="ew")
        self.cmd_menu.bind("<<ComboboxSelected>>", lambda _e: self.on_command_change(self.cmd_var.get()))

        # Tarjeta redondeada (12px): Parámetros y Argumentos
        args_card_wrap = ui_theme.RoundedCard(self.left_frame, title="Parámetros y Opciones", padding=(2, 2))
        args_card_wrap.grid(row=2, column=0, pady=(0, 10), sticky="nsew")
        args_card_wrap.body.grid_rowconfigure(0, weight=1)
        args_card_wrap.body.grid_columnconfigure(0, weight=1)

        self.args_frame = ScrolledFrame(args_card_wrap.body, auto_hide=False, padding=4)
        self.args_frame.grid(row=0, column=0, sticky="nsew")

        # Botonera de ejecución
        self.btn_frame = tb.Frame(self.left_frame)
        self.btn_frame.grid(row=3, column=0, sticky="ew")

        self.execute_btn = tb.Button(
            self.btn_frame, text=" Ejecutar Comando", image=self._icons["play"], compound="left",
            bootstyle="success", command=self.toggle_execution,
        )
        self.execute_btn.pack(side="left", fill="x", expand=True, padx=(0, 6))
        ui_theme.add_tooltip(self.execute_btn, "Ejecutar el comando en segundo plano (Ctrl+Enter)")

        self.pause_btn = tb.Button(
            self.btn_frame, text=" Posponer", image=self._icons["pause"], compound="left",
            bootstyle="warning", command=self.pause_execution,
        )

        self.fav_btn = tb.Button(
            self.btn_frame, image=self._icons["star"], bootstyle="warning", command=self.save_favorite
        )
        self.fav_btn.pack(side="right")
        ui_theme.add_tooltip(self.fav_btn, "Guardar o remover de Favoritos")

        # ---------- PANEL DERECHO: Consola, Progreso y Sensores ----------
        self.right_frame = tb.Frame(self, padding=(6, 10, 12, 10))
        self.right_frame.grid(row=0, column=1, sticky="nsew")
        self.right_frame.grid_rowconfigure(0, weight=1)
        self.right_frame.grid_columnconfigure(0, weight=1)

        console_card_wrap = ui_theme.RoundedCard(self.right_frame, title="Consola y Ejecución en Vivo", padding=(4, 2))
        console_card_wrap.grid(row=0, column=0, sticky="nsew")
        console_card = console_card_wrap.body
        console_card.grid_rowconfigure(1, weight=1)
        console_card.grid_columnconfigure(0, weight=1)

        self.preview_var = tk.StringVar(value="")
        self.preview_entry = tb.Entry(
            console_card, textvariable=self.preview_var, state="readonly", font=("Consolas", 11, "bold"), bootstyle="info"
        )
        self.preview_entry.grid(row=0, column=0, pady=(0, 8), sticky="ew")

        self.output_textbox = ScrolledText(console_card, font=("Consolas", 10), wrap="none", auto_hide=False)
        self.output_textbox.grid(row=1, column=0, pady=(0, 8), sticky="nsew")
        self.output_textbox.text.configure(state="disabled")

        # Barra de progreso redondeada tipo píldora (10px) + contadores de avance y ETA
        self.progress_frame = tb.Frame(console_card, style="PulseCardInner.TFrame")
        self.progress_frame.grid(row=2, column=0, pady=(0, 8), sticky="ew")
        self.progress_frame.grid_columnconfigure(0, weight=1)

        self.progressbar = ui_theme.RoundedProgressBar(
            self.progress_frame, maximum=100, value=0, height=24, radius=10, theme_name=self.current_theme
        )
        self.progressbar.grid(row=0, column=0, sticky="ew")

        self.lbl_progress = tk.Label(self.progress_frame, text="Listo (0%)", font=("Consolas", 10, "bold"), anchor="e")
        self.lbl_progress.grid(row=0, column=1, padx=(10, 0), sticky="e")

        self.lbl_eta = tk.Label(self.progress_frame, text="ETA: --:--", font=("Consolas", 10, "bold"), anchor="e")
        self.lbl_eta.grid(row=0, column=2, padx=(10, 0), sticky="e")

        # Acciones de salida y limpieza
        actions_row = tb.Frame(console_card, style="PulseCardInner.TFrame")
        actions_row.grid(row=3, column=0, pady=(0, 6), sticky="ew")

        self.export_btn = tb.Button(actions_row, text="Exportar Actual", bootstyle="success", command=self.export_output)
        self.export_btn.pack(side="left", padx=(0, 6))

        self.table_btn = tb.Button(
            actions_row, text=" Ver como Tabla", image=self._icons["table"], compound="left",
            bootstyle="info", command=self.show_table_view,
        )
        self.table_btn.pack(side="left", padx=(0, 6))
        ui_theme.add_tooltip(self.table_btn, "Ver resultados en una tabla interactiva (ideal para CSV)")

        self.interpreter_btn = tb.Button(
            actions_row, text=" Interpretar Resultados", image=self._icons["ai"], compound="left",
            bootstyle="primary", command=self.run_interpreter,
        )
        self.interpreter_btn.pack(side="left")
        ui_theme.add_tooltip(self.interpreter_btn, "Analiza el reporte con Inteligencia Artificial o de manera local")

        self.clear_btn = tb.Button(actions_row, text="Limpiar", bootstyle="warning", command=self.clear_output)
        self.clear_btn.pack(side="right")
        ui_theme.add_tooltip(self.clear_btn, "Limpiar la consola manualmente (Ctrl+L)")

        self.auto_clear_var = tk.BooleanVar(value=True)
        self.auto_clear_cb = tb.Checkbutton(
            actions_row, text="Auto-Limpiar", variable=self.auto_clear_var, bootstyle="round-toggle"
        )
        self.auto_clear_cb.pack(side="right", padx=(0, 10))
        ui_theme.add_tooltip(self.auto_clear_cb, "Limpiar la consola antes de ejecutar un nuevo comando")

        # Controles de energía y combos
        self.power_frame = tb.Frame(console_card, style="PulseCardInner.TFrame")
        self.power_frame.grid(row=4, column=0, pady=(2, 0), sticky="ew")

        self.keep_awake_var = tk.BooleanVar(value=False)
        self.keep_awake_cb = tb.Checkbutton(
            self.power_frame, text="Evitar suspensión / hibernación", variable=self.keep_awake_var, bootstyle="round-toggle"
        )
        self.keep_awake_cb.pack(side="left", padx=(0, 16))
        ui_theme.add_tooltip(
            self.keep_awake_cb,
            "Evita que Windows suspenda o hiberne mientras se ejecuta un comando (la pantalla puede apagarse normalmente).",
        )

        self.shutdown_after_var = tk.BooleanVar(value=False)
        self.shutdown_after_cb = tb.Checkbutton(
            self.power_frame, text="Apagar PC al finalizar", variable=self.shutdown_after_var, bootstyle="danger-round-toggle"
        )
        self.shutdown_after_cb.pack(side="left", padx=(0, 16))
        ui_theme.add_tooltip(
            self.shutdown_after_cb,
            "Al terminar la ejecución, inicia una cuenta regresiva cancelable de 60s para apagar el equipo. Si ocurre un error, guarda un reporte HTML en el Escritorio.",
        )

        self.combo_suggestions_var = tk.BooleanVar(value=True)
        self.combo_suggestions_cb = tb.Checkbutton(
            self.power_frame, text="Sugerencias de combos", variable=self.combo_suggestions_var, bootstyle="info-round-toggle"
        )
        self.combo_suggestions_cb.pack(side="left")
        ui_theme.add_tooltip(
            self.combo_suggestions_cb,
            "Muestra un modal con funciones recomendadas antes (Protocolo Seguro) o después del comando actual para encadenarlas automáticamente.",
        )

        # ---------- DASHBOARD DINÁMICO DE SENSORES (Tarjeta redondeada 12px + Meters) ----------
        self.sensors_card = ui_theme.RoundedCard(self.right_frame, title="Sensores del Sistema en Tiempo Real", padding=(6, 2))
        self.sensors_card.grid(row=1, column=0, pady=(10, 0), sticky="ew")

        meters_wrap = tb.Frame(self.sensors_card.body, style="PulseCardInner.TFrame")
        meters_wrap.pack(side="left")

        self.meter_cpu = Meter(
            meters_wrap,
            metersize=92,
            amountused=0,
            amounttotal=100,
            metertype="semi",
            subtext="CPU",
            textright="%",
            meterthickness=7,
            stripethickness=2,
            textfont=("Segoe UI", 9, "bold"),
            subtextfont=("Segoe UI", 8),
            bootstyle="success",
            interactive=False,
        )
        self.meter_cpu.pack(side="left", padx=(0, 14))

        self.meter_ram = Meter(
            meters_wrap,
            metersize=92,
            amountused=0,
            amounttotal=100,
            metertype="semi",
            subtext="RAM",
            textright="%",
            meterthickness=7,
            stripethickness=2,
            textfont=("Segoe UI", 9, "bold"),
            subtextfont=("Segoe UI", 8),
            bootstyle="success",
            interactive=False,
        )
        self.meter_ram.pack(side="left", padx=(0, 14))

        self.meter_disk = Meter(
            meters_wrap,
            metersize=92,
            amountused=0,
            amounttotal=100,
            metertype="semi",
            subtext="Disco C:",
            textright="%",
            meterthickness=7,
            stripethickness=2,
            textfont=("Segoe UI", 9, "bold"),
            subtextfont=("Segoe UI", 8),
            bootstyle="info",
            interactive=False,
        )
        self.meter_disk.pack(side="left", padx=(0, 14))

        stats_info = tb.Frame(self.sensors_card.body, style="PulseCardInner.TFrame")
        stats_info.pack(side="right", fill="y", padx=(8, 4))

        self.lbl_cpu = tb.Label(stats_info, text="CPU: --% | Hilos: --", font=("Consolas", 9, "bold"), anchor="e", style="PulseCard.TLabel")
        self.lbl_cpu.pack(anchor="e", pady=2)

        self.lbl_ram = tb.Label(stats_info, text="RAM: -- / -- GB", font=("Consolas", 9, "bold"), anchor="e", style="PulseCard.TLabel")
        self.lbl_ram.pack(anchor="e", pady=2)

        self.lbl_disk = tb.Label(stats_info, text="Disco C: -- GB libres", font=("Consolas", 9, "bold"), anchor="e", style="PulseCard.TLabel")
        self.lbl_disk.pack(anchor="e", pady=2)

        self.update_console_tags()
        self.update_status_dashboard()
        self.protocol("WM_DELETE_WINDOW", self._on_app_close)

        # Atajos de teclado
        self.bind("<Control-Return>", lambda _e: self.toggle_execution())
        self.bind("<Control-l>", lambda _e: self.clear_output())
        self.bind("<Control-L>", lambda _e: self.clear_output())

        self.on_category_change(self.cat_var.get())

        self.after(500, lambda: check_dependencies(self))
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
        except Exception:
            pass

        try:
            with open(get_user_data_path("favorites.json"), "r", encoding="utf-8") as f:
                favs = json.load(f)
                if favs:
                    config["categories"].insert(0, {
                        "name": FAVORITES_CATEGORY_NAME,
                        "commands": favs,
                    })
        except Exception:
            pass

        return config

    @staticmethod
    def _sensor_bootstyle(val):
        if val < 55:
            return "success"
        if val < 80:
            return "warning"
        return "danger"

    def update_status_dashboard(self):
        try:
            cpu = psutil.cpu_percent(interval=None)
            vm = psutil.virtual_memory()
            ram = vm.percent
            ram_used_gb = vm.used / (1024 ** 3)
            ram_total_gb = vm.total / (1024 ** 3)
            threads = os.cpu_count() or 0

            sys_drive = os.environ.get("SystemDrive", "C:") + "\\"
            du = psutil.disk_usage(sys_drive)
            disk_pct = du.percent
            disk_free_gb = du.free / (1024 ** 3)

            cpu_int = int(round(cpu))
            ram_int = int(round(ram))
            disk_int = int(round(disk_pct))
            cpu_style = self._sensor_bootstyle(cpu)
            ram_style = self._sensor_bootstyle(ram)
            disk_style = self._sensor_bootstyle(disk_pct)

            prev = getattr(self, "_last_sensor_vals", {})
            if prev.get("cpu") != (cpu_int, cpu_style):
                self.meter_cpu.configure(amountused=cpu_int, bootstyle=cpu_style)
            if prev.get("ram") != (ram_int, ram_style):
                self.meter_ram.configure(amountused=ram_int, bootstyle=ram_style)
            if prev.get("disk") != (disk_int, disk_style):
                self.meter_disk.configure(amountused=disk_int, bootstyle=disk_style)
            self._last_sensor_vals = {
                "cpu": (cpu_int, cpu_style),
                "ram": (ram_int, ram_style),
                "disk": (disk_int, disk_style),
            }

            self.lbl_cpu.configure(text=f"CPU: {cpu:.0f}% | Hilos: {threads}", bootstyle=cpu_style)
            self.lbl_ram.configure(text=f"RAM: {ram_used_gb:.1f} / {ram_total_gb:.1f} GB ({ram:.0f}%)", bootstyle=ram_style)
            self.lbl_disk.configure(text=f"Disco C: {disk_free_gb:.1f} GB libres ({disk_pct:.0f}%)", bootstyle=disk_style)
        except Exception:
            self.lbl_cpu.configure(text="CPU: --%")
            self.lbl_ram.configure(text="RAM: --%")
            self.lbl_disk.configure(text="Disco C: --")
        self.after(2000, self.update_status_dashboard)

    def get_windows_drives(self):
        drives = []
        try:
            output = subprocess.check_output(
                ["powershell", "-Command", "Get-CimInstance Win32_LogicalDisk | Where-Object DriveType -eq 3 | ForEach-Object { $n = $_.VolumeName; if(-not $n){ $n = $_.Description }; $_.DeviceID + ' (' + $n + ')' }"],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            ).decode("mbcs", errors="ignore").strip().split("\n")
            for line in output:
                if line.strip():
                    drives.append(line.strip())
        except Exception:
            pass
        if not drives:
            import string
            bitmask = ctypes.windll.kernel32.GetLogicalDrives()
            for letter in string.ascii_uppercase:
                if bitmask & 1:
                    drives.append(f"{letter}:")
                bitmask >>= 1
        return drives if drives else ["C:"]

    def get_physical_disks(self, filter_status=None):
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
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            ).decode("mbcs", errors="ignore").strip().split("\n")
            for line in output:
                if line.strip():
                    disks.append(line.strip())
        except Exception:
            pass
        if not disks:
            disks = ["(Ningun disco)"]
        return disks

    def get_wifi_profiles(self):
        profiles = []
        try:
            output = subprocess.check_output(
                "netsh wlan show profiles", shell=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
            ).decode("mbcs", errors="ignore").split("\n")
            for line in output:
                if "Perfil de todos los usuarios" in line or "All User Profile" in line:
                    profile_name = line.split(":", 1)[1].strip()
                    if profile_name:
                        profiles.append(profile_name)
        except Exception:
            pass
        return profiles if profiles else ["(Ninguna red encontrada)"]

    def get_network_adapters(self):
        adapters = []
        try:
            output = subprocess.check_output(
                ["powershell", "-Command", "Get-NetAdapter | Select-Object -ExpandProperty Name"],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            ).decode("mbcs", errors="ignore").strip().split("\n")
            for line in output:
                if line.strip():
                    adapters.append(line.strip())
        except Exception:
            pass
        return adapters if adapters else ["(Ninguno)"]

    def get_cpu_threads_list(self):
        try:
            threads = os.cpu_count() or 4
        except Exception:
            threads = 4
        options = ["0 (Auto - Todos)"]
        for i in range(1, threads + 1):
            options.append(str(i))
        return options

    def on_theme_toggle(self, is_dark):
        target = ui_theme.DEFAULT_DARK_THEME if is_dark else ui_theme.DEFAULT_LIGHT_THEME
        if target == self.current_theme:
            return
        saved = ui_theme.set_saved_theme(target)
        self.current_theme = saved
        try:
            self.style.theme_use(saved)
        except Exception:
            pass
        ui_theme.apply_rounded_styles(self.style, saved)
        if hasattr(self, "dark_mode_var"):
            self.dark_mode_var.set(bool(is_dark))
        if hasattr(self, "theme_switch"):
            self.theme_switch.configure(text="Modo Oscuro" if is_dark else "Modo Claro")
        if hasattr(self, "progressbar"):
            self.progressbar.apply_palette(saved)
        self.update_console_tags()
        self.after_idle(lambda d=is_dark: ui_theme.apply_dwm_titlebar(self, dark=d))

    def update_console_tags(self):
        is_dark = ui_theme.is_dark_theme(self.current_theme)
        pal = ui_theme.get_pulse_palette(self.current_theme)
        tk_txt = self.output_textbox.text
        tk_txt.configure(bg=pal["well_bg"], fg=pal["fg"], insertbackground=pal["fg"], relief="flat", bd=1)
        tk_txt.tag_config("error", foreground="#FF5C5C" if is_dark else "#C62828")
        tk_txt.tag_config("success", foreground="#4ADE80" if is_dark else "#148F47")
        tk_txt.tag_config("ip", foreground="#60A5FA" if is_dark else "#008CC7")
        tk_txt.tag_config("path", foreground="#FBBF24" if is_dark else "#D98A00")
        tk_txt.tag_config("highlight", foreground="#F472B6" if is_dark else "#5B3299")

        card_bg = pal["card_bg"]
        fg = pal["fg"]
        for lbl in (getattr(self, "lbl_progress", None), getattr(self, "lbl_eta", None)):
            if lbl is not None:
                lbl.configure(bg=card_bg, fg=fg)

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
        info_win = tb.Toplevel(self)
        info_win.title(title)
        center_window(info_win, 480, 270)
        info_win.resizable(False, False)
        info_win.transient(self)
        info_win.grab_set()
        ui_theme.apply_window_chrome(info_win, self.current_theme)

        tb.Label(info_win, text=title, font=("Segoe UI", 13, "bold"), bootstyle="info").pack(pady=(18, 10), padx=16)
        tb.Label(info_win, text=message, font=("Segoe UI", 10), justify="center", wraplength=430).pack(pady=8, fill="both", expand=True, padx=20)
        tb.Button(info_win, text="Entendido", command=info_win.destroy, bootstyle="primary", width=16).pack(pady=(8, 18))
        ui_theme.bring_to_front(info_win)

    def show_command_info(self):
        cmd_data = self.get_command_data(self.cmd_var.get())
        if cmd_data:
            self.show_custom_info(f"Info: {cmd_data.get('name')}", cmd_data.get("description", ""))

    def show_arg_info(self, arg_name, arg_desc):
        self.show_custom_info(f"Info: {arg_name}", arg_desc)

    def on_search(self, *_args):
        if hasattr(self, "search_entry") and self.search_entry.is_placeholder_active():
            return
        query = self.search_entry.get_value().strip().lower() if hasattr(self, "search_entry") else self.search_var.get().strip().lower()
        if not query:
            self.cat_menu.configure(state="readonly")
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
        if self.cat_var.get() == FAVORITES_CATEGORY_NAME:
            self.fav_btn.configure(image=self._icons["trash"], bootstyle="danger", command=self.remove_favorite)
        else:
            self.fav_btn.configure(image=self._icons["star"], bootstyle="warning", command=self.save_favorite)

        for widget in self.args_frame.winfo_children():
            widget.destroy()
        self.current_args_vars.clear()

        cmd_data = self.get_command_data(selected_command)
        if cmd_data:
            from functions.setup_manager import PLUGINS, get_missing_commands
            missing = get_missing_commands()
            if cmd_data.get("command") in missing:
                plugin_needed = None
                for pid, p in PLUGINS.items():
                    if cmd_data.get("command") in p["cmds"]:
                        plugin_needed = pid
                        break

                tb.Label(
                    self.args_frame,
                    text=f"[AVISO] Falta {PLUGINS[plugin_needed]['name']}.",
                    bootstyle="danger",
                    font=("Segoe UI", 11, "bold"),
                ).pack(pady=18)

                def install_it():
                    from functions.setup_manager import PluginInstaller
                    def on_done(success):
                        if success:
                            self.on_command_change(selected_command)
                    PluginInstaller(self, plugin_needed, on_done)

                tb.Button(self.args_frame, text="Instalar Complemento", bootstyle="warning", command=install_it).pack(pady=8)
                self.execute_btn.configure(state="disabled")
                return
            else:
                self.execute_btn.configure(state="normal")

            if cmd_data.get("name") == "Compresor de Multimedia":
                self.update_hardware_options(cmd_data)

            for arg in cmd_data.get("args", []):
                arg_name = arg.get("name")
                arg_type = arg.get("type")
                arg_flag = arg.get("flag", "")
                arg_desc = arg.get("description", "")
                visible_when = arg.get("visible_when")

                holder_frame = tb.Frame(self.args_frame)
                holder_frame.pack(fill="x")
                row_frame = tb.Frame(holder_frame)
                row_frame.pack(fill="x", pady=6, padx=2)

                var = tk.StringVar(value=arg.get("value", ""))
                var.trace_add("write", lambda *_a: self.update_preview())

                option_map = None
                entry_widget = None

                if arg_type == "checkbox":
                    chk = tb.Checkbutton(row_frame, text=arg_name, variable=var, onvalue=arg_flag, offvalue="", bootstyle="primary")
                    chk.pack(side="left", padx=(0, 8))

                elif arg_type in ["entry", "directory_entry", "file_entry", "save_file_entry"]:
                    tb.Label(row_frame, text=f"{arg_name}:", wraplength=170, justify="left").pack(side="left", padx=(0, 6))

                    btn_info = tb.Button(
                        row_frame, image=self._icons["info"], bootstyle="info",
                        command=lambda n=arg_name, d=arg_desc: self.show_arg_info(n, d),
                    )
                    btn_info.pack(side="right", padx=(4, 0))

                    if arg_type in ["directory_entry", "file_entry", "save_file_entry"]:
                        def browse_folder(v=var):
                            folder = filedialog.askdirectory(parent=self)
                            if folder:
                                folder = folder.replace("/", "\\")
                                if " " in folder and not folder.startswith('"'):
                                    folder = f'"{folder}"'
                                v.set(folder)

                        def browse_file(v=var):
                            file_path = filedialog.askopenfilename(parent=self)
                            if file_path:
                                file_path = file_path.replace("/", "\\")
                                if " " in file_path and not file_path.startswith('"'):
                                    file_path = f'"{file_path}"'
                                v.set(file_path)

                        def browse_save_file(v=var):
                            file_path = filedialog.asksaveasfilename(parent=self, defaultextension="*.*", filetypes=[("Todos los archivos", "*.*")])
                            if file_path:
                                file_path = file_path.replace("/", "\\")
                                if " " in file_path and not file_path.startswith('"'):
                                    file_path = f'"{file_path}"'
                                v.set(file_path)

                        btn_frame_paths = tb.Frame(row_frame)
                        btn_frame_paths.pack(side="right", padx=(4, 0))

                        if arg_type == "save_file_entry":
                            tb.Button(btn_frame_paths, text="Guardar...", bootstyle="secondary", command=browse_save_file).pack(side="left", padx=(0, 4))
                        elif arg_type == "file_entry":
                            tb.Button(btn_frame_paths, text="Archivo", bootstyle="secondary", command=browse_file).pack(side="left", padx=(0, 4))
                        if arg_type in ["directory_entry", "file_entry"]:
                            tb.Button(btn_frame_paths, text="Carpeta", bootstyle="secondary", command=browse_folder).pack(side="left")

                    entry_widget = tb.Entry(row_frame, textvariable=var)
                    entry_widget.pack(side="left", fill="x", expand=True, padx=(0, 4))

                    self.current_args_vars[arg_name] = {
                        "var": var,
                        "type": arg_type,
                        "flag": arg_flag,
                        "option_map": option_map,
                        "row_frame": row_frame,
                        "visible_when": visible_when,
                        "is_visible": True,
                    }
                    continue

                elif arg_type == "radio_group":
                    header_r = tb.Frame(row_frame)
                    header_r.pack(fill="x")
                    tb.Label(header_r, text=f"{arg_name}:", font=("Segoe UI", 9, "bold")).pack(side="left")
                    tb.Button(
                        header_r, image=self._icons["info"], bootstyle="info",
                        command=lambda n=arg_name, d=arg_desc: self.show_arg_info(n, d),
                    ).pack(side="right")

                    rb_frame = tb.Frame(row_frame)
                    rb_frame.pack(fill="x", padx=(12, 0), pady=(4, 0))
                    for opt in arg.get("options", []):
                        tb.Radiobutton(
                            rb_frame, text=opt.get("name"), variable=var, value=opt.get("flag", ""), bootstyle="info"
                        ).pack(anchor="w", pady=2)

                    self.current_args_vars[arg_name] = {
                        "var": var,
                        "type": arg_type,
                        "flag": arg_flag,
                        "option_map": option_map,
                        "row_frame": row_frame,
                        "visible_when": visible_when,
                        "is_visible": True,
                    }
                    continue

                elif arg_type == "drive_dropdown":
                    tb.Label(row_frame, text=f"{arg_name}:").pack(side="left", padx=(0, 6))
                    drives = self.get_windows_drives()
                    if drives:
                        var.set(drives[0])
                    tb.Combobox(row_frame, textvariable=var, values=drives, state="readonly").pack(side="left", fill="x", expand=True, padx=(0, 6))

                elif arg_type in ["disk_dropdown", "disk_online_dropdown", "disk_offline_dropdown"]:
                    tb.Label(row_frame, text=f"{arg_name}:").pack(side="left", padx=(0, 6))
                    if arg_type == "disk_online_dropdown":
                        pdisks = self.get_physical_disks(filter_status="Online")
                    elif arg_type == "disk_offline_dropdown":
                        pdisks = self.get_physical_disks(filter_status="Offline")
                    else:
                        pdisks = self.get_physical_disks()
                    if pdisks:
                        var.set(pdisks[0])
                    tb.Combobox(row_frame, textvariable=var, values=pdisks, state="readonly").pack(side="left", fill="x", expand=True, padx=(0, 6))

                elif arg_type == "netadapter_dropdown":
                    tb.Label(row_frame, text=f"{arg_name}:").pack(side="left", padx=(0, 6))
                    adapters = self.get_network_adapters()
                    if adapters:
                        var.set(adapters[0])
                    tb.Combobox(row_frame, textvariable=var, values=adapters, state="readonly").pack(side="left", fill="x", expand=True, padx=(0, 6))

                elif arg_type == "wifi_radio_group":
                    header_w = tb.Frame(row_frame)
                    header_w.pack(fill="x")
                    tb.Label(header_w, text=f"{arg_name}:", font=("Segoe UI", 9, "bold")).pack(side="left")
                    tb.Button(
                        header_w, image=self._icons["info"], bootstyle="info",
                        command=lambda n=arg_name, d=arg_desc: self.show_arg_info(n, d),
                    ).pack(side="right")

                    rb_frame = tb.Frame(row_frame)
                    rb_frame.pack(fill="x", padx=(12, 0), pady=(4, 0))
                    profiles = self.get_wifi_profiles()
                    if profiles:
                        var.set(profiles[0])
                    for prof in profiles:
                        tb.Radiobutton(rb_frame, text=prof, variable=var, value=prof, bootstyle="info").pack(anchor="w", pady=2)

                    self.current_args_vars[arg_name] = {
                        "var": var,
                        "type": arg_type,
                        "flag": arg_flag,
                        "option_map": option_map,
                        "row_frame": row_frame,
                        "visible_when": visible_when,
                        "is_visible": True,
                    }
                    continue

                elif arg_type == "dropdown":
                    tb.Label(row_frame, text=f"{arg_name}:").pack(side="left", padx=(0, 6))
                    raw_opts = arg.get("options", [])
                    if raw_opts and isinstance(raw_opts[0], dict):
                        display_opts = [o.get("name", "") for o in raw_opts]
                        option_map = {o.get("name", ""): str(o.get("value", "")) for o in raw_opts}
                    else:
                        display_opts = raw_opts
                    tb.Combobox(row_frame, textvariable=var, values=display_opts, state="readonly").pack(side="left", fill="x", expand=True, padx=(0, 6))
                    if display_opts and (not var.get() or var.get() not in display_opts):
                        var.set(display_opts[0])

                elif arg_type == "threads_dropdown":
                    tb.Label(row_frame, text=f"{arg_name}:").pack(side="left", padx=(0, 6))
                    threads_options = self.get_cpu_threads_list()
                    if threads_options:
                        var.set(threads_options[0])
                    tb.Combobox(row_frame, textvariable=var, values=threads_options, state="readonly").pack(side="left", fill="x", expand=True, padx=(0, 6))

                elif arg_type == "password_single":
                    tb.Label(row_frame, text=f"{arg_name}:").pack(side="left", padx=(0, 6))
                    ent = tb.Entry(row_frame, textvariable=var, show="*")
                    ent.pack(side="left", fill="x", expand=True, padx=(0, 4))

                    btn_show_s = tb.Button(row_frame, image=self._icons["eye"], bootstyle="secondary")
                    def toggle_show_s(b=btn_show_s, e=ent):
                        if e.cget("show") == "*":
                            e.configure(show="")
                            b.configure(image=self._icons["eye_off"])
                        else:
                            e.configure(show="*")
                            b.configure(image=self._icons["eye"])
                    btn_show_s.configure(command=toggle_show_s)
                    btn_show_s.pack(side="left", padx=(0, 6))

                elif arg_type == "password_double":
                    header_p = tb.Frame(row_frame)
                    header_p.pack(fill="x")
                    tb.Label(header_p, text=f"{arg_name}:").pack(side="left")
                    tb.Button(
                        header_p, image=self._icons["info"], bootstyle="info",
                        command=lambda n=arg_name, d=arg_desc: self.show_arg_info(n, d),
                    ).pack(side="right")

                    pw_frame = tb.Frame(row_frame)
                    pw_frame.pack(fill="x", pady=(4, 0))
                    var1 = tk.StringVar()
                    var2 = tk.StringVar()
                    var.set("")

                    ent1 = tb.Entry(pw_frame, textvariable=var1, show="*")
                    ent1.pack(side="left", fill="x", expand=True, padx=(0, 4))
                    ent2 = tb.Entry(pw_frame, textvariable=var2, show="*")
                    ent2.pack(side="left", fill="x", expand=True, padx=(4, 4))

                    btn_show = tb.Button(pw_frame, image=self._icons["eye"], bootstyle="secondary")
                    def toggle_show(b=btn_show, e1=ent1, e2=ent2):
                        if e1.cget("show") == "*":
                            e1.configure(show="")
                            e2.configure(show="")
                            b.configure(image=self._icons["eye_off"])
                        else:
                            e1.configure(show="*")
                            e2.configure(show="*")
                            b.configure(image=self._icons["eye"])
                    btn_show.configure(command=toggle_show)
                    btn_show.pack(side="left")

                    def check_match(*_cb, v=var, e2=ent2, v1_var=var1, v2_var=var2):
                        v1, v2 = v1_var.get(), v2_var.get()
                        if v1 != v2 or not v1:
                            e2.configure(bootstyle="danger")
                            v.set("")
                        else:
                            e2.configure(bootstyle="success")
                            v.set(v1)
                    var1.trace_add("write", check_match)
                    var2.trace_add("write", check_match)

                    self.current_args_vars[arg_name] = {
                        "var": var,
                        "type": arg_type,
                        "flag": arg_flag,
                        "option_map": option_map,
                        "row_frame": row_frame,
                        "visible_when": visible_when,
                        "is_visible": True,
                    }
                    continue

                self.current_args_vars[arg_name] = {
                    "var": var,
                    "type": arg_type,
                    "flag": arg_flag,
                    "option_map": option_map,
                    "row_frame": row_frame,
                    "visible_when": visible_when,
                    "is_visible": True,
                }

                tb.Button(
                    row_frame, image=self._icons["info"], bootstyle="info",
                    command=lambda n=arg_name, d=arg_desc: self.show_arg_info(n, d),
                ).pack(side="right")

        self.update_preview()

    def _refresh_conditional_args(self):
        """Muestra u oculta campos condicionales según visible_when sin alterar el orden vertical."""
        for _name, arg_data in self.current_args_vars.items():
            cond = arg_data.get("visible_when")
            row = arg_data.get("row_frame")
            if not cond or row is None:
                arg_data["is_visible"] = True
                continue
            parent = self.current_args_vars.get(cond.get("arg"))
            if not parent:
                arg_data["is_visible"] = True
                continue
            raw_val = parent["var"].get().strip()
            opt_map = parent.get("option_map")
            eff_val = opt_map.get(raw_val, raw_val) if opt_map else raw_val
            should_show = eff_val in (cond.get("values") or [])
            arg_data["is_visible"] = should_show
            if should_show:
                if not row.winfo_ismapped():
                    row.pack(fill="x", pady=6, padx=2)
            else:
                if row.winfo_ismapped():
                    row.pack_forget()

    def update_hardware_options(self, cmd_data):
        has_nvenc = False
        has_amf = False
        has_qsv = False
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            output = subprocess.check_output(
                ["powershell", "-Command", "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"],
                text=True,
                startupinfo=startupinfo,
            )
            out_upper = output.upper()
            has_nvenc = "NVIDIA" in out_upper
            has_amf = "AMD" in out_upper or "RADEON" in out_upper
            has_qsv = "INTEL" in out_upper
        except Exception:
            pass

        options = [{"name": "Auto-Detectar (Prioriza Dedicada)", "flag": "--hw auto"}]
        if has_nvenc:
            options.append({"name": "NVIDIA (NVENC) - Dedicada", "flag": "--hw nvenc"})
        if has_amf:
            options.append({"name": "AMD (AMF)", "flag": "--hw amf"})
        if has_qsv:
            options.append({"name": "Intel (QSV) - Integrada", "flag": "--hw qsv"})
        options.append({"name": "Solo CPU (Lento pero seguro)", "flag": "--hw cpu"})

        for arg in cmd_data.get("args", []):
            if arg.get("name") == "Motor de Aceleracion de Hardware":
                arg["options"] = options
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

        self._refresh_conditional_args()

        command_list = [cmd_data.get("command", "")]
        for _arg_name, arg_data in self.current_args_vars.items():
            if not arg_data.get("is_visible", True):
                continue
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

        if selected_command == "Compresor de Multimedia":
            args_map = {k: d["var"].get().strip() for k, d in self.current_args_vars.items()}
            input_val = (args_map.get("Seleccionar Carpeta (Lote)", "") or args_map.get("Seleccionar Archivo (Individual)", "")).strip("\"'")
            out_val = args_map.get("Salida (Carpeta opcional)", "").strip("\"'")
            suffix = args_map.get("Sufijo de archivo", "")

            if not out_val and input_val:
                out_val = os.path.dirname(input_val) if os.path.isfile(input_val) else input_val

            if input_val and out_val and input_val.lower() == out_val.lower() and not suffix:
                self.execute_btn.configure(state="disabled", text=" Falta sufijo (Evitará sobrescribir originales)")
            elif not self.is_running:
                self.execute_btn.configure(state="normal", text=" Ejecutar Comando")

    def pause_execution(self):
        if not self.is_running:
            return
        appdata = os.environ.get("APPDATA", "")
        flag_file = os.path.join(appdata, "cmd_gui_advance", "pause.flag")
        try:
            os.makedirs(os.path.dirname(flag_file), exist_ok=True)
            with open(flag_file, "w", encoding="utf-8") as f:
                f.write("1")
            self.append_output("\n[SISTEMA] Señal de pausa enviada. El proceso se detendrá al terminar su tarea actual...\n")
            self.pause_btn.configure(state="disabled", text=" Pausando...")
        except Exception as e:
            self.append_output(f"\nError enviando señal de pausa: {e}\n")

    def run_help(self):
        if self.is_running:
            return
        cmd_data = self.get_command_data(self.cmd_var.get())
        if cmd_data:
            self.execute_external(f"{cmd_data.get('command')} /?")

    @staticmethod
    def get_active_warning(cmd_data, cmd_str):
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
        level = warning.get("level", "caution")
        title = warning.get("title", "Confirmación de Ejecución")
        message = warning.get("message", "Esta operación realizará cambios en el sistema o en tus archivos.")
        is_danger = level == "danger"
        style_key = "danger" if is_danger else "warning"
        badge_text = "ACCIÓN CRÍTICA" if is_danger else "CONFIRMACIÓN DE CAMBIO"

        result = {"proceed": False}
        win = tb.Toplevel(self)
        win.title(f"Advertencia — {title}")
        win.geometry("560x370")
        win.resizable(False, False)
        win.transient(self)
        win.grab_set()
        ui_theme.apply_window_chrome(win, self.current_theme)

        win.update_idletasks()
        x = int(self.winfo_x() + (self.winfo_width() / 2) - 280)
        y = int(self.winfo_y() + (self.winfo_height() / 2) - 185)
        win.geometry(f"+{x}+{y}")

        header = tb.Frame(win, bootstyle=style_key, padding=10)
        header.pack(fill="x", padx=16, pady=(14, 10))
        tb.Label(
            header, text=f"{badge_text}  —  {title}", font=("Segoe UI", 12, "bold"),
            bootstyle=f"inverse-{style_key}", wraplength=500, justify="left",
        ).pack(anchor="w")

        tb.Label(win, text=message, font=("Segoe UI", 10), wraplength=510, justify="left", anchor="w").pack(fill="x", padx=18, pady=(4, 10))

        preview_text = cmd_str if len(cmd_str) <= 220 else cmd_str[:217] + "..."
        preview_box = ScrolledText(win, height=4, font=("Consolas", 9), wrap="word", auto_hide=True)
        preview_box.pack(fill="x", padx=18, pady=(0, 12))
        preview_box.text.insert("1.0", f"Comando a ejecutar:\n{preview_text}")
        preview_box.text.configure(state="disabled")

        btn_row = tb.Frame(win)
        btn_row.pack(fill="x", padx=18, pady=(4, 14))

        def on_cancel():
            result["proceed"] = False
            win.destroy()

        def on_continue():
            result["proceed"] = True
            win.destroy()

        cancel_btn = tb.Button(btn_row, text="Cancelar", bootstyle="secondary-outline", command=on_cancel, width=16)
        cancel_btn.pack(side="left")

        tb.Button(btn_row, text="Continuar y Ejecutar", bootstyle=style_key, command=on_continue, width=22).pack(side="right")

        win.bind("<Escape>", lambda _e: on_cancel())
        win.protocol("WM_DELETE_WINDOW", on_cancel)
        ui_theme.bring_to_front(win)
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
        from functions import power_manager
        try:
            content = self.output_textbox.text.get("1.0", "end-1c")
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
        from functions import power_manager
        state = {"remaining": int(seconds), "cancelled": False, "timer_id": None}

        win = tb.Toplevel(self)
        win.title("Apagado Automático Programado")
        win.geometry("520x300")
        win.resizable(False, False)
        win.transient(self)
        win.grab_set()
        ui_theme.apply_window_chrome(win, self.current_theme)

        win.update_idletasks()
        x = int(self.winfo_x() + (self.winfo_width() / 2) - 260)
        y = int(self.winfo_y() + (self.winfo_height() / 2) - 150)
        win.geometry(f"+{x}+{y}")

        style_key = "warning" if had_error else "info"
        header_txt = "Tarea finalizada con error — Apagado en curso" if had_error else "Tarea finalizada — Apagado automático"
        header = tb.Frame(win, bootstyle=style_key, padding=10)
        header.pack(fill="x", padx=16, pady=(14, 10))
        tb.Label(header, text=header_txt, font=("Segoe UI", 12, "bold"), bootstyle=f"inverse-{style_key}").pack(anchor="w")

        countdown_lbl = tb.Label(win, text=f"El equipo se apagará en {state['remaining']} segundos.", font=("Segoe UI", 14, "bold"))
        countdown_lbl.pack(pady=(8, 6))

        if had_error and report_path:
            extra_msg = f"Se guardó automáticamente el reporte HTML de errores en tu Escritorio:\n{report_path}"
        elif had_error:
            extra_msg = "El comando finalizó con errores. Puedes cancelar el apagado para revisar la consola."
        else:
            extra_msg = "Puedes cancelar el apagado en cualquier momento antes de que termine el conteo."

        tb.Label(win, text=extra_msg, font=("Segoe UI", 10), wraplength=470, justify="center").pack(padx=18, pady=(0, 14))

        btn_row = tb.Frame(win)
        btn_row.pack(fill="x", padx=18, pady=(4, 14))

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

        cancel_btn = tb.Button(btn_row, text="Cancelar Apagado", bootstyle="danger", command=cancel_shutdown, width=20)
        cancel_btn.pack(side="left")

        tb.Button(btn_row, text="Apagar Ahora", bootstyle="info", command=shutdown_now, width=16).pack(side="right")

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

        win.bind("<Escape>", lambda _e: cancel_shutdown())
        win.protocol("WM_DELETE_WINDOW", cancel_shutdown)
        ui_theme.bring_to_front(win)
        cancel_btn.focus_set()
        state["timer_id"] = win.after(1000, tick)

    def navigate_to_command(self, target_cmd_name):
        if hasattr(self, "search_entry") and self.search_entry.get_value():
            self.search_entry.set_value("")
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
        result = {"action": None, "before": [], "after": [], "auto_execute": True}
        before_vars = []
        after_vars = []
        auto_exec_var = tk.BooleanVar(value=True)

        win = tb.Toplevel(self)
        win.title(f"Sugerencias de Combo — {main_cmd_name}")
        win.geometry("660x530")
        win.resizable(False, False)
        win.transient(self)
        win.grab_set()
        ui_theme.apply_window_chrome(win, self.current_theme)

        win.update_idletasks()
        x = int(self.winfo_x() + (self.winfo_width() / 2) - 330)
        y = int(self.winfo_y() + (self.winfo_height() / 2) - 265)
        win.geometry(f"+{x}+{y}")

        header = tb.Frame(win, bootstyle="primary", padding=10)
        header.pack(fill="x", padx=16, pady=(14, 8))
        tb.Label(
            header, text=f"Combos Recomendados para: {main_cmd_name}",
            font=("Segoe UI", 12, "bold"), bootstyle="inverse-primary", wraplength=600,
        ).pack(anchor="w")

        scroll = ScrolledFrame(win, auto_hide=True, padding=6)
        scroll.pack(fill="both", expand=True, padx=14, pady=(0, 8))

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

        def add_section(title_txt, style_key, items, target_vars):
            sec = tb.Labelframe(scroll, text=title_txt, padding=8, bootstyle=style_key)
            sec.pack(fill="x", pady=6, padx=2)
            for item in items:
                var = tk.BooleanVar(value=False)
                var.trace_add("write", refresh_confirm_label)
                target_vars.append((var, item))
                mode_tag = "[Automático en cola]" if item["mode"] == "auto" else "[Abrir para configurar]"
                cb = tb.Checkbutton(sec, text=f"{item['command']}  {mode_tag}", variable=var, bootstyle=style_key)
                cb.pack(anchor="w", pady=(4, 1))
                if item.get("reason"):
                    tb.Label(sec, text=item["reason"], font=("Segoe UI", 9), wraplength=560, bootstyle="secondary").pack(anchor="w", padx=(24, 4), pady=(0, 4))

        if before_list:
            add_section("PROTOCOLO SEGURO — Ejecutar ANTES de tu comando", "warning", before_list, before_vars)
        if after_list:
            add_section("CONTINUACIÓN — Ejecutar o abrir DESPUÉS de tu comando", "success", after_list, after_vars)

        opt_bar = tb.Frame(win, padding=(16, 4))
        opt_bar.pack(fill="x")
        auto_cb = tb.Checkbutton(
            opt_bar,
            text="Autoejecutar cola completa en un solo clic (servicio continuo sin pausas)",
            variable=auto_exec_var,
            bootstyle="success-round-toggle",
        )
        auto_cb.pack(anchor="w")
        auto_exec_var.trace_add("write", refresh_confirm_label)
        ui_theme.add_tooltip(
            auto_cb,
            "Activo: ejecuta de corrido todos los pasos automáticos seleccionados. Desactivado: abre el siguiente paso al terminar para revisarlo.",
        )

        btn_row = tb.Frame(win)
        btn_row.pack(fill="x", padx=16, pady=(8, 14))

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

        tb.Button(btn_row, text="Cancelar", bootstyle="secondary-outline", command=on_cancel, width=12).pack(side="left")
        tb.Button(btn_row, text="Solo mi comando", bootstyle="secondary", command=on_only_main, width=16).pack(side="right", padx=(8, 0))

        confirm_btn = tb.Button(btn_row, text="Aceptar y Continuar", bootstyle="success", command=on_confirm, width=24)
        confirm_btn.pack(side="right")
        confirm_btn_ref["btn"] = confirm_btn

        win.bind("<Escape>", lambda _e: on_cancel())
        win.protocol("WM_DELETE_WINDOW", on_cancel)
        ui_theme.bring_to_front(win)
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
                        cmd_name, cmd_str, sel_before, sel_after, auto_execute=auto_exec, context=ctx
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
        if not cmd_str:
            return
        drives = set(re.findall(r"([A-Za-z]):[\\/]", cmd_str))
        drives.update(re.findall(r"--drive\s+([A-Za-z]):?", cmd_str, flags=re.IGNORECASE))
        if not drives:
            self.run_command()
            return

        self.execute_btn.configure(text=" Analizando disco...", state="disabled")

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
                    out = subprocess.check_output(
                        ["powershell", "-NoProfile", "-Command", script],
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                        text=True,
                    ).strip()
                    if out:
                        parts = out.split("|")
                        if len(parts) >= 3:
                            media_type, is_ro, health = parts[0], parts[1], parts[2]
                            if is_ro.lower() == "true":
                                warnings.append(f"• El disco {d}: está bloqueado en modo Solo Lectura (Hardware). Cualquier comando de escritura o borrado fallará.")
                            if health.lower() not in ["healthy", "unknown", ""]:
                                warnings.append(f"• El estado de salud del disco {d}: es '{health}'. Proceder con precaución.")
                            if media_type.lower() == "ssd":
                                cmd_lower = cmd_str.lower()
                                if "chkdsk" in cmd_lower and "/r" in cmd_lower:
                                    warnings.append(f"• Vas a ejecutar CHKDSK /R en un SSD ({d}:). Esto causa desgaste innecesario en SSDs.")
                                if "clear-disk" in cmd_lower:
                                    warnings.append(f"• CUIDADO: Clear-Disk borrará TODA la información y particiones del SSD ({d}:) de forma irrecuperable.")
                                if "--run-sdelete" in cmd_lower:
                                    warnings.append(
                                        f"• ADVERTENCIA SSD ({d}:): Vas a ejecutar SDelete sobre un SSD. Debido al wear leveling, "
                                        "múltiples pasadas desgastan los ciclos de vida (TBW). Modo seguro recomendado: 1 pasada (-p 1), Optimizar/TRIM o BitLocker."
                                    )
            except Exception:
                pass
            self.after(0, self._on_check_done, warnings)

        threading.Thread(target=_check, daemon=True).start()

    def _on_check_done(self, warnings):
        self.execute_btn.configure(text=" Ejecutar Comando", state="normal")
        if warnings:
            msg = "Resultados del Análisis de Unidad:\n\n" + "\n\n".join(warnings) + "\n\n¿Estás completamente seguro de continuar con la ejecución?"
            if not messagebox.askyesno("Advertencia de Hardware", msg, parent=self):
                return
        self.run_command()

    def remove_favorite(self):
        cmd_name = self.cmd_var.get()
        try:
            fav_path = get_user_data_path("favorites.json")
            if not os.path.exists(fav_path):
                return
            with open(fav_path, "r", encoding="utf-8") as f:
                favs = json.load(f)
        except Exception:
            return

        new_favs = [f for f in favs if f.get("name") != cmd_name]
        with open(get_user_data_path("favorites.json"), "w", encoding="utf-8") as f:
            json.dump(new_favs, f, indent=4)

        self.output_textbox.text.configure(state="normal")
        self.output_textbox.text.insert("end", f"\n[!] Comando '{cmd_name}' eliminado de Favoritos.\n(Reinicia la app para actualizar la lista)\n", "error")
        self.output_textbox.text.see("end")
        self.output_textbox.text.configure(state="disabled")

    def save_favorite(self):
        cmd_data = self.get_command_data(self.cmd_var.get())
        if not cmd_data:
            return
        fav_cmd = copy.deepcopy(cmd_data)
        for arg in fav_cmd.get("args", []):
            arg_name = arg.get("name")
            if arg_name in self.current_args_vars:
                arg["value"] = self.current_args_vars[arg_name]["var"].get()

        favs = []
        try:
            fav_path = get_user_data_path("favorites.json")
            if os.path.exists(fav_path):
                with open(fav_path, "r", encoding="utf-8") as f:
                    favs = json.load(f)
        except Exception:
            pass

        base_name = f"{fav_cmd['name']} (Fav)"
        fav_name = base_name
        counter = 1
        while any(f.get("name") == fav_name for f in favs):
            existing = next((f for f in favs if f.get("name") == fav_name), None)
            if existing and existing.get("args") == fav_cmd.get("args"):
                self.output_textbox.text.configure(state="normal")
                self.output_textbox.text.insert("end", "\n[!] Este comando con los mismos parámetros ya existe en Favoritos.\n", "error")
                self.output_textbox.text.see("end")
                self.output_textbox.text.configure(state="disabled")
                return
            counter += 1
            fav_name = f"{base_name} {counter}"

        fav_cmd["name"] = fav_name
        favs.append(fav_cmd)
        with open(get_user_data_path("favorites.json"), "w", encoding="utf-8") as f:
            json.dump(favs, f, indent=4)

        self.output_textbox.text.configure(state="normal")
        self.output_textbox.text.insert("end", f"\n[OK] Comando '{fav_name}' guardado en Favoritos.\n(Reinicia la app para verlo en la lista)\n", "success")
        self.output_textbox.text.see("end")
        self.output_textbox.text.configure(state="disabled")

    def run_command(self):
        if not self.preview_var.get():
            return
        self.execute_external(self.preview_var.get())

    @staticmethod
    def extract_progress_from_text(text):
        if not text:
            return None
        lower = text.lower()
        if any(k in lower for k in ("espacio ahorrado", "incremento de peso", "ram:", "cpu:")):
            return None
        m_pct = re.search(r"(?<!\d)(\d{1,3}(?:[.,]\d+)?)\s*%", text)
        if m_pct:
            try:
                val = float(m_pct.group(1).replace(",", "."))
                if 0.0 <= val <= 100.0:
                    return val
            except ValueError:
                pass
        m_frac = re.search(r"[\[\(](\d+)\s*/\s*(\d+)[\]\)]", text)
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
        p = max(0.0, min(100.0, float(pct)))
        if p < 25.0:
            return "#dc3545"
        if p < 50.0:
            return "#fd7e14"
        if p < 75.0:
            return "#ffc107" if ui_theme.is_dark_theme() else "#B45309"
        return "#28a745"

    @staticmethod
    def get_eta_color(pct):
        p = max(0.0, min(100.0, float(pct)))
        if p >= 100.0:
            return "#28a745"
        if p < 25.0:
            return "#28a745"
        if p < 50.0:
            return "#ffc107" if ui_theme.is_dark_theme() else "#B45309"
        if p < 75.0:
            return "#fd7e14"
        return "#dc3545"

    @staticmethod
    def _progress_bootstyle(pct):
        if pct < 25.0:
            return "danger"
        if pct < 60.0:
            return "warning"
        if pct < 90.0:
            return "info"
        return "success"

    def _get_elapsed_seconds(self):
        return max(0.0, time.time() - getattr(self, "_cmd_start_time", time.time()))

    def _format_elapsed(self):
        return self.format_duration(self._get_elapsed_seconds())

    def _refresh_progress_labels(self, pct, detail=None):
        elapsed_sec = self._get_elapsed_seconds()
        elapsed_str = self.format_duration(elapsed_sec)
        if hasattr(self, "lbl_progress"):
            prefix = f"{detail}: " if detail else ""
            self.lbl_progress.configure(text=f"{prefix}{pct:.0f}% ({elapsed_str})", fg=self.get_progress_color(pct))
        if hasattr(self, "lbl_eta"):
            rem = self.estimate_remaining_seconds(elapsed_sec, pct)
            eta_str = self.format_duration(rem) if rem is not None else "--:--"
            self.lbl_eta.configure(text=f"ETA: {eta_str}", fg=self.get_eta_color(pct))

    def _set_determinate_progress(self, pct, detail=None):
        if not hasattr(self, "progressbar"):
            return
        pct_clamped = max(0.0, min(100.0, float(pct)))
        if not getattr(self, "_has_determinate_progress", False):
            self._has_determinate_progress = True
            try:
                self.progressbar.stop()
            except Exception:
                pass
        self._last_progress_pct = pct_clamped
        self._last_progress_detail = detail
        self.progressbar.set_progress(
            value=pct_clamped,
            mode="determinate",
            bootstyle=self._progress_bootstyle(pct_clamped),
        )
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
            if hasattr(self, "lbl_progress"):
                self.lbl_progress.configure(text=f"Ejecutando... ({elapsed})", fg="#dc3545")
            if hasattr(self, "lbl_eta"):
                self.lbl_eta.configure(text="ETA: --:--", fg="#28a745")
        self._progress_timer_id = self.after(1000, self._tick_progress_timer)

    def _start_storage_job_monitor(self, command_str):
        storage_keywords = ("Format-Volume", "Clear-Disk", "Optimize-Volume", "Initialize-Disk", "New-Partition")
        if not any(k.lower() in command_str.lower() for k in storage_keywords):
            return

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
        if hasattr(self, "auto_clear_var") and self.auto_clear_var.get():
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

        self.execute_btn.configure(text=" Detener ejecución", image=self._icons["stop"], bootstyle="danger")
        self.cat_menu.configure(state="disabled")
        self.cmd_menu.configure(state="disabled")
        self.pause_btn.pack(side="left", padx=(0, 6), before=self.fav_btn)

        appdata = os.environ.get("APPDATA", "")
        flag_file = os.path.join(appdata, "cmd_gui_advance", "pause.flag")
        if os.path.exists(flag_file):
            try:
                os.remove(flag_file)
            except Exception:
                pass

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
            if hasattr(self, "progressbar"):
                try:
                    self.progressbar.stop()
                except Exception:
                    pass
                if last_rc == 0 and not self._queue_had_error:
                    self.progressbar.set_progress(value=100, mode="determinate", bootstyle="success")
                    self.lbl_progress.configure(text=f"100% Completado ({elapsed})", fg="#28a745")
                    self.lbl_eta.configure(text="ETA: 00:00", fg="#28a745")
                else:
                    last_pct = getattr(self, "_last_progress_pct", 0.0) if getattr(self, "_has_determinate_progress", False) else 0.0
                    self.progressbar.set_progress(value=last_pct, mode="determinate", bootstyle="danger")
                    self.lbl_progress.configure(text=f"Detenido / Error ({elapsed})", fg="#dc3545")
                    self.lbl_eta.configure(text="ETA: --:--", fg="#dc3545")

            self.execute_btn.configure(text=" Ejecutar Comando", image=self._icons["play"], bootstyle="success")
            self.cat_menu.configure(state="readonly")
            self.cmd_menu.configure(state="readonly")
            self.pause_btn.configure(state="normal", text=" Posponer")
            self.pause_btn.pack_forget()

            if next_navigate_name and not getattr(self, "_stopped_by_user", False):
                self.navigate_to_command(next_navigate_name)
                self.append_output(f"\n[COMBO] Siguiente paso listo para configurar y ejecutar: '{next_navigate_name}'.\n")

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

            if hasattr(self, "progressbar"):
                try:
                    self.progressbar.set_progress(value=0, mode="indeterminate", bootstyle="info")
                    self.progressbar.start(35)
                except Exception:
                    pass
                step_prefix = f"[{self._queue_step_idx}/{self._queue_total}] " if self._queue_total > 1 else ""
                self.lbl_progress.configure(text=f"{step_prefix}Ejecutando... (00:00)", fg="#dc3545")
                self.lbl_eta.configure(text="ETA: --:--", fg="#28a745")

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
            tk_txt = self.output_textbox.text
            tk_txt.configure(state="normal")

            if text.endswith("\r\n"):
                text = text[:-2] + "\n"

            if self._last_was_cr:
                if text == "\n":
                    self._last_was_cr = False
                    tk_txt.insert("end", "\n")
                    tk_txt.see("end")
                    tk_txt.configure(state="disabled")
                    return
                tk_txt.delete("end-1c linestart", "end-1c")
                self._last_was_cr = False

            if text.endswith("\r"):
                self._last_was_cr = True
                text = text[:-1]

            if text:
                pattern = re.compile(
                    r"(\b\d{1,3}(?:\.\d{1,3}){3}\b)|(\b(?:error|failed|denied|fallo|denegado|acceso denegado)\b)|(\b(?:success|exitoso|completado|100%|correcto)\b)|([A-Za-z]:\\[^\s]*)",
                    re.IGNORECASE,
                )
                last_end = 0
                for match in pattern.finditer(text):
                    start, end = match.span()
                    if start > last_end:
                        tk_txt.insert("end", text[last_end:start])
                    matched_text = match.group(0)
                    if match.group(1):
                        tk_txt.insert("end", matched_text, "ip")
                    elif match.group(2):
                        tk_txt.insert("end", matched_text, "error")
                    elif match.group(3):
                        tk_txt.insert("end", matched_text, "success")
                    elif match.group(4):
                        tk_txt.insert("end", matched_text, "path")
                    last_end = end

                if last_end < len(text):
                    tk_txt.insert("end", text[last_end:])
                tk_txt.see("end")

                pct = self.extract_progress_from_text(text)
                if pct is not None and hasattr(self, "progressbar"):
                    self._set_determinate_progress(pct)

            tk_txt.configure(state="disabled")

        self.after(0, _append)

    def clear_output(self):
        tk_txt = self.output_textbox.text
        tk_txt.configure(state="normal")
        tk_txt.delete("1.0", "end")
        tk_txt.configure(state="disabled")

    def get_html_template(self, content, title="Reporte de Ejecución", command="Desconocido", category=""):
        from functions.report_generator import generate_html_report
        return generate_html_report(
            content=content,
            title=title,
            command=command,
            category=category or (self.cat_var.get() if hasattr(self, "cat_var") else ""),
        )

    def show_plugins(self):
        from functions.setup_manager import PLUGINS, PluginInstaller, is_plugin_installed

        win = tb.Toplevel(self)
        win.title("Gestor de Complementos")
        win.geometry("600x480")
        win.transient(self)
        win.grab_set()
        ui_theme.apply_window_chrome(win, self.current_theme)

        win.update_idletasks()
        x = int(self.winfo_x() + (self.winfo_width() / 2) - 300)
        y = int(self.winfo_y() + (self.winfo_height() / 2) - 240)
        win.geometry(f"+{x}+{y}")

        tb.Label(win, text="Complementos Disponibles", font=("Segoe UI", 14, "bold"), bootstyle="primary").pack(pady=12)

        self.backup_vars = {}
        frame = ScrolledFrame(win, auto_hide=True, padding=6)
        frame.pack(fill="both", expand=True, padx=16, pady=(0, 10))

        for pid, p in PLUGINS.items():
            path = get_user_data_path(os.path.join("tools", p["filename"]))
            is_installed = is_plugin_installed(p)

            row = tb.Labelframe(frame, text=f"{p['name']} ({p['size_str']})", padding=10, bootstyle="success" if is_installed else "secondary")
            row.pack(fill="x", padx=4, pady=6)

            tb.Label(row, text=p["desc"], bootstyle="secondary", wraplength=480, justify="left").pack(anchor="w")
            tb.Label(
                row,
                text="Estado: Instalado" if is_installed else "Estado: No Instalado",
                bootstyle="success" if is_installed else "warning",
                font=("Segoe UI", 9, "bold"),
            ).pack(anchor="w", pady=(4, 8))

            btn_frame = tb.Frame(row)
            btn_frame.pack(fill="x")

            def open_folder(fpath=path):
                tools_dir = os.path.dirname(fpath)
                os.makedirs(tools_dir, exist_ok=True)
                subprocess.Popen(f'explorer "{tools_dir}"', creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

            def delete_plugin(fpath=path):
                try:
                    os.remove(fpath)
                    messagebox.showinfo("Éxito", "Complemento eliminado. El programa se reiniciará.", parent=win)
                    win.destroy()
                    self.quit()
                    if getattr(sys, "frozen", False):
                        ctypes.windll.shell32.ShellExecuteW(None, "open", sys.executable, "", None, 1)
                    else:
                        ctypes.windll.shell32.ShellExecuteW(None, "open", sys.executable, f'"{os.path.abspath(sys.argv[0])}"', None, 1)
                    os._exit(0)
                except Exception as e:
                    messagebox.showerror("Error", f"No se pudo eliminar: {e}", parent=win)

            def install_plugin(plug_id=pid):
                def on_done(success):
                    if success:
                        win.destroy()
                        self.show_plugins()
                        self.on_category_change(self.cat_var.get())
                PluginInstaller(win, plug_id, on_done)

            if is_installed:
                tb.Button(btn_frame, text="Abrir Ubicación", bootstyle="info-outline", command=open_folder).pack(side="left", padx=(0, 6))
                tb.Button(btn_frame, text="Eliminar", bootstyle="danger", command=delete_plugin).pack(side="left", padx=(0, 6))
                if pid == "ai_vault":
                    def open_ai_config():
                        from functions.interpreter_addon import ConfigAPIWindow
                        ConfigAPIWindow(self)
                    tb.Button(btn_frame, text="Configurar Bóveda IA", bootstyle="primary", command=open_ai_config).pack(side="left", padx=(0, 6))

                self.backup_vars[pid] = tk.IntVar(value=0)
                tb.Checkbutton(btn_frame, text="Respaldar", variable=self.backup_vars[pid], bootstyle="primary").pack(side="right")
            else:
                tb.Button(btn_frame, text="Instalar", bootstyle="warning", command=install_plugin).pack(side="left")

        def export_plugins():
            to_export = [pid for pid, var in self.backup_vars.items() if var.get() == 1]
            if not to_export:
                messagebox.showwarning("Aviso", "Selecciona al menos un complemento instalado para respaldar.", parent=win)
                return
            zip_path = filedialog.asksaveasfilename(parent=win, defaultextension=".zip", filetypes=[("Archivos ZIP", "*.zip")], title="Respaldar Complementos")
            if zip_path:
                try:
                    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                        for pid in to_export:
                            filename = PLUGINS[pid]["filename"]
                            filepath = get_user_data_path(os.path.join("tools", filename))
                            if os.path.exists(filepath):
                                zipf.write(filepath, arcname=filename)
                    messagebox.showinfo("Éxito", f"Complementos respaldados en:\n{zip_path}", parent=win)
                except Exception as e:
                    messagebox.showerror("Error", f"Fallo al respaldar: {e}", parent=win)

        def import_plugins():
            zip_path = filedialog.askopenfilename(parent=win, filetypes=[("Archivos ZIP", "*.zip")], title="Importar Complementos")
            if zip_path:
                try:
                    with zipfile.ZipFile(zip_path, "r") as zipf:
                        tools_dir = get_user_data_path("tools")
                        os.makedirs(tools_dir, exist_ok=True)
                        for filename in zipf.namelist():
                            if ".." in filename or filename.startswith("/"):
                                continue
                            zipf.extract(filename, path=tools_dir)
                    messagebox.showinfo("Éxito", "Complementos importados correctamente. El gestor se recargará.", parent=win)
                    win.destroy()
                    self.show_plugins()
                except Exception as e:
                    messagebox.showerror("Error", f"Fallo al importar: {e}", parent=win)

        btn_action_frame = tb.Frame(win)
        btn_action_frame.pack(fill="x", padx=16, pady=(0, 14))
        tb.Button(btn_action_frame, text="Exportar ZIP", bootstyle="info", command=export_plugins).pack(side="left", expand=True, fill="x", padx=(0, 6))
        tb.Button(btn_action_frame, text="Importar ZIP", bootstyle="success", command=import_plugins).pack(side="right", expand=True, fill="x", padx=(6, 0))
        ui_theme.bring_to_front(win)

    def show_table_view(self):
        content = self.output_textbox.text.get("1.0", "end-1c").strip()
        if not content:
            messagebox.showinfo("Información", "No hay resultados para mostrar en la tabla.", parent=self)
            return
        lines = content.split("\n")
        clean_lines = [l for l in lines if not l.startswith("---")]
        from functions.tabular_viewer import show_tabular_data
        show_tabular_data(self, self.cmd_var.get(), "\n".join(clean_lines))

    def export_output(self):
        content = self.output_textbox.text.get("1.0", "end-1c")
        if not content.strip():
            return

        ans = messagebox.askyesnocancel(
            "Tipo de Exportación",
            "¿Deseas exportar TODO el historial de la consola?\n\n"
            "• SÍ: Exporta toda la salida (útil para ver procesos detalle a detalle).\n"
            "• NO: Exporta SOLO el resumen final (recomendado para no sobrecargar archivos HTML).\n"
            "• CANCELAR: Aborta la exportación.",
            parent=self,
        )
        if ans is None:
            return

        if not ans:
            lines = content.split("\n")
            summary_start = 0
            for i in range(len(lines) - 1, -1, -1):
                if "ARCHIVOS COMPLETADOS" in lines[i] or "ARCHIVOS CON ERRORES" in lines[i] or "RESUMEN DE" in lines[i]:
                    for j in range(i, max(-1, i - 5), -1):
                        if "===" in lines[j]:
                            summary_start = j
                            break
                    else:
                        summary_start = max(0, i - 2)
                    break

            if summary_start > 0:
                content = "\n... (Salida larga de proceso omitida) ...\n\n" + "\n".join(lines[summary_start:])
            elif len(lines) > 300:
                content = "\n... (Salida larga omitida, marcador de resumen no detectado) ...\n\n" + "\n".join(lines[-300:])

        file_path = filedialog.asksaveasfilename(
            parent=self,
            defaultextension=".html",
            filetypes=[("HTML Interactivo", "*.html"), ("Text file", "*.txt")],
            title="Exportar Consola a Plantilla",
        )
        if file_path:
            with open(file_path, "w", encoding="utf-8") as f:
                if file_path.endswith(".html"):
                    cmd = self.cmd_var.get()
                    f.write(self.get_html_template(content, title=cmd, command=self.preview_var.get() or cmd))
                else:
                    f.write(content)
            self.output_textbox.text.configure(state="normal")
            self.output_textbox.text.insert("end", f"\n[!] Reporte Exportado con Plantilla a: {file_path}\n", "success")
            self.output_textbox.text.see("end")
            self.output_textbox.text.configure(state="disabled")

    def run_interpreter(self):
        text_content = self.output_textbox.text.get("1.0", "end")
        from functions.interpreter_addon import InterpreterApp
        InterpreterApp(self, initial_text=text_content)

    def show_credits(self):
        credits_win = tb.Toplevel(self)
        credits_win.title("Acerca de GUI CMD ADVANCE")
        center_window(credits_win, 420, 420)
        credits_win.resizable(False, False)
        credits_win.transient(self)
        credits_win.grab_set()
        ui_theme.apply_window_chrome(credits_win, self.current_theme)

        tb.Label(credits_win, text="GUI CMD ADVANCE", font=("Segoe UI", 18, "bold"), bootstyle="warning").pack(pady=(22, 4))
        tb.Label(credits_win, text=f"Versión {__version__}", font=("Segoe UI", 10), bootstyle="secondary").pack(pady=(0, 14))

        desc = (
            "Herramienta gráfica avanzada para comandos de sistema.\n"
            "Diseñada para simplificar y optimizar tareas de\n"
            "mantenimiento, red y gestión de archivos en Windows."
        )
        tb.Label(credits_win, text=desc, font=("Segoe UI", 10), justify="center").pack(pady=10, padx=16)

        tb.Label(credits_win, text="Desarrollador: GOLDEN FENIX", font=("Segoe UI", 11, "bold")).pack(pady=(12, 4))
        tb.Label(credits_win, text="© 2026 GoldenFenix. Todos los derechos reservados.", font=("Segoe UI", 9), bootstyle="secondary").pack(pady=4)

        tb.Button(
            credits_win,
            text="Ver Repositorio en GitHub",
            bootstyle="info-outline",
            command=lambda: webbrowser.open("https://github.com/GoldenFenix92/gui-cmd-advance"),
        ).pack(pady=16)

        tb.Button(credits_win, text="Cerrar", bootstyle="secondary", command=credits_win.destroy, width=14).pack(pady=(4, 16))
        ui_theme.bring_to_front(credits_win)

    def open_process_manager(self):
        try:
            env = os.environ.copy()
            if getattr(sys, "frozen", False):
                cmd = [sys.executable, "--run-process-manager"]
                env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
                env.pop("_MEIPASS2", None)
            else:
                cmd = [sys.executable, os.path.abspath(sys.argv[0]), "--run-process-manager"]
            subprocess.Popen(cmd, env=env, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir el Gestor de Procesos:\n{e}", parent=self)

    def optimize_ram(self):
        vbs_path = None
        try:
            gc.collect()
            vbs_path = get_user_data_path("liberar_ram.vbs")
            with open(vbs_path, "w", encoding="utf-8") as f:
                f.write("FreeMem=Space(100000000)")
            subprocess.run(["cscript", "//nologo", vbs_path], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            messagebox.showinfo("RAM Optimizada", "Memoria inactiva liberada y procesos de fondo limpios correctamente.", parent=self)
        except Exception as e:
            messagebox.showerror("Error", f"Ocurrió un error al intentar optimizar la RAM:\n{e}", parent=self)
        finally:
            if vbs_path and os.path.exists(vbs_path):
                try:
                    os.remove(vbs_path)
                except Exception:
                    pass
