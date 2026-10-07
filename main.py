import ctypes
import sys
from gui_app import App

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
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
        elif sys.argv[1] == "--run-file-compressor":
            from functions import file_compressor
            sys.argv.pop(1)
            app = file_compressor.FileCompressorApp()
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
        elif sys.argv[1] == "--run-7z":
            from gui_app import get_user_data_path
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
            import sys
            
            exe = get_user_data_path("tools\\7za.exe")
            if not os.path.exists(exe):
                print("Error: No se encontro 7za.exe en tools\\.")
                sys.exit(1)
                
            cmd = [exe]
            if args.action == "compress":
                cmd.extend(["a", args.dest, args.src, "-bsp1", "-ssw"])
                if args.pwd: cmd.append(f"-p{args.pwd}")
                if args.level: cmd.append(args.level)
                if args.threads: cmd.append(f"-mmt{args.threads}")
                if args.split and args.split != "Sin dividir":
                    split_val = args.split.split(" ")[0]
                    cmd.append(f"-v{split_val}")
                print("Comprimiendo...")
            elif args.action == "extract":
                cmd.extend(["x", args.src, f"-o{args.dest}", "-y", "-bsp1"])
                if args.pwd: cmd.append(f"-p{args.pwd}")
                if args.threads: cmd.append(f"-mmt{args.threads}")
                print(f"Descomprimiendo en: {args.dest}")
            elif args.action == "analyze":
                cmd.extend(["t", args.src])
                if args.pwd: cmd.append(f"-p{args.pwd}")
                if args.threads: cmd.append(f"-mmt{args.threads}")
                print("Analizando integridad...")
                
            try:
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
                for line in proc.stdout:
                    print(line, end="")
                proc.wait()
            except Exception as e:
                print(f"Error ejecutando 7z: {e}")
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
