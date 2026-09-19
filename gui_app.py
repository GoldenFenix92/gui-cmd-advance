import json
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
        self.geometry("900x600")

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=3)

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

        self.execute_btn = ctk.CTkButton(self.left_frame, text="Ejecutar Comando", command=self.toggle_execution)
        self.execute_btn.grid(row=6, column=0, padx=15, pady=15, sticky="ew")

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

        self.export_btn = ctk.CTkButton(self.right_frame, text="Exportar", width=100, command=self.export_output)
        self.export_btn.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="sw")

        self.clear_btn = ctk.CTkButton(self.right_frame, text="Limpiar", width=100, fg_color="transparent", border_width=1, text_color=("#24292F", "#C9D1D9"), command=self.clear_output)
        self.clear_btn.grid(row=2, column=1, padx=10, pady=(0, 10), sticky="se")

        self.on_category_change(self.cat_var.get())

    def load_config(self):
        try:
            with open("commands_config.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            return {"categories": []}

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
                
                var = ctk.StringVar(value="")
                var.trace_add("write", lambda *args: self.update_preview())
                
                if arg_type == "checkbox":
                    chk = ctk.CTkCheckBox(row_frame, text=arg_name, variable=var, onvalue=arg_flag, offvalue="")
                    chk.pack(side="left", padx=(0, 10))
                elif arg_type == "entry":
                    lbl = ctk.CTkLabel(row_frame, text=f"{arg_name}:")
                    lbl.pack(side="left", padx=(0, 5))
                    ent = ctk.CTkEntry(row_frame, textvariable=var, placeholder_text="Escribir...")
                    ent.pack(side="left", fill="x", expand=True, padx=(0, 10))
                
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
                if arg_data["type"] == "checkbox":
                    command_list.append(val)
                elif arg_data["type"] == "entry":
                    if arg_data["flag"]:
                        command_list.append(arg_data["flag"])
                    command_list.append(val)
        
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

    def run_command(self):
        if not self.preview_var.get():
            return
        self.execute_external(self.preview_var.get())

    def execute_external(self, command_str):
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
            self.output_textbox.configure(state="normal")
            self.output_textbox.insert("end", text)
            self.output_textbox.see("end")
            self.output_textbox.configure(state="disabled")
        self.after(0, _append)

    def clear_output(self):
        self.output_textbox.configure(state="normal")
        self.output_textbox.delete("1.0", "end")
        self.output_textbox.configure(state="disabled")

    def export_output(self):
        content = self.output_textbox.get("1.0", "end-1c")
        if not content.strip(): return
        file_path = filedialog.asksaveasfilename(defaultextension=".txt", title="Exportar Consola")
        if file_path:
            with open(file_path, "w", encoding="utf-8") as f: f.write(content)
            self.append_output(f"\n[!] Exportado a: {file_path}\n")
