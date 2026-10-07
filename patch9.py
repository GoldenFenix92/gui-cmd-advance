import os

repair_path = r"f:\Proyectos\gui-cmd-advance\functions\media_repair.py"
with open(repair_path, "r", encoding="utf-8") as f:
    code = f.read()

if "from functions.task_memory import TaskMemory" not in code:
    code = code.replace("from functions.utils import get_ffmpeg_path", "from functions.utils import get_ffmpeg_path\nfrom functions.task_memory import TaskMemory")

old_main = '''    print("==================================================================================")
    print(" INICIANDO REPARACIÓN DE MULTIMEDIA")
    print(f" Total de archivos encontrados: {len(files_to_process)}")
    if args.reference:
        print(f" Usando archivo de referencia: {args.reference}")
    print("==================================================================================\\n")

    for f in files_to_process:
        ext = f.suffix.lower()
        out_path = get_output_path(f, args.output, args.suffix)
        
        if ext in image_exts:
            if repair_image(f, out_path, args.reference):
                success_count += 1
            else:
                fail_count += 1
        elif ext in video_exts:
            if repair_video(f, out_path, args.reference):
                success_count += 1
            else:
                fail_count += 1'''

new_main = '''    context = "_".join(args.input)
    memory = TaskMemory("media_repair", context)
    resumed_count = memory.get_processed_count()

    print("==================================================================================")
    print(" INICIANDO REPARACIÓN DE MULTIMEDIA")
    print(f" Total de archivos encontrados: {len(files_to_process)}")
    if args.reference:
        print(f" Usando archivo de referencia: {args.reference}")
    if resumed_count > 0:
        print(f" Reanudando tarea... Saltando {resumed_count} archivos reparados previamente.")
    print("==================================================================================\\n")

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
            print("\\n=======================================================")
            print("🛑 PROCESO POSPUESTO POR EL USUARIO 🛑")
            print(f"Estado guardado. Archivos procesados hasta ahora: {memory.get_processed_count()}")
            print("Puedes reanudar este proceso más tarde ejecutando el mismo comando.")
            print("=======================================================")
            import sys
            sys.exit(0)

    memory.clear()'''

code = code.replace(old_main, new_main)

with open(repair_path, "w", encoding="utf-8") as f:
    f.write(code)

print("media_repair.py patched for TaskMemory.")
