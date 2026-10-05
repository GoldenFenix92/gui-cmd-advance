import customtkinter as ctk
import psutil
import subprocess
import os
import json
import datetime
import urllib.request
import urllib.error
from tkinter import messagebox
import sys
import threading

def get_base_path():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_user_data_path(filename):
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, filename)

def get_history_path():
    return get_user_data_path("process_history.json")

def load_history():
    p = get_history_path()
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            try: return json.load(f)
            except: return []
    return []

def save_to_history(action, item_type, name, extra_info=""):
    hist = load_history()
    hist.insert(0, {
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "action": action,
        "type": item_type,
        "name": name,
        "extra_info": extra_info
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
    "searchindexer.exe": "Indexador de búsqueda de Windows."
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
    "w32time": "Hora de Windows. Mantiene sincronizada la fecha y hora."
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
    "wmpnetworksvc": "Uso compartido de red del Reproductor de Windows Media."
}

class ProcessManagerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Administrador de Tareas Avanzado")
        self.geometry("950x650")
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Titulo y botones de actualizacion
        self.top_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.top_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        
        ctk.CTkLabel(self.top_frame, text="Gestor de Procesos y Servicios", font=("Arial", 20, "bold")).pack(side="left")
        
        self.refresh_btn = ctk.CTkButton(self.top_frame, text="🔄 Actualizar", width=100, command=self.refresh_data)
        self.refresh_btn.pack(side="right")
        
        self.btn_ai = ctk.CTkButton(self.top_frame, text="🧠 Analizador IA", width=120, fg_color="#8E44AD", hover_color="#9B59B6", command=self.run_ai_analysis)
        self.btn_ai.pack(side="right", padx=(0, 10))
        
        # Tabs
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        
        self.tab_proc = self.tabview.add("Procesos")
        self.tab_serv = self.tabview.add("Servicios")
        self.tab_bloat = self.tabview.add("🧹 Bloatware")
        self.tab_hist = self.tabview.add("🕒 Historial")
        
        # Configurar Tab Procesos
        self.tab_proc.grid_columnconfigure(0, weight=1)
        self.tab_proc.grid_rowconfigure(0, weight=1)
        self.scroll_proc = ctk.CTkScrollableFrame(self.tab_proc)
        self.scroll_proc.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # Configurar Tab Servicios
        self.tab_serv.grid_columnconfigure(0, weight=1)
        self.tab_serv.grid_rowconfigure(0, weight=1)
        self.scroll_serv = ctk.CTkScrollableFrame(self.tab_serv)
        self.scroll_serv.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # Configurar Tab Bloatware
        self.tab_bloat.grid_columnconfigure(0, weight=1)
        self.tab_bloat.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(self.tab_bloat, text="Selecciona los servicios de Bloatware que deseas deshabilitar (Pasar a Manual):", font=("Arial", 12, "bold")).grid(row=0, column=0, pady=5, sticky="w")
        self.scroll_bloat = ctk.CTkScrollableFrame(self.tab_bloat)
        self.scroll_bloat.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.btn_bloat_apply = ctk.CTkButton(self.tab_bloat, text="🚀 Optimizar Seleccionados", command=self.apply_bloatware_fix, fg_color="#E67E22", hover_color="#D35400")
        self.btn_bloat_apply.grid(row=2, column=0, pady=10)
        self.bloat_vars = {}
        
        # Configurar Tab Historial
        self.tab_hist.grid_columnconfigure(0, weight=1)
        self.tab_hist.grid_rowconfigure(0, weight=1)
        self.scroll_hist = ctk.CTkScrollableFrame(self.tab_hist)
        self.scroll_hist.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        self.refresh_data()
        
    def refresh_data(self):
        self.load_processes()
        self.load_services()
        self.load_bloatware()
        self.load_history_ui()
        
    def load_processes(self):
        for widget in self.scroll_proc.winfo_children():
            widget.destroy()
            
        ctk.CTkLabel(self.scroll_proc, text="PID", font=("Arial", 12, "bold"), width=60).grid(row=0, column=0, padx=5, pady=5)
        ctk.CTkLabel(self.scroll_proc, text="Nombre", font=("Arial", 12, "bold"), width=200, anchor="w").grid(row=0, column=1, padx=5, pady=5, sticky="w")
        ctk.CTkLabel(self.scroll_proc, text="RAM (MB)", font=("Arial", 12, "bold"), width=80).grid(row=0, column=2, padx=5, pady=5)
        ctk.CTkLabel(self.scroll_proc, text="Acción", font=("Arial", 12, "bold"), width=100).grid(row=0, column=3, padx=5, pady=5)
        
        processes = []
        for p in psutil.process_iter(['pid', 'name', 'memory_info']):
            try:
                mem = p.info['memory_info'].rss / (1024 * 1024)
                processes.append((p.info['pid'], p.info['name'], mem))
            except:
                pass
                
        processes.sort(key=lambda x: x[2], reverse=True)
        
        for i, (pid, name, mem) in enumerate(processes[:50], start=1):
            name_lower = name.lower() if name else ""
            is_critical = name_lower in CRITICAL_PROCESSES
            
            text_color = "#E74C3C" if is_critical else "white"
            
            ctk.CTkLabel(self.scroll_proc, text=str(pid), width=60, text_color=text_color).grid(row=i, column=0, padx=5, pady=2)
            ctk.CTkLabel(self.scroll_proc, text=name, width=200, anchor="w", text_color=text_color).grid(row=i, column=1, padx=5, pady=2, sticky="w")
            ctk.CTkLabel(self.scroll_proc, text=f"{mem:.1f} MB", width=80, text_color=text_color).grid(row=i, column=2, padx=5, pady=2)
            
            actions_frame = ctk.CTkFrame(self.scroll_proc, fg_color="transparent")
            actions_frame.grid(row=i, column=3, padx=5, pady=2)
            
            btn_info = ctk.CTkButton(actions_frame, text="ℹ️", width=30, fg_color="#3498DB", hover_color="#2980B9",
                                     command=lambda n=name_lower: self.show_process_info(n))
            btn_info.pack(side="left", padx=2)
            
            btn_stop = ctk.CTkButton(actions_frame, text="Detener", width=70, fg_color="#E74C3C", hover_color="#C0392B", 
                                     command=lambda p=pid, n=name: self.kill_process(p, n))
            btn_stop.pack(side="left", padx=2)

    def show_process_info(self, name_lower):
        if name_lower in CRITICAL_PROCESSES:
            desc = CRITICAL_PROCESSES[name_lower]
            messagebox.showwarning("Proceso Crítico", f"Proceso: {name_lower}\\n\\n{desc}\\n\\nNO detener este proceso.", parent=self)
        else:
            messagebox.showinfo("Proceso de Usuario", f"Proceso: {name_lower}\\n\\nEste proceso no es crítico. Es seguro detenerlo.", parent=self)

    def load_services(self):
        for widget in self.scroll_serv.winfo_children():
            widget.destroy()
            
        ctk.CTkLabel(self.scroll_serv, text="Nombre / Mostrar", font=("Arial", 12, "bold"), width=250, anchor="w").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ctk.CTkLabel(self.scroll_serv, text="Estado", font=("Arial", 12, "bold"), width=100).grid(row=0, column=1, padx=5, pady=5)
        ctk.CTkLabel(self.scroll_serv, text="Tipo Inicio", font=("Arial", 12, "bold"), width=100).grid(row=0, column=2, padx=5, pady=5)
        ctk.CTkLabel(self.scroll_serv, text="Acción", font=("Arial", 12, "bold"), width=150).grid(row=0, column=3, padx=5, pady=5)
        
        services = []
        try:
            for s in psutil.win_service_iter():
                try:
                    info = s.as_dict()
                    if info.get('start_type') in ['automatic', 'manual']:
                        services.append(info)
                except:
                    pass
        except Exception as e:
            ctk.CTkLabel(self.scroll_serv, text=f"Error cargando servicios: {e}").grid(row=1, column=0)
            return

        services = [s for s in services if s.get('status') == 'running' or s.get('start_type') == 'automatic']
        services.sort(key=lambda x: (x.get('status') != 'running', x.get('display_name')))
        
        for i, s in enumerate(services[:50], start=1):
            name = s.get('name', 'N/A')
            display = s.get('display_name', name)[:40]
            status = s.get('status', 'N/A')
            start_type = s.get('start_type', 'N/A')
            
            name_lower = name.lower()
            is_critical = name_lower in CRITICAL_SERVICES
            
            text_color = "#E74C3C" if is_critical else "white"
            
            ctk.CTkLabel(self.scroll_serv, text=display, width=250, anchor="w", text_color=text_color).grid(row=i, column=0, padx=5, pady=2, sticky="w")
            ctk.CTkLabel(self.scroll_serv, text=status, width=100, text_color=text_color).grid(row=i, column=1, padx=5, pady=2)
            ctk.CTkLabel(self.scroll_serv, text=start_type, width=100, text_color=text_color).grid(row=i, column=2, padx=5, pady=2)
            
            btn_frame = ctk.CTkFrame(self.scroll_serv, fg_color="transparent")
            btn_frame.grid(row=i, column=3, padx=5, pady=2)
            
            btn_info = ctk.CTkButton(btn_frame, text="ℹ️", width=30, fg_color="#3498DB", hover_color="#2980B9",
                                     command=lambda n=name_lower: self.show_service_info(n))
            btn_info.pack(side="left", padx=2)
            
            if start_type != 'manual':
                ctk.CTkButton(btn_frame, text="A Manual", width=70, fg_color="#F39C12", hover_color="#D68910",
                              command=lambda n=name: self.set_service_manual(n)).pack(side="left", padx=2)
                              
            if status == 'running':
                ctk.CTkButton(btn_frame, text="Detener", width=70, fg_color="#E74C3C", hover_color="#C0392B",
                              command=lambda n=name: self.stop_service(n)).pack(side="left", padx=2)

    def show_service_info(self, name_lower):
        if name_lower in CRITICAL_SERVICES:
            messagebox.showwarning("Servicio Crítico", f"Servicio: {name_lower}\\n\\n{CRITICAL_SERVICES[name_lower]}\\n\\nNO modificar.", parent=self)
        else:
            messagebox.showinfo("Servicio Secundario", f"Servicio: {name_lower}\\n\\nNo es crítico. Puedes ponerlo en Manual.", parent=self)

    def load_bloatware(self):
        for widget in self.scroll_bloat.winfo_children():
            widget.destroy()
        self.bloat_vars.clear()
        
        row = 0
        try:
            for s in psutil.win_service_iter():
                info = s.as_dict()
                name = info.get('name', '').lower()
                if name in BLOATWARE_LIST and info.get('start_type') != 'manual':
                    var = ctk.BooleanVar(value=True)
                    self.bloat_vars[info.get('name')] = var
                    chk = ctk.CTkCheckBox(self.scroll_bloat, text=f"{info.get('display_name')} ({name}) - {BLOATWARE_LIST[name]}", variable=var)
                    chk.grid(row=row, column=0, sticky="w", padx=5, pady=5)
                    row += 1
        except: pass
        if row == 0:
            ctk.CTkLabel(self.scroll_bloat, text="✅ Excelente, no se encontró Bloatware activo.").grid(row=0, column=0)

    def apply_bloatware_fix(self):
        count = 0
        for name, var in self.bloat_vars.items():
            if var.get():
                try:
                    subprocess.run(["sc", "config", name, "start=", "demand"], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
                    subprocess.run(["net", "stop", name, "/y"], creationflags=subprocess.CREATE_NO_WINDOW)
                    save_to_history("A Manual y Detenido (Bloatware)", "Servicio", name, "automatic")
                    count += 1
                except: pass
        messagebox.showinfo("Optimización", f"Se optimizaron {count} servicios identificados como Bloatware.")
        self.refresh_data()

    def load_history_ui(self):
        for widget in self.scroll_hist.winfo_children():
            widget.destroy()
        hist = load_history()
        if not hist:
            ctk.CTkLabel(self.scroll_hist, text="No hay historial registrado.").grid(row=0, column=0)
            return
        
        for i, item in enumerate(hist):
            txt = f"[{item['timestamp']}] {item['type']} '{item['name']}' -> {item['action']}"
            ctk.CTkLabel(self.scroll_hist, text=txt, anchor="w", width=500).grid(row=i, column=0, sticky="w", padx=5, pady=2)
            btn = ctk.CTkButton(self.scroll_hist, text="Deshacer / Restaurar", width=120, command=lambda it=item: self.undo_action(it))
            btn.grid(row=i, column=1, padx=5, pady=2)

    def undo_action(self, item):
        if item['type'] == "Proceso":
            if item['extra_info']:
                try:
                    subprocess.Popen([item['extra_info']], creationflags=subprocess.CREATE_NO_WINDOW)
                    messagebox.showinfo("Restaurado", f"Se relanzó el ejecutable: {item['name']}")
                except Exception as e:
                    messagebox.showerror("Error", f"No se pudo iniciar {item['extra_info']}: {e}")
            else:
                messagebox.showwarning("Aviso", "No se guardó la ruta del ejecutable.")
        elif "Servicio" in item['type']:
            try:
                name = item['name']
                subprocess.run(["sc", "config", name, "start=", "auto"], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
                subprocess.run(["net", "start", name], creationflags=subprocess.CREATE_NO_WINDOW)
                messagebox.showinfo("Restaurado", f"Servicio {name} vuelto a Automático y arrrancado.")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo restaurar el servicio: {e}")

    def kill_process(self, pid, name):
        try:
            p = psutil.Process(pid)
            exe_path = ""
            try: exe_path = p.exe()
            except: pass
            p.kill()
            save_to_history("Detenido", "Proceso", name, exe_path)
            messagebox.showinfo("Proceso Detenido", f"El proceso {name} (PID: {pid}) ha sido detenido.", parent=self)
            self.load_processes()
            self.load_history_ui()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo detener el proceso {name}:\\n{e}", parent=self)
            
    def set_service_manual(self, name):
        try:
            subprocess.run(["sc", "config", name, "start=", "demand"], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            save_to_history("A Manual", "Servicio", name, "automatic")
            messagebox.showinfo("Servicio Modificado", f"El servicio {name} ahora está en modo Manual.", parent=self)
            self.load_services()
            self.load_history_ui()
        except subprocess.CalledProcessError:
            messagebox.showerror("Permisos", f"No se pudo modificar {name}. ¿Ejecutaste el programa como Administrador?", parent=self)
        except Exception as e:
            messagebox.showerror("Error", f"Error inesperado: {e}", parent=self)

    def stop_service(self, name):
        try:
            subprocess.run(["net", "stop", name, "/y"], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            save_to_history("Detenido", "Servicio", name, "")
            messagebox.showinfo("Servicio Detenido", f"El servicio {name} ha sido detenido.", parent=self)
            self.load_services()
            self.load_history_ui()
        except subprocess.CalledProcessError:
            messagebox.showerror("Permisos", f"No se pudo detener {name}. Es posible que se requieran permisos.", parent=self)
        except Exception as e:
            messagebox.showerror("Error", f"Error inesperado: {e}", parent=self)

    def run_ai_analysis(self):
        try:
            from functions.interpreter_addon import get_api_settings
            settings = get_api_settings()
        except:
            messagebox.showerror("Error", "No se pudo cargar la configuración de IA. Verifica el archivo ai_settings.json.")
            return
            
        train = settings.get("model_train", [])
        if not train:
            messagebox.showwarning("IA", "No hay modelos en el Tren de Modelos. Ve al panel de Interpretación de Comandos y configura tu API/Tren primero.")
            return
            
        proc_list = []
        try:
            for p in psutil.process_iter(['name', 'memory_info']):
                try: proc_list.append((p.info['name'], p.info['memory_info'].rss / (1024*1024)))
                except: pass
        except: pass
        
        proc_list.sort(key=lambda x: x[1], reverse=True)
        top_15 = [f"{n} ({m:.1f}MB)" for n, m in proc_list[:15]]
        prompt = "Actúa como experto en Windows. Analiza esta lista de procesos que consumen más RAM y sugiere cuáles son inútiles (bloatware) y seguros de matar para optimizar: " + ", ".join(top_15)
        
        self.btn_ai.configure(text="⏳ Analizando...", state="disabled")
        
        def _fetch():
            res = None
            for item in train:
                provider = item.get("provider")
                model = item.get("model")
                prov_data = settings.get("providers", {}).get(provider, {})
                api_key = prov_data.get("api_key", "")
                
                try:
                    if provider == "Google Gemini":
                        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
                        payload = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode('utf-8')
                        req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'}, method='POST')
                        with urllib.request.urlopen(req, timeout=15) as r:
                            resp = json.loads(r.read())
                            res = f"🤖 [Analizado por {model}]:\\n\\n" + resp['candidates'][0]['content']['parts'][0]['text']
                            break
                    elif provider in ["OpenAI", "Groq"]:
                        url = "https://api.openai.com/v1/chat/completions" if provider == "OpenAI" else "https://api.groq.com/openai/v1/chat/completions"
                        payload = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}]}).encode('utf-8')
                        req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}'}, method='POST')
                        with urllib.request.urlopen(req, timeout=15) as r:
                            resp = json.loads(r.read())
                            res = f"🤖 [Analizado por {model}]:\\n\\n" + resp['choices'][0]['message']['content']
                            break
                except Exception as e:
                    print("AI Error con", provider, e)
                    continue
            
            def _done():
                self.btn_ai.configure(text="🧠 Analizador IA", state="normal")
                if res:
                    messagebox.showinfo("Análisis Inteligente", res)
                    save_to_history("Análisis IA Realizado", "IA", "Optimización", "")
                    self.load_history_ui()
                else:
                    messagebox.showerror("Fallo IA", "Fallaron todos los modelos del tren. Verifica tus llaves API o conexión.")
            self.after(0, _done)
            
        threading.Thread(target=_fetch, daemon=True).start()

def main():
    app = ProcessManagerApp()
    app.mainloop()

if __name__ == "__main__":
    main()
