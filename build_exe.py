import os
import sys
import subprocess

VERSION_FILE_TEMPLATE = """# UTF-8
#
# For more details about fixed file info 'ffi' see:
# http://msdn.microsoft.com/en-us/library/ms646997.aspx
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({v1}, {v2}, {v3}, {v4}),
    prodvers=({v1}, {v2}, {v3}, {v4}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
    ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        '040904B0',
        [StringStruct('CompanyName', '{company}'),
        StringStruct('FileDescription', '{description}'),
        StringStruct('FileVersion', '{v1}.{v2}.{v3}.{v4}'),
        StringStruct('InternalName', '{name}'),
        StringStruct('LegalCopyright', '{copyright}'),
        StringStruct('OriginalFilename', '{name}.exe'),
        StringStruct('ProductName', '{name}'),
        StringStruct('ProductVersion', '{v1}.{v2}.{v3}.{v4}')])
      ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""

def get_git_commit_count():
    try:
        output = subprocess.check_output(["git", "rev-list", "--count", "HEAD"], stderr=subprocess.STDOUT).decode("utf-8").strip()
        return int(output)
    except Exception:
        return 0

def main():
    print("="*60)
    print("  COMPILACIÓN AUTOMÁTICA (.EXE) - GUI CMD ADVANCE")
    print("="*60)

    # Preguntar si es fase beta
    ans = input("¿Es fase Beta? (S/n): ").strip().lower()
    is_beta = ans != 'n'

    # Variables solicitadas
    company = "GOLDEN FENIX"
    
    # Nombre sin guiones ni guiones bajos
    base_name = "Gui Cmd Advance"
    if is_beta:
        name = f"{base_name} Beta"
    else:
        name = base_name

    description = "Herramienta gráfica avanzada para comandos de sistema"
    copyright_txt = "© 2026 GoldenFenix Todos los derechos reservados."
    icon = "app_icon.ico"
    
    commit_count = get_git_commit_count()
    version_windows = f"1.0.{commit_count}.0"
    
    version_ui = f"1.0.{commit_count}"
    if is_beta:
        version_ui += " Beta"
        
    v1, v2, v3, v4 = 1, 0, commit_count, 0

    print(f"[*] Versión detectada por Git: {version_ui}")
    
    # Escribir version.py para que la GUI lo lea
    with open("version.py", "w", encoding="utf-8") as vf:
        vf.write(f'__version__ = "{version_ui}"\n')
    print("[+] Archivo 'version.py' actualizado.")

    # Escribir metadatos de Windows
    version_content = VERSION_FILE_TEMPLATE.format(
        v1=v1, v2=v2, v3=v3, v4=v4,
        company=company,
        name=name,
        description=description,
        copyright=copyright_txt
    )
    
    version_file = "version_info.txt"
    with open(version_file, "w", encoding="utf-8") as f:
        f.write(version_content)
    
    print(f"[+] Archivo '{version_file}' generado con metadatos de Windows.")

    try:
        import PyInstaller
    except ImportError:
        print("\nPyInstaller no está instalado. Instalándolo ahora...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
        
    print("\nGenerando el ejecutable principal...")
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onefile",          
        "--windowed",        
        "--version-file", version_file,
        "--name", name,
        "--add-data", "commands_config.json;.",
        "--add-data", "github_theme.json;.",
        "--add-data", "custom_github_theme.json;.",
        "--add-data", "ffmpeg.exe;.",
        "--add-data", "app_icon.ico;.",
        "--icon", icon,
        "main.py"
    ]
    
    print(f"Ejecutando: {' '.join(cmd)}\n")
    subprocess.run(cmd)
    
    print("\n" + "="*60)
    print("  COMPILACIÓN COMPLETADA")
    print("="*60)
    print(f"Tu programa compilado está en la carpeta 'dist/{name}'")

if __name__ == "__main__":
    main()
