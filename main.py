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
            import compressor
            sys.argv.pop(1)
            compressor.main()
            sys.exit(0)
        elif sys.argv[1] == "--run-duplicate-finder":
            import duplicate_finder
            sys.argv.pop(1)
            app = duplicate_finder.DuplicateFinderApp()
            app.mainloop()
            sys.exit(0)
        elif sys.argv[1] == "--run-temp-cleaner":
            import temp_cleaner
            sys.argv.pop(1)
            app = temp_cleaner.TempCleanerApp()
            app.mainloop()
            sys.exit(0)
        elif sys.argv[1] == "--run-advanced-search":
            import advanced_search
            sys.argv.pop(1)
            app = advanced_search.AdvancedSearchApp()
            app.mainloop()
            sys.exit(0)
        elif sys.argv[1] == "--run-smart-info":
            import smart_info
            sys.argv.pop(1)
            app = smart_info.SmartInfoApp()
            app.mainloop()
            sys.exit(0)
        elif sys.argv[1] == "--run-vault":
            import credentials_vault
            sys.argv.pop(1)
            app = credentials_vault.CredentialsVaultApp()
            app.mainloop()
            sys.exit(0)
        elif sys.argv[1] == "--run-media-repair":
            import media_repair
            sys.argv.pop(1)
            media_repair.main()
            sys.exit(0)
            
    if is_admin():
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)
            
        try:
            app = App()
            app.mainloop()
        except Exception as e:
            import traceback, os
            with open(os.path.join(os.path.dirname(__file__), "crash.log"), "w") as f:
                f.write(traceback.format_exc())
    else:
        # Volver a ejecutar el script con privilegios de administrador
        if getattr(sys, 'frozen', False):
            # Running as compiled executable
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, "", None, 1)
        else:
            # Running as python script
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{__file__}"', None, 1)
