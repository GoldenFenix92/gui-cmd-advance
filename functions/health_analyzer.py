import os
import sys
import argparse
import subprocess
from pathlib import Path
import time
from functions.utils import get_ffmpeg_path

def ensure_requirements():
    try:
        from PIL import Image
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow"])

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
        # Modo rápido: revisa los primeros 5 frames
        cmd.extend(["-frames:v", "5"])
        
    if threads > 0:
        cmd.extend(["-threads", str(threads)])
        
    cmd.extend(["-f", "null", "-"])
    
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    BELOW_NORMAL_PRIORITY_CLASS = 0x00004000
    
    try:
        process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, startupinfo=startupinfo, creationflags=BELOW_NORMAL_PRIORITY_CLASS, encoding='utf-8', errors='ignore')
        if process.returncode != 0 or len(process.stderr.strip()) > 0:
            return False, process.stderr.strip()[:300]
        return True, ""
    except Exception as e:
        return False, str(e)

def safe_str(s):
    try:
        s.encode(sys.stdout.encoding or 'utf-8')
        return s
    except UnicodeEncodeError:
        return s.encode('ascii', errors='replace').decode('ascii')

def main(folder, recursive=False, threads=0, quick_mode=False):
    ensure_requirements()
    if not folder or not os.path.isdir(folder):
        print(f"Error: La ruta '{folder}' no es una carpeta válida.")
        sys.exit(1)
        
    print(f"Iniciando Analizador de Salud Multimedia en: {safe_str(folder)}")
    if quick_mode:
        print("Modo de escaneo: Rápido (Solo cabeceras y primeros frames)")
    else:
        print("Modo de escaneo: Profundo (Lectura completa de inicio a fin)")
    print("")
    
    image_exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}
    video_exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".3gp", ".mpeg", ".mpg", ".ts"}
    
    files_to_check = []
    
    if recursive:
        for root, dirs, files in os.walk(folder):
            for f in files:
                ext = Path(f).suffix.lower()
                if ext in image_exts or ext in video_exts:
                    files_to_check.append(os.path.join(root, f))
    else:
        for f in os.listdir(folder):
            path = os.path.join(folder, f)
            if os.path.isfile(path):
                ext = Path(path).suffix.lower()
                if ext in image_exts or ext in video_exts:
                    files_to_check.append(path)
                
    corrupt_files = []
    healthy_count = 0
    total = len(files_to_check)
    
    if total == 0:
        print("No se encontraron archivos multimedia compatibles para analizar.")
        sys.exit(0)
        
    for i, file_path in enumerate(files_to_check):
        ext = Path(file_path).suffix.lower()
        is_healthy = True
        error_msg = ""
        
        safe_name = safe_str(os.path.basename(file_path))
        print(f"Analizando [{i+1}/{total}]: {safe_name}", end="\r", flush=True)
        
        if ext in image_exts:
            is_healthy, error_msg = check_image(file_path)
        elif ext in video_exts:
            is_healthy, error_msg = check_video(file_path, threads, quick_mode)
            
        print(" " * 100, end="\r") # Limpiar linea
        
        if is_healthy:
            healthy_count += 1
            print(f"[OK] {safe_name}")
        else:
            corrupt_files.append((file_path, error_msg))
            print(f"[CORRUPTO] {safe_name}")
            
    print("\n\n=======================================================")
    print("REPORTE FINAL DE SALUD MULTIMEDIA")
    print("=======================================================")
    print(f"Archivos Sanos: {healthy_count}")
    print(f"Archivos Corruptos: {len(corrupt_files)}")
    
    if corrupt_files:
        print("\nLista de archivos corruptos encontrados:")
        for fp, err in corrupt_files:
            print(f" - {safe_str(os.path.basename(fp))}")
            print(f"   Motivo: {err.replace(chr(10), ' | ')}")
    print("=======================================================")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("folder")
    parser.add_argument("--recursive", action="store_true")
    parser.add_argument("--threads", type=int, default=0)
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args()
    main(args.folder, args.recursive, args.threads, args.quick)
