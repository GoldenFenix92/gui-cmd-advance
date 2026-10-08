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

def apply_window_theme(window):
    def _apply():
        try:
            window.iconbitmap(get_resource_path('resources/app_icon.ico'))
        except: pass
        import customtkinter as ctk
        if ctk.get_appearance_mode().lower() == 'dark':
            try:
                import ctypes
                window.update()
                hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
                DWMWA_USE_IMMERSIVE_DARK_MODE = 20
                value = ctypes.c_int(2)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(value), ctypes.sizeof(value))
            except: pass
    window.after(200, _apply)

# Monkey-patching para aplicar el icono y tema a TODAS las ventanas automáticamente
import customtkinter as ctk

if not hasattr(ctk, '_theme_patched'):
    ctk._theme_patched = True
    _original_ctk_init = ctk.CTk.__init__
    _original_toplevel_init = ctk.CTkToplevel.__init__

    def _patched_ctk_init(self, *args, **kwargs):
        _original_ctk_init(self, *args, **kwargs)
        apply_window_theme(self)

    def _patched_toplevel_init(self, *args, **kwargs):
        _original_toplevel_init(self, *args, **kwargs)
        apply_window_theme(self)

    ctk.CTk.__init__ = _patched_ctk_init
    ctk.CTkToplevel.__init__ = _patched_toplevel_init
