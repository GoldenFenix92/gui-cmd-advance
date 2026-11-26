import argparse
import math
import multiprocessing
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from functions.task_memory import TaskMemory
from functions.utils import get_ffmpeg_path, safe_print, send_to_recycle_bin

# Forzar UTF-8 en la salida estándar para evitar errores de codificación con emojis en los nombres de archivo
for _stream in (sys.stdout, sys.stderr):
    if _stream is not None and hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
CONVERT_TO_JPG_EXTS = {".bmp", ".tif", ".tiff"}
VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".3gp", ".mpeg", ".mpg", ".ts"}
NVENC_PRESET_MAP = {"fast": "p3", "medium": "p4", "slow": "p6"}


def _creation_flags(below_normal=False):
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if below_normal and os.name == "nt":
        flags |= 0x00004000  # BELOW_NORMAL_PRIORITY_CLASS
    return flags


def ensure_requirements():
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        if getattr(sys, "frozen", False):
            safe_print("Error: Pillow no está disponible en el ejecutable compilado.")
            sys.exit(1)
        safe_print("Instalando Pillow para procesamiento de imágenes...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow"])


def is_ffmpeg_installed():
    try:
        proc = subprocess.run(
            [get_ffmpeg_path(), "-version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=_creation_flags(),
            timeout=10,
        )
        return proc.returncode == 0
    except Exception:
        return False


def _make_temp_output_path(output_path):
    p = Path(output_path)
    return str(p.parent / f".{p.stem}.part{p.suffix}")


def _cleanup_file_silent(path_str):
    if not path_str:
        return
    try:
        if os.path.exists(path_str):
            os.remove(path_str)
    except Exception:
        pass


def format_size(size_bytes):
    """Formatea bytes a una cadena legible soportando 0 y valores negativos sin error."""
    if size_bytes == 0:
        return "0 B"
    sign = "-" if size_bytes < 0 else ""
    abs_bytes = abs(size_bytes)
    size_name = ("B", "KB", "MB", "GB", "TB")
    i = min(int(math.floor(math.log(abs_bytes, 1024))), len(size_name) - 1)
    p = math.pow(1024, i)
    s = round(abs_bytes / p, 2)
    return f"{sign}{s} {size_name[i]}"


def compress_image(input_path, output_path, quality=75, file_index=0, total_files=1):
    from PIL import Image, ImageOps

    tmp_path = _make_temp_output_path(output_path)
    try:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        out_ext = Path(output_path).suffix.lower()

        with Image.open(input_path) as raw_img:
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

            if out_ext == ".png":
                img.save(tmp_path, "PNG", optimize=True)
            elif out_ext == ".webp":
                save_kwargs = {"quality": quality, "method": 4}
                if exif_bytes:
                    save_kwargs["exif"] = exif_bytes
                img.save(tmp_path, "WEBP", **save_kwargs)
            else:
                if img.mode not in ("RGB", "L"):
                    img = img.convert("RGB")
                save_kwargs = {"quality": quality, "optimize": True}
                if exif_bytes:
                    save_kwargs["exif"] = exif_bytes
                img.save(tmp_path, "JPEG", **save_kwargs)

        # Verificación de integridad antes de mover atómicamente al destino final
        if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) == 0:
            raise RuntimeError("El archivo de salida generado está vacío.")
        with Image.open(tmp_path) as check_img:
            check_img.verify()

        os.replace(tmp_path, output_path)
        safe_print(f"[SUCCESS] Imagen comprimida: {output_path}")
        overall_pct = int(((file_index + 1) * 100) / max(1, total_files))
        safe_print(f"Progreso Total: {overall_pct}%\r", end="", flush=True)
        return {"status": "success", "file": input_path, "out_file": output_path, "type": "image"}
    except Exception as e:
        _cleanup_file_silent(tmp_path)
        safe_print(f"[ERROR] No se pudo comprimir {input_path}: {e}")
        return {"status": "error", "file": input_path, "msg": str(e), "type": "image"}


