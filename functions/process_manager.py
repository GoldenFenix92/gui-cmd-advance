import customtkinter as ctk
import psutil
import subprocess
import os
from tkinter import messagebox

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

class ProcessManagerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Administrador de Tareas Avanzado")
        self.geometry("900x600")
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Titulo y botones de actualizacion
        self.top_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.top_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        
        ctk.CTkLabel(self.top_frame, text="Gestor de Procesos y Servicios", font=("Arial", 20, "bold")).pack(side="left")
        
        self.refresh_btn = ctk.CTkButton(self.top_frame, text="🔄 Actualizar", width=100, command=self.refresh_data)
        self.refresh_btn.pack(side="right")
        
        # Tabs
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        
        self.tab_proc = self.tabview.add("Procesos")
        self.tab_serv = self.tabview.add("Servicios")
        
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
        
        self.refresh_data()
        
    def refresh_data(self):
        self.load_processes()
        self.load_services()
        
    def load_processes(self):
        # Limpiar
        for widget in self.scroll_proc.winfo_children():
            widget.destroy()
            
        # Encabezados
        ctk.CTkLabel(self.scroll_proc, text="PID", font=("Arial", 12, "bold"), width=60).grid(row=0, column=0, padx=5, pady=5)
        ctk.CTkLabel(self.scroll_proc, text="Nombre", font=("Arial", 12, "bold"), width=200, anchor="w").grid(row=0, column=1, padx=5, pady=5, sticky="w")
        ctk.CTkLabel(self.scroll_proc, text="RAM (MB)", font=("Arial", 12, "bold"), width=80).grid(row=0, column=2, padx=5, pady=5)
        ctk.CTkLabel(self.scroll_proc, text="Acción", font=("Arial", 12, "bold"), width=100).grid(row=0, column=3, padx=5, pady=5)
        
        processes = []
        for p in psutil.process_iter(['pid', 'name', 'memory_info']):
            try:
                mem = p.info['memory_info'].rss / (1024 * 1024)
                processes.append((p.info['pid'], p.info['name'], mem))
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
                
        # Ordenar por uso de RAM (descendente) y tomar los top 50 para no trabar la UI
        processes.sort(key=lambda x: x[2], reverse=True)
        
        for i, (pid, name, mem) in enumerate(processes[:50], start=1):
            name_lower = name.lower() if name else ""
            is_critical = name_lower in CRITICAL_PROCESSES
            
            # Color coding
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
            messagebox.showwarning("Proceso Crítico / Delicado", f"Proceso: {name_lower}\n\n{desc}\n\nSe recomienda NO detener este proceso.", parent=self)
        else:
            messagebox.showinfo("Proceso de Usuario / Aplicación", f"Proceso: {name_lower}\n\nEste proceso no está en la lista de procesos críticos del sistema. Generalmente es seguro detenerlo si corresponde a una aplicación congelada o que consume mucha RAM, pero podrías perder datos no guardados de esa aplicación.", parent=self)

    def load_services(self):
        # Limpiar
        for widget in self.scroll_serv.winfo_children():
            widget.destroy()
            
        # Encabezados
        ctk.CTkLabel(self.scroll_serv, text="Nombre / Mostrar", font=("Arial", 12, "bold"), width=250, anchor="w").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ctk.CTkLabel(self.scroll_serv, text="Estado", font=("Arial", 12, "bold"), width=100).grid(row=0, column=1, padx=5, pady=5)
        ctk.CTkLabel(self.scroll_serv, text="Tipo Inicio", font=("Arial", 12, "bold"), width=100).grid(row=0, column=2, padx=5, pady=5)
        ctk.CTkLabel(self.scroll_serv, text="Acción", font=("Arial", 12, "bold"), width=150).grid(row=0, column=3, padx=5, pady=5)
        
        services = []
        try:
            for s in psutil.win_service_iter():
                try:
                    info = s.as_dict()
                    # Mostrar solo aquellos que se puedan modificar razonablemente y esten running o auto
                    if info.get('start_type') in ['automatic', 'manual']:
                        services.append(info)
                except Exception:
                    pass
        except Exception as e:
            ctk.CTkLabel(self.scroll_serv, text=f"Error cargando servicios: {e}").grid(row=1, column=0)
            return

        # Filtrar o ordenar si es necesario. Mostrar primeros 50 ejecutandose o auto
        services = [s for s in services if s.get('status') == 'running' or s.get('start_type') == 'automatic']
        services.sort(key=lambda x: (x.get('status') != 'running', x.get('display_name')))
        
        for i, s in enumerate(services[:50], start=1):
            name = s.get('name', 'N/A')
            display = s.get('display_name', name)[:40]
            status = s.get('status', 'N/A')
            start_type = s.get('start_type', 'N/A')
            
            name_lower = name.lower()
            is_critical = name_lower in CRITICAL_SERVICES
            
            # Color coding
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
            desc = CRITICAL_SERVICES[name_lower]
            messagebox.showwarning("Servicio Crítico / Delicado", f"Servicio: {name_lower}\n\n{desc}\n\nSe recomienda NO cambiar a Manual ni detener este servicio.", parent=self)
        else:
            messagebox.showinfo("Servicio Secundario", f"Servicio: {name_lower}\n\nEste servicio no está catalogado como crítico del núcleo de Windows. Generalmente es seguro cambiarlo a Manual si pertenece a aplicaciones de terceros (como actualizadores) para ahorrar RAM. Si algo deja de funcionar, puedes volver a iniciarlo.", parent=self)

    def kill_process(self, pid, name):
        try:
            p = psutil.Process(pid)
            p.kill()
            messagebox.showinfo("Proceso Detenido", f"El proceso {name} (PID: {pid}) ha sido detenido.", parent=self)
            self.load_processes()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo detener el proceso {name}:\n{e}", parent=self)
            
    def set_service_manual(self, name):
        try:
            # sc config "name" start= demand
            subprocess.run(["sc", "config", name, "start=", "demand"], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            messagebox.showinfo("Servicio Modificado", f"El servicio {name} ahora está en modo Manual.", parent=self)
            self.load_services()
        except subprocess.CalledProcessError:
            messagebox.showerror("Permisos", f"No se pudo modificar {name}. ¿Ejecutaste el programa como Administrador?", parent=self)
        except Exception as e:
            messagebox.showerror("Error", f"Error inesperado: {e}", parent=self)

    def stop_service(self, name):
        try:
            # net stop "name" /y
            subprocess.run(["net", "stop", name, "/y"], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            messagebox.showinfo("Servicio Detenido", f"El servicio {name} ha sido detenido.", parent=self)
            self.load_services()
        except subprocess.CalledProcessError:
            messagebox.showerror("Permisos", f"No se pudo detener {name}. Es posible que se requieran permisos de Administrador.", parent=self)
        except Exception as e:
            messagebox.showerror("Error", f"Error inesperado: {e}", parent=self)

def main():
    app = ProcessManagerApp()
    app.mainloop()

if __name__ == "__main__":
    main()
