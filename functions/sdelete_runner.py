import argparse
import os
import re
import shutil
import subprocess
import sys

from functions.utils import get_user_data_path, safe_print

# Rutas críticas del sistema que NUNCA se permiten borrar con SDelete en modo archivo/carpeta
PROTECTED_DIRS = {
    "windows",
    "program files",
    "program files (x86)",
    "programdata",
    "users",
    "system volume information",
    "$recycle.bin",
    "recovery",
    "perflogs",
}


def find_sdelete_executable():
    """Localiza sdelete64.exe (o sdelete.exe) en tools/ del usuario o en el PATH."""
    candidates = [
        get_user_data_path(os.path.join("tools", "sdelete64.exe")),
        get_user_data_path(os.path.join("tools", "sdelete.exe")),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    for name in ("sdelete64.exe", "sdelete.exe"):
        found = shutil.which(name)
        if found:
            return found
    return None


def is_protected_path(target_path):
    """Retorna True si la ruta es raíz de unidad o un directorio crítico de Windows."""
    if not target_path or not str(target_path).strip():
        return True
    cleaned = str(target_path).strip().strip('"').strip("'")
    norm = os.path.normpath(os.path.abspath(cleaned))
    drive, tail = os.path.splitdrive(norm)
    parts = [p.lower() for p in tail.strip("\\/").split("\\") if p]
    if not parts:
        # Raíz de unidad (ej. C:\, D:\)
        return True
    if len(parts) == 1 and parts[0] in PROTECTED_DIRS:
        return True
    # Proteger también subcarpetas directas de C:\Windows
    if len(parts) >= 1 and parts[0] == "windows":
        return True
    return False


def get_drive_media_type(drive_letter):
    """Consulta el MediaType del disco (SSD / HDD / Unknown) para la letra dada."""
    if not drive_letter:
        return "Unknown"
    letter = str(drive_letter).strip().rstrip(":\\/").upper()
    if len(letter) != 1 or not letter.isalpha():
        return "Unknown"
    ps = (
        f"$p = Get-Partition -DriveLetter '{letter}' -ErrorAction SilentlyContinue; "
        "if ($p) { "
        "$pd = Get-PhysicalDisk -ErrorAction SilentlyContinue | Where-Object { $_.DeviceId -eq [string]$p.DiskNumber } | Select-Object -First 1; "
        "if ($pd -and $pd.MediaType) { Write-Output $pd.MediaType } else { Write-Output 'Unknown' } "
        "}"
    )
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            timeout=10,
        )
        out = (proc.stdout or "").strip()
        return out if out else "Unknown"
    except Exception:
        return "Unknown"


def extract_sdelete_percent(text):
    """Extrae el porcentaje de avance de la salida de SDelete (0..100)."""
    if not text:
        return None
    m = re.search(r"(\d{1,3})\s*%", text)
    if not m:
        return None
    val = int(m.group(1))
    if 0 <= val <= 100:
        return val
    return None