def detect_best_encoder():
    try:
        output = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"],
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=_creation_flags(),
            timeout=10,
        )
        out_upper = output.upper()
        if "NVIDIA" in out_upper:
            return "h264_nvenc"
        elif "AMD" in out_upper or "RADEON" in out_upper:
            return "h264_amf"
        elif "INTEL" in out_upper:
            return "h264_qsv"
    except Exception:
        pass
    return "libx264"


def _build_ffmpeg_command(ffmpeg_exe, input_path, output_path, encoder, crf, preset, threads, attempt):
    cmd = [ffmpeg_exe, "-y", "-nostdin"]
    if attempt == 2:
        cmd.extend(["-fflags", "+genpts"])
    elif attempt >= 3:
        cmd.extend(["-err_detect", "ignore_err"])

    cmd.extend(["-i", input_path])

    if encoder == "h264_nvenc":
        nv_preset = NVENC_PRESET_MAP.get(preset, "p4")
        cmd.extend(["-c:v", "h264_nvenc", "-cq", str(crf), "-rc", "vbr", "-preset", nv_preset])
    elif encoder == "h264_amf":
        amf_quality = "speed" if preset == "fast" else "balanced"
        cmd.extend(["-c:v", "h264_amf", "-rc", "cqp", "-qp_i", str(crf), "-qp_p", str(crf), "-quality", amf_quality])
    elif encoder == "h264_qsv":
        cmd.extend(["-c:v", "h264_qsv", "-global_quality", str(crf), "-preset", preset])
    else:
        cmd.extend(["-c:v", "libx264", "-crf", str(crf), "-preset", preset])
        calc_threads = threads if threads > 0 else max(1, multiprocessing.cpu_count() - 2)
        if calc_threads > 0:
            cmd.extend(["-threads", str(calc_threads)])

    # Compatibilidad universal de píxeles, audio y streaming MP4
    cmd.extend(["-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart"])

    # Opciones de compatibilidad para reintentos compatibles con FFmpeg 6/7/8
    if attempt == 2:
        cmd.extend(["-fps_mode", "cfr", "-af", "aresample=async=1"])
    elif attempt >= 3:
        cmd.extend(["-fps_mode", "cfr"])

    cmd.append(output_path)
    return cmd


