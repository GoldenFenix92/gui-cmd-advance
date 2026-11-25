import argparse
import datetime
import json
import os
import subprocess
import sys
from pathlib import Path

from functions.utils import get_ffmpeg_path, get_user_data_path, safe_print

DEFAULT_MANIFEST_NAME = "health_corrupt_manifest.json"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".3gp", ".mpeg", ".mpg", ".ts"}


def get_default_manifest_path():
    return get_user_data_path(DEFAULT_MANIFEST_NAME)


def ensure_requirements():
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        if getattr(sys, "frozen", False):
            safe_print("Error: Pillow no está disponible en el paquete compilado.")
            sys.exit(1)
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "Pillow"],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )


def check_image(file_path):
    from PIL import Image
    try:
        with Image.open(file_path) as img:
            img.verify()
        return True, ""
    except Exception as e:
        return False, str(e)


def check_video(file_path, threads=0, quick_mode=False):
    ffmpeg = get_ffmpeg_path()
    cmd = [ffmpeg, "-y", "-v", "error", "-i", file_path]

    if quick_mode:
        cmd.extend(["-frames:v", "5"])

    if threads > 0:
        cmd.extend(["-threads", str(threads)])

    cmd.extend(["-f", "null", "-"])

    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    BELOW_NORMAL_PRIORITY_CLASS = 0x00004000

    try:
        process = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            startupinfo=startupinfo,
            creationflags=BELOW_NORMAL_PRIORITY_CLASS,
            encoding="utf-8",
            errors="ignore",
        )
        if process.returncode != 0 or len(process.stderr.strip()) > 0:
            return False, process.stderr.strip()[:300]
        return True, ""
    except Exception as e:
        return False, str(e)


def safe_str(s):
    try:
        s.encode(getattr(sys.stdout, "encoding", None) or "utf-8")
        return s
    except UnicodeEncodeError:
        return s.encode("ascii", errors="replace").decode("ascii")


def write_corrupt_manifest(manifest_path, source_folder, recursive, media_type, corrupt_entries):
    """Guarda el manifiesto JSON con exclusivamente los archivos corruptos detectados."""
    payload = {
        "source_folder": os.path.abspath(str(source_folder)),
        "recursive": bool(recursive),
        "media_type": str(media_type or "all"),
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "corrupt_files": corrupt_entries,
    }
    os.makedirs(os.path.dirname(os.path.abspath(manifest_path)), exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return manifest_path


def main(folder, recursive=False, threads=0, quick_mode=False, media_type="all", manifest_out=None):
    ensure_requirements()
    if not folder or not os.path.isdir(folder):
        safe_print(f"Error: La ruta '{folder}' no es una carpeta válida.")
        sys.exit(1)

    mtype = str(media_type or "all").strip().lower()
    if mtype not in ("all", "videos", "images"):
        mtype = "all"

    allowed_exts = set()
    if mtype in ("all", "images"):
        allowed_exts.update(IMAGE_EXTS)
    if mtype in ("all", "videos"):
        allowed_exts.update(VIDEO_EXTS)

    safe_print(f"Iniciando Analizador de Salud Multimedia en: {safe_str(folder)}")
    safe_print(f"Filtro de tipo: {mtype} | Subcarpetas: {'Sí' if recursive else 'No'}")
    if quick_mode:
        safe_print("Modo de escaneo: Rápido (Solo cabeceras y primeros frames)")
    else:
        safe_print("Modo de escaneo: Profundo (Lectura completa de inicio a fin)")
    safe_print("")

    files_to_check = []
    if recursive:
        for root, dirs, files in os.walk(folder):
            dirs[:] = [
                d for d in dirs
                if not os.path.islink(os.path.join(root, d))
                and not (hasattr(os.path, "isjunction") and os.path.isjunction(os.path.join(root, d)))
            ]
            for f in files:
                ext = Path(f).suffix.lower()
                if ext in allowed_exts:
                    files_to_check.append(os.path.join(root, f))
    else:
        for f in os.listdir(folder):
            path = os.path.join(folder, f)
            if os.path.isfile(path):
                ext = Path(path).suffix.lower()
                if ext in allowed_exts:
                    files_to_check.append(path)

    manifest_path = manifest_out or get_default_manifest_path()
    corrupt_files = []
    healthy_count = 0
    total = len(files_to_check)

    if total == 0:
        write_corrupt_manifest(manifest_path, folder, recursive, mtype, [])
        safe_print("No se encontraron archivos multimedia compatibles para analizar.")
        sys.exit(0)

    for i, file_path in enumerate(files_to_check):
        ext = Path(file_path).suffix.lower()
        is_healthy = True
        error_msg = ""

        safe_name = safe_str(os.path.basename(file_path))
        safe_print(f"Analizando [{i + 1}/{total}]: {safe_name}", end="\r", flush=True)

        if ext in IMAGE_EXTS:
            is_healthy, error_msg = check_image(file_path)
            kind = "image"
        elif ext in VIDEO_EXTS:
            is_healthy, error_msg = check_video(file_path, threads, quick_mode)
            kind = "video"
        else:
            kind = "other"

        safe_print(" " * 100, end="\r")

        if is_healthy:
            healthy_count += 1
            safe_print(f"[OK] {safe_name}")
        else:
            corrupt_files.append({"path": os.path.abspath(file_path), "type": kind, "error": error_msg})
            safe_print(f"[CORRUPTO] {safe_name}")

        pct = int(((i + 1) / total) * 100)
        safe_print(f"Progreso Total: {pct}%")

    write_corrupt_manifest(manifest_path, folder, recursive, mtype, corrupt_files)

    safe_print("\n=======================================================")
    safe_print("REPORTE FINAL DE SALUD MULTIMEDIA")
    safe_print("=======================================================")
    safe_print(f"Archivos Sanos: {healthy_count}")
    safe_print(f"Archivos Corruptos: {len(corrupt_files)}")
    safe_print(f"Manifiesto de corruptos guardado en: {manifest_path}")

    if corrupt_files:
        safe_print("\nLista de archivos corruptos encontrados:")
        for item in corrupt_files:
            safe_print(f" - {safe_str(item['path'])}")
            safe_print(f"   Motivo: {item['error'].replace(chr(10), ' | ')}")
    safe_print("=======================================================")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("folder")
    parser.add_argument("--recursive", action="store_true")
    parser.add_argument("--threads", type=int, default=0)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--media-type", choices=["all", "videos", "images"], default="all")
    parser.add_argument("--manifest-out", default=None)
    args = parser.parse_args()
    main(args.folder, args.recursive, args.threads, args.quick, args.media_type, args.manifest_out)
