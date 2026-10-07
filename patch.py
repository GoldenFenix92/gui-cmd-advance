import json

config_path = r"f:\Proyectos\gui-cmd-advance\resources\commands_config.json"

with open(config_path, "r", encoding="utf-8") as f:
    data = json.load(f)

# 1. Update Temp Cleaner
for cat in data["categories"]:
    for cmd in cat.get("commands", []):
        if cmd.get("name") == "Limpieza Selectiva de Temporales":
            cmd["args"] = [
                {"name": "Temp de Usuario", "type": "checkbox", "flag": "--user-temp", "description": "Limpia la carpeta Temp del usuario actual."},
                {"name": "Temp de Windows", "type": "checkbox", "flag": "--win-temp", "description": "Limpia la carpeta Temp del sistema Windows."},
                {"name": "Prefetch", "type": "checkbox", "flag": "--prefetch", "description": "Limpia los archivos de Prefetch."},
                {"name": "Windows Update (Descargas)", "type": "checkbox", "flag": "--win-update", "description": "Limpia la caché de descargas de Windows Update."}
            ]
        
        # 2. Update passwords
        if cmd.get("name") == "Compresión de Archivos (7-Zip)":
            for arg in cmd.get("args", []):
                if arg.get("flag") == "--pwd":
                    arg["type"] = "password_double"
                    
        if cmd.get("name") == "Descomprimir Archivo (7-Zip)" or cmd.get("name") == "Analizar Integridad (7-Zip)":
            for arg in cmd.get("args", []):
                if arg.get("flag") == "--pwd":
                    arg["type"] = "password_single"
                    
# 3. Remove Vault
for cat in data["categories"]:
    cmds = cat.get("commands", [])
    cat["commands"] = [c for c in cmds if c.get("name") != "Credenciales de Red (Bóveda)"]

with open(config_path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=4, ensure_ascii=False)

print("Patch applied.")
