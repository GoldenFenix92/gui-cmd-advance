import ctypes
import sys

for _stream in (sys.stdout, sys.stderr):
    if _stream is not None and hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

from gui_app import App

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "--run-compressor":
            from functions import compressor
            sys.argv.pop(1)
            compressor.main()
            sys.exit(0)
        elif sys.argv[1] == "--run-duplicate-finder":
            from functions import duplicate_finder
            sys.argv.pop(1)
            import argparse
            parser = argparse.ArgumentParser()
            parser.add_argument("folder", nargs="?", default="")
            parser.add_argument("--hw", default="cpu")
            parser.add_argument("--mode", default="both")
            parser.add_argument("--threads", type=int, default=0)
            args = parser.parse_args(sys.argv[1:])
            app = duplicate_finder.DuplicateFinderApp(folder=args.folder, hw=args.hw, mode=args.mode, threads=args.threads)
            app.mainloop()
            sys.exit(0)
        elif sys.argv[1] == "--run-temp-cleaner":
            from functions import temp_cleaner
            sys.argv.pop(1)
            temp_cleaner.main()
            sys.exit(0)
        elif sys.argv[1] == "--run-process-manager":
            from functions import process_manager
            sys.argv.pop(1)
            process_manager.main()
            sys.exit(0)
        elif sys.argv[1] == "--run-advanced-search":
            from functions import advanced_search
            sys.argv.pop(1)
            app = advanced_search.AdvancedSearchApp()
            app.mainloop()
            sys.exit(0)
        elif sys.argv[1] == "--run-smart-info":
            from functions import smart_info
            sys.argv.pop(1)
            app = smart_info.SmartInfoApp()
            app.mainloop()
            sys.exit(0)
        elif sys.argv[1] == "--run-vault":
            from functions import credentials_vault_cli
            sys.argv.pop(1)
            credentials_vault_cli.main_cli()
            sys.exit(0)
        elif sys.argv[1] == "--run-name-sanitizer":
            from functions import name_sanitizer
            sys.argv.pop(1)
            import argparse
            parser = argparse.ArgumentParser()
            parser.add_argument("folder", nargs="?", default="")
            parser.add_argument("--recursive", action="store_true")
            args, _ = parser.parse_known_args(sys.argv[1:])
            name_sanitizer.main(args.folder, recursive=args.recursive)
            sys.exit(0)
        elif sys.argv[1] == "--run-health-analyzer":
            from functions import health_analyzer
            sys.argv.pop(1)
            import argparse
            parser = argparse.ArgumentParser()
            parser.add_argument("folder", nargs="?", default="")
            parser.add_argument("--recursive", action="store_true")
            parser.add_argument("--threads", type=int, default=0)
            parser.add_argument("--quick", action="store_true")
            parser.add_argument("--media-type", choices=["all", "videos", "images"], default="all")
            parser.add_argument("--manifest-out", default=None)
            args, _ = parser.parse_known_args(sys.argv[1:])
            health_analyzer.main(
                args.folder,
                recursive=args.recursive,
                threads=args.threads,
                quick_mode=args.quick,
                media_type=args.media_type,
                manifest_out=args.manifest_out,
            )
            sys.exit(0)
        elif sys.argv[1] == "--run-7z":
            from functions.utils import get_user_data_path, safe_print
            sys.argv.pop(1)
            import argparse
            parser = argparse.ArgumentParser()
            parser.add_argument("--action")
            parser.add_argument("--src")
            parser.add_argument("--dest")
            parser.add_argument("--pwd", default="")
            parser.add_argument("--level", default="")
            parser.add_argument("--threads", default="")
            parser.add_argument("--split", default="")
            args, _ = parser.parse_known_args()
            
            import subprocess, os
            
            exe = get_user_data_path("tools\\7za.exe")
            if not os.path.exists(exe):
                safe_print("Error: No se encontro 7za.exe en tools\\.")
                sys.exit(1)
                
            cmd = [exe]
            if args.action == "compress":
                if not args.src or not args.dest:
                    safe_print("Error: Debes seleccionar la ruta origen (--src) y el archivo destino (--dest).")
                    sys.exit(1)
                cmd.extend(["a", args.dest, args.src, "-bsp1", "-ssw"])
                if args.pwd: cmd.append(f"-p{args.pwd}")
                if args.level: cmd.append(args.level)
                if args.threads: cmd.append(f"-mmt{args.threads}")
                if args.split and args.split != "Sin dividir":
                    split_val = args.split.split(" ")[0]
                    cmd.append(f"-v{split_val}")
                safe_print("Comprimiendo...")
            elif args.action == "extract":
                if not args.src or not args.dest:
                    safe_print("Error: Debes seleccionar el archivo comprimido (--src) y la carpeta destino (--dest).")
                    sys.exit(1)
                cmd.extend(["x", args.src, f"-o{args.dest}", "-y", "-bsp1"])
                if args.pwd: cmd.append(f"-p{args.pwd}")
                if args.threads: cmd.append(f"-mmt{args.threads}")
                safe_print(f"Descomprimiendo en: {args.dest}")
            elif args.action == "analyze":
                if not args.src:
                    safe_print("Error: Debes seleccionar el archivo a analizar (--src).")
                    sys.exit(1)
                cmd.extend(["t", args.src])
                if args.pwd: cmd.append(f"-p{args.pwd}")
                if args.threads: cmd.append(f"-mmt{args.threads}")
                safe_print("Analizando integridad...")
            else:
                safe_print(f"Error: Acción de 7-Zip no reconocida: {args.action}")
                sys.exit(1)
                
            try:
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", bufsize=1, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                for line in proc.stdout:
                    safe_print(line, end="")
                proc.wait()
            except Exception as e:
                safe_print(f"Error ejecutando 7z: {e}")
            sys.exit(0)
        elif sys.argv[1] == "--run-media-repair":
            from functions import media_repair
            sys.argv.pop(1)
            media_repair.main()
            sys.exit(0)
        elif sys.argv[1] == "--run-office-deploy":
            from functions import office_deploy
            sys.argv.pop(1)
            app = office_deploy.OfficeDeployApp()
            app.mainloop()
            sys.exit(0)
        elif sys.argv[1] == "--run-disk-attributes":
            from functions import disk_attributes
            sys.argv.pop(1)
            disk_attributes.main()
            sys.exit(0)
        elif sys.argv[1] == "--run-usb-audit":
            from functions import usb_auditor
            sys.argv.pop(1)
            usb_auditor.main()
            sys.exit(0)
        elif sys.argv[1] == "--run-surface-scan":
            from functions import surface_scanner
            sys.argv.pop(1)
            surface_scanner.main()
            sys.exit(0)
        elif sys.argv[1] == "--run-sdelete":
            from functions import sdelete_runner
            sys.argv.pop(1)
            sdelete_runner.main()
            sys.exit(0)
        elif sys.argv[1] == "--run-ram-auditor":
            from functions import ram_auditor
            sys.argv.pop(1)
            ram_auditor.main()
            sys.exit(0)
        elif sys.argv[1] == "--run-media-studio":
            from functions import media_studio
            sys.argv.pop(1)
            sys.exit(media_studio.main())
        elif sys.argv[1] == "--run-ffmpeg-skill":
            from functions import ffmpeg_skill_runner
            sys.argv.pop(1)
            sys.exit(ffmpeg_skill_runner.main())
        elif sys.argv[1] == "--run-video-trimmer":
            from functions import video_trimmer
            sys.argv.pop(1)
            sys.exit(video_trimmer.main())
            
    if is_admin():
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)
            
        try:
            app = App()
            app.mainloop()
        except Exception as e:
            import traceback
            from functions.utils import get_user_data_path
            with open(get_user_data_path("crash.log"), "w") as f:
                f.write(traceback.format_exc())
    else:
        # Volver a ejecutar el script con privilegios de administrador
        if getattr(sys, 'frozen', False):
            # Running as compiled executable
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, "", None, 1)
        else:
            # Running as python script
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{__file__}"', None, 1)
