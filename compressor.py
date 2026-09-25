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

def compress_image(input_path, output_path, quality=75):
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
    except Exception as e:
        print(f"[ERROR] No se pudo comprimir {input_path}: {e}")

def compress_video(input_path, output_path, crf=23):
    if not is_ffmpeg_installed():
        print("[ERROR] FFmpeg no esta instalado o no esta en el PATH del sistema.")
        print("Por favor, instala FFmpeg para poder comprimir videos (https://ffmpeg.org/download.html).")
        return False
        
    try:
        import re
        print(f"Comprimiendo video: {input_path} (CRF: {crf})... esto puede tardar un poco.")
        cmd = [
            get_ffmpeg_path(), "-y", "-i", input_path,
            "-vcodec", "libx264", "-crf", str(crf),
            "-preset", "fast", output_path
        ]
        
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, startupinfo=startupinfo)
        
        duration_sec = 0
        
        # Regex para Duration y Time
        duration_re = re.compile(r"Duration: (\d{2}):(\d{2}):(\d{2}\.\d{2})")
        time_re = re.compile(r"time=(\d{2}):(\d{2}):(\d{2}\.\d{2})")
        
        for line in process.stdout:
            print(line, end='', flush=True)
            
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
                    print(f" {pct}%", end='', flush=True)
            
        process.wait()
        
        if process.returncode == 0:
            print(f"\n[SUCCESS] Video comprimido: {output_path}")
            print(" 100%", end='', flush=True)
        else:
            print(f"\n[ERROR] Fallo la compresion de {input_path}")
    except Exception as e:
        print(f"[ERROR] Excepcion al comprimir {input_path}: {e}")

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
    
    args = parser.parse_args()
    
    ensure_requirements()
    
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
        
    for f in files_to_process:
        ext = f.suffix.lower()
        if ext in image_exts:
            out = get_output_path(f, args.output, args.suffix)
            compress_image(str(f), out, quality=args.quality)
        elif ext in video_exts:
            out = get_output_path(f, args.output, args.suffix)
            compress_video(str(f), out, crf=args.crf)

if __name__ == "__main__":
    main()
