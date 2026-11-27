import argparse
import os
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from functions.versioning import (
    apply_release_channel,
    detect_version_from_git,
    format_git_tag,
    is_prerelease,
    is_valid_canonical_semver,
    read_canonical_version,
    sync_version_files,
    to_windows_version_tuple,
)

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
        StringStruct('ProductVersion', '{product_version}')])
      ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""

HIDDEN_IMPORTS = [
    "PIL",
    "pymupdf",
    "psutil",
    "ttkbootstrap",
    "functions.advanced_search",
    "functions.ai_engine",
    "functions.cmd_executor",
    "functions.combo_engine",
    "functions.compressor",
    "functions.credentials_vault_cli",
    "functions.disk_attributes",
    "functions.drag_drop",
    "functions.duplicate_finder",
    "functions.health_analyzer",
    "functions.interpreter_addon",
    "functions.media_repair",
    "functions.media_studio",
    "functions.name_sanitizer",
    "functions.office_deploy",
    "functions.power_manager",
    "functions.process_manager",
    "functions.ram_auditor",
    "functions.report_generator",
    "functions.sdelete_runner",
    "functions.setup_manager",
    "functions.smart_info",
    "functions.surface_scanner",
    "functions.tabular_viewer",
    "functions.task_memory",
    "functions.telemetry",
    "functions.temp_cleaner",
    "functions.ui_theme",
    "functions.usb_auditor",
    "functions.utils",
    "functions.versioning",
]


def get_git_commit_count():
    try:
        output = subprocess.check_output(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=PROJECT_ROOT,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).decode("utf-8").strip()
        return int(output)
    except Exception:
        return 0


def resolve_build_metadata(version_override=None, commit_count=None, auto_detect=True, is_beta=None):
    """Resuelve toda la metadata de compilación desde VERSION + detección automática de commits Git.

    Si is_beta se especifica (True o False), fuerza el canal a '-beta' o estable sin sufijos .1/.2.
    Garantiza coherencia automática entre versión SemVer, canal Beta/Estable,
    nombre del ejecutable y tupla FileVersion de Windows (MAJOR.MINOR.PATCH.BUILD).
    """
    detection = {
        "base_version": None,
        "detected_version": None,
        "impact": "none",
        "commits_since": 0,
        "auto_bumped": False,
    }
    if version_override is not None:
        canonical = str(version_override).strip()
        if not is_valid_canonical_semver(canonical):
            raise ValueError(f"Versión SemVer inválida: {canonical!r}")
        detection["base_version"] = canonical
        detection["detected_version"] = canonical
    elif auto_detect:
        detection = detect_version_from_git(os.path.join(PROJECT_ROOT, "VERSION"), PROJECT_ROOT)
        canonical = detection["detected_version"]
    else:
        canonical = read_canonical_version(os.path.join(PROJECT_ROOT, "VERSION"))
        detection["base_version"] = canonical
        detection["detected_version"] = canonical

    if is_beta is not None:
        canonical = apply_release_channel(canonical, bool(is_beta))
    elif is_prerelease(canonical):
        # Normalizar siempre pre-releases a '-beta' limpio (sin .1 / .2)
        canonical = apply_release_channel(canonical, True)

    build_num = get_git_commit_count() if commit_count is None else int(commit_count)
    v1, v2, v3, v4 = to_windows_version_tuple(canonical, build_number=build_num)
    prerelease = is_prerelease(canonical)

    base_name = "Gui Cmd Advance"
    exe_name = f"{base_name} Beta" if prerelease else base_name

    return {
        "version": canonical,
        "base_version": detection["base_version"],
        "impact": detection["impact"],
        "commits_since": detection["commits_since"],
        "auto_bumped": detection["auto_bumped"] or (canonical != detection["base_version"]),
        "git_tag": format_git_tag(canonical),
        "build": v4,
        "is_prerelease": prerelease,
        "exe_name": exe_name,
        "win_tuple": (v1, v2, v3, v4),
        "file_version": f"{v1}.{v2}.{v3}.{v4}",
    }


def build_pyinstaller_command(name, version_file, icon="resources/app_icon.ico"):
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--version-file", version_file,
        "--name", name,
        "--add-data", "resources;resources",
        "--collect-all", "ttkbootstrap",
    ]
    for mod in HIDDEN_IMPORTS:
        cmd.extend(["--hidden-import", mod])
    cmd.extend(["--icon", icon, "main.py"])
    return cmd


