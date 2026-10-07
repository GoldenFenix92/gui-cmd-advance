import json
import os

config_path = r"f:\Proyectos\gui-cmd-advance\resources\commands_config.json"

with open(config_path, "r", encoding="utf-8") as f:
    data = json.load(f)

for cat in data["categories"]:
    for cmd in cat.get("commands", []):
        if cmd.get("name") == "Comprimir Archivos (7-Zip)":
            # Check if volume arg exists
            has_split = any(arg.get("flag") == "--split" for arg in cmd.get("args", []))
            if not has_split:
                cmd["args"].append({
                    "name": "Dividir Archivo por Volúmenes",
                    "flag": "--split",
                    "type": "dropdown",
                    "options": [
                        "Sin dividir",
                        "10m (10 Megabytes)",
                        "50m (50 Megabytes)",
                        "100m (100 Megabytes)",
                        "500m (500 Megabytes)",
                        "1g (1 Gigabyte)",
                        "2g (2 Gigabytes)",
                        "4g (4 Gigabytes - Límite FAT32)"
                    ],
                    "description": "Si deseas dividir el archivo resultante en varias partes más pequeñas."
                })

with open(config_path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=4, ensure_ascii=False)

print("commands_config.json patched for 7-Zip split.")

# Patch main.py
main_path = r"f:\Proyectos\gui-cmd-advance\main.py"
with open(main_path, "r", encoding="utf-8") as f:
    main_code = f.read()

old_args = '''            parser.add_argument("--level", default="")
            parser.add_argument("--threads", default="")
            args, _ = parser.parse_known_args()'''

new_args = '''            parser.add_argument("--level", default="")
            parser.add_argument("--threads", default="")
            parser.add_argument("--split", default="")
            args, _ = parser.parse_known_args()'''
main_code = main_code.replace(old_args, new_args)

old_cmd_build = '''            if args.threads:
                cmd.append(f"-mmt={args.threads}")'''

new_cmd_build = '''            if args.threads:
                cmd.append(f"-mmt={args.threads}")
            if args.split and args.split != "Sin dividir":
                # Extract the value before the space, e.g., '10m' from '10m (10 Megabytes)'
                split_val = args.split.split(" ")[0]
                cmd.append(f"-v{split_val}")'''
main_code = main_code.replace(old_cmd_build, new_cmd_build)

with open(main_path, "w", encoding="utf-8") as f:
    f.write(main_code)

print("main.py patched for 7-Zip split.")
