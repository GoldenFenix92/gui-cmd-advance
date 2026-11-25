import datetime
import json
import os
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox
import psutil
import ttkbootstrap as tb
from ttkbootstrap.widgets.scrolled import ScrolledFrame, ScrolledText
from functions.utils import center_window, get_user_data_path, safe_print
from functions import ui_theme


def get_history_path():
    return get_user_data_path("process_history.json")


def load_history():
    p = get_history_path()
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                return []
    return []


def save_to_history(action, item_type, name, extra_info=""):
    hist = load_history()
    hist.insert(0, {
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "action": action,
        "type": item_type,
        "name": name,
        "extra_info": extra_info,
    })
    hist = hist[:100]
    with open(get_history_path(), "w", encoding="utf-8") as f:
        json.dump(hist, f, indent=4)


CRITICAL_PROCESSES = {
    "svchost.exe": "Proceso anfitrión de Windows. Aloja servicios vitales del sistema. NUNCA detener.",
    "system": "Proceso central del kernel de Windows. Muy delicado.",
    "system idle process": "Mide el tiempo inactivo del procesador.",
    "csrss.exe": "Subsistema de tiempo de ejecución del cliente/servidor de Windows.",
    "wininit.exe": "Aplicación de inicio vital de Windows.",
    "services.exe": "Administrador de servicios del sistema.",
    "lsass.exe": "Proceso de autoridad de seguridad local.",
    "smss.exe": "Administrador de sesiones de Windows.",
    "winlogon.exe": "Controla el inicio de sesión de Windows.",
    "explorer.exe": "Explorador de Windows (Barra de tareas, escritorio). Si se cierra, la pantalla parpadeará.",
    "taskmgr.exe": "Administrador de tareas de Windows.",
    "dwm.exe": "Administrador de ventanas de escritorio (Renderizado de interfaz).",
    "spoolsv.exe": "Servicio de cola de impresión.",
    "conhost.exe": "Host de ventana de consola.",
    "sihost.exe": "Host de experiencia de shell de Windows.",
    "taskhostw.exe": "Host de tareas para servicios de Windows.",
    "ctfmon.exe": "Controla la entrada de texto y teclado.",
    "registry": "Almacenamiento del registro del sistema en RAM.",
    "memory compression": "Proceso de compresión de memoria de Windows.",
    "searchindexer.exe": "Indexador de búsqueda de Windows.",
}

CRITICAL_SERVICES = {
    "rpcss": "Llamada a procedimiento remoto (RPC). CRÍTICO. No detener ni modificar.",
    "dcomlaunch": "Iniciador de procesos de servidor DCOM. CRÍTICO.",
    "plugplay": "Plug and Play. Reconoce el hardware. CRÍTICO.",
    "samss": "Administrador de cuentas de seguridad. CRÍTICO.",
    "eventlog": "Registro de eventos de Windows. CRÍTICO.",
    "winmgmt": "Instrumental de administración de Windows (WMI).",
    "dnscache": "Cliente DNS. Si se detiene perderás acceso fluido a internet.",
    "lanmanserver": "Servidor. Comparte archivos e impresoras en red.",
    "lanmanworkstation": "Estación de trabajo. Conecta con otros equipos.",
    "dhcp": "Cliente DHCP. Gestiona tu dirección IP en la red.",
    "audiosrv": "Audio de Windows. Si se detiene te quedarás sin sonido.",
    "cryptsvc": "Servicios criptográficos. Requerido para Windows Update.",
    "windefend": "Microsoft Defender Antivirus.",
    "mpssvc": "Firewall de Windows Defender. Protege de accesos no autorizados.",
    "bfe": "Motor de filtrado de base. Crítico para la red y Firewall.",
    "w32time": "Hora de Windows. Mantiene sincronizada la fecha y hora.",
}

BLOATWARE_LIST = {
    "diagtrack": "Servicio de telemetría y recolección de datos de Microsoft.",
    "wsearch": "Windows Search (Indexador, consume mucho disco/RAM si no buscas archivos seguido).",
    "xblauthmanager": "Servicio de Xbox Live Auth (Innecesario si no juegas en Xbox App).",
    "xblgamesave": "Servicio de guardado de Xbox Live.",
    "xboxnetapisvc": "Servicio de red de Xbox Live.",
    "edgeupdate": "Servicio de actualización de Microsoft Edge.",
    "sysmain": "Superfetch/SysMain (Precarga apps en RAM, a veces causa 100% uso de disco).",
    "mapsbroker": "Administrador de mapas descargados.",
    "lfsvc": "Servicio de geolocalización.",
    "wmpnetworksvc": "Uso compartido de red del Reproductor de Windows Media.",
}


