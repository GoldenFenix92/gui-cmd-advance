import os
import shutil
import argparse
import sys

def get_targets(args):
    targets = []
    if getattr(args, 'user_temp', False):
        targets.append({"name": "Temp de Usuario", "path": os.environ.get('TEMP', '')})
    if getattr(args, 'win_temp', False):
        targets.append({"name": "Temp de Windows", "path": r"C:\Windows\Temp"})
    if getattr(args, 'prefetch', False):
        targets.append({"name": "Prefetch", "path": r"C:\Windows\Prefetch"})
    if getattr(args, 'win_update', False):
        targets.append({"name": "SoftwareDistribution (Descargas WinUpdate)", "path": r"C:\Windows\SoftwareDistribution\Download"})
    return targets

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-temp", action="store_true")
    parser.add_argument("--win-temp", action="store_true")
    parser.add_argument("--prefetch", action="store_true")
    parser.add_argument("--win-update", action="store_true")
    args, _ = parser.parse_known_args()
    
    targets = get_targets(args)
    if not targets:
        print("No se seleccionó ninguna carpeta para limpiar. Activa las opciones en el panel.")
        return
        
    print("Escaneando carpetas seleccionadas...")
    files_to_delete = []
    total_size = 0
    
    for t in targets:
        path = t["path"]
        if os.path.exists(path):
            for root, dirs, files in os.walk(path):
                for f in files:
                    fp = os.path.join(root, f)
                    try:
                        size = os.path.getsize(fp)
                        files_to_delete.append((fp, size))
                        total_size += size
                    except: pass
                    
    if total_size == 0:
        print("100%")
        print("No hay basura para eliminar en las carpetas seleccionadas.")
        return
        
    print(f"Total a limpiar: {total_size/(1024*1024):.2f} MB ({len(files_to_delete)} archivos)")
    
    freed = 0
    for i, (fp, size) in enumerate(files_to_delete):
        try:
            os.remove(fp)
            freed += size
        except: pass
        
        # Actualizar progreso cada 20 archivos o al final
        if i % 20 == 0 or i == len(files_to_delete) - 1:
            percent = int((freed / total_size) * 100) if total_size > 0 else 100
            print(f"{percent}%")
            sys.stdout.flush()
            
    # Limpiar directorios vacíos
    for t in targets:
        path = t["path"]
        if os.path.exists(path):
            for root, dirs, files in os.walk(path, topdown=False):
                for name in dirs:
                    dp = os.path.join(root, name)
                    try: os.rmdir(dp)
                    except: pass
                    
    print("100%")
    print(f"Limpieza completa. Se liberaron {freed/(1024*1024):.2f} MB.")

if __name__ == "__main__":
    main()