def compress_video(input_path, output_path, crf=23, hw="auto", preset="fast", threads=0, file_index=0, total_files=1, attempt=1):
    if not is_ffmpeg_installed():
        safe_print("[ERROR] FFmpeg no está instalado o no está en el PATH del sistema.")
        safe_print("Por favor, instala FFmpeg desde Complementos o https://ffmpeg.org/download.html.")
        return {"status": "error", "file": input_path, "msg": "FFmpeg no instalado", "type": "video"}

    tmp_path = _make_temp_output_path(output_path)
    process = None
    encoder = "libx264"

    try:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        _cleanup_file_silent(tmp_path)

        if hw == "auto":
            encoder = detect_best_encoder()
        elif hw == "nvenc":
            encoder = "h264_nvenc"
        elif hw == "amf":
            encoder = "h264_amf"
        elif hw == "qsv":
            encoder = "h264_qsv"

        if attempt == 1:
            safe_print(f"Comprimiendo video: {input_path}")
            safe_print(f"Hardware Encoder: {encoder} | Preset: {preset} | CRF: {crf}")
        else:
            safe_print(f"Reintentando video (Intento {attempt}/3): {input_path}")

        cmd = _build_ffmpeg_command(
            ffmpeg_exe=get_ffmpeg_path(),
            input_path=input_path,
            output_path=tmp_path,
            encoder=encoder,
            crf=crf,
            preset=preset,
            threads=threads,
            attempt=attempt,
        )

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=_creation_flags(below_normal=True),
        )

        duration_sec = 0.0
        duration_re = re.compile(r"Duration:\s*(\d{2}):(\d{2}):(\d{2}\.\d{2})")
        time_re = re.compile(r"time=(\d{2}):(\d{2}):(\d{2}\.\d{2})")

        last_error = "Error desconocido en FFmpeg"
        last_progress_time = time.time()
        last_time_str = None
        timeout_seconds = 120 if attempt < 3 else 60
        timed_out = False

        try:
            for line in process.stdout:
                if "time=" in line:
                    match_time_check = time_re.search(line)
                    if match_time_check:
                        current_time_str = match_time_check.group(0)
                        if current_time_str != last_time_str:
                            last_time_str = current_time_str
                            last_progress_time = time.time()

                if time.time() - last_progress_time > timeout_seconds:
                    safe_print(f"\n[ERROR] FFmpeg se ha colgado (timeout de {timeout_seconds}s sin avance). Abortando...")
                    last_error = "El archivo original está corrupto o el codificador se atascó (Timeout excedido)"
                    timed_out = True
                    process.kill()
                    break

                if any(tok in line for tok in ("Error", "error", "Invalid", "Cannot", "Unrecognized")):
                    last_error = line.strip()

                if duration_sec == 0.0:
                    match_dur = duration_re.search(line)
                    if match_dur:
                        h, m, s = match_dur.groups()
                        duration_sec = int(h) * 3600 + int(m) * 60 + float(s)

                if duration_sec > 0.0:
                    match_time = time_re.search(line)
                    if match_time:
                        h, m, s = match_time.groups()
                        current_sec = int(h) * 3600 + int(m) * 60 + float(s)
                        pct = min(100, int((current_sec / duration_sec) * 100))
                        overall_pct = int(((file_index * 100) + pct) / max(1, total_files))
                        safe_print(f"Progreso Total: {overall_pct}%\r", end="", flush=True)
        finally:
            if process.stdout is not None:
                try:
                    process.stdout.close()
                except Exception:
                    pass

        process.wait(timeout=10)

        if not timed_out and process.returncode == 0 and os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0:
            os.replace(tmp_path, output_path)
            safe_print(f"\n[SUCCESS] Video comprimido: {output_path}")
            overall_pct = int(((file_index + 1) * 100) / max(1, total_files))
            safe_print(f"Progreso Total: {overall_pct}%\r", end="", flush=True)
            return {"status": "success", "file": input_path, "out_file": output_path, "type": "video"}

        # Falló o generó archivo vacío: limpiar temporal antes de reintentar
        _cleanup_file_silent(tmp_path)

        if encoder != "libx264" and attempt == 1:
            safe_print(f"\n[WARNING] Falló la compresión con {encoder}. Reintentando automáticamente con CPU (libx264)...")
            return compress_video(input_path, output_path, crf, "cpu", preset, threads, file_index, total_files, attempt=1)
        elif attempt < 3:
            safe_print(f"\n[WARNING] Falló la compresión (Intento {attempt}/3). Reintentando en modo de compatibilidad...")
            return compress_video(input_path, output_path, crf, "cpu", preset, threads, file_index, total_files, attempt=attempt + 1)

        safe_print(f"\n[ERROR] Fallo definitivo en la compresión de {input_path}")
        return {"status": "error", "file": input_path, "msg": last_error, "type": "video"}
    except Exception as e:
        if process is not None:
            try:
                process.kill()
                process.wait(timeout=3)
            except Exception:
                pass
        _cleanup_file_silent(tmp_path)

        if encoder != "libx264" and attempt == 1:
            safe_print(f"\n[WARNING] Excepción con {encoder}. Reintentando automáticamente con CPU (libx264)...")
            return compress_video(input_path, output_path, crf, "cpu", preset, threads, file_index, total_files, attempt=1)
        elif attempt < 3:
            safe_print(f"\n[WARNING] Excepción al comprimir (Intento {attempt}/3). Reintentando en modo de compatibilidad...")
            return compress_video(input_path, output_path, crf, "cpu", preset, threads, file_index, total_files, attempt=attempt + 1)

        safe_print(f"\n[ERROR] Excepción definitiva al comprimir {input_path}: {e}")
        return {"status": "error", "file": input_path, "msg": str(e), "type": "video"}


