import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from PIL import Image, ImageFile, ImageOps

# Habilitar la carga de imágenes truncadas/corruptas en Pillow
ImageFile.LOAD_TRUNCATED_IMAGES = True

from functions.task_memory import TaskMemory
from functions.utils import get_ffmpeg_path, get_user_data_path, safe_print

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}
VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv", ".webm", ".m4v", ".3gp", ".mpeg", ".mpg", ".ts"}
DEFAULT_MANIFEST_NAME = "health_corrupt_manifest.json"

for _stream in (sys.stdout, sys.stderr):
    if _stream is not None and hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _creation_flags():
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _make_temp_output_path(output_path):
    p = Path(output_path)
    return str(p.parent / f".{p.stem}.part{p.suffix}")


def _cleanup_silent(path_str):
    if not path_str:
        return
    try:
        if os.path.exists(path_str):
            os.remove(path_str)
    except Exception:
        pass


def _is_video_clean(video_path):
    """Verifica con FFmpeg si el video se decodifica sin errores de frames ni audio."""
    ffmpeg = get_ffmpeg_path()
    try:
        proc = subprocess.run(
            [ffmpeg, "-v", "error", "-i", str(video_path), "-f", "null", "-"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=_creation_flags(),
            timeout=120,
        )
        return proc.returncode == 0 and proc.stderr.strip() == ""
    except Exception:
        return False


def repair_image(input_path, output_path, reference_path=None):
    tmp_path = _make_temp_output_path(output_path)
    try:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        safe_print(f"[{'REFERENCE' if reference_path else 'BASIC'} REPAIR] Intentando reparar imagen: {input_path}")

        with Image.open(input_path) as raw_img:
            raw_img.load()
            img = ImageOps.exif_transpose(raw_img)

            exif_bytes = None
            try:
                exif_obj = img.getexif()
                if exif_obj:
                    if 274 in exif_obj:
                        exif_obj[274] = 1
                    exif_bytes = exif_obj.tobytes()
            except Exception:
                exif_bytes = None

            if img.mode != "RGB":
                img = img.convert("RGB")

            save_kwargs = {"quality": 95, "optimize": True}
            if exif_bytes:
                save_kwargs["exif"] = exif_bytes
            img.save(tmp_path, "JPEG", **save_kwargs)

        if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) == 0:
            raise RuntimeError("La imagen reparada quedó vacía.")
        with Image.open(tmp_path) as check_img:
            check_img.verify()

        os.replace(tmp_path, output_path)
        safe_print(f" [OK] Imagen reparada guardada en: {output_path}")
        return True
    except Exception as e:
        _cleanup_silent(tmp_path)
        safe_print(f" [ERROR] No se pudo reparar la imagen: {e}")
        return False


def repair_video(input_path, output_path, reference_path=None):
    ffmpeg = get_ffmpeg_path()
    creation_flags = _creation_flags()
    tmp_path = _make_temp_output_path(output_path)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    _cleanup_silent(tmp_path)

    safe_print(f"[{'REFERENCE' if reference_path else 'BASIC'} REPAIR] Intento 1 (Remux) en video: {input_path}")
    cmd_remux = [
        ffmpeg, "-y", "-nostdin",
        "-err_detect", "ignore_err",
        "-i", str(input_path),
        "-c", "copy",
        "-movflags", "+faststart",
        tmp_path,
    ]

    try:
        result = subprocess.run(
            cmd_remux,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creation_flags,
        )
        if result.returncode == 0 and os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 1024:
            if _is_video_clean(tmp_path):
                os.replace(tmp_path, output_path)
                safe_print(f" [OK] Video reparado (Remux limpio) guardado en: {output_path}")
                return True
            safe_print(" [WARN] El Remux conservó paquetes/frames corruptos; pasando a reconstrucción profunda (Re-encode)...")
    except Exception as e:
        safe_print(f" [WARN] Falló el Intento 1 (Remux): {e}")
    finally:
        _cleanup_silent(tmp_path)

    safe_print(f"[REPAIR] Intento 2 (Re-encode profundo) en video: {input_path}")
    cmd_reencode = [
        ffmpeg, "-y", "-nostdin",
        "-fflags", "+discardcorrupt+genpts",
        "-err_detect", "ignore_err",
        "-i", str(input_path),
        "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        "-max_error_rate", "1.0",
        tmp_path,
    ]

    try:
        result = subprocess.run(
            cmd_reencode,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creation_flags,
        )
        if result.returncode == 0 and os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 1024:
            os.replace(tmp_path, output_path)
            safe_print(f" [OK] Video reparado (Re-encode profundo) guardado en: {output_path}")
            return True
        _cleanup_silent(tmp_path)
        safe_print(" [ERROR] FFmpeg no pudo reparar el video de forma nativa.")
        if reference_path:
            safe_print(" [INFO] Nota: Se proporcionó un archivo de referencia. Para reparaciones profundas de la cabecera 'moov', se requiere una herramienta externa especializada como 'untrunc'.")
        return False
    except Exception as e:
        _cleanup_silent(tmp_path)
        safe_print(f" [ERROR] Ocurrió un error en la re-codificación: {e}")
        return False


