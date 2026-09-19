import json
import customtkinter as ctk
import cmd_executor
import os
from tkinter import filedialog

# Cargar el tema de GitHub creado
try:
    ctk.set_default_color_theme("custom_github_theme.json")
except Exception as e:
    print(f"No se pudo cargar el tema, usando blue: {e}")
    ctk.set_default_color_theme("blue")

ctk.set_appearance_mode("Dark")  # Inicializar en modo oscuro por defecto como GitHub

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("CMD GUI Advance")
        self.geometry("900x600")

        # Configurar grid layout general para mejor distribución al maximizar
        self.grid_rowconfigure(0, weight=1)
        # Columna 0: Panel de control (peso 1)
        # Columna 1: Consola (peso 2, toma más espacio al estirar)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=3)

        # Cargar configuración de comandos
        self.commands_config = self.load_config()

        # ---------- FRAME IZQUIERDO: Panel de Control ----------
        self.left_frame = ctk.CTkFrame(self)
        self.left_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        # El área de los checkboxes se expandirá
        self.left_frame.grid_rowconfigure(5, weight=1)
        self.left_frame.grid_columnconfigure(0, weight=1)

        # Header: Switch de Tema
        self.theme_switch = ctk.CTkSwitch(self.left_frame, text="Modo Oscuro", command=self.toggle_theme)
        self.theme_switch.grid(row=0, column=0, padx=15, pady=15, sticky="nw")
        self.theme_switch.select() # Porque empezamos en Dark

        # Label Categoría
        self.lbl_cat = ctk.CTkLabel(self.left_frame, text="Categoría:", font=("Arial", 12, "bold"))
        self.lbl_cat.grid(row=1, column=0, padx=15, pady=(5, 0), sticky="w")

        # Dropdown Categorías
        categories = [cat.get("name", "Unknown") for cat in self.commands_config.get("categories", [])]
        self.cat_var = ctk.StringVar(value=categories[0] if categories else "")
        self.cat_menu = ctk.CTkOptionMenu(self.left_frame, values=categories, variable=self.cat_var, command=self.on_category_change)
        self.cat_menu.grid(row=2, column=0, padx=15, pady=5, sticky="ew")

        # Label Comando
        self.lbl_cmd = ctk.CTkLabel(self.left_frame, text="Comando:", font=("Arial", 12, "bold"))
        self.lbl_cmd.grid(row=3, column=0, padx=15, pady=(10, 0), sticky="w")

        # Dropdown Comandos
        self.cmd_var = ctk.StringVar(value="")
        self.cmd_menu = ctk.CTkOptionMenu(self.left_frame, variable=self.cmd_var, command=self.on_command_change)
        self.cmd_menu.grid(row=4, column=0, padx=15, pady=5, sticky="ew")

        # Área para Checkboxes (Argumentos)
        self.args_frame = ctk.CTkScrollableFrame(self.left_frame, fg_color="transparent")
        self.args_frame.grid(row=5, column=0, padx=10, pady=10, sticky="nsew")
        
        # Diccionario para guardar variables de los checkboxes actuales
        self.current_args_vars = {}

        # Botón Ejecutar
        self.execute_btn = ctk.CTkButton(self.left_frame, text="Ejecutar Comando", command=self.run_command)
        self.execute_btn.grid(row=6, column=0, padx=15, pady=15, sticky="ew")

        # ---------- FRAME DERECHO: Consola y Exportar ----------
        self.right_frame = ctk.CTkFrame(self)
        self.right_frame.grid(row=0, column=1, padx=(0, 10), pady=10, sticky="nsew")
        self.right_frame.grid_rowconfigure(0, weight=1)
        self.right_frame.grid_columnconfigure(0, weight=1)
        self.right_frame.grid_columnconfigure(1, weight=0)

        # Consola
        self.output_textbox = ctk.CTkTextbox(self.right_frame, font=("Consolas", 13), wrap="none")
        self.output_textbox.grid(row=0, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")
        self.output_textbox.configure(state="disabled")

        # Botón Exportar
        self.export_btn = ctk.CTkButton(self.right_frame, text="Exportar Resultado", command=self.export_output)
        self.export_btn.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="sw")

        # Botón Limpiar
        self.clear_btn = ctk.CTkButton(self.right_frame, text="Limpiar Consola", fg_color="transparent", border_width=1, command=self.clear_output)
        self.clear_btn.grid(row=1, column=1, padx=10, pady=(0, 10), sticky="se")

        # Inicializar los menús dependientes
        self.on_category_change(self.cat_var.get())

    def load_config(self):
        try:
            with open("commands_config.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
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
        # Limpiar checkboxes anteriores
        for widget in self.args_frame.winfo_children():
            widget.destroy()
        self.current_args_vars.clear()

        cmd_data = self.get_command_data(selected_command)
        if cmd_data:
            # Mostrar descripción del comando
            desc = cmd_data.get("description", "")
            if desc:
                lbl_desc = ctk.CTkLabel(self.args_frame, text=desc, font=("Arial", 11, "italic"), text_color="gray", wraplength=250, justify="left")
                lbl_desc.pack(anchor="w", pady=(0, 10))

            # Generar Checkboxes
            args = cmd_data.get("args", [])
            for arg in args:
                if arg.get("type") == "checkbox":
                    var = ctk.StringVar(value="")
                    chk = ctk.CTkCheckBox(
                        self.args_frame, 
                        text=arg.get("name"), 
                        variable=var, 
                        onvalue=arg.get("flag"), 
                        offvalue=""
                    )
                    chk.pack(anchor="w", pady=4)
                    self.current_args_vars[arg.get("name")] = var
                    
                    # Tooltip/Descripción opcional para el argumento
                    arg_desc = arg.get("description", "")
                    if arg_desc:
                        lbl_arg_desc = ctk.CTkLabel(self.args_frame, text=f"  ↳ {arg_desc}", font=("Arial", 10), text_color="gray")
                        lbl_arg_desc.pack(anchor="w", pady=(0, 6))

    def run_command(self):
        selected_command = self.cmd_var.get()
        if not selected_command:
            return

        cmd_data = self.get_command_data(selected_command)
        if not cmd_data:
            return

        cmd_base = cmd_data.get("command")
        command_list = [cmd_base]
        
        # Añadir argumentos seleccionados
        for arg_name, var in self.current_args_vars.items():
            val = var.get()
            if val:
                command_list.append(val)
        
        full_command_str = " ".join(command_list)
        self.append_output(f"\n> {full_command_str}\n")
        self.execute_btn.configure(state="disabled", text="Ejecutando...")
        
        # Callback cuando termina
        def on_finish():
            self.execute_btn.configure(state="normal", text="Ejecutar Comando")

        # Ejecutar asincrónicamente
        cmd_executor.execute_command_async(
            command_list=full_command_str,
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
        # Obtener el texto actual de la consola
        content = self.output_textbox.get("1.0", "end-1c")
        if not content.strip():
            return # No hay nada que exportar
            
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("Markdown files", "*.md"), ("All files", "*.*")],
            title="Exportar Consola"
        )
        
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
                self.append_output(f"\n[!] Salida exportada a: {file_path}\n")
            except Exception as e:
                self.append_output(f"\n[!] Error al exportar: {e}\n")
