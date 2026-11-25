import os
import sys

def get_resource_path(relative_path):
    """
    Retorna la ruta absoluta al recurso, compatible con la ejecución
    normal de Python y la ejecución empaquetada con PyInstaller.
    """
    if getattr(sys, 'frozen', False):
        # Si se ejecuta como exe de PyInstaller
        return os.path.join(sys._MEIPASS, relative_path)
    # Si se ejecuta como script normal
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), relative_path)

def get_user_data_path(relative_path):
    base_dir = os.path.join(os.environ.get("SystemDrive", "C:") + os.sep, "GuiCmdAdvance")
    os.makedirs(base_dir, exist_ok=True)
    return os.path.join(base_dir, relative_path)

def get_ffmpeg_path():
    """
    Retorna la ruta al ejecutable de ffmpeg. Busca en los datos persistentes del usuario.
    """
    local_ffmpeg = get_user_data_path(os.path.join("tools", "ffmpeg.exe"))
    if os.path.exists(local_ffmpeg):
        return local_ffmpeg
    return "ffmpeg"


def safe_print(text="", end="\n", flush=True):
    """Imprime texto en consola de forma segura en Windows (incluso con sys.stdout=None en --windowed)."""
    if sys.stdout is None:
        return
    try:
        print(text, end=end, flush=flush)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "cp1252"
        safe_text = str(text).encode(enc, errors="replace").decode(enc, errors="replace")
        print(safe_text, end=end, flush=flush)
    except Exception:
        pass


def center_window(window, width, height):
    """Centra una ventana Tkinter/ttkbootstrap en la pantalla."""
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    x = int((screen_width / 2) - (width / 2))
    y = int((screen_height / 2) - (height / 2))
    window.geometry(f"{width}x{height}+{x}+{y}")


def send_to_recycle_bin(file_path):
    """
    Envía un archivo a la Papelera de Reciclaje de Windows usando SHFileOperationW (FOF_ALLOWUNDO).
    No realiza borrado permanente si falla. Retorna (True, '') o (False, mensaje_error).
    """
    abs_path = os.path.abspath(str(file_path))
    if not os.path.exists(abs_path):
        return False, "El archivo no existe."

    if os.name != "nt":
        return False, "La Papelera de Reciclaje nativa solo está soportada en Windows."

    try:
        import ctypes
        from ctypes import wintypes

        class SHFILEOPSTRUCTW(ctypes.Structure):
            _fields_ = [
                ("hwnd", wintypes.HWND),
                ("wFunc", wintypes.UINT),
                ("pFrom", wintypes.LPCWSTR),
                ("pTo", wintypes.LPCWSTR),
                ("fFlags", ctypes.c_uint16),
                ("fAnyOperationsAborted", wintypes.BOOL),
                ("hNameMappings", ctypes.c_void_p),
                ("lpszProgressTitle", wintypes.LPCWSTR),
            ]

        FO_DELETE = 0x0003
        FOF_SILENT = 0x0004
        FOF_NOCONFIRMATION = 0x0010
        FOF_ALLOWUNDO = 0x0040
        FOF_NOERRORUI = 0x0400

        op = SHFILEOPSTRUCTW()
        op.hwnd = None
        op.wFunc = FO_DELETE
        op.pFrom = abs_path + "\0\0"
        op.pTo = None
        op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI
        op.fAnyOperationsAborted = False
        op.hNameMappings = None
        op.lpszProgressTitle = None

        rc = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
        if rc == 0 and not op.fAnyOperationsAborted:
            return True, ""
        return False, f"SHFileOperationW código {rc} (cancelado={bool(op.fAnyOperationsAborted)})"
    except Exception as e:
        return False, str(e)

def apply_window_theme(window):
    """Aplica ícono de la aplicación y barra de título Win32 acorde al tema activo de ttkbootstrap."""
    try:
        from functions import ui_theme
        ui_theme.apply_window_chrome(window)
    except Exception:
        pass