def get_output_path(input_path, output_dir, suffix="_reparado", force_ext=None, base_root=None):
    p = Path(input_path)
    if not output_dir:
        target_dir = p.parent
    else:
        target_dir = Path(output_dir)
        if base_root:
            try:
                rel_parent = p.resolve().parent.relative_to(Path(base_root).resolve())
                if str(rel_parent) not in ("", "."):
                    target_dir = target_dir / rel_parent
            except Exception:
                pass
        target_dir.mkdir(parents=True, exist_ok=True)

    ext = force_ext if force_ext else p.suffix
    out_path = target_dir / f"{p.stem}{suffix}{ext}"
    if out_path.resolve() == p.resolve():
        out_path = target_dir / f"{p.stem}_out{ext}"

    return str(out_path)


def _allowed_exts_for_media_type(media_type):
    mtype = str(media_type or "all").strip().lower()
    if mtype == "videos":
        return set(VIDEO_EXTS)
    if mtype == "images":
        return set(IMAGE_EXTS)
    return set(IMAGE_EXTS | VIDEO_EXTS)


def load_corrupt_files_from_manifest(manifest_path, media_type="all"):
    """Lee el manifiesto de health_analyzer y retorna (lista_de_Paths_corruptos, source_folder)."""
    if not manifest_path or not os.path.exists(manifest_path):
        return None, None
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None, None
    allowed = _allowed_exts_for_media_type(media_type)
    files = []
    for entry in data.get("corrupt_files", []):
        raw_p = entry.get("path") if isinstance(entry, dict) else str(entry)
        if not raw_p:
            continue
        p = Path(raw_p)
        if p.is_file() and p.suffix.lower() in allowed:
            files.append(p)
    return files, data.get("source_folder")


def find_resumable_manifest(manifest_path, source_folder, recursive, media_type="all"):
    """Si existe un manifiesto pendiente para la misma carpeta y configuración, retorna sus archivos restantes."""
    if not manifest_path or not os.path.exists(manifest_path):
        return None
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None

    m_src = data.get("source_folder")
    if not m_src or not source_folder:
        return None
    try:
        same_folder = Path(m_src).resolve() == Path(source_folder).resolve()
    except Exception:
        same_folder = os.path.normcase(os.path.abspath(m_src)) == os.path.normcase(os.path.abspath(source_folder))

    if not same_folder:
        return None
    if bool(data.get("recursive", False)) != bool(recursive):
        return None

    allowed = _allowed_exts_for_media_type(media_type)
    pending = []
    for entry in data.get("corrupt_files", []):
        raw_p = entry.get("path") if isinstance(entry, dict) else str(entry)
        if raw_p and Path(raw_p).is_file() and Path(raw_p).suffix.lower() in allowed:
            pending.append(Path(raw_p))
    return pending if pending else None