def get_output_path(input_path, output_dir, suffix="", force_ext=None, base_dir=None):
    p = Path(input_path)
    if not output_dir:
        output_dir_path = p.parent
    else:
        output_dir_path = Path(output_dir)
        if base_dir:
            try:
                rel = p.parent.relative_to(base_dir)
                output_dir_path = output_dir_path / rel
            except ValueError:
                pass
        output_dir_path.mkdir(parents=True, exist_ok=True)

    ext = force_ext if force_ext else p.suffix

    if suffix and (suffix.strip() == '""' or suffix.strip() == "''"):
        suffix = ""

    out_path = output_dir_path / f"{p.stem}{suffix}{ext}"
    if out_path.resolve() == p.resolve():
        out_path = output_dir_path / f"{p.stem}_out{ext}"

    return str(out_path)


def _resolve_inputs(raw_inputs):
    """Si se pasó carpeta + archivo individual desde la GUI, el archivo individual tiene prioridad."""
    cleaned = [i for i in (raw_inputs or []) if i and str(i).strip()]
    if len(cleaned) >= 2:
        last_p = Path(cleaned[-1])
        first_p = Path(cleaned[0])
        if last_p.is_file() and first_p.is_dir():
            return [cleaned[-1]]
    return cleaned


def _get_target_output(f_path, output_dir, suffix, base_dir):
    ext = f_path.suffix.lower()
    if ext in IMAGE_EXTS:
        force_ext = ".jpg" if ext in CONVERT_TO_JPG_EXTS else None
        return get_output_path(f_path, output_dir, suffix, force_ext=force_ext, base_dir=base_dir)
    if ext in VIDEO_EXTS:
        return get_output_path(f_path, output_dir, suffix, force_ext=".mp4", base_dir=base_dir)
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(description="Compresor de Video e Imágenes")
    parser.add_argument("--input", action="append", help="Archivo o carpeta de entrada")
    parser.add_argument("--input-list", default="", help="Archivo JSON con lista de archivos multimedia a comprimir")
    parser.add_argument("--output", default="", help="Carpeta de salida (opcional)")
    parser.add_argument("--suffix", default="", help="Sufijo para archivos comprimidos")
    parser.add_argument("--quality", type=int, default=75, help="Calidad de imagen (0-100)")
    parser.add_argument("--crf", type=int, default=23, help="CRF para video (menor = mejor calidad, 18-28 recomendado)")
    parser.add_argument("--hw", default="auto", help="Motor de aceleración de hardware")
    parser.add_argument("--preset", default="fast", help="Preset de velocidad y consumo")
    parser.add_argument("--threads", type=int, default=0, help="Hilos de CPU a usar (0 = auto)")
    parser.add_argument("--delete-original", action="store_true", help="Eliminar archivos originales procesados con éxito")

    args = parser.parse_args(argv)
    raw_inputs = list(args.input or [])
    if args.input_list:
        from functions.drag_drop import load_input_list_file
        raw_inputs.extend(load_input_list_file(args.input_list))
    resolved_inputs = _resolve_inputs(raw_inputs)
    if not resolved_inputs:
        safe_print("[ERROR] Debes seleccionar una carpeta o un archivo de entrada (--input o --input-list).")
        sys.exit(1)

    ensure_requirements()
    start_time = time.time()

    output_resolved = Path(args.output).resolve() if args.output else None
    clean_suffix = "" if args.suffix.strip() in ('""', "''") else args.suffix

    files_to_process = []
    for inp in resolved_inputs:
        input_path = Path(inp)
        if input_path.is_file():
            files_to_process.append((input_path, input_path.parent))
        elif input_path.is_dir():
            for root, dirs, files in os.walk(input_path):
                # Prevenir bucles infinitos (symlinks/junctions) y excluir la carpeta de salida si está dentro del origen
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
                    f_path = Path(os.path.join(root, f))
                    # Ignorar temporales .part y archivos ya comprimidos con el mismo sufijo
                    if ".part." in f_path.name:
                        continue
                    if clean_suffix and f_path.stem.endswith(clean_suffix):
                        continue
                    if f_path.suffix.lower() in IMAGE_EXTS or f_path.suffix.lower() in VIDEO_EXTS:
                        files_to_process.append((f_path, input_path))
        else:
            safe_print(f"[ERROR] La ruta de entrada no existe: {inp}")

    if not files_to_process:
        safe_print("[INFO] No se encontraron imágenes o videos compatibles para comprimir.")
        return

    context = "_".join(resolved_inputs)
    memory = TaskMemory("media_compressor", context)
    resumed_count = memory.get_processed_count()
    if resumed_count > 0:
        safe_print(f"Reanudando tarea... Se omitirán {resumed_count} archivos previamente procesados.\n")

    safe_print("\n[INFO] Realizando análisis previo de archivos...")
    files_to_compress = []
    already_processed = 0
    total_files = len(files_to_process)

    for f, base_dir in files_to_process:
        fp_str = str(f)
        out = _get_target_output(f, args.output, clean_suffix, base_dir)

        is_processed = memory.is_processed(fp_str)
        if not is_processed and out and os.path.exists(out) and os.path.getsize(out) > 0:
            is_processed = True
            memory.mark_processed(fp_str)

        if is_processed:
            already_processed += 1
        else:
            files_to_compress.append((f, base_dir))

    safe_print(f"[ANALISIS] Total encontrados: {total_files} | Ya procesados: {already_processed} | Pendientes: {len(files_to_compress)}\n")

    results = []
    skipped = already_processed

    if total_files > 0 and skipped > 0:
        safe_print(f"Progreso Total: {int((skipped / total_files) * 100)}%\r", end="", flush=True)

    for i, (f, base_dir) in enumerate(files_to_compress):
        real_index = skipped + i
        fp_str = str(f)
        ext = f.suffix.lower()
        out = _get_target_output(f, args.output, clean_suffix, base_dir)

        res = None
        if ext in IMAGE_EXTS:
            res = compress_image(fp_str, out, quality=args.quality, file_index=real_index, total_files=total_files)
            if res:
                results.append(res)
        elif ext in VIDEO_EXTS:
            res = compress_video(
                fp_str,
                out,
                crf=args.crf,
                hw=args.hw,
                preset=args.preset,
                threads=args.threads,
                file_index=real_index,
                total_files=total_files,
            )
            if res:
                results.append(res)

        # Solo marcar como procesado en memoria si realmente tuvo éxito
        if res and res.get("status") == "success":
            memory.mark_processed(fp_str)

        if TaskMemory.check_pause_signal():
            memory.flush()
            safe_print("\n=======================================================")
            safe_print("[PAUSA] PROCESO POSPUESTO POR EL USUARIO")
            safe_print(f"Estado guardado. Archivos procesados hasta ahora: {memory.get_processed_count()}")
            safe_print("Puedes reanudar este proceso más tarde ejecutando el mismo comando.")
            safe_print("=======================================================")
            sys.exit(0)

    memory.clear()
    elapsed = time.time() - start_time
    mins, secs = divmod(int(elapsed), 60)

    success_img = [r for r in results if r["status"] == "success" and r.get("type") == "image"]
    success_vid = [r for r in results if r["status"] == "success" and r.get("type") == "video"]
    error_img = [r for r in results if r["status"] == "error" and r.get("type") == "image"]
    error_vid = [r for r in results if r["status"] == "error" and r.get("type") == "video"]

    safe_print("\n\n==================================================================================")
    safe_print("[REPORTE FINAL DE CONVERSIÓN POR LOTES]")
    safe_print(f"Tiempo total: {mins} minutos y {secs} segundos.")
    safe_print("==================================================================================")

    safe_print("\n[ TABLA DE RESUMEN DE ARCHIVOS ]")
    safe_print(f"{'TIPO':<15} | {'COMPLETADOS':<15} | {'FALLIDOS':<15} | {'TOTAL':<15}")
    safe_print("-" * 65)
    safe_print(f"{'Imágenes':<15} | {len(success_img):<15} | {len(error_img):<15} | {len(success_img) + len(error_img):<15}")
    safe_print(f"{'Videos':<15} | {len(success_vid):<15} | {len(error_vid):<15} | {len(success_vid) + len(error_vid):<15}")
    safe_print("-" * 65)
    safe_print(f"{'TOTAL GENERAL':<15} | {len(success_img) + len(success_vid):<15} | {len(error_img) + len(error_vid):<15} | {len(results):<15}")

    total_orig_size = 0
    total_comp_size = 0

    for r in success_img + success_vid:
        try:
            total_orig_size += Path(r["file"]).stat().st_size
            total_comp_size += Path(r["out_file"]).stat().st_size
        except Exception:
            pass

    if total_orig_size > 0:
        ahorro = total_orig_size - total_comp_size
        ahorro_pct = (ahorro / total_orig_size) * 100
        safe_print("\n[ RESUMEN DE ESPACIO ]")
        safe_print(f"Peso Original : {format_size(total_orig_size)}")
        safe_print(f"Peso Final    : {format_size(total_comp_size)}")
        if ahorro >= 0:
            safe_print(f"Espacio Ahorrado: {format_size(ahorro)} ({ahorro_pct:.1f}%)")
        else:
            safe_print(f"Incremento de Peso: +{format_size(abs(ahorro))} (+{abs(ahorro_pct):.1f}%)")

    failed_paths = set()
    for err in error_img + error_vid:
        try:
            failed_paths.add(str(Path(err["file"]).resolve()))
        except Exception:
            failed_paths.add(str(err["file"]))

    if success_img or success_vid:
        safe_print("\n[ ARCHIVOS COMPLETADOS CON ÉXITO ]")
        for r in success_img + success_vid:
            file_p = Path(r["file"])
            out_p = Path(r["out_file"])
            safe_print(f" - [OK] {file_p.name}")
            if args.delete_original:
                try:
                    resolved_src = str(file_p.resolve())
                    if r.get("status") != "success" or resolved_src in failed_paths:
                        safe_print(f"   -> (Omitido por error previo; original conservado: {file_p.name})")
                    elif not out_p.exists() or out_p.stat().st_size == 0:
                        safe_print(f"   -> (Original conservado por seguridad: salida no verificada para {file_p.name})")
                    elif out_p.resolve() == file_p.resolve():
                        safe_print("   -> (Original conservado por seguridad: ruta de salida coincide con origen)")
                    else:
                        ok_trash, err_trash = send_to_recycle_bin(file_p)
                        if ok_trash:
                            safe_print(f"   -> (Enviado a la Papelera de Reciclaje: {file_p.name})")
                        else:
                            safe_print(f"   -> (No se pudo enviar a la Papelera; original conservado: {err_trash})")
                except Exception as e:
                    safe_print(f"   -> (No se pudo enviar a la Papelera; original conservado: {e})")

    if error_img or error_vid:
        safe_print("\n[ ARCHIVOS CON ERRORES (ORIGINALES CONSERVADOS INTACTOS) ]")
        safe_print(f"{'ARCHIVO':<45} | {'MOTIVO DEL FALLO'}")
        safe_print("-" * 80)
        for err in error_img + error_vid:
            msg = err["msg"][:100] + "..." if len(err["msg"]) > 100 else err["msg"]
            name = Path(err["file"]).name
            name = name[:40] + "..." if len(name) > 40 else name
            safe_print(f"{name:<45} | {msg}")

    safe_print("==================================================================================\n")


if __name__ == "__main__":
    main()
