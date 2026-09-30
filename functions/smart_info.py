import customtkinter as ctk
import subprocess
import threading
import json
import re
from gui_app import center_window, get_resource_path

def parse_smart_data(vendor_specific):
    attributes = []
    if not vendor_specific or len(vendor_specific) < 362:
        return attributes
    
    for i in range(30):
        offset = 2 + (i * 12)
        attr_id = vendor_specific[offset]
        if attr_id == 0:
            continue
            
        current_val = vendor_specific[offset+3]
        worst_val = vendor_specific[offset+4]
        
        raw_val = 0
        for j in range(6):
            raw_val |= (vendor_specific[offset + 5 + j] << (8 * j))
            
        attributes.append({
            "id": attr_id,
            "current": current_val,
            "worst": worst_val,
            "raw": raw_val
        })
    return attributes

KNOWN_ATTRIBUTES = {
    1: "Tasa de Errores de Lectura",
    2: "Rendimiento (Throughput)",
    3: "Tiempo de Arranque (Spin-Up)",
    4: "Ciclos de Arranque/Parada",
    5: "Sectores Reasignados (Peligro)",
    7: "Tasa de Errores de Búsqueda",
    8: "Rendimiento de Búsqueda",
    9: "Horas de Encendido (Uso Total)",
    10: "Reintentos de Giro",
    12: "Ciclos de Encendido",
    192: "Apagados Inseguros",
    193: "Ciclos de Carga/Descarga",
    194: "Temperatura (°C)",
    196: "Eventos de Reasignación",
    197: "Sectores Pendientes (Precaución)",
    198: "Sectores Incorregibles",
    199: "Errores CRC UltraDMA",
    232: "Desgaste del Disco (Wear %)"
}

class SmartInfoApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Estado de Salud SMART Avanzado (CrystalDiskInfo Clone)")
        center_window(self, 900, 600)
        try: self.iconbitmap(get_resource_path("app_icon.ico"))
        except: pass
        
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, padx=20, pady=10, sticky="ew")
        
        self.btn_refresh = ctk.CTkButton(top, text="🔄 Analizar Discos", command=self.analyze, fg_color="#27AE60", hover_color="#1E8449")
        self.btn_refresh.pack(side="left")
        
        self.lbl_status = ctk.CTkLabel(top, text="Presiona Analizar para leer datos SMART...", font=("Arial", 12))
        self.lbl_status.pack(side="left", padx=20)
        
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")

    def analyze(self):
        for w in self.scroll.winfo_children(): w.destroy()
        self.lbl_status.configure(text="Extrayendo datos de WMI/CIM...")
        self.btn_refresh.configure(state="disabled")
        
        def task():
            # 1. ATAPI Smart Data (SATA/HDD)
            cmd_smart = "Get-WmiObject -Namespace root\\wmi -Class MSStorageDriver_ATAPISmartData | Select-Object InstanceName, VendorSpecific | ConvertTo-Json -Depth 3"
            try:
                out = subprocess.check_output(["powershell", "-Command", cmd_smart], creationflags=subprocess.CREATE_NO_WINDOW)
                d = out.decode('mbcs', 'ignore').strip()
                smart_raw = json.loads(d) if d else []
                if isinstance(smart_raw, dict): smart_raw = [smart_raw]
            except:
                smart_raw = []
                
            # 2. Storage Reliability Counters (NVMe y otros modernos)
            cmd_rel = "Get-PhysicalDisk | Get-StorageReliabilityCounter | Select-Object DeviceId, Temperature, PowerOnHours, ReadErrorsTotal, WriteErrorsTotal, Wear | ConvertTo-Json -Depth 3"
            try:
                out_rel = subprocess.check_output(["powershell", "-Command", cmd_rel], creationflags=subprocess.CREATE_NO_WINDOW)
                d_rel = out_rel.decode('mbcs', 'ignore').strip()
                rel_data = json.loads(d_rel) if d_rel else []
                if isinstance(rel_data, dict): rel_data = [rel_data]
            except:
                rel_data = []
                
            # 3. Discos Físicos (General)
            cmd_phys = "Get-PhysicalDisk | Select-Object DeviceId, FriendlyName, MediaType, HealthStatus, Temperature | ConvertTo-Json -Depth 3"
            try:
                out = subprocess.check_output(["powershell", "-Command", cmd_phys], creationflags=subprocess.CREATE_NO_WINDOW)
                d = out.decode('mbcs', 'ignore').strip()
                phys_data = json.loads(d) if d else []
                if isinstance(phys_data, dict): phys_data = [phys_data]
            except:
                phys_data = []

            disks_info = []
            for phys in phys_data:
                name = phys.get("FriendlyName", "Unknown")
                status = phys.get("HealthStatus", "Unknown")
                temp = phys.get("Temperature")
                media = phys.get("MediaType", "Unknown")
                dev_id = str(phys.get("DeviceId", ""))
                
                # Coincidencia con ATAPI
                matching_smart = None
                clean_name = re.sub(r'[^A-Z0-9]', '', name.upper())
                
                for sr in smart_raw:
                    inst = sr.get("InstanceName", "")
                    clean_inst = re.sub(r'[^A-Z0-9]', '', inst.upper())
                    
                    if len(clean_name) > 5 and clean_name[:int(len(clean_name)/1.5)] in clean_inst:
                        matching_smart = sr
                        break
                    
                    n_parts = name.upper().replace("-", " ").split()
                    matches = sum(1 for p in n_parts if len(p) > 3 and p in inst.upper())
                    if (len(n_parts) == 1 and matches == 1) or (len(n_parts) > 1 and matches >= 2):
                        matching_smart = sr
                        break

                parsed_attrs = []
                if matching_smart and "VendorSpecific" in matching_smart:
                    parsed_attrs = parse_smart_data(matching_smart["VendorSpecific"])
                
                # Coincidencia con NVMe Reliability
                disk_rel = next((r for r in rel_data if str(r.get("DeviceId")) == dev_id), None)
                if disk_rel:
                    # Enriquecer o crear atributos SMART faltantes para NVMe
                    existing_ids = [a["id"] for a in parsed_attrs]
                    if disk_rel.get("PowerOnHours") is not None and 9 not in existing_ids:
                        parsed_attrs.append({"id": 9, "current": 100, "worst": 100, "raw": disk_rel["PowerOnHours"]})
                    if disk_rel.get("Wear") is not None and 232 not in existing_ids:
                        parsed_attrs.append({"id": 232, "current": 100 - disk_rel["Wear"], "worst": 100, "raw": disk_rel["Wear"]})
                    if disk_rel.get("ReadErrorsTotal") is not None and 1 not in existing_ids:
                        parsed_attrs.append({"id": 1, "current": 100, "worst": 100, "raw": disk_rel["ReadErrorsTotal"]})
                    if disk_rel.get("Temperature") is not None and 194 not in existing_ids:
                        parsed_attrs.append({"id": 194, "current": 100, "worst": 100, "raw": disk_rel["Temperature"]})
                
                # Ordenar atributos por ID
                parsed_attrs.sort(key=lambda x: x["id"])
                    
                disks_info.append({
                    "name": name,
                    "media": media,
                    "status": status,
                    "temp": temp,
                    "smart": parsed_attrs
                })
                
            self.after(0, self.done, disks_info)
            
        threading.Thread(target=task, daemon=True).start()

    def done(self, disks_info):
        self.btn_refresh.configure(state="normal")
        if not disks_info:
            self.lbl_status.configure(text="No se pudo obtener información SMART. Asegúrate de ejecutar como Administrador.")
            return
            
        self.lbl_status.configure(text="Análisis completado.")
        
        for disk in disks_info:
            f = ctk.CTkFrame(self.scroll, fg_color="#1E1E1E", corner_radius=8, border_width=1, border_color="#333333")
            f.pack(fill="x", pady=10, padx=5)
            
            top_bar = ctk.CTkFrame(f, fg_color="transparent")
            top_bar.pack(fill="x", padx=10, pady=10)
            
            color = "#28a745" if disk["status"] == "Healthy" else "#dc3545"
            ctk.CTkLabel(top_bar, text=f"💾 {disk['name']} ({disk['media']})", font=("Arial", 16, "bold")).pack(side="left")
            ctk.CTkLabel(top_bar, text=f"Salud: {disk['status']}", font=("Arial", 14, "bold"), text_color=color).pack(side="right", padx=20)
            
            final_temp = disk["temp"]
            for attr in disk["smart"]:
                if attr["id"] == 194:
                    t_val = attr["raw"] & 0xFF
                    if t_val > 0 and t_val < 100:
                        final_temp = t_val
                        break

            if final_temp:
                ctk.CTkLabel(top_bar, text=f"🌡️ {final_temp} °C", font=("Arial", 15, "bold"), text_color="#F39C12").pack(side="right", padx=20)
            else:
                ctk.CTkLabel(top_bar, text="🌡️ N/A", font=("Arial", 15, "bold"), text_color="gray").pack(side="right", padx=20)

            if disk["smart"]:
                table_frame = ctk.CTkFrame(f, fg_color="transparent")
                table_frame.pack(fill="x", padx=10, pady=(0, 10))
                
                ctk.CTkLabel(table_frame, text="ID", font=("Arial", 12, "bold"), width=40).grid(row=0, column=0, padx=5, sticky="w")
                ctk.CTkLabel(table_frame, text="Atributo", font=("Arial", 12, "bold"), width=250).grid(row=0, column=1, padx=5, sticky="w")
                ctk.CTkLabel(table_frame, text="Actual", font=("Arial", 12, "bold"), width=80).grid(row=0, column=2, padx=5)
                ctk.CTkLabel(table_frame, text="Peor", font=("Arial", 12, "bold"), width=80).grid(row=0, column=3, padx=5)
                ctk.CTkLabel(table_frame, text="Valores Crudos", font=("Arial", 12, "bold"), width=150).grid(row=0, column=4, padx=5, sticky="e")
                
                row_idx = 1
                for attr in disk["smart"]:
                    a_id = attr["id"]
                    name = KNOWN_ATTRIBUTES.get(a_id, f"Atributo Desconocido ({a_id})")
                    
                    tc = "white"
                    if "Peligro" in name: tc = "#E74C3C"
                    elif "Precaución" in name: tc = "#F39C12"
                    
                    ctk.CTkLabel(table_frame, text=f"{a_id:02X}", font=("Consolas", 12)).grid(row=row_idx, column=0, padx=5, sticky="w")
                    ctk.CTkLabel(table_frame, text=name, font=("Arial", 12), text_color=tc).grid(row=row_idx, column=1, padx=5, sticky="w")
                    ctk.CTkLabel(table_frame, text=str(attr["current"]), font=("Consolas", 12)).grid(row=row_idx, column=2, padx=5)
                    ctk.CTkLabel(table_frame, text=str(attr["worst"]), font=("Consolas", 12)).grid(row=row_idx, column=3, padx=5)
                    ctk.CTkLabel(table_frame, text=f"{attr['raw']}", font=("Consolas", 12)).grid(row=row_idx, column=4, padx=5, sticky="e")
                    
                    row_idx += 1
            else:
                ctk.CTkLabel(f, text="Detalles SMART no disponibles para esta unidad.", font=("Arial", 12), text_color="gray").pack(pady=(0, 10))

if __name__ == "__main__":
    app = SmartInfoApp()
    app.mainloop()