def remove_file_from_manifest(manifest_path, repaired_path):
    """Elimina atómicamente un archivo ya reparado del manifiesto (y borra el manifiesto si queda vacío)."""
    if not manifest_path or not os.path.exists(manifest_path):
        return
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return

    target_norm = os.path.normcase(os.path.abspath(str(repaired_path)))
    remaining = []
    for entry in data.get("corrupt_files", []):
        raw_p = entry.get("path") if isinstance(entry, dict) else str(entry)
        if not raw_p:
            continue
        if os.path.normcase(os.path.abspath(raw_p)) != target_norm:
            remaining.append(entry)

    if not remaining:
        _cleanup_silent(manifest_path)
        return

    data["corrupt_files"] = remaining
    tmp_manifest = f"{manifest_path}.tmp"
    try:
        with open(tmp_manifest, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_manifest, manifest_path)
    except Exception:
        _cleanup_silent(tmp_manifest)


def collect_target_files(inputs, media_type="all", recursive=False, output_dir=None, suffix="_reparado"):
    """Recolecta archivos multimedia según filtro de tipo y modo recursivo (desactivado por defecto)."""
    allowed = _allowed_exts_for_media_type(media_type)
    output_resolved = Path(output_dir).resolve() if output_dir else None
    files_to_process = []

    for inp in inputs:
        input_path = Path(inp)
        if input_path.is_file():
            if input_path.suffix.lower() in allowed:
                files_to_process.append(input_path)
        elif input_path.is_dir():
            if recursive:
                for root, dirs, files in os.walk(input_path):
                    filtered_dirs = []
                    for d in dirs:
                        full_d = os.path.join(root, d)
                        if os.path.islink(full_d) or (hasattr(os.path, "isjunction") and os.path.isjunction(full_d)):
                            continue
                        if output_resolved is not None:
                            try:
                                if Path(full_d).resolve() == output_resolved:
                                    continue
                            except Exception:
                                pass
                        filtered_dirs.append(d)
                    dirs[:] = filtered_dirs

                    for f in files:
                        fp = Path(os.path.join(root, f))
                        if ".part." in fp.name:
                            continue
                        if suffix and fp.stem.endswith(suffix):
                            continue
                        if fp.suffix.lower() in allowed:
                            files_to_process.append(fp)
            else:
                for f in os.listdir(input_path):
                    fp = input_path / f
                    if not fp.is_file():
                        continue
                    if ".part." in fp.name:
                        continue
                    if suffix and fp.stem.endswith(suffix):
                        continue
                    if fp.suffix.lower() in allowed:
                        files_to_process.append(fp)

    return files_to_process


def filter_corrupt_files_and_save_manifest(candidate_files, source_folder, recursive, media_type, manifest_path=None):
    """Analiza los archivos candidatos, guarda el manifiesto de corruptos y retorna solo los dañados."""
    from functions import health_analyzer

    mpath = manifest_path or get_user_data_path(DEFAULT_MANIFEST_NAME)
    corrupt_paths = []
    corrupt_entries = []
    total = len(candidate_files)

    safe_print("==================================================================================")
    safe_print(f" [FASE 1/2] ANALIZANDO SALUD DE {total} ARCHIVOS (AISLANDO SOLO CORRUPTOS)")
    safe_print("==================================================================================")

    for idx, fp in enumerate(candidate_files, 1):
        fp_str = str(fp)
        ext = fp.suffix.lower()
        if ext in IMAGE_EXTS:
            is_ok, err = health_analyzer.check_image(fp_str)
            kind = "image"
        elif ext in VIDEO_EXTS:
            is_ok, err = health_analyzer.check_video(fp_str)
            kind = "video"
        else:
            continue

        if is_ok:
            safe_print(f" [SANO - OMITIDO] {fp.name}")
        else:
            safe_print(f" [CORRUPTO] {fp_str}")
            corrupt_paths.append(fp)
            corrupt_entries.append({"path": os.path.abspath(fp_str), "type": kind, "error": err})

        pct = int((idx / max(1, total)) * 50)
        safe_print(f"Progreso Total: {pct}%")

    health_analyzer.write_corrupt_manifest(mpath, source_folder, recursive, media_type, corrupt_entries)
    safe_print(f"\n[MANIFIESTO] {len(corrupt_paths)} archivo(s) corrupto(s) guardado(s) en: {mpath}\n")
    return corrupt_paths


