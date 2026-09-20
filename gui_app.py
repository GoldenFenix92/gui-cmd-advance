import json
import re
import customtkinter as ctk
import cmd_executor
import os
from tkinter import filedialog
from tkinter import messagebox

try:
    ctk.set_default_color_theme("custom_github_theme.json")
except Exception as e:
    print(f"No se pudo cargar el tema, usando blue: {e}")
    ctk.set_default_color_theme("blue")

ctk.set_appearance_mode("Dark")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("CMD GUI Advance")
        self.geometry("1000x650")

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)

        self.commands_config = self.load_config()
        self.is_running = False

        # ---------- FRAME IZQUIERDO: Panel de Control ----------
        self.left_frame = ctk.CTkFrame(self)
        self.left_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        self.left_frame.grid_rowconfigure(5, weight=1)
        self.left_frame.grid_columnconfigure(0, weight=1)

        self.theme_switch = ctk.CTkSwitch(self.left_frame, text="Modo Oscuro", command=self.toggle_theme)
        self.theme_switch.grid(row=0, column=0, padx=15, pady=15, sticky="nw")
        self.theme_switch.select()

        self.lbl_cat = ctk.CTkLabel(self.left_frame, text="Categoría:", font=("Arial", 12, "bold"))
        self.lbl_cat.grid(row=1, column=0, padx=15, pady=(5, 0), sticky="w")

        categories = [cat.get("name", "Unknown") for cat in self.commands_config.get("categories", [])]
        self.cat_var = ctk.StringVar(value=categories[0] if categories else "")
        self.cat_menu = ctk.CTkOptionMenu(self.left_frame, values=categories, variable=self.cat_var, command=self.on_category_change)
        self.cat_menu.grid(row=2, column=0, padx=15, pady=5, sticky="ew")

        # Frame Comando (Label + Info + Help)
        self.cmd_label_frame = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        self.cmd_label_frame.grid(row=3, column=0, padx=15, pady=(10, 0), sticky="ew")
        
        self.lbl_cmd = ctk.CTkLabel(self.cmd_label_frame, text="Comando:", font=("Arial", 12, "bold"))
        self.lbl_cmd.pack(side="left")

        # Info button
        self.cmd_info_btn = ctk.CTkButton(self.cmd_label_frame, text="ℹ", width=25, height=25, command=self.show_command_info)
        self.cmd_info_btn.pack(side="right", padx=(5, 0))

        # Help button
        self.cmd_help_btn = ctk.CTkButton(self.cmd_label_frame, text="❔", width=25, height=25, command=self.run_help)
        self.cmd_help_btn.pack(side="right")

        self.cmd_var = ctk.StringVar(value="")
        self.cmd_menu = ctk.CTkOptionMenu(self.left_frame, variable=self.cmd_var, command=self.on_command_change)
        self.cmd_menu.grid(row=4, column=0, padx=15, pady=5, sticky="ew")

        self.args_frame = ctk.CTkScrollableFrame(self.left_frame, fg_color="transparent")
        self.args_frame.grid(row=5, column=0, padx=10, pady=10, sticky="nsew")
        
        self.current_args_vars = {}

        self.btn_frame = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        self.btn_frame.grid(row=6, column=0, padx=15, pady=15, sticky="ew")

        self.execute_btn = ctk.CTkButton(self.btn_frame, text="Ejecutar Comando", command=self.toggle_execution)
        self.execute_btn.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        self.fav_btn = ctk.CTkButton(self.btn_frame, text="⭐", width=40, font=("Segoe UI Emoji", 15), anchor="center", command=self.save_favorite, fg_color="#F39C12", hover_color="#D68910")
        self.fav_btn.pack(side="right")

        # ---------- FRAME DERECHO: Consola y Exportar ----------
        self.right_frame = ctk.CTkFrame(self)
        self.right_frame.grid(row=0, column=1, padx=(0, 10), pady=10, sticky="nsew")
        self.right_frame.grid_rowconfigure(1, weight=1)
        self.right_frame.grid_columnconfigure(0, weight=1)
        self.right_frame.grid_columnconfigure(1, weight=0)

        # Preview de comando en vivo
        self.preview_var = ctk.StringVar(value="")
        self.preview_entry = ctk.CTkEntry(self.right_frame, textvariable=self.preview_var, state="disabled", font=("Consolas", 14, "bold"), text_color="#3B8ED0")
        self.preview_entry.grid(row=0, column=0, columnspan=2, padx=10, pady=(10, 0), sticky="ew")

        # Consola
        self.output_textbox = ctk.CTkTextbox(self.right_frame, font=("Consolas", 13), wrap="none")
        self.output_textbox.grid(row=1, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")
        self.output_textbox.configure(state="disabled")

        self.progressbar = ctk.CTkProgressBar(self.right_frame)
        self.progressbar.grid(row=2, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="ew")
        self.progressbar.set(0)

        # Export Button
        self.export_btn = ctk.CTkButton(self.right_frame, text="Exportar", width=100, command=self.export_output)
        self.export_btn.grid(row=3, column=0, padx=10, pady=(0, 5), sticky="sw")
        
        # Dashboard (Status Bar)
        self.status_bar = ctk.CTkFrame(self.right_frame, height=25, fg_color="transparent")
        self.status_bar.grid(row=4, column=0, columnspan=2, sticky="ew")
        self.lbl_status = ctk.CTkLabel(self.status_bar, text="Iniciando sistema...", font=("Consolas", 12, "bold"), text_color="#A9A9A9")
        self.lbl_status.pack(side="right", padx=10)
        
        # Configurar tags de sintaxis
        self.output_textbox.tag_config("error", foreground="#FF4C4C")
        self.output_textbox.tag_config("success", foreground="#4CFF4C")
        self.output_textbox.tag_config("ip", foreground="#42A5F5")
        self.output_textbox.tag_config("path", foreground="#FFCA28")
        self.output_textbox.tag_config("highlight", foreground="#FF4081")

        self.update_status_dashboard()

        self.clear_btn = ctk.CTkButton(self.right_frame, text="Limpiar", width=100, fg_color="transparent", border_width=1, text_color=("#24292F", "#C9D1D9"), command=self.clear_output)
        self.clear_btn.grid(row=3, column=1, padx=10, pady=(0, 10), sticky="se")

        self.on_category_change(self.cat_var.get())

    def load_config(self):
        config = {"categories": []}
        try:
            with open("commands_config.json", "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception as e:
            pass
            
        try:
            with open("favorites.json", "r", encoding="utf-8") as f:
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
            self.lbl_status.configure(text=f"💻 CPU: {cpu}%   |   🧠 RAM: {ram}%")
        except:
            self.lbl_status.configure(text="💻 CPU: --%   |   🧠 RAM: --%")
        self.after(2000, self.update_status_dashboard)

    def get_windows_drives(self):
        import subprocess
        drives = []
        try:
            output = subprocess.check_output(
                ["powershell", "-Command", "Get-CimInstance Win32_LogicalDisk | Where-Object DriveType -eq 3 | ForEach-Object { $_.DeviceID + ' (' + $_.VolumeName + ')' }"],
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

    def toggle_theme(self):
        if self.theme_switch.get() == 1:
            ctk.set_appearance_mode("Dark")
            self.theme_switch.configure(text="Modo Oscuro")
        else:
            ctk.set_appearance_mode("Light")
            self.theme_switch.configure(text="Modo Claro")

    def get_category_data(self, cat_name):
        for cat in self.commands_config.get("categories", []):
            if cat.get("name") == cat_name:
                return cat
        return None

    def get_command_data(self, cmd_name):
        cat_data = self.get_category_data(self.cat_var.get())
        if cat_data:
            for cmd in cat_data.get("commands", []):
                if cmd.get("name") == cmd_name:
                    return cmd
        return None

    def show_command_info(self):
        cmd_data = self.get_command_data(self.cmd_var.get())
        if cmd_data:
            messagebox.showinfo(f"Info: {cmd_data.get('name')}", cmd_data.get("description", ""))

    def show_arg_info(self, arg_name, arg_desc):
        messagebox.showinfo(f"Info: {arg_name}", arg_desc)

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

        cmd_data = self.get_command_data(selected_command)
        if cmd_data:
            args = cmd_data.get("args", [])
            for arg in args:
                arg_name = arg.get("name")
                arg_type = arg.get("type")
                arg_flag = arg.get("flag", "")
                arg_desc = arg.get("description", "")
                
                row_frame = ctk.CTkFrame(self.args_frame, fg_color="transparent")
                row_frame.pack(fill="x", pady=4)
                
                var = ctk.StringVar(value=arg.get("value", ""))
                var.trace_add("write", lambda *args: self.update_preview())
                
                if arg_type == "checkbox":
                    chk = ctk.CTkCheckBox(row_frame, text=arg_name, variable=var, onvalue=arg_flag, offvalue="")
                    chk.pack(side="left", padx=(0, 10))
                elif arg_type in ["entry", "directory_entry", "file_entry"]:
                    lbl = ctk.CTkLabel(row_frame, text=f"{arg_name}:")
                    lbl.pack(side="left", padx=(0, 5))
                    ent = ctk.CTkEntry(row_frame, textvariable=var, placeholder_text="Escribir...")
                    ent.pack(side="left", fill="x", expand=True, padx=(0, 10))
                    
                    if arg_type == "directory_entry":
                        def browse_folder(v=var):
                            folder = filedialog.askdirectory()
                            if folder:
                                folder = folder.replace("/", "\\")
                                if " " in folder and not folder.startswith('"'):
                                    folder = f'"{folder}"'
                                v.set(folder)
                        btn_browse = ctk.CTkButton(row_frame, text="Examinar", width=80, command=browse_folder)
                        btn_browse.pack(side="left", padx=(0, 10))
                        
                    elif arg_type == "file_entry":
                        def browse_file(v=var):
                            file_path = filedialog.askopenfilename()
                            if file_path:
                                file_path = file_path.replace("/", "\\")
                                if " " in file_path and not file_path.startswith('"'):
                                    file_path = f'"{file_path}"'
                                v.set(file_path)
                        btn_browse_f = ctk.CTkButton(row_frame, text="Examinar", width=80, command=browse_file)
                        btn_browse_f.pack(side="left", padx=(0, 10))
                        
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
                
                self.current_args_vars[arg_name] = {"var": var, "type": arg_type, "flag": arg_flag}
                
                btn_info = ctk.CTkButton(
                    row_frame, text="ℹ", width=25, height=25, fg_color="transparent", border_width=1,
                    text_color=("black", "white"), command=lambda n=arg_name, d=arg_desc: self.show_arg_info(n, d)
                )
                btn_info.pack(side="right")
        
        self.update_preview()

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
                    command_list.append(val)
                elif arg_data["type"] in ["entry", "directory_entry", "file_entry"]:
                    if arg_data["type"] in ["directory_entry", "file_entry"]:
                        val = val.replace("/", "\\")
                    if " " in val and not val.startswith('"'):
                        val = f'"{val}"'
                    if arg_data["flag"]:
                        command_list.append(arg_data["flag"])
                    command_list.append(val)
                elif arg_data["type"] in ["drive_dropdown", "disk_dropdown"]:
                    drive = val.split(" ")[0]
                    if arg_data["flag"]:
                        command_list.append(arg_data["flag"])
                    command_list.append(drive)
        
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
            self.run_command()

    def remove_favorite(self):
        cmd_name = self.cmd_var.get()
        favs = []
        try:
            if os.path.exists("favorites.json"):
                with open("favorites.json", "r", encoding="utf-8") as f:
                    favs = json.load(f)
        except:
            return
            
        new_favs = [f for f in favs if f.get("name") != cmd_name]
        
        with open("favorites.json", "w", encoding="utf-8") as f:
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
            if os.path.exists("favorites.json"):
                with open("favorites.json", "r", encoding="utf-8") as f:
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
        with open("favorites.json", "w", encoding="utf-8") as f:
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
        if hasattr(self, 'progressbar'):
            self.progressbar.set(0)
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
                
                match = re.search(r'(\d+)%', text)
                if match and hasattr(self, 'progressbar'):
                    try:
                        self.progressbar.set(int(match.group(1)) / 100.0)
                    except:
                        pass
                        
            self.output_textbox.configure(state="disabled")
        self.after(0, _append)

    def clear_output(self):
        self.output_textbox.configure(state="normal")
        self.output_textbox.delete("1.0", "end")
        self.output_textbox.configure(state="disabled")

    def export_output(self):
        content = self.output_textbox.get("1.0", "end-1c")
        if not content.strip(): return
        file_path = filedialog.asksaveasfilename(defaultextension=".html", filetypes=[("HTML Report", "*.html"), ("Text file", "*.txt")], title="Exportar Consola")
        if file_path:
            with open(file_path, "w", encoding="utf-8") as f:
                if file_path.endswith(".html"):
                    import datetime
                    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Reporte de Ejecución - CMD GUI Advance</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #1e1e1e; color: #d4d4d4; padding: 20px; }}
        .header {{ border-bottom: 2px solid #007acc; padding-bottom: 10px; margin-bottom: 20px; }}
        .console {{ background-color: #000000; padding: 15px; border-radius: 8px; font-family: Consolas, monospace; white-space: pre-wrap; overflow-x: auto; color: #00ff00; }}
        h1 {{ margin: 0; color: #ffffff; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📋 Reporte de Ejecución</h1>
        <p><strong>Fecha:</strong> {timestamp}</p>
    </div>
    <div class="console">{content}</div>
</body>
</html>"""
                    f.write(html_content)
                else:
                    f.write(content)
            self.output_textbox.configure(state="normal")
            self.output_textbox.insert("end", f"\n[!] Exportado a: {file_path}\n", "success")
            self.output_textbox.see("end")
            self.output_textbox.configure(state="disabled")
