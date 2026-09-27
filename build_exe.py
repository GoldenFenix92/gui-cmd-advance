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

def prompt(text, default=""):
    val = input(f"{text} [{default}]: ").strip()
    return val if val else default

def main():
    print("="*60)
    print("  ASISTENTE DE COMPILACIÓN (.EXE) CON COPYRIGHT Y METADATOS")
    print("="*60)
    print("Este asistente te guiará para crear tu archivo .exe con información")
    print("de copyright, lo cual ayuda a evitar falsos positivos en el")
    print("SmartScreen de Windows y antivirus.\\n")

    # 1. Ask for metadata
    company = prompt("Nombre de la empresa o creador", "Mi Empresa")
    name = prompt("Nombre del programa", "GUI_CMD_Advance")
    description = prompt("Descripción corta", "Herramienta avanzada de comandos")
    copyright_txt = prompt("Texto de Copyright", "© 2026 Todos los derechos reservados")
    version = prompt("Versión del programa (formato X.X.X.X)", "1.0.0.0")

    # Parse version
    v_parts = version.split(".")
    while len(v_parts) < 4:
        v_parts.append("0")
    try:
        v1, v2, v3, v4 = [int(x) for x in v_parts[:4]]
    except:
        print("Formato de versión inválido. Usando 1.0.0.0")
        v1, v2, v3, v4 = 1, 0, 0, 0

    # 2. Write version info file
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
    
    print(f"\\n[+] Archivo '{version_file}' generado con éxito.")

    # 3. Check for pyinstaller
    try:
        import PyInstaller
    except ImportError:
        print("\\nPyInstaller no está instalado. Instalándolo ahora...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
        
    icon = prompt("Ruta del icono (.ico) (Deja en blanco si no tienes)", "")
    
    # 4. Build command for PyInstaller
    print("\\nGenerando el ejecutable principal...")
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onedir",          
        "--windowed",        
        "--version-file", version_file,
        "--name", name,
        "--add-data", f"commands_config.json;.",
        "--add-data", f"github_theme.json;.",
        "--add-data", f"custom_github_theme.json;.",
        "--add-data", f"ffmpeg.exe;.",
        "main.py"
    ]
    
    if icon and os.path.exists(icon):
        cmd.extend(["--icon", icon])
        
    print(f"Ejecutando: {' '.join(cmd)}\\n")
    subprocess.run(cmd)
    
    print("\\n" + "="*60)
    print("  COMPILACIÓN COMPLETADA")
    print("="*60)
    print(f"Tu programa compilado está en la carpeta 'dist/{name}'")
    print("Recuerda que para que los scripts adicionales (compressor.py, duplicate_finder.py) funcionen")
    print("debes colocarlos junto al main.exe, o compilarlos como ejecutables separados.")

if __name__ == "__main__":
    main()