def main(argv=None):
    parser = argparse.ArgumentParser(description="Reparador Avanzado de Multimedia (Fotos y Videos)")
    parser.add_argument("--input", nargs="+", help="Archivo o carpeta de origen")
    parser.add_argument("--output", help="Carpeta de destino (opcional)")
    parser.add_argument("--media-type", choices=["all", "videos", "images"], default="all", help="Tipo de archivos a reparar")
    parser.add_argument("--recursive", action="store_true", help="Incluir subcarpetas al escanear sin análisis previo")
    parser.add_argument("--from-manifest", action="store_true", help="Reparar exclusivamente los archivos corruptos del último análisis de salud")
    parser.add_argument("--manifest", default=None, help="Ruta personalizada al manifiesto JSON de archivos corruptos")
    parser.add_argument("--force-all", action="store_true", help="Forzar reparación de todos los archivos sin filtrar sanos (no recomendado)")
    parser.add_argument("--reference", help="Archivo saludable de referencia genérico (retrocompatible)")
    parser.add_argument("--ref-video", help="Archivo de video saludable de referencia (opcional)")
    parser.add_argument("--ref-image", help="Archivo de imagen saludable de referencia (opcional)")
    parser.add_argument("--suffix", default="_reparado", help="Sufijo para archivos reparados")

    args = parser.parse_args(argv)

    base_root = None
    active_manifest_path = None
    used_manifest_mode = bool(args.from_manifest or args.manifest)
    if used_manifest_mode:
        mpath = args.manifest or get_user_data_path(DEFAULT_MANIFEST_NAME)
        active_manifest_path = mpath
        loaded, src_root = load_corrupt_files_from_manifest(mpath, media_type=args.media_type)
        if loaded is None:
            safe_print(f"[ERROR] No se encontró el manifiesto de análisis previo en: {mpath}")
            sys.exit(1)
        files_to_process = loaded
        base_root = src_root
        if not files_to_process:
            safe_print("[OK] El análisis de salud previo no detectó archivos corruptos que coincidan con el filtro seleccionado. No hay nada que reparar.")
            _cleanup_silent(active_manifest_path)
            safe_print(f"[LIMPIEZA] Manifiesto temporal eliminado: {active_manifest_path}")
            sys.exit(0)
    else:
        if not args.input:
            safe_print("[ERROR] Debes indicar --input o --from-manifest.")
            sys.exit(1)
        candidates = collect_target_files(
            args.input,
            media_type=args.media_type,
            recursive=args.recursive,
            output_dir=args.output,
            suffix=args.suffix,
        )
        if not candidates:
            safe_print("No se encontraron archivos multimedia para procesar.")
            sys.exit(1)

        has_directory_input = any(os.path.isdir(inp) for inp in args.input)
        if len(args.input) == 1 and os.path.isdir(args.input[0]):
            base_root = args.input[0]

        if has_directory_input and not args.force_all:
            src_folder = base_root or os.path.dirname(os.path.abspath(str(candidates[0])))
            active_manifest_path = get_user_data_path(DEFAULT_MANIFEST_NAME)
            resumed_pending = find_resumable_manifest(
                active_manifest_path,
                source_folder=src_folder,
                recursive=args.recursive,
                media_type=args.media_type,
            )
            if resumed_pending:
                safe_print(
                    f"[REANUDANDO] Se encontró un manifiesto pendiente para esta carpeta con "
                    f"{len(resumed_pending)} archivo(s) por reparar. Continuando sin repetir los ya reparados..."
                )
                files_to_process = resumed_pending
            else:
                files_to_process = filter_corrupt_files_and_save_manifest(
                    candidates,
                    source_folder=src_folder,
                    recursive=args.recursive,
                    media_type=args.media_type,
                    manifest_path=active_manifest_path,
                )
            used_manifest_mode = True
            if not files_to_process:
                safe_print("[OK] Todos los archivos analizados están sanos (0 corruptos). No se modificó ningún archivo.")
                _cleanup_silent(active_manifest_path)
                safe_print(f"[LIMPIEZA] Manifiesto temporal eliminado: {active_manifest_path}")
                sys.exit(0)
        else:
            files_to_process = candidates

    if not files_to_process:
        safe_print("No se encontraron archivos multimedia para procesar.")
        sys.exit(1)

    ref_video = args.ref_video or args.reference
    ref_image = args.ref_image or args.reference

    success_count = 0
    fail_count = 0

    context = "_".join(args.input or [args.manifest or "manifest"]) + f"_{args.media_type}"
    memory = TaskMemory("media_repair", context)
    resumed_count = memory.get_processed_count()

    safe_print("==================================================================================")
    safe_print(" INICIANDO REPARACIÓN DE MULTIMEDIA")
    safe_print(f" Modo: {'Exclusivo solo corruptos (manifiesto)' if used_manifest_mode else 'Archivo puntual'} | Tipo: {args.media_type}")
    safe_print(f" Total de archivos a reparar: {len(files_to_process)}")
    if ref_video:
        safe_print(f" Video sano de referencia: {ref_video}")
    if ref_image:
        safe_print(f" Imagen sana de referencia: {ref_image}")
    if resumed_count > 0:
        safe_print(f" Reanudando tarea... Saltando {resumed_count} archivos reparados previamente.")
    safe_print("==================================================================================\n")

    total_files = len(files_to_process)

    for i, f in enumerate(files_to_process):
        fp_str = str(f)
        if memory.is_processed(fp_str):
            if (i + 1) == total_files or (i + 1) % 10 == 0:
                safe_print(f"Progreso Total: {int(((i + 1) / total_files) * 100)}%")
            continue

        ext = f.suffix.lower()
        force_ext = ".mp4" if ext in VIDEO_EXTS else ".jpg"
        out_path = get_output_path(f, args.output, args.suffix, force_ext=force_ext, base_root=base_root)

        ok = False
        if ext in IMAGE_EXTS:
            ok = repair_image(fp_str, out_path, ref_image)
        elif ext in VIDEO_EXTS:
            ok = repair_video(fp_str, out_path, ref_video)
        else:
            safe_print(f"[SKIP] Formato no soportado: {f.name}")

        if ok:
            success_count += 1
            memory.mark_processed(fp_str)
            if active_manifest_path:
                remove_file_from_manifest(active_manifest_path, fp_str)
        elif ext in IMAGE_EXTS or ext in VIDEO_EXTS:
            fail_count += 1

        pct = int(((i + 1) / max(1, total_files)) * 100)
        safe_print(f"Progreso Total: {pct}%")

        if TaskMemory.check_pause_signal():
            memory.flush()
            safe_print("\n=======================================================")
            safe_print("[PAUSA] PROCESO POSPUESTO POR EL USUARIO")
            safe_print(f"Estado guardado. Archivos procesados hasta ahora: {memory.get_processed_count()}")
            safe_print("Puedes reanudar este proceso más tarde ejecutando el mismo comando.")
            safe_print("=======================================================")
            sys.exit(0)

    memory.clear()
    if active_manifest_path and os.path.exists(active_manifest_path):
        _cleanup_silent(active_manifest_path)
        safe_print(f"\n[LIMPIEZA] Manifiesto temporal eliminado al concluir: {active_manifest_path}")

    safe_print("\n==================================================================================")
    safe_print(" RESUMEN DE REPARACIÓN")
    safe_print("==================================================================================")
    safe_print(f" Exitosos: {success_count}")
    safe_print(f" Fallidos: {fail_count}")
    safe_print("==================================================================================")


if __name__ == "__main__":
    main()
