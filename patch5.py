import os

# 1. Fix credentials_vault_cli.py
cli_path = r"f:\Proyectos\gui-cmd-advance\functions\credentials_vault_cli.py"
with open(cli_path, "r", encoding="utf-8") as f:
    cli_code = f.read()

cli_code = cli_code.replace("🔐", "*").replace("💡", "->")

with open(cli_path, "w", encoding="utf-8") as f:
    f.write(cli_code)

# 2. Fix gui_app.py
gui_path = r"f:\Proyectos\gui-cmd-advance\gui_app.py"
with open(gui_path, "r", encoding="utf-8") as f:
    gui_code = f.read()

old_check_match = '''                    def check_match(*args_cb):
                        v1 = var1.get()
                        v2 = var2.get()
                        if v1 != v2 or not v1:
                            ent2.configure(border_color="red", border_width=2)
                            var.set("")
                        else:
                            ent2.configure(border_color="green", border_width=2)
                            var.set(v1)'''

new_check_match = '''                    def check_match(*args_cb, v=var, e2=ent2, v1_var=var1, v2_var=var2):
                        v1 = v1_var.get()
                        v2 = v2_var.get()
                        if v1 != v2 or not v1:
                            e2.configure(border_color="red", border_width=2)
                            v.set("")
                        else:
                            e2.configure(border_color="green", border_width=2)
                            v.set(v1)'''
                            
gui_code = gui_code.replace(old_check_match, new_check_match)

gui_code = gui_code.replace('if pid == "ai_interpreter":', 'if pid == "ai_vault":')

with open(gui_path, "w", encoding="utf-8") as f:
    f.write(gui_code)

print("Patch 5 applied.")
