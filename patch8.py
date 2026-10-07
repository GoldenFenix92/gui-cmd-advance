import os

compressor_path = r"f:\Proyectos\gui-cmd-advance\functions\compressor.py"
with open(compressor_path, "r", encoding="utf-8") as f:
    code = f.read()

# Import TaskMemory
if "from functions.task_memory import TaskMemory" not in code:
    code = code.replace("from functions.utils import get_ffmpeg_path", "from functions.utils import get_ffmpeg_path\nfrom functions.task_memory import TaskMemory")

# Add Memory logic in main
old_main = '''    results = []
    total_files = len(files_to_process)
    
    for i, f in enumerate(files_to_process):
        ext = f.suffix.lower()
        if ext in image_exts:
            out = get_output_path(f, args.output, args.suffix)
            res = compress_image(str(f), out, quality=args.quality, file_index=i, total_files=total_files)
            if res: results.append(res)
        elif ext in video_exts:
            out = get_output_path(f, args.output, args.suffix, force_ext=".mp4")
            res = compress_video(str(f), out, crf=args.crf, hw=args.hw, preset=args.preset, threads=args.threads, file_index=i, total_files=total_files)
            if res: results.append(res)

    elapsed = time.time() - start_time'''

new_main = '''    # Inicializar memoria
    context = "_".join(args.input)
    memory = TaskMemory("media_compressor", context)
    resumed_count = memory.get_processed_count()
    if resumed_count > 0:
        print(f"Reanudando tarea... Se omitirán {resumed_count} archivos previamente procesados.\\n")

    results = []
    total_files = len(files_to_process)
    skipped = 0
    
    for i, f in enumerate(files_to_process):
        fp_str = str(f)
        if memory.is_processed(fp_str):
            skipped += 1
            if (i+1) == total_files or (i+1) % 10 == 0:
                print(f"{int(((i+1)/total_files)*100)}%")
            continue
            
        ext = f.suffix.lower()
        res = None
        if ext in image_exts:
            out = get_output_path(f, args.output, args.suffix)
            res = compress_image(fp_str, out, quality=args.quality, file_index=i, total_files=total_files)
            if res: results.append(res)
        elif ext in video_exts:
            out = get_output_path(f, args.output, args.suffix, force_ext=".mp4")
            res = compress_video(fp_str, out, crf=args.crf, hw=args.hw, preset=args.preset, threads=args.threads, file_index=i, total_files=total_files)
            if res: results.append(res)
            
        if ext in image_exts or ext in video_exts:
            memory.mark_processed(fp_str)
            
        # Verificar pausa
        if TaskMemory.check_pause_signal():
            print("\\n=======================================================")
            print("🛑 PROCESO POSPUESTO POR EL USUARIO 🛑")
            print(f"Estado guardado. Archivos procesados hasta ahora: {memory.get_processed_count()}")
            print("Puedes reanudar este proceso más tarde ejecutando el mismo comando.")
            print("=======================================================")
            sys.exit(0)

    memory.clear()
    elapsed = time.time() - start_time'''

code = code.replace(old_main, new_main)

with open(compressor_path, "w", encoding="utf-8") as f:
    f.write(code)

print("compressor.py patched for TaskMemory.")
