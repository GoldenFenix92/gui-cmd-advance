import os
import sys
import argparse
import subprocess
from pathlib import Path

def ensure_requirements():
    try:
        from PIL import Image
    except ImportError:
        print("Instalando Pillow para procesamiento de imagenes...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow"])
        from PIL import Image

def get_ffmpeg_path():
    import os
    local_ffmpeg = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ffmpeg.exe")
    if os.path.exists(local_ffmpeg):
        return local_ffmpeg
    return "ffmpeg"

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
        print(f" {overall_pct}%", end='', flush=True)
        return {'status': 'success', 'file': input_path, 'type': 'image'}
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

def compress_video(input_path, output_path, crf=23, hw="auto", preset="fast", file_index=0, total_files=1):
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
            get_ffmpeg_path(), "-y", "-i", input_path,
            "-vcodec", encoder, "-crf", str(crf) if encoder == "libx264" else str(crf),
            "-preset", preset, output_path
        ]
        
        # Ajuste para encoders especificos
        if encoder == "h264_nvenc":
            cmd = [
                get_ffmpeg_path(), "-y", "-i", input_path,
                "-vcodec", "h264_nvenc", "-cq", str(crf), "-rc", "vbr",
                "-preset", preset, output_path
            ]
        elif encoder == "h264_amf":
            cmd = [
                get_ffmpeg_path(), "-y", "-i", input_path,
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
        for line in process.stdout:
            print(line, end='', flush=True)
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
                    print(f" {overall_pct}%", end='', flush=True)
            
        process.wait()
        
        if process.returncode == 0:
            print(f"\n[SUCCESS] Video comprimido: {output_path}")
            overall_pct = int(((file_index + 1) * 100) / total_files)
            print(f" {overall_pct}%", end='', flush=True)
            return {"status": "success", "file": input_path, "type": "video"}
        else:
            print(f"\n[ERROR] Fallo la compresion de {input_path}")
            return {"status": "error", "file": input_path, "msg": last_error, "type": "video"}
    except Exception as e:
        print(f"[ERROR] Excepcion al comprimir {input_path}: {e}")
        return {"status": "error", "file": input_path, "msg": str(e), "type": "video"}

def get_output_path(input_path, output_dir, suffix="_comprimido"):
    p = Path(input_path)
    if not output_dir:
        output_dir = p.parent
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
    return str(output_dir / f"{p.stem}{suffix}{p.suffix}")

def main():
    parser = argparse.ArgumentParser(description="Compresor de Video e Imagenes")
    parser.add_argument("--input", action='append', required=True, help="Archivo o carpeta de entrada")
    parser.add_argument("--output", default="", help="Carpeta de salida (opcional)")
    parser.add_argument("--suffix", default="_comprimido", help="Sufijo para archivos comprimidos")
    parser.add_argument("--quality", type=int, default=75, help="Calidad de imagen (0-100)")
    parser.add_argument("--crf", type=int, default=23, help="CRF para video (menor = mejor calidad, 18-28 recomendado)")
    
    parser.add_argument("--hw", default="auto", help="Motor de aceleracion de hardware")
    parser.add_argument("--preset", default="fast", help="Preset de velocidad y consumo")
    
    args = parser.parse_args()
    
    ensure_requirements()
    import time
    start_time = time.time()
    
    image_exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}
    video_exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v"}
    
    files_to_process = []
    
    for inp in args.input:
        input_path = Path(inp)
        if input_path.is_file():
            files_to_process.append(input_path)
        elif input_path.is_dir():
            for f in input_path.rglob("*"):
                if f.is_file():
                    files_to_process.append(f)
        else:
            print(f"[ERROR] La ruta de entrada no existe: {inp}")
        
    results = []
    total_files = len(files_to_process)
    
    for i, f in enumerate(files_to_process):
        ext = f.suffix.lower()
        if ext in image_exts:
            out = get_output_path(f, args.output, args.suffix)
            res = compress_image(str(f), out, quality=args.quality, file_index=i, total_files=total_files)
            if res: results.append(res)
        elif ext in video_exts:
            out = get_output_path(f, args.output, args.suffix)
            res = compress_video(str(f), out, crf=args.crf, hw=args.hw, preset=args.preset, file_index=i, total_files=total_files)
            if res: results.append(res)

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
    
    if success_img or success_vid:
        print("\n[ ARCHIVOS COMPLETADOS CON EXITO ]")
        for r in success_img + success_vid:
            print(f" - [OK] {Path(r['file']).name}")
            
    if error_img or error_vid:
        print("\n[ ARCHIVOS CON ERRORES ]")
        print(f"{'ARCHIVO':<35} | {'MOTIVO DEL FALLO'}")
        print("-" * 80)
        for err in error_img + error_vid:
            msg = err["msg"][:40] + "..." if len(err["msg"]) > 40 else err["msg"]
            name = Path(err['file']).name
            name = name[:32] + "..." if len(name) > 32 else name
            print(f"{name:<35} | {msg}")
            
    print(f"==================================================================================\n")

if __name__ == "__main__":
    main()
