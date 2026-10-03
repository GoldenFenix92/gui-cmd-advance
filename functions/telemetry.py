import os
import sys
import json
import urllib.request
import threading
import subprocess
import ctypes
import traceback
import customtkinter as ctk
from tkinter import messagebox
from functions.utils import get_user_data_path
try:
    from version import __version__
except ImportError:
    __version__ = "0.0.0"

# ==============================================================
# CONFIGURACIÓN DEL DESARROLLADOR
# ==============================================================
GITHUB_REPO = "GoldenFenix92/gui-cmd-advance"
# Pon aquí tu URL del Webhook de Discord. Si está vacío, no se enviará nada.
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1556016800335007804/F6DCAMgpvrkVwIQVFPsdR_Kx5JYdunfCY_3xdgwNN5FcauFsDeSroYnb5-OhPU6CgHfy" 
# ==============================================================

def check_for_updates(master_win):
    """
    Comprueba de forma asíncrona si hay actualizaciones en GitHub.
    Si hay una versión mayor, muestra un diálogo de actualización.
    """
    def _check():
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                
            latest_tag = data.get("tag_name", "").replace("v", "").replace("-beta", "")
            current = __version__
            
            # Comparación muy básica (solo por si es diferente)
            if latest_tag and latest_tag != current:
                assets = data.get("assets", [])
                exe_url = None
                for asset in assets:
                    if asset["name"].endswith(".exe"):
                        exe_url = asset["browser_download_url"]
                        break
                
                if exe_url:
                    master_win.after(0, lambda: _prompt_update(master_win, data.get("tag_name"), data.get("body", ""), exe_url))
        except Exception as e:
            print(f"Error comprobando actualizaciones: {e}")

    threading.Thread(target=_check, daemon=True).start()

def _prompt_update(master_win, tag_name, release_notes, download_url):
    update_win = ctk.CTkToplevel(master_win)
    update_win.title("¡Nueva versión disponible!")
    update_win.geometry("500x450")
    update_win.transient(master_win)
    update_win.grab_set()
    
    update_win.update_idletasks()
    x = int(master_win.winfo_x() + (master_win.winfo_width() / 2) - (500 / 2))
    y = int(master_win.winfo_y() + (master_win.winfo_height() / 2) - (450 / 2))
    update_win.geometry(f"+{x}+{y}")
    
    def set_win_icon():
        try: 
            from functions.utils import get_resource_path
            update_win.iconbitmap(get_resource_path("resources/app_icon.ico"))
        except: pass
    update_win.after(200, set_win_icon)
    
    lbl_title = ctk.CTkLabel(update_win, text=f"Actualización detectada: {tag_name}", font=("Arial", 16, "bold"))
    lbl_title.pack(pady=10)
    
    txt_notes = ctk.CTkTextbox(update_win, width=460, height=250)
    txt_notes.pack(padx=20, pady=10)
    txt_notes.insert("0.0", release_notes)
    txt_notes.configure(state="disabled")
    
    btn_frame = ctk.CTkFrame(update_win, fg_color="transparent")
    btn_frame.pack(pady=10)
    
    def do_update():
        update_win.destroy()
        _download_and_apply_update(master_win, download_url)
        
    btn_yes = ctk.CTkButton(btn_frame, text="Descargar e Instalar", fg_color="#1F883D", hover_color="#1A7F37", command=do_update)
    btn_yes.pack(side="left", padx=10)
    
    btn_no = ctk.CTkButton(btn_frame, text="Más tarde", fg_color="#E74C3C", hover_color="#C0392B", command=update_win.destroy)
    btn_no.pack(side="left", padx=10)

