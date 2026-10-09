import os
import re
import sys

def sanitize_name(name):
    # Caracteres inválidos en Windows: < > : " / \ | ? *
    invalid_chars = r'[<>:"/\\|?*]'
    new_name = re.sub(invalid_chars, '_', name)
    
    # Windows no permite puntos o espacios al final
    new_name = new_name.rstrip(' .')
    
    if not new_name:
        new_name = "Archivo_Renombrado"
        
    return new_name if new_name != name else None

def main(folder, recursive=False):
    if not folder or not os.path.isdir(folder):
        print(f"Error: La ruta '{folder}' no es una carpeta válida.")
        sys.exit(1)
        
    print(f"Iniciando escaneo y reparación de nombres en: {folder}\n")
    renamed_count = 0
    error_count = 0
    
    if recursive:
        items_to_process = list(os.walk(folder, topdown=False))
    else:
        try:
            items = os.listdir(folder)
            files = [f for f in items if os.path.isfile(os.path.join(folder, f))]
            dirs = [d for d in items if os.path.isdir(os.path.join(folder, d))]
            items_to_process = [(folder, dirs, files)]
        except Exception as e:
            print(f"Error accediendo a la carpeta: {e}")
            sys.exit(1)
            
    # Renombrar (bottom-up si es recursivo) para evitar romper rutas
    analyzed_count = 0
    for root, dirs, files in items_to_process:
        analyzed_count += len(files) + len(dirs)
        # Archivos
        for name in files:
            new_name = sanitize_name(name)
            if new_name:
                old_path = os.path.join(root, name)
                new_path = os.path.join(root, new_name)
                
                # Manejar duplicados si el nuevo nombre ya existe
                counter = 1
                base, ext = os.path.splitext(new_name)
                while os.path.exists(new_path):
                    new_path = os.path.join(root, f"{base}_{counter}{ext}")
                    counter += 1
                    
                try:
                    os.rename(old_path, new_path)
                    print(f"[OK] Archivo renombrado: {name} -> {os.path.basename(new_path)}")
                    renamed_count += 1
                except Exception as e:
                    print(f"[ERROR] No se pudo renombrar el archivo '{name}': {e}")
                    error_count += 1
                    
        # Carpetas
        for name in dirs:
            new_name = sanitize_name(name)
            if new_name:
                old_path = os.path.join(root, name)
                new_path = os.path.join(root, new_name)
                
                counter = 1
                while os.path.exists(new_path):
                    new_path = os.path.join(root, f"{new_name}_{counter}")
                    counter += 1
                    
                try:
                    os.rename(old_path, new_path)
                    print(f"[OK] Carpeta renombrada: {name} -> {os.path.basename(new_path)}")
                    renamed_count += 1
                except Exception as e:
                    print(f"[ERROR] No se pudo renombrar la carpeta '{name}': {e}")
                    error_count += 1
                    
    print(f"\nProceso finalizado. Total analizados: {analyzed_count} | Renombrados: {renamed_count} | Errores: {error_count}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("folder")
    args = parser.parse_args()
    main(args.folder)
