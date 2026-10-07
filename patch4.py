import json
import os

config_path = r"f:\Proyectos\gui-cmd-advance\resources\commands_config.json"

with open(config_path, "r", encoding="utf-8") as f:
    data = json.load(f)

# Restore vault and update passwords
has_vault = False
for cat in data["categories"]:
    for cmd in cat.get("commands", []):
        if cmd.get("name") == "Credenciales de Red (Bóveda)":
            has_vault = True
            
        if "7-Zip" in cmd.get("name", ""):
            if "Comprimir" in cmd.get("name", ""):
                for arg in cmd.get("args", []):
                    if arg.get("flag") == "--pwd":
                        arg["type"] = "password_double"
            else:
                for arg in cmd.get("args", []):
                    if arg.get("flag") == "--pwd":
                        arg["type"] = "password_single"

if not has_vault:
    # Add vault back to Seguridad y Privacidad
    for cat in data["categories"]:
        if cat["name"] == "Seguridad y Privacidad":
            cat["commands"].insert(0, {
                "name": "Credenciales de Red (Bóveda)",
                "description": "Lista las credenciales guardadas en Windows con una explicación detallada.",
                "command": "__INTERNAL__ --run-vault",
                "args": []
            })
            break

with open(config_path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=4, ensure_ascii=False)

print("commands_config.json patched.")

# Patch gui_app.py
gui_path = r"f:\Proyectos\gui-cmd-advance\gui_app.py"
with open(gui_path, "r", encoding="utf-8") as f:
    gui_code = f.read()

# 1. Fix password eye button styling
old_btn_s = 'btn_show_s = ctk.CTkButton(row_frame, text="👁️", width=30)'
new_btn_s = 'btn_show_s = ctk.CTkButton(row_frame, text="👁️", width=30, fg_color="transparent", text_color=("black", "white"), hover_color=("#E5E5E5", "#333333"))'
gui_code = gui_code.replace(old_btn_s, new_btn_s)

old_btn_d = 'btn_show = ctk.CTkButton(pw_frame, text="👁️", width=30)'
new_btn_d = 'btn_show = ctk.CTkButton(pw_frame, text="👁️", width=30, fg_color="transparent", text_color=("black", "white"), hover_color=("#E5E5E5", "#333333"))'
gui_code = gui_code.replace(old_btn_d, new_btn_d)

# 2. Fix Powershell Quoting
old_quote = '''                    if any(c in val for c in [" ", ",", ";", "&", "|", "(", ")", "'"]) and not val.startswith('"'):
                        val = f'"{val}"'
                    if arg_data["flag"]:'''
new_quote = '''                    if any(c in val for c in [" ", ",", ";", "&", "|", "(", ")", "'"]) and not val.startswith('"'):
                        if "powershell" in command_list[0].lower():
                            val = f"'\\"{val}\\"'"
                        else:
                            val = f'"{val}"'
                    if arg_data["flag"]:'''
gui_code = gui_code.replace(old_quote, new_quote)

# 3. Fix Plugins window AI config / Vault config
old_plugins_top = '''        def open_ai_config():
            from functions.interpreter_addon import ConfigAPIWindow
            ConfigAPIWindow(self)

        btn_ai_config = ctk.CTkButton(win, text="⚙️ Configurar Bóveda IA", fg_color="#8E44AD", hover_color="#9B59B6", command=open_ai_config)
        btn_ai_config.pack(pady=(0, 10))
        
        def open_vault():
            subprocess.Popen([sys.executable, sys.argv[0], "--run-vault"])

        btn_vault = ctk.CTkButton(win, text="🔐 Acceder al Baúl de Credenciales", fg_color="#F39C12", hover_color="#D68910", command=open_vault)
        btn_vault.pack(pady=(0, 15))'''
gui_code = gui_code.replace(old_plugins_top, "")

old_plugin_btn_del = '''                btn_del = ctk.CTkButton(btn_frame, text="Eliminar", width=80, fg_color="#E74C3C", hover_color="#C0392B", command=delete_plugin)
                btn_del.pack(side="left")'''
new_plugin_btn_del = '''                btn_del = ctk.CTkButton(btn_frame, text="Eliminar", width=80, fg_color="#E74C3C", hover_color="#C0392B", command=delete_plugin)
                btn_del.pack(side="left")
                
                if pid == "ai_interpreter":
                    def open_ai_config():
                        from functions.interpreter_addon import ConfigAPIWindow
                        ConfigAPIWindow(self)
                    btn_ai = ctk.CTkButton(btn_frame, text="⚙️ Configurar Bóveda IA", width=120, fg_color="#8E44AD", hover_color="#9B59B6", command=open_ai_config)
                    btn_ai.pack(side="left", padx=(10, 0))'''
gui_code = gui_code.replace(old_plugin_btn_del, new_plugin_btn_del)

with open(gui_path, "w", encoding="utf-8") as f:
    f.write(gui_code)

print("gui_app.py patched.")
