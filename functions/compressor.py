import os
import sys
import argparse
import subprocess
from pathlib import Path

# Forzar UTF-8 en la salida estándar para evitar errores de codificación con emojis en los nombres de archivo
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

def ensure_requirements():
    try:
        from PIL import Image
    except ImportError:
        print("Instalando Pillow para procesamiento de imagenes...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow"])
        from PIL import Image

from functions.utils import get_ffmpeg_path
from functions.task_memory import TaskMemory

def is_ffmpeg_installed():
    try:
        subprocess.run([get_ffmpeg_path(), "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except FileNotFoundError:
        return False

def compress_image(input_path, output_path, quality=75, file_index=0, total_files=1):
    from PIL import Image
    try:
        img = Image.open(input_path)
        # Preserve transparency for PNG, else convert to RGB for JPEG
        if img.format == "PNG":
            # Compress PNG (basic Pillow optimize)
            img.save(output_path, "PNG", optimize=True)
        else:
            if img.mode != 'RGB':
                img = img.convert('RGB')
            img.save(output_path, "JPEG", quality=quality, optimize=True)
        print(f"[SUCCESS] Imagen comprimida: {output_path}")
        overall_pct = int(((file_index + 1) * 100) / total_files)
        print(f"Progreso Total: {overall_pct}%\r", end='', flush=True)
        return {'status': 'success', 'file': input_path, 'out_file': output_path, 'type': 'image'}
    except Exception as e:
        print(f"[ERROR] No se pudo comprimir {input_path}: {e}")
        return {'status': 'error', 'file': input_path, 'msg': str(e), 'type': 'image'}

def detect_best_encoder():
    try:
        import subprocess
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        output = subprocess.check_output(['powershell', '-Command', 'Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name'], text=True, startupinfo=startupinfo)
        out_upper = output.upper()
        if 'NVIDIA' in out_upper:
            return 'h264_nvenc'
        elif 'AMD' in out_upper or 'RADEON' in out_upper:
            return 'h264_amf'
        elif 'INTEL' in out_upper:
            return 'h264_qsv'
    except Exception:
        pass
    return 'libx264'

def compress_video(input_path, output_path, crf=23, hw="auto", preset="fast", threads=0, file_index=0, total_files=1):
    if not is_ffmpeg_installed():
        print("[ERROR] FFmpeg no esta instalado o no esta en el PATH del sistema.")
        print("Por favor, instala FFmpeg para poder comprimir videos (https://ffmpeg.org/download.html).")
        return {'status': 'error', 'file': input_path, 'msg': 'FFmpeg no instalado', 'type': 'video'}
        
    try:
        # Analisis de hardware
        encoder = "libx264"
        if hw == "auto":
            encoder = detect_best_encoder()
        elif hw == "nvenc":
            encoder = "h264_nvenc"
        elif hw == "amf":
            encoder = "h264_amf"
        elif hw == "qsv":
            encoder = "h264_qsv"
            
        import re
        print(f"Comprimiendo video: {input_path}")
        print(f"Hardware Encoder: {encoder} | Preset: {preset} | CRF: {crf}")
        
        cmd = [
            get_ffmpeg_path(), "-y", "-nostdin", "-i", input_path,
            "-vcodec", encoder, "-crf", str(crf) if encoder == "libx264" else str(crf),
            "-preset", preset
        ]
        
        if threads > 0:
            cmd.extend(["-threads", str(threads)])
            
        cmd.append(output_path)
        
        # Ajuste para encoders especificos
        if encoder == "h264_nvenc":
            cmd = [
                get_ffmpeg_path(), "-y", "-nostdin", "-i", input_path,
                "-vcodec", "h264_nvenc", "-cq", str(crf), "-rc", "vbr",
                "-preset", preset, output_path
            ]
        elif encoder == "h264_amf":
            cmd = [
                get_ffmpeg_path(), "-y", "-nostdin", "-i", input_path,
                "-vcodec", "h264_amf", "-rc", "cqp", "-qp_i", str(crf), "-qp_p", str(crf),
                "-quality", "speed" if preset == "fast" else "balanced", output_path
            ]
            
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, startupinfo=startupinfo)
        
        duration_sec = 0
        
        # Regex para Duration y Time
        duration_re = re.compile(r"Duration: (\d{2}):(\d{2}):(\d{2}\.\d{2})")
        time_re = re.compile(r"time=(\d{2}):(\d{2}):(\d{2}\.\d{2})")
        
        last_error = "Error desconocido"
        
        last_progress_time = time.time()
        last_time_str = None
        timeout_seconds = 120
        
        for line in process.stdout:
            print(line, end='', flush=True)
            
            # Watchdog anti-cuelgues
            if "time=" in line:
                match_time_check = time_re.search(line)
                if match_time_check:
                    current_time_str = match_time_check.group(0)
                    if current_time_str != last_time_str:
                        last_time_str = current_time_str
                        last_progress_time = time.time()
                        
            if time.time() - last_progress_time > timeout_seconds:
                print(f"\n[ERROR] FFmpeg se ha colgado (timeout de {timeout_seconds}s sin avance en el video). Abortando...")
                last_error = "El archivo original esta corrupto o el codificador se ha atascado (Timeout de seguridad excedido)"
                process.kill()
                break
                
            if "Error" in line or "error" in line or "Cannot" in line:
                last_error = line.strip()
                
            # Buscar duracion total
            if duration_sec == 0:
                match_dur = duration_re.search(line)
                if match_dur:
                    h, m, s = match_dur.groups()
                    duration_sec = int(h)*3600 + int(m)*60 + float(s)
            
            # Calcular y emitir porcentaje
            if duration_sec > 0:
                match_time = time_re.search(line)
                if match_time:
                    h, m, s = match_time.groups()
                    current_sec = int(h)*3600 + int(m)*60 + float(s)
                    pct = int((current_sec / duration_sec) * 100)
                    overall_pct = int(((file_index * 100) + pct) / total_files)
                    print(f"Progreso Total: {overall_pct}%\r", end='', flush=True)
            
        process.wait()
        
        if process.returncode == 0:
            print(f"\n[SUCCESS] Video comprimido: {output_path}")
            overall_pct = int(((file_index + 1) * 100) / total_files)
            print(f"Progreso Total: {overall_pct}%\r", end='', flush=True)
            return {"status": "success", "file": input_path, "out_file": output_path, "type": "video"}
        else:
            if encoder != "libx264":
                print(f"\n[WARNING] Fallo la compresion con {encoder}. Reintentando automaticamente con CPU...")
                return compress_video(input_path, output_path, crf, "cpu", preset, threads, file_index, total_files)
            print(f"\n[ERROR] Fallo la compresion de {input_path}")
            return {"status": "error", "file": input_path, "msg": last_error, "type": "video"}
    except Exception as e:
        if 'encoder' in locals() and encoder != "libx264":
            print(f"\n[WARNING] Excepcion con {encoder}. Reintentando automaticamente con CPU...")
            return compress_video(input_path, output_path, crf, "cpu", preset, threads, file_index, total_files)
        print(f"\n[ERROR] Excepcion al comprimir {input_path}: {e}")
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

def main():
    parser = argparse.ArgumentParser(description="Compresor de Video e Imagenes")
    parser.add_argument("--input", action='append', required=True, help="Archivo o carpeta de entrada")
    parser.add_argument("--output", default="", help="Carpeta de salida (opcional)")
    parser.add_argument("--suffix", default="", help="Sufijo para archivos comprimidos")
    parser.add_argument("--quality", type=int, default=75, help="Calidad de imagen (0-100)")
    parser.add_argument("--crf", type=int, default=23, help="CRF para video (menor = mejor calidad, 18-28 recomendado)")
    
    parser.add_argument("--hw", default="auto", help="Motor de aceleracion de hardware")
    parser.add_argument("--preset", default="fast", help="Preset de velocidad y consumo")
    parser.add_argument("--threads", type=int, default=0, help="Hilos de CPU a usar (0 = auto)")
    parser.add_argument("--delete-original", action="store_true", help="Eliminar archivos originales procesados con exito")
    
    args = parser.parse_args()
    
    ensure_requirements()
    import time
    start_time = time.time()
    
    image_exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}
    video_exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".3gp", ".mpeg", ".mpg", ".ts"}
    
    files_to_process = []
    
    for inp in args.input:
        input_path = Path(inp)
        if input_path.is_file():
            files_to_process.append((input_path, input_path.parent))
        elif input_path.is_dir():
            for root, dirs, files in os.walk(input_path):
                # Prevenir bucles infinitos en Windows
                dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(root, d)) and not (hasattr(os.path, 'isjunction') and os.path.isjunction(os.path.join(root, d)))]
                for f in files:
                    files_to_process.append((Path(os.path.join(root, f)), input_path))
        else:
            print(f"[ERROR] La ruta de entrada no existe: {inp}")
        
    # Inicializar memoria
    context = "_".join(args.input)
    memory = TaskMemory("media_compressor", context)
    resumed_count = memory.get_processed_count()
    if resumed_count > 0:
        print(f"Reanudando tarea... Se omitirán {resumed_count} archivos previamente procesados.\n")

    print("\n[INFO] Realizando analisis previo de archivos...")
    files_to_compress = []
    already_processed = 0
    total_files = len(files_to_process)
    
    for f, base_dir in files_to_process:
        fp_str = str(f)
        ext = f.suffix.lower()
        
        out = None
        if ext in image_exts:
            out = get_output_path(f, args.output, args.suffix, base_dir=base_dir)
        elif ext in video_exts:
            out = get_output_path(f, args.output, args.suffix, force_ext=".mp4", base_dir=base_dir)
            
        is_processed = memory.is_processed(fp_str)
        if not is_processed and out and os.path.exists(out) and os.path.getsize(out) > 0:
            is_processed = True
            memory.mark_processed(fp_str)
            
        if is_processed:
            already_processed += 1
        else:
            files_to_compress.append((f, base_dir))
            
    print(f"[ANALISIS] Total encontrados: {total_files} | Ya procesados: {already_processed} | Pendientes: {len(files_to_compress)}\n")
    
    results = []
    skipped = already_processed
    
    # Enviar progreso inicial si ya hay archivos procesados
    if total_files > 0 and skipped > 0:
        print(f"Progreso Total: {int((skipped/total_files)*100)}%\r", end='', flush=True)
    
    for i, (f, base_dir) in enumerate(files_to_compress):
        real_index = skipped + i
        fp_str = str(f)
            
        ext = f.suffix.lower()
        res = None
        if ext in image_exts:
            out = get_output_path(f, args.output, args.suffix, base_dir=base_dir)
            res = compress_image(fp_str, out, quality=args.quality, file_index=real_index, total_files=total_files)
            if res: results.append(res)
        elif ext in video_exts:
            out = get_output_path(f, args.output, args.suffix, force_ext=".mp4", base_dir=base_dir)
            res = compress_video(fp_str, out, crf=args.crf, hw=args.hw, preset=args.preset, threads=args.threads, file_index=real_index, total_files=total_files)
            if res: results.append(res)
            
        if ext in image_exts or ext in video_exts:
            memory.mark_processed(fp_str)
            
        # Verificar pausa
        if TaskMemory.check_pause_signal():
            print("\n=======================================================")
            print("🛑 PROCESO POSPUESTO POR EL USUARIO 🛑")
            print(f"Estado guardado. Archivos procesados hasta ahora: {memory.get_processed_count()}")
            print("Puedes reanudar este proceso más tarde ejecutando el mismo comando.")
            print("=======================================================")
            sys.exit(0)

    memory.clear()
    elapsed = time.time() - start_time
    mins, secs = divmod(int(elapsed), 60)
    
    success_img = [r for r in results if r["status"] == "success" and r.get("type") == "image"]
    success_vid = [r for r in results if r["status"] == "success" and r.get("type") == "video"]
    error_img = [r for r in results if r["status"] == "error" and r.get("type") == "image"]
    error_vid = [r for r in results if r["status"] == "error" and r.get("type") == "video"]
    
    print(f"\n\n==================================================================================")
    print(f"[REPORTE FINAL DE CONVERSION POR LOTES]")
    print(f"Tiempo total: {mins} minutos y {secs} segundos.")
    print(f"==================================================================================")
    
    print("\n[ TABLA DE RESUMEN DE ARCHIVOS ]")
    print(f"{'TIPO':<15} | {'COMPLETADOS':<15} | {'FALLIDOS':<15} | {'TOTAL':<15}")
    print("-" * 65)
    print(f"{'Imagenes':<15} | {len(success_img):<15} | {len(error_img):<15} | {len(success_img)+len(error_img):<15}")
    print(f"{'Videos':<15} | {len(success_vid):<15} | {len(error_vid):<15} | {len(success_vid)+len(error_vid):<15}")
    print("-" * 65)
    print(f"{'TOTAL GENERAL':<15} | {len(success_img)+len(success_vid):<15} | {len(error_img)+len(error_vid):<15} | {len(results):<15}")
    
    total_orig_size = 0
    total_comp_size = 0
    
    for r in success_img + success_vid:
        try:
            total_orig_size += Path(r['file']).stat().st_size
            total_comp_size += Path(r['out_file']).stat().st_size
        except:
            pass

    def format_size(size_bytes):
        if size_bytes == 0: return "0 B"
        import math
        size_name = ("B", "KB", "MB", "GB", "TB")
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_name[i]}"
        
    if total_orig_size > 0:
        ahorro = total_orig_size - total_comp_size
        ahorro_pct = (ahorro / total_orig_size) * 100
        print(f"\n[ RESUMEN DE ESPACIO ]")
        print(f"Peso Original : {format_size(total_orig_size)}")
        print(f"Peso Final    : {format_size(total_comp_size)}")
        print(f"Espacio Ahorrado: {format_size(ahorro)} ({ahorro_pct:.1f}%)")
    
    if success_img or success_vid:
        print("\n[ ARCHIVOS COMPLETADOS CON EXITO ]")
        for r in success_img + success_vid:
            file_p = Path(r['file'])
            print(f" - [OK] {file_p.name}")
            if args.delete_original:
                try:
                    file_p.unlink()
                    print(f"   -> (Eliminado original: {file_p.name})")
                except Exception as e:
                    print(f"   -> (No se pudo eliminar: {e})")
            
    if error_img or error_vid:
        print("\n[ ARCHIVOS CON ERRORES ]")
        print(f"{'ARCHIVO':<35} | {'MOTIVO DEL FALLO'}")
        print("-" * 80)
        for err in error_img + error_vid:
            msg = err["msg"][:100] + "..." if len(err["msg"]) > 100 else err["msg"]
            name = Path(err['file']).name
            name = name[:40] + "..." if len(name) > 40 else name
            print(f"{name:<45} | {msg}")
            
    print(f"==================================================================================\n")

if __name__ == "__main__":
    main()
