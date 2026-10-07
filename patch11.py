import os

gui_path = r"f:\Proyectos\gui-cmd-advance\gui_app.py"
with open(gui_path, "r", encoding="utf-8") as f:
    gui_code = f.read()

old_threads = '''                elif arg_type == "threads_dropdown":
                    lbl = ctk.CTkLabel(row_frame, text=f"{arg_name}:")
                    lbl.pack(side="left", padx=(0, 5))
                    threads_options = self.get_cpu_threads_list()
                    if threads_options:
                        var.set(threads_options[0])
                    dropdown = ctk.CTkOptionMenu(row_frame, variable=var, values=threads_options)
                    dropdown.pack(side="left", fill="x", expand=True, padx=(0, 10))'''

new_dropdown = '''                elif arg_type == "dropdown":
                    lbl = ctk.CTkLabel(row_frame, text=f"{arg_name}:")
                    lbl.pack(side="left", padx=(0, 5))
                    opts = arg.get("options", [])
                    dropdown = ctk.CTkOptionMenu(row_frame, variable=var, values=opts)
                    dropdown.pack(side="left", fill="x", expand=True, padx=(0, 10))
                    if opts and not var.get():
                        var.set(opts[0])
                elif arg_type == "threads_dropdown":
                    lbl = ctk.CTkLabel(row_frame, text=f"{arg_name}:")
                    lbl.pack(side="left", padx=(0, 5))
                    threads_options = self.get_cpu_threads_list()
                    if threads_options:
                        var.set(threads_options[0])
                    dropdown = ctk.CTkOptionMenu(row_frame, variable=var, values=threads_options)
                    dropdown.pack(side="left", fill="x", expand=True, padx=(0, 10))'''

gui_code = gui_code.replace(old_threads, new_dropdown)

with open(gui_path, "w", encoding="utf-8") as f:
    f.write(gui_code)

print("gui_app.py rendering patched correctly.")
