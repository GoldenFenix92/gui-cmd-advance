import argparse
import os
import subprocess
import sys
from pathlib import Path
from PIL import Image, ImageFile, ImageOps

# Habilitar la carga de imágenes truncadas/corruptas en Pillow
ImageFile.LOAD_TRUNCATED_IMAGES = True

from functions.task_memory import TaskMemory
from functions.utils import get_ffmpeg_path, safe_print

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
            # Forzar la carga completa para rescatar píxeles en archivos truncados
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

    # Intento 1: Remuxing rápido (Copia directa) + verificación de limpieza real
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

    # Intento 2: Re-codificación profunda descartando paquetes corruptos (compatible FFmpeg 6/7/8)
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
        else:
            _cleanup_silent(tmp_path)
            safe_print(" [ERROR] FFmpeg no pudo reparar el video de forma nativa.")
            if reference_path:
                safe_print(" [INFO] Nota: Se proporcionó un archivo de referencia. Para reparaciones profundas de la cabecera 'moov', se requiere una herramienta externa especializada como 'untrunc'.")
            return False
    except Exception as e:
        _cleanup_silent(tmp_path)
        safe_print(f" [ERROR] Ocurrió un error en la re-codificación: {e}")
        return False


def get_output_path(input_path, output_dir, suffix="_reparado", force_ext=None):
    p = Path(input_path)
    if not output_dir:
        output_dir = p.parent
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    ext = force_ext if force_ext else p.suffix

    out_path = output_dir / f"{p.stem}{suffix}{ext}"
    if out_path.resolve() == p.resolve():
        out_path = output_dir / f"{p.stem}_out{ext}"

    return str(out_path)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Reparador Avanzado de Multimedia (Fotos y Videos)")
    parser.add_argument("--input", required=True, nargs="+", help="Archivo o carpeta de origen")
    parser.add_argument("--output", help="Carpeta de destino (opcional)")
    parser.add_argument("--reference", help="Archivo saludable de referencia de la misma cámara (opcional)")
    parser.add_argument("--suffix", default="_reparado", help="Sufijo para archivos reparados")

    args = parser.parse_args(argv)

    image_exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}
    video_exts = {".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv", ".webm", ".m4v"}
    output_resolved = Path(args.output).resolve() if args.output else None

    files_to_process = []
    for inp in args.input:
        input_path = Path(inp)
        if input_path.is_file():
            files_to_process.append(input_path)
        elif input_path.is_dir():
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
                    if args.suffix and fp.stem.endswith(args.suffix):
                        continue
                    if fp.suffix.lower() in image_exts or fp.suffix.lower() in video_exts:
                        files_to_process.append(fp)

    if not files_to_process:
        safe_print("No se encontraron archivos multimedia para procesar.")
        sys.exit(1)

    success_count = 0
    fail_count = 0

    context = "_".join(args.input)
    memory = TaskMemory("media_repair", context)
    resumed_count = memory.get_processed_count()

    safe_print("==================================================================================")
    safe_print(" INICIANDO REPARACIÓN DE MULTIMEDIA")
    safe_print(f" Total de archivos encontrados: {len(files_to_process)}")
    if args.reference:
        safe_print(f" Usando archivo de referencia: {args.reference}")
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
        force_ext = ".mp4" if ext in video_exts else ".jpg"
        out_path = get_output_path(f, args.output, args.suffix, force_ext=force_ext)

        ok = False
        if ext in image_exts:
            ok = repair_image(fp_str, out_path, args.reference)
        elif ext in video_exts:
            ok = repair_video(fp_str, out_path, args.reference)
        else:
            safe_print(f"[SKIP] Formato no soportado: {f.name}")

        if ok:
            success_count += 1
            memory.mark_processed(fp_str)
        elif ext in image_exts or ext in video_exts:
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

    safe_print("\n==================================================================================")
    safe_print(" RESUMEN DE REPARACIÓN")
    safe_print("==================================================================================")
    safe_print(f" Exitosos: {success_count}")
    safe_print(f" Fallidos: {fail_count}")
    safe_print("==================================================================================")


if __name__ == "__main__":
    main()
