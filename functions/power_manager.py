import ctypes
import os
import subprocess
import sys

# Constantes Win32 SetThreadExecutionState
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002


def prevent_sleep(keep_display=False):
    """Evita que Windows entre en suspensión o hibernación mientras una tarea está activa.

    Con keep_display=False (por defecto), permite que la pantalla se apague para ahorrar energía
    sin detener ni suspender la ejecución en curso.
    """
    if sys.platform != "win32":
        return False
    flags = ES_CONTINUOUS | ES_SYSTEM_REQUIRED
    if keep_display:
        flags |= ES_DISPLAY_REQUIRED
    try:
        res = ctypes.windll.kernel32.SetThreadExecutionState(flags)
        return res != 0
    except Exception:
        return False


def allow_sleep():
    """Restaura la política normal de suspensión/hibernación de Windows."""
    if sys.platform != "win32":
        return False
    try:
        res = ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
        return res != 0
    except Exception:
        return False


def get_desktop_path():
    """Resuelve la ruta real del Escritorio del usuario en Windows (incluyendo OneDrive si aplica)."""
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
            ) as key:
                val, _ = winreg.QueryValueEx(key, "Desktop")
                expanded = os.path.expandvars(val)
                if expanded and os.path.isdir(expanded):
                    return expanded
        except Exception:
            pass
    fallback = os.path.join(os.path.expanduser("~"), "Desktop")
    return fallback


def execute_shutdown_now(reason="GUI CMD Advance: Tarea finalizada."):
    """Ejecuta el apagado inmediato del equipo sin mostrar ventana negra."""
    if sys.platform != "win32":
        return 1
    try:
        proc = subprocess.run(
            ["shutdown", "/s", "/t", "0", "/c", reason],
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            timeout=10,
        )
        return proc.returncode
    except Exception:
        return 1


def cancel_scheduled_shutdown():
    """Cancela cualquier apagado programado de Windows."""
    if sys.platform != "win32":
        return 1
    try:
        proc = subprocess.run(
            ["shutdown", "/a"],
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            timeout=10,
        )
        return proc.returncode
    except Exception:
        return 1