class AIResultWindow(tb.Toplevel):
    def __init__(self, parent, title, text):
        super().__init__(parent)
        self.title(title)
        center_window(self, 760, 560)
        ui_theme.apply_window_chrome(self)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.textbox = ScrolledText(self, font=("Consolas", 11), wrap="word", autohide=True)
        self.textbox.grid(row=0, column=0, padx=15, pady=15, sticky="nsew")
        self.textbox.text.insert("1.0", text)
        self.textbox.text.configure(state="disabled")

        self.btn_close = tb.Button(self, text="Cerrar", command=self.destroy, bootstyle="secondary", width=16)
        self.btn_close.grid(row=1, column=0, pady=(0, 14))
        ui_theme.bring_to_front(self)


class ProcessManagerApp(tb.Window):
    def __init__(self):
        theme = ui_theme.get_saved_theme()
        super().__init__(themename=theme)
        self.title("Administrador de Tareas Avanzado")
        center_window(self, 980, 660)
        ui_theme.apply_window_chrome(self, theme)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._icon_info = ui_theme.get_bootstrap_icon("info", size=14, color="#FFFFFF", master=self)
        self._icon_refresh = ui_theme.get_bootstrap_icon("refresh", size=14, color="#FFFFFF", master=self)
        self._icon_ai = ui_theme.get_bootstrap_icon("ai", size=14, color="#FFFFFF", master=self)

        self.top_frame = tb.Frame(self, padding=(12, 10))
        self.top_frame.grid(row=0, column=0, sticky="ew")

        tb.Label(self.top_frame, text="Gestor de Procesos y Servicios", font=("Segoe UI", 16, "bold"), bootstyle="primary").pack(side="left")

        self.refresh_btn = tb.Button(
            self.top_frame, text=" Actualizar", image=self._icon_refresh, compound="left",
            command=self.refresh_data, bootstyle="primary",
        )
        self.refresh_btn.pack(side="right")

        self.btn_ai = tb.Button(
            self.top_frame, text=" Analizador IA", image=self._icon_ai, compound="left",
            command=self.run_ai_analysis, bootstyle="info",
        )
        self.btn_ai.pack(side="right", padx=(0, 10))

        self.notebook = tb.Notebook(self, bootstyle="primary")
        self.notebook.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="nsew")

        self.tab_proc = tb.Frame(self.notebook, padding=8)
        self.tab_serv = tb.Frame(self.notebook, padding=8)
        self.tab_bloat = tb.Frame(self.notebook, padding=8)
        self.tab_hist = tb.Frame(self.notebook, padding=8)

        self.notebook.add(self.tab_proc, text="Procesos")
        self.notebook.add(self.tab_serv, text="Servicios")
        self.notebook.add(self.tab_bloat, text="Bloatware")
        self.notebook.add(self.tab_hist, text="Historial")

        self.tab_proc.grid_columnconfigure(0, weight=1)
        self.tab_proc.grid_rowconfigure(0, weight=1)
        self.scroll_proc = ScrolledFrame(self.tab_proc, autohide=True)
        self.scroll_proc.grid(row=0, column=0, sticky="nsew")

        self.tab_serv.grid_columnconfigure(0, weight=1)
        self.tab_serv.grid_rowconfigure(0, weight=1)
        self.scroll_serv = ScrolledFrame(self.tab_serv, autohide=True)
        self.scroll_serv.grid(row=0, column=0, sticky="nsew")

        self.tab_bloat.grid_columnconfigure(0, weight=1)
        self.tab_bloat.grid_rowconfigure(1, weight=1)
        tb.Label(
            self.tab_bloat,
            text="Selecciona los servicios de Bloatware que deseas deshabilitar (Pasar a Manual):",
            font=("Segoe UI", 10, "bold"),
        ).grid(row=0, column=0, pady=(0, 6), sticky="w")
        self.scroll_bloat = ScrolledFrame(self.tab_bloat, autohide=True)
        self.scroll_bloat.grid(row=1, column=0, sticky="nsew")
        self.btn_bloat_apply = tb.Button(self.tab_bloat, text="Optimizar Seleccionados", command=self.apply_bloatware_fix, bootstyle="warning")
        self.btn_bloat_apply.grid(row=2, column=0, pady=(10, 2))
        self.bloat_vars = {}

        self.tab_hist.grid_columnconfigure(0, weight=1)
        self.tab_hist.grid_rowconfigure(0, weight=1)
        self.scroll_hist = ScrolledFrame(self.tab_hist, autohide=True)
        self.scroll_hist.grid(row=0, column=0, sticky="nsew")

        self.refresh_data()

    def refresh_data(self):
        self.load_processes()
        self.load_services()
        self.load_bloatware()
        self.load_history_ui()

    def load_processes(self):
        for widget in self.scroll_proc.winfo_children():
            widget.destroy()

        tb.Label(self.scroll_proc, text="PID", font=("Segoe UI", 10, "bold"), width=8).grid(row=0, column=0, padx=6, pady=6)
        tb.Label(self.scroll_proc, text="Nombre", font=("Segoe UI", 10, "bold"), width=28, anchor="w").grid(row=0, column=1, padx=6, pady=6, sticky="w")
        tb.Label(self.scroll_proc, text="RAM (MB)", font=("Segoe UI", 10, "bold"), width=12).grid(row=0, column=2, padx=6, pady=6)
        tb.Label(self.scroll_proc, text="Acción", font=("Segoe UI", 10, "bold")).grid(row=0, column=3, padx=6, pady=6)

        processes = []
        for p in psutil.process_iter(["pid", "name", "memory_info"]):
            try:
                mem = p.info["memory_info"].rss / (1024 * 1024)
                processes.append((p.info["pid"], p.info["name"], mem))
            except Exception:
                pass

        processes.sort(key=lambda x: x[2], reverse=True)

        for i, (pid, name, mem) in enumerate(processes[:50], start=1):
            name_lower = name.lower() if name else ""
            is_critical = name_lower in CRITICAL_PROCESSES
            row_style = "danger" if is_critical else "default"

            tb.Label(self.scroll_proc, text=str(pid), width=8, bootstyle=row_style).grid(row=i, column=0, padx=6, pady=3)
            tb.Label(self.scroll_proc, text=name, width=28, anchor="w", bootstyle=row_style).grid(row=i, column=1, padx=6, pady=3, sticky="w")
            tb.Label(self.scroll_proc, text=f"{mem:.1f} MB", width=12, bootstyle=row_style).grid(row=i, column=2, padx=6, pady=3)

            actions_frame = tb.Frame(self.scroll_proc)
            actions_frame.grid(row=i, column=3, padx=6, pady=3)

            btn_info = tb.Button(
                actions_frame, image=self._icon_info, bootstyle="info",
                command=lambda n=name_lower: self.show_process_info(n),
            )
            btn_info.pack(side="left", padx=2)
            ui_theme.add_tooltip(btn_info, "Información del proceso")

            btn_stop = tb.Button(
                actions_frame, text="Detener", bootstyle="danger",
                command=lambda p=pid, n=name: self.kill_process(p, n),
            )
            btn_stop.pack(side="left", padx=2)

    def show_process_info(self, name_lower):
        if name_lower in CRITICAL_PROCESSES:
            desc = CRITICAL_PROCESSES[name_lower]
            messagebox.showwarning("Proceso Crítico", f"Proceso: {name_lower}\n\n{desc}\n\nNO detener este proceso.", parent=self)
        else:
            messagebox.showinfo("Proceso de Usuario", f"Proceso: {name_lower}\n\nEste proceso no es crítico. Es seguro detenerlo.", parent=self)

    def load_services(self):
        for widget in self.scroll_serv.winfo_children():
            widget.destroy()

        tb.Label(self.scroll_serv, text="Nombre / Mostrar", font=("Segoe UI", 10, "bold"), width=34, anchor="w").grid(row=0, column=0, padx=6, pady=6, sticky="w")
        tb.Label(self.scroll_serv, text="Estado", font=("Segoe UI", 10, "bold"), width=12).grid(row=0, column=1, padx=6, pady=6)
        tb.Label(self.scroll_serv, text="Tipo Inicio", font=("Segoe UI", 10, "bold"), width=12).grid(row=0, column=2, padx=6, pady=6)
        tb.Label(self.scroll_serv, text="Acción", font=("Segoe UI", 10, "bold")).grid(row=0, column=3, padx=6, pady=6)

        services = []
        try:
            for s in psutil.win_service_iter():
                try:
                    info = s.as_dict()
                    if info.get("start_type") in ["automatic", "manual"]:
                        services.append(info)
                except Exception:
                    pass
        except Exception as e:
            tb.Label(self.scroll_serv, text=f"Error cargando servicios: {e}", bootstyle="danger").grid(row=1, column=0)
            return

        services = [s for s in services if s.get("status") == "running" or s.get("start_type") == "automatic"]
        services.sort(key=lambda x: (x.get("status") != "running", x.get("display_name")))

        for i, s in enumerate(services[:50], start=1):
            name = s.get("name", "N/A")
            display = s.get("display_name", name)[:40]
            status = s.get("status", "N/A")
            start_type = s.get("start_type", "N/A")
            name_lower = name.lower()
            row_style = "danger" if name_lower in CRITICAL_SERVICES else "default"

            tb.Label(self.scroll_serv, text=display, width=34, anchor="w", bootstyle=row_style).grid(row=i, column=0, padx=6, pady=3, sticky="w")
            tb.Label(self.scroll_serv, text=status, width=12, bootstyle=row_style).grid(row=i, column=1, padx=6, pady=3)
            tb.Label(self.scroll_serv, text=start_type, width=12, bootstyle=row_style).grid(row=i, column=2, padx=6, pady=3)

            btn_frame = tb.Frame(self.scroll_serv)
            btn_frame.grid(row=i, column=3, padx=6, pady=3)

            btn_info = tb.Button(
                btn_frame, image=self._icon_info, bootstyle="info",
                command=lambda n=name_lower: self.show_service_info(n),
            )
            btn_info.pack(side="left", padx=2)
            ui_theme.add_tooltip(btn_info, "Información del servicio")

            if start_type != "manual":
                tb.Button(
                    btn_frame, text="A Manual", bootstyle="warning",
                    command=lambda n=name: self.set_service_manual(n),
                ).pack(side="left", padx=2)

            if status == "running":
                tb.Button(
                    btn_frame, text="Detener", bootstyle="danger",
                    command=lambda n=name: self.stop_service(n),
                ).pack(side="left", padx=2)

    def show_service_info(self, name_lower):
        if name_lower in CRITICAL_SERVICES:
            messagebox.showwarning("Servicio Crítico", f"Servicio: {name_lower}\n\n{CRITICAL_SERVICES[name_lower]}\n\nNO modificar.", parent=self)
        else:
            messagebox.showinfo("Servicio Secundario", f"Servicio: {name_lower}\n\nNo es crítico. Puedes ponerlo en Manual.", parent=self)

    def load_bloatware(self):
        for widget in self.scroll_bloat.winfo_children():
            widget.destroy()
        self.bloat_vars.clear()

        row = 0
        try:
            for s in psutil.win_service_iter():
                info = s.as_dict()
                name = info.get("name", "").lower()
                if name in BLOATWARE_LIST and info.get("start_type") != "manual":
                    var = tk.BooleanVar(value=True)
                    self.bloat_vars[info.get("name")] = var
                    chk = tb.Checkbutton(
                        self.scroll_bloat,
                        text=f"{info.get('display_name')} ({name}) - {BLOATWARE_LIST[name]}",
                        variable=var,
                        bootstyle="warning",
                    )
                    chk.grid(row=row, column=0, sticky="w", padx=6, pady=5)
                    row += 1
        except Exception:
            pass
        if row == 0:
            tb.Label(self.scroll_bloat, text="Excelente, no se encontró Bloatware activo.", bootstyle="success").grid(row=0, column=0, padx=6, pady=8)

    def apply_bloatware_fix(self):
        count = 0
        for name, var in self.bloat_vars.items():
            if var.get():
                try:
                    subprocess.run(["sc", "config", name, "start=", "demand"], check=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                    subprocess.run(["net", "stop", name, "/y"], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                    save_to_history("A Manual y Detenido (Bloatware)", "Servicio", name, "automatic")
                    safe_print(f"[ProcessManager] Bloatware optimizado: {name}.")
                    count += 1
                except Exception:
                    pass
        messagebox.showinfo("Optimización", f"Se optimizaron {count} servicios identificados como Bloatware.", parent=self)
        self.refresh_data()

    def load_history_ui(self):
        for widget in self.scroll_hist.winfo_children():
            widget.destroy()
        hist = load_history()
        if not hist:
            tb.Label(self.scroll_hist, text="No hay historial registrado.", bootstyle="secondary").grid(row=0, column=0, padx=6, pady=8)
            return

        for i, item in enumerate(hist):
            txt = f"[{item['timestamp']}] {item['type']} '{item['name']}' -> {item['action']}"
            tb.Label(self.scroll_hist, text=txt, anchor="w", width=65).grid(row=i, column=0, sticky="w", padx=6, pady=3)
            btn = tb.Button(self.scroll_hist, text="Deshacer / Restaurar", bootstyle="secondary-outline", command=lambda it=item: self.undo_action(it))
            btn.grid(row=i, column=1, padx=6, pady=3)

    def undo_action(self, item):
        if item["type"] == "Proceso":
            if item["extra_info"]:
                try:
                    subprocess.Popen([item["extra_info"]], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                    messagebox.showinfo("Restaurado", f"Se relanzó el ejecutable: {item['name']}", parent=self)
                except Exception as e:
                    messagebox.showerror("Error", f"No se pudo iniciar {item['extra_info']}: {e}", parent=self)
            else:
                messagebox.showwarning("Aviso", "No se guardó la ruta del ejecutable.", parent=self)
        elif "Servicio" in item["type"]:
            try:
                name = item["name"]
                subprocess.run(["sc", "config", name, "start=", "auto"], check=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                subprocess.run(["net", "start", name], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                messagebox.showinfo("Restaurado", f"Servicio {name} vuelto a Automático y arrancado.", parent=self)
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo restaurar el servicio: {e}", parent=self)

    def kill_process(self, pid, name):
        try:
            p = psutil.Process(pid)
            exe_path = ""
            try:
                exe_path = p.exe()
            except Exception:
                pass
            p.kill()
            save_to_history("Detenido", "Proceso", name, exe_path)
            safe_print(f"[ProcessManager] Se detuvo el proceso {name} (PID: {pid}).")
            messagebox.showinfo("Proceso Detenido", f"El proceso {name} (PID: {pid}) ha sido detenido.", parent=self)
            self.load_processes()
            self.load_history_ui()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo detener el proceso {name}:\n{e}", parent=self)

    def set_service_manual(self, name):
        try:
            subprocess.run(["sc", "config", name, "start=", "demand"], check=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            save_to_history("A Manual", "Servicio", name, "automatic")
            safe_print(f"[ProcessManager] El servicio {name} ha sido puesto en modo Manual.")
            messagebox.showinfo("Servicio Modificado", f"El servicio {name} ahora está en modo Manual.", parent=self)
            self.load_services()
            self.load_history_ui()
        except subprocess.CalledProcessError:
            messagebox.showerror("Permisos", f"No se pudo modificar {name}. ¿Ejecutaste el programa como Administrador?", parent=self)
        except Exception as e:
            messagebox.showerror("Error", f"Error inesperado: {e}", parent=self)

    def stop_service(self, name):
        try:
            subprocess.run(["net", "stop", name, "/y"], check=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            save_to_history("Detenido", "Servicio", name, "")
            safe_print(f"[ProcessManager] El servicio {name} ha sido detenido.")
            messagebox.showinfo("Servicio Detenido", f"El servicio {name} ha sido detenido.", parent=self)
            self.load_services()
            self.load_history_ui()
        except subprocess.CalledProcessError:
            messagebox.showerror("Permisos", f"No se pudo detener {name}. Es posible que se requieran permisos.", parent=self)
        except Exception as e:
            messagebox.showerror("Error", f"Error inesperado: {e}", parent=self)

    def run_ai_analysis(self):
        try:
            from functions import ai_engine
            settings = ai_engine.load_ai_settings()
        except Exception:
            messagebox.showerror("Error", "No se pudo cargar la configuración de IA. Verifica el archivo ai_settings.json.", parent=self)
            return

        proc_list = []
        try:
            for p in psutil.process_iter(["name", "memory_info"]):
                try:
                    proc_list.append((p.info["name"], p.info["memory_info"].rss / (1024 * 1024)))
                except Exception:
                    pass
        except Exception:
            pass

        proc_list.sort(key=lambda x: x[1], reverse=True)
        top_15 = [f"{n} ({m:.1f} MB)" for n, m in proc_list[:15]]
        raw_summary = "Top 15 procesos por consumo de RAM:\n" + "\n".join(f"- {item}" for item in top_15)
        prompt = ai_engine.build_analysis_prompt(raw_summary, style="tecnico", domain="processes")

        self.btn_ai.configure(text=" Analizando...", state="disabled")

        def _fetch():
            result = ai_engine.run_model_train(settings, prompt, use_train=True, timeout=25)

            def _done():
                self.btn_ai.configure(text=" Analizador IA", state="normal")
                if result["ok"]:
                    header = f"[Analizado por {result['provider']} - {result['model']}]\n\n"
                    AIResultWindow(self, "Análisis Inteligente de Procesos", header + result["text"])
                    save_to_history("Análisis IA Realizado", "IA", "Optimización", "")
                    self.load_history_ui()
                else:
                    detail = "\n".join(result.get("errors") or [])[:400]
                    messagebox.showerror(
                        "Fallo IA",
                        f"No se pudo completar el análisis con IA.\n\nDetalle:\n{detail}",
                        parent=self,
                    )

            self.after(0, _done)

        threading.Thread(target=_fetch, daemon=True).start()


def main():
    app = ProcessManagerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
