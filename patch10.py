import os

gui_path = r"f:\Proyectos\gui-cmd-advance\gui_app.py"
with open(gui_path, "r", encoding="utf-8") as f:
    gui_code = f.read()

# 1. Add rendering logic for 'dropdown'
if 'elif arg_type == "dropdown":' not in gui_code:
    old_threads = '''                elif arg_type == "threads_dropdown":
                    lbl = ctk.CTkLabel(row_frame, text=f"{arg_name}:")
                    lbl.pack(side="left", padx=(0, 5))
                    import multiprocessing
                    max_t = multiprocessing.cpu_count()
                    opts = ["0 (Auto - Todos)"] + [str(i) for i in [1, 2, 4, 8, 16, 32, 64] if i <= max_t]
                    if str(max_t) not in opts and max_t > 0:
                        opts.append(str(max_t))
                    dd = ctk.CTkOptionMenu(row_frame, variable=var, values=opts, width=150)
                    dd.pack(side="left", fill="x", expand=True)
                    if not var.get():
                        var.set(opts[0])'''

    new_dropdown = '''                elif arg_type == "dropdown":
                    lbl = ctk.CTkLabel(row_frame, text=f"{arg_name}:")
                    lbl.pack(side="left", padx=(0, 5))
                    opts = arg.get("options", [])
                    dd = ctk.CTkOptionMenu(row_frame, variable=var, values=opts, width=150)
                    dd.pack(side="left", fill="x", expand=True)
                    if opts and not var.get():
                        var.set(opts[0])
                elif arg_type == "threads_dropdown":
                    lbl = ctk.CTkLabel(row_frame, text=f"{arg_name}:")
                    lbl.pack(side="left", padx=(0, 5))
                    import multiprocessing
                    max_t = multiprocessing.cpu_count()
                    opts = ["0 (Auto - Todos)"] + [str(i) for i in [1, 2, 4, 8, 16, 32, 64] if i <= max_t]
                    if str(max_t) not in opts and max_t > 0:
                        opts.append(str(max_t))
                    dd = ctk.CTkOptionMenu(row_frame, variable=var, values=opts, width=150)
                    dd.pack(side="left", fill="x", expand=True)
                    if not var.get():
                        var.set(opts[0])'''
                        
    gui_code = gui_code.replace(old_threads, new_dropdown)

# 2. Add parsing logic for 'dropdown'
if '"dropdown"' not in gui_code.split('elif arg_data["type"] in [')[2]:  # check if dropdown is in the parsing list
    old_parsing = 'elif arg_data["type"] in ["drive_dropdown", "disk_dropdown", "threads_dropdown"]:'
    new_parsing = 'elif arg_data["type"] in ["drive_dropdown", "disk_dropdown", "threads_dropdown", "dropdown"]:'
    gui_code = gui_code.replace(old_parsing, new_parsing)

with open(gui_path, "w", encoding="utf-8") as f:
    f.write(gui_code)

print("gui_app.py patched to support dropdown.")
