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
        # Ocultar la consola de fondo en Windows
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)
            
        app = App()
        app.mainloop()
    else:
        # Volver a ejecutar el script con privilegios de administrador
        if getattr(sys, 'frozen', False):
            # Running as compiled executable
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, "", None, 1)
        else:
            # Running as python script
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{__file__}"', None, 1)