def prompt_beta_channel(default_is_beta=True, input_fn=input):
    """Pregunta interactivamente si la compilación sigue siendo Beta o pasa a Estable."""
    default_hint = "S/n" if default_is_beta else "s/N"
    while True:
        try:
            ans = str(input_fn(f"¿Esta compilación continúa siendo BETA? ({default_hint}): ")).strip().lower()
        except EOFError:
            return default_is_beta
        if not ans:
            return default_is_beta
        if ans in ("s", "si", "sí", "y", "yes"):
            return True
        if ans in ("n", "no"):
            return False
        print("  Respuesta no válida. Escribe 's' para Beta o 'n' para Estable.")


def main(argv=None):
    os.chdir(PROJECT_ROOT)

    parser = argparse.ArgumentParser(description="Compilador automático (.exe) de GUI CMD Advance.")
    channel_group = parser.add_mutually_exclusive_group()
    channel_group.add_argument("--beta", action="store_true", help="Compilar directamente en canal Beta sin preguntar.")
    channel_group.add_argument("--stable", action="store_true", help="Compilar directamente en canal Estable sin preguntar.")
    args = parser.parse_args(argv)

    print("=" * 60)
    print("  COMPILACIÓN AUTOMÁTICA (.EXE) - GUI CMD ADVANCE")
    print("=" * 60)

    preview = resolve_build_metadata()
    print(f"[*] Versión base (VERSION)     : {preview['base_version']}")
    if preview["commits_since"] > 0 and preview["impact"] != "none":
        print(
            f"[*] Cambios detectados en Git  : impacto '{preview['impact']}' "
            f"({preview['commits_since']} commit(s) nuevos) -> {preview['version']}"
        )

    if args.beta:
        chosen_beta = True
    elif args.stable:
        chosen_beta = False
    else:
        chosen_beta = prompt_beta_channel(default_is_beta=preview["is_prerelease"])

    meta = resolve_build_metadata(is_beta=chosen_beta)
    v1, v2, v3, v4 = meta["win_tuple"]
    name = meta["exe_name"]
    version_ui = meta["version"]
    channel = "Pre-release (Beta)" if meta["is_prerelease"] else "Estable"

    company = "GOLDEN FENIX"
    description = "Herramienta gráfica avanzada para comandos de sistema"
    copyright_txt = "© 2026 GoldenFenix Todos los derechos reservados."
    icon = "resources/app_icon.ico"

    print(f"[*] Versión base (VERSION)     : {meta['base_version']}")
    if meta["auto_bumped"]:
        print(
            f"[*] Versión auto-detectada     : {version_ui} "
            f"(impacto: {meta['impact']} | {meta['commits_since']} commit(s) nuevos)"
        )
    else:
        print(f"[*] Versión activa             : {version_ui}")
    print(f"[*] Canal detectado            : {channel}")
    print(f"[*] FileVersion Windows        : {meta['file_version']} (build Git #{meta['build']})")
    print(f"[*] Tag Git recomendado        : {meta['git_tag']}")
    print(f"[*] Ejecutable destino         : dist/{name}.exe")

    sync_version_files(version_ui, build_number=meta["build"], repo_root=PROJECT_ROOT)
    print("[+] Archivos 'VERSION' y 'version.py' sincronizados automáticamente.")

    version_content = VERSION_FILE_TEMPLATE.format(
        v1=v1,
        v2=v2,
        v3=v3,
        v4=v4,
        company=company,
        name=name,
        description=description,
        copyright=copyright_txt,
        product_version=version_ui,
    )

    version_file = "version_info.txt"
    with open(version_file, "w", encoding="utf-8") as f:
        f.write(version_content)
    print(f"[+] Archivo '{version_file}' generado con metadatos de Windows.")

    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("\nPyInstaller no está instalado. Instalándolo ahora...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "pyinstaller"],
            check=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    print("\nGenerando el ejecutable principal...")
    cmd = build_pyinstaller_command(name=name, version_file=version_file, icon=icon)
    print(f"Ejecutando: {' '.join(cmd)}\n")
    subprocess.run(cmd, check=True)

    print("\n" + "=" * 60)
    print("  COMPILACIÓN COMPLETADA")
    print("=" * 60)
    print(f"Tu programa compilado está en la carpeta 'dist/{name}.exe'")
    print(f"Versión: {version_ui} (FileVersion {meta['file_version']} | Tag: {meta['git_tag']})")


if __name__ == "__main__":
    main()
