import os
import argparse
import sys
from functions.task_memory import TaskMemory
from functions.utils import safe_print

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
        safe_print("No se seleccionó ninguna carpeta para limpiar. Activa las opciones en el panel.")
        return
        
    # Inicializar memoria de tarea basada en los argumentos
    context = "_".join([t["name"] for t in targets])
    memory = TaskMemory("temp_cleaner", context)
    
    resumed_count = memory.get_processed_count()
    if resumed_count > 0:
        safe_print(f"Reanudando tarea... Se omitirán {resumed_count} archivos previamente eliminados.\n")
    else:
        safe_print("Escaneando carpetas seleccionadas...\n")
        
    files_to_delete = []
    total_size = 0
    
    protected_meipass = os.path.normcase(os.path.abspath(getattr(sys, "_MEIPASS", ""))) if getattr(sys, "_MEIPASS", None) else ""
    for t in targets:
        path = t["path"]
        if os.path.exists(path):
            for root, dirs, files in os.walk(path):
                # Remover junctions/symlinks y carpetas activas de PyInstaller (_MEI*) para no dañar el .exe en ejecución
                filtered_dirs = []
                for d in dirs:
                    full_d = os.path.join(root, d)
                    if os.path.islink(full_d) or (hasattr(os.path, 'isjunction') and os.path.isjunction(full_d)):
                        continue
                    if d.startswith("_MEI"):
                        continue
                    if protected_meipass and os.path.normcase(os.path.abspath(full_d)) == protected_meipass:
                        continue
                    filtered_dirs.append(d)
                dirs[:] = filtered_dirs
                for f in files:
                    fp = os.path.join(root, f)
                    try:
                        size = os.path.getsize(fp)
                        files_to_delete.append((fp, size))
                        total_size += size
                    except Exception: pass
                    
    if total_size == 0 and resumed_count == 0:
        safe_print("100%")
        safe_print("No hay basura para eliminar en las carpetas seleccionadas.")
        return
        
    safe_print(f"Total a limpiar detectado: {total_size/(1024*1024):.2f} MB ({len(files_to_delete)} archivos)")
    
    freed = 0
    skipped = 0
    
    for i, (fp, size) in enumerate(files_to_delete):
        # Revisar Memoria
        if memory.is_processed(fp):
            skipped += 1
            freed += size
            continue
            
        try:
            os.remove(fp)
            freed += size
            memory.mark_processed(fp)
        except Exception: pass
        
        # Verificar pausa
        if TaskMemory.check_pause_signal():
            memory.flush()
            safe_print("\n=======================================================")
            safe_print("[PAUSA] PROCESO POSPUESTO POR EL USUARIO")
            safe_print(f"Estado guardado. Archivos procesados hasta ahora: {memory.get_processed_count()}")
            safe_print("Puedes reanudar este proceso más tarde ejecutando el mismo comando.")
            safe_print("=======================================================")
            sys.exit(0)
        
        # Actualizar progreso
        if (i - skipped) % 20 == 0 or i == len(files_to_delete) - 1:
            percent = int((freed / total_size) * 100) if total_size > 0 else 100
            safe_print(f"{percent}%")
            
    # Al terminar exitosamente, limpiar directorios vacíos
    for t in targets:
        path = t["path"]
        if os.path.exists(path):
            for root, dirs, files in os.walk(path, topdown=False):
                for name in dirs:
                    dp = os.path.join(root, name)
                    try: os.rmdir(dp)
                    except Exception: pass
                    
    safe_print("100%")
    safe_print(f"Limpieza completa. Se liberaron {(freed)/(1024*1024):.2f} MB.")
    memory.clear()

if __name__ == "__main__":
    main()
