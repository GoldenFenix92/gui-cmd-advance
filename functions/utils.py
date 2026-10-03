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

def get_ffmpeg_path():
    """
    Retorna la ruta al ejecutable de ffmpeg. Primero busca en la carpeta
    local tools/ffmpeg.exe. Si no existe, asume que está en el PATH del sistema.
    """
    local_ffmpeg = get_resource_path(os.path.join("tools", "ffmpeg.exe"))
    if os.path.exists(local_ffmpeg):
        return local_ffmpeg
    return "ffmpeg"