def build_sdelete_command(
    exe_path,
    mode,
    target="",
    drive="",
    passes=1,
    recursive=False,
    remove_readonly=True,
):
    """Construye la lista segura de argumentos para sdelete64.exe validando el modo.

    Lanza ValueError si los parámetros son inválidos o peligrosos.
    """
    if not exe_path:
        raise ValueError("No se especificó la ruta del ejecutable sdelete64.exe.")

    try:
        p_int = int(passes)
    except Exception:
        p_int = 1
    p_int = max(1, min(35, p_int))

    cmd = [exe_path, "-accepteula", "-nobanner", "-p", str(p_int)]

    if mode == "file":
        cleaned = (target or "").strip().strip('"').strip("'")
        if not cleaned:
            raise ValueError("Debes seleccionar un archivo o carpeta para destruir en modo Archivo/Carpeta.")
        if is_protected_path(cleaned):
            raise ValueError(
                f"BLOQUEADO POR SEGURIDAD: La ruta '{cleaned}' es una raíz de unidad o directorio crítico de Windows."
            )
        if recursive:
            cmd.append("-s")
        if remove_readonly:
            cmd.append("-r")
        cmd.append(cleaned)
        return cmd

    if mode in ("free-zero", "free-clean"):
        letter = (drive or "").strip().rstrip(":\\/").upper()
        if len(letter) != 1 or not letter.isalpha():
            raise ValueError("Debes seleccionar una unidad válida (ej. E:) para limpiar el espacio libre.")
        flag = "-z" if mode == "free-zero" else "-c"
        cmd.extend([flag, f"{letter}:"])
        return cmd

    raise ValueError(f"Modo SDelete no soportado: {mode}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Borrado Seguro Irreversible (Sysinternals SDelete)")
    parser.add_argument("--mode", choices=["file", "free-zero", "free-clean"], default="file")
    parser.add_argument("--target", default="", help="Ruta de archivo o carpeta (modo file)")
    parser.add_argument("--drive", default="", help="Letra de unidad (modos free-zero / free-clean)")
    parser.add_argument("--passes", type=int, default=1, help="Número de pasadas de sobrescritura (default: 1)")
    parser.add_argument("--recursive", action="store_true", help="Incluir subcarpetas (-s)")
    parser.add_argument("--remove-readonly", action="store_true", help="Quitar atributo solo lectura (-r)")
    args = parser.parse_args(argv)

    exe_path = find_sdelete_executable()
    if not exe_path:
        safe_print(
            "[ERROR] No se encontró sdelete64.exe. Instálalo desde el botón 'Complementos' -> 'Sysinternals SDelete'."
        )
        sys.exit(1)

    target_clean = (args.target or "").strip().strip('"').strip("'")
    if args.mode == "file" and target_clean and not os.path.exists(target_clean):
        safe_print(f"[ERROR] La ruta seleccionada no existe: {target_clean}")
        sys.exit(1)

    try:
        cmd = build_sdelete_command(
            exe_path=exe_path,
            mode=args.mode,
            target=target_clean,
            drive=args.drive,
            passes=args.passes,
            recursive=args.recursive,
            remove_readonly=args.remove_readonly,
        )
    except ValueError as exc:
        safe_print(f"[ERROR] {exc}")
        sys.exit(1)

    # Detectar letra de unidad para advertencia informativa de SSD
    check_letter = ""
    if args.mode == "file" and target_clean:
        drv, _ = os.path.splitdrive(os.path.abspath(target_clean))
        check_letter = drv.rstrip(":")
    elif args.drive:
        check_letter = args.drive.strip().rstrip(":\\/")

    media_type = get_drive_media_type(check_letter)

    safe_print("=" * 74)
    safe_print("  BORRADO SEGURO IRREVERSIBLE (MICROSOFT SYSINTERNALS SDELETE)")
    safe_print("=" * 74)
    safe_print(f"  Ejecutable : {exe_path}")
    safe_print(f"  Modo       : {args.mode} | Pasadas: {args.passes}")
    if args.mode == "file":
        safe_print(f"  Objetivo   : {target_clean}")
    else:
        safe_print(f"  Unidad     : {check_letter}: ({media_type})")

    if media_type.upper() == "SSD":
        safe_print("-" * 74)
        safe_print(
            f"  [AVISO SSD] La unidad {check_letter}: es un SSD. Por wear leveling, multiples pasadas "
            "causan desgaste innecesario (TBW) sin garantizar borrado de celdas reasignadas."
        )
        safe_print(
            "  [TIP] En SSD se recomienda usar 1 pasada (-p 1), Optimizar/TRIM o cifrado BitLocker."
        )
    safe_print("=" * 74)

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            bufsize=0,
        )
        buffer = bytearray()
        last_pct = -1
        while True:
            b = proc.stdout.read(1)
            if not b:
                if buffer:
                    line = buffer.decode("utf-8", errors="replace").strip()
                    if line:
                        safe_print(line)
                break
            if b in (b"\r", b"\n"):
                if buffer:
                    line = buffer.decode("utf-8", errors="replace").strip()
                    buffer.clear()
                    if line:
                        pct = extract_sdelete_percent(line)
                        if pct is not None:
                            if pct != last_pct:
                                last_pct = pct
                                safe_print(f"Progreso Total: {pct}%")
                        else:
                            safe_print(line)
            else:
                buffer.extend(b)

        proc.wait()
        if proc.returncode != 0:
            safe_print(f"\n[ERROR] SDelete finalizó con código {proc.returncode}.")
            sys.exit(proc.returncode)

        safe_print("Progreso Total: 100%")
        safe_print("\n[OK] Operación de borrado seguro completada exitosamente.")
        sys.exit(0)
    except Exception as exc:
        safe_print(f"[ERROR] Falló la ejecución de SDelete: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
