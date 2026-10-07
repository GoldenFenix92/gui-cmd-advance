import os
import sys
import argparse
import subprocess
from pathlib import Path
from PIL import Image, ImageFile

# Habilitar la carga de imágenes truncadas/corruptas en Pillow
ImageFile.LOAD_TRUNCATED_IMAGES = True

from functions.utils import get_ffmpeg_path
from functions.task_memory import TaskMemory

def repair_image(input_path, output_path, reference_path=None):
    try:
        print(f"[{'REFERENCE' if reference_path else 'BASIC'} REPAIR] Intentando reparar imagen: {input_path}")
        # Abrir la imagen, Pillow intentará rellenar los datos faltantes porque LOAD_TRUNCATED_IMAGES = True
        img = Image.open(input_path)
        
        # Forzar la carga completa de la imagen para desencadenar el rescate de pixeles
        img.load()
        
        # Convertir a RGB para asegurar compatibilidad al guardar como JPEG
        if img.mode != 'RGB':
            img = img.convert('RGB')
            
        img.save(output_path, "JPEG", quality=95)
        print(f" [OK] Imagen reparada guardada en: {output_path}")
        return True
    except Exception as e:
        print(f" [ERROR] No se pudo reparar la imagen: {e}")
        return False

def repair_video(input_path, output_path, reference_path=None):
    ffmpeg = get_ffmpeg_path()
    
    # Intento 1: Remuxing ignorando errores (Copia directa, rápido)
    print(f"[{'REFERENCE' if reference_path else 'BASIC'} REPAIR] Intento 1 (Remux) en video: {input_path}")
    cmd_remux = [
        ffmpeg, "-y", 
        "-err_detect", "ignore_err", 
        "-i", str(input_path), 
        "-c", "copy", 
        str(output_path)
    ]
    
    try:
        result = subprocess.run(cmd_remux, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode == 0 and Path(output_path).exists() and Path(output_path).stat().st_size > 1024:
            print(f" [OK] Video reparado (Remux) guardado en: {output_path}")
            return True
    except Exception as e:
        print(f" [WARN] Fallo el Intento 1: {e}")

    # Intento 2: Re-codificación forzada (Más lento, pero rescata frames viables)
    print(f"[REPAIR] Intento 2 (Re-encode) en video: {input_path}")
    cmd_reencode = [
        ffmpeg, "-y", 
        "-err_detect", "ignore_err",
        "-i", str(input_path), 
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        str(output_path)
    ]
    
    try:
        result = subprocess.run(cmd_reencode, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode == 0 and Path(output_path).exists() and Path(output_path).stat().st_size > 1024:
            print(f" [OK] Video reparado (Re-encode) guardado en: {output_path}")
            return True
        else:
            print(f" [ERROR] FFmpeg no pudo reparar el video de forma nativa.")
            if reference_path:
                print(f" [INFO] Nota: Se proporcionó un archivo de referencia. Para reparaciones profundas de la cabecera 'moov', se requiere una herramienta externa especializada como 'untrunc'.")
            return False
    except Exception as e:
        print(f" [ERROR] Ocurrió un error en la re-codificación: {e}")
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

def main():
    parser = argparse.ArgumentParser(description="Reparador Avanzado de Multimedia (Fotos y Videos)")
    parser.add_argument("--input", required=True, nargs='+', help="Archivo o carpeta de origen")
    parser.add_argument("--output", help="Carpeta de destino (opcional)")
    parser.add_argument("--reference", help="Archivo saludable de referencia de la misma cámara (opcional)")
    parser.add_argument("--suffix", default="_reparado", help="Sufijo para archivos reparados")
    
    args = parser.parse_args()

    files_to_process = []
    
    for inp in args.input:
        input_path = Path(inp)
        if input_path.is_file():
            files_to_process.append(input_path)
        elif input_path.is_dir():
            for f in input_path.rglob("*"):
                if f.is_file():
                    files_to_process.append(f)

    if not files_to_process:
        print("No se encontraron archivos para procesar.")
        sys.exit(1)

    image_exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}
    video_exts = {".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv", ".webm", ".m4v"}

    success_count = 0
    fail_count = 0

    context = "_".join(args.input)
    memory = TaskMemory("media_repair", context)
    resumed_count = memory.get_processed_count()

    print("==================================================================================")
    print(" INICIANDO REPARACIÓN DE MULTIMEDIA")
    print(f" Total de archivos encontrados: {len(files_to_process)}")
    if args.reference:
        print(f" Usando archivo de referencia: {args.reference}")
    if resumed_count > 0:
        print(f" Reanudando tarea... Saltando {resumed_count} archivos reparados previamente.")
    print("==================================================================================\n")

    skipped_count = 0
    total_files = len(files_to_process)

    for i, f in enumerate(files_to_process):
        fp_str = str(f)
        if memory.is_processed(fp_str):
            skipped_count += 1
            if (i+1) == total_files or (i+1) % 10 == 0:
                print(f"{int(((i+1)/total_files)*100)}%")
            continue
            
        ext = f.suffix.lower()
        out_path = get_output_path(f, args.output, args.suffix)
        
        if ext in image_exts:
            if repair_image(fp_str, out_path, args.reference):
                success_count += 1
            else:
                fail_count += 1
        elif ext in video_exts:
            if repair_video(fp_str, out_path, args.reference):
                success_count += 1
            else:
                fail_count += 1
                
        if ext in image_exts or ext in video_exts:
            memory.mark_processed(fp_str)
            
        # Verificar pausa
        if TaskMemory.check_pause_signal():
            print("\n=======================================================")
            print("🛑 PROCESO POSPUESTO POR EL USUARIO 🛑")
            print(f"Estado guardado. Archivos procesados hasta ahora: {memory.get_processed_count()}")
            print("Puedes reanudar este proceso más tarde ejecutando el mismo comando.")
            print("=======================================================")
            import sys
            sys.exit(0)

    memory.clear()
        else:
            print(f"[SKIP] Formato no soportado: {f.name}")

    print("\n==================================================================================")
    print(" RESUMEN DE REPARACIÓN")
    print("==================================================================================")
    print(f" Exitosos: {success_count}")
    print(f" Fallidos: {fail_count}")
    print("==================================================================================")

if __name__ == "__main__":
    main()