def _download_and_apply_update(master_win, download_url):
    dl_win = ctk.CTkToplevel(master_win)
    dl_win.title("Actualizando...")
    dl_win.geometry("400x150")
    dl_win.transient(master_win)
    dl_win.grab_set()
    
    dl_win.update_idletasks()
    x = int(master_win.winfo_x() + (master_win.winfo_width() / 2) - (400 / 2))
    y = int(master_win.winfo_y() + (master_win.winfo_height() / 2) - (150 / 2))
    dl_win.geometry(f"+{x}+{y}")
    
    lbl = ctk.CTkLabel(dl_win, text="Descargando la nueva versión...\nPor favor espera, el programa se reiniciará automáticamente.", font=("Arial", 12))
    lbl.pack(pady=20)
    
    progress = ctk.CTkProgressBar(dl_win, width=300)
    progress.pack(pady=10)
    progress.set(0)
    progress.start()
    
    def dl_thread():
        try:
            update_exe = get_user_data_path("update_temp.exe")
            urllib.request.urlretrieve(download_url, update_exe)
            
            # Generar el script de actualización
            current_exe = sys.executable
            bat_path = get_user_data_path("apply_update.bat")
            
            bat_content = f'''@echo off
timeout /t 2 /nobreak >nul
del "{current_exe}"
move /Y "{update_exe}" "{current_exe}"
start "" "{current_exe}"
del "%~f0"
'''
            with open(bat_path, "w") as f:
                f.write(bat_content)
                
            master_win.after(0, lambda: _restart_and_update(bat_path))
        except Exception as e:
            print(f"Error descargando actualización: {e}")
            master_win.after(0, lambda: messagebox.showerror("Error", "No se pudo descargar la actualización."))
            master_win.after(0, dl_win.destroy)
            
    threading.Thread(target=dl_thread, daemon=True).start()

def _restart_and_update(bat_path):
    # Ejecuta el script BAT de forma independiente y cierra la app actual
    ctypes.windll.shell32.ShellExecuteW(None, "open", bat_path, "", None, 0)
    os._exit(0)

# ==============================================================
# CRASH REPORTER
# ==============================================================

def check_for_crashes(master_win):
    """
    Comprueba si existe el archivo crash.log de un cierre inesperado previo.
    """
    crash_file = get_user_data_path("crash.log")
    if os.path.exists(crash_file):
        with open(crash_file, "r") as f:
            content = f.read().strip()
            
        if content:
            _prompt_crash_report(master_win, content, crash_file)
        else:
            try: os.remove(crash_file)
            except: pass

def _prompt_crash_report(master_win, crash_data, crash_file):
    crash_win = ctk.CTkToplevel(master_win)
    crash_win.title("Reporte de Error")
    crash_win.geometry("500x250")
    crash_win.transient(master_win)
    
    crash_win.update_idletasks()
    x = int(master_win.winfo_x() + (master_win.winfo_width() / 2) - (500 / 2))
    y = int(master_win.winfo_y() + (master_win.winfo_height() / 2) - (250 / 2))
    crash_win.geometry(f"+{x}+{y}")
    
    def set_win_icon():
        try: 
            from functions.utils import get_resource_path
            crash_win.iconbitmap(get_resource_path("resources/app_icon.ico"))
        except: pass
    crash_win.after(200, set_win_icon)
    
    lbl = ctk.CTkLabel(crash_win, text="El programa se cerró inesperadamente la última vez.\n¿Deseas enviar el reporte de error de forma anónima\nal desarrollador para que pueda solucionarlo?", font=("Arial", 12))
    lbl.pack(pady=30)
    
    btn_frame = ctk.CTkFrame(crash_win, fg_color="transparent")
    btn_frame.pack(pady=10)
    
    def send_report():
        crash_win.destroy()
        if not DISCORD_WEBHOOK_URL:
            messagebox.showinfo("Reporte", "El Webhook no está configurado, no se pudo enviar el reporte.")
            _cleanup_crash(crash_file)
            return
            
        def _send():
            try:
                payload = {
                    "content": f"🚨 **Nuevo Crash Report - v{__version__}** 🚨\n```python\n{crash_data[:1800]}\n```"
                }
                req = urllib.request.Request(DISCORD_WEBHOOK_URL, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
                urllib.request.urlopen(req, timeout=5)
            except Exception as e:
                print(f"Error enviando crash report: {e}")
            finally:
                _cleanup_crash(crash_file)
                
        threading.Thread(target=_send, daemon=True).start()
        
    def cancel_report():
        crash_win.destroy()
        _cleanup_crash(crash_file)
        
    btn_yes = ctk.CTkButton(btn_frame, text="Enviar Reporte", fg_color="#F39C12", hover_color="#D68910", command=send_report)
    btn_yes.pack(side="left", padx=10)
    
    btn_no = ctk.CTkButton(btn_frame, text="Ignorar", command=cancel_report)
    btn_no.pack(side="left", padx=10)

def _cleanup_crash(crash_file):
    try:
        os.remove(crash_file)
    except:
        pass
