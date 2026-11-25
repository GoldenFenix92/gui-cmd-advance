import json
import re
import subprocess
import threading
import ttkbootstrap as tb
from ttkbootstrap.widgets.scrolled import ScrolledFrame
from functions.utils import center_window
from functions import ui_theme


def parse_smart_data(vendor_specific):
    attributes = []
    if not vendor_specific or len(vendor_specific) < 362:
        return attributes

    for i in range(30):
        offset = 2 + (i * 12)
        attr_id = vendor_specific[offset]
        if attr_id == 0:
            continue

        current_val = vendor_specific[offset + 3]
        worst_val = vendor_specific[offset + 4]

        raw_val = 0
        for j in range(6):
            raw_val |= vendor_specific[offset + 5 + j] << (8 * j)

        attributes.append({
            "id": attr_id,
            "current": current_val,
            "worst": worst_val,
            "raw": raw_val,
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
    232: "Desgaste del Disco (Wear %)",
}


class SmartInfoApp(tb.Window):
    def __init__(self):
        theme = ui_theme.get_saved_theme()
        super().__init__(themename=theme)
        self.title("Estado de Salud SMART Avanzado")
        center_window(self, 940, 640)
        ui_theme.apply_window_chrome(self, theme)

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        top = tb.Frame(self, padding=(16, 12))
        top.grid(row=0, column=0, sticky="ew")

        icon_refresh = ui_theme.get_bootstrap_icon("refresh", size=14, color="#FFFFFF", master=self)
        self.btn_refresh = tb.Button(
            top, text=" Analizar Discos", image=icon_refresh, compound="left",
            command=self.analyze, bootstyle="success",
        )
        self.btn_refresh.pack(side="left")

        icon_ai = ui_theme.get_bootstrap_icon("ai", size=14, color="#FFFFFF", master=self)
        self.btn_ai_smart = tb.Button(
            top, text=" Interpretar SMART con IA", image=icon_ai, compound="left",
            command=self.interpret_with_ai, bootstyle="info", state="disabled",
        )
        self.btn_ai_smart.pack(side="right")

        self.lbl_status = tb.Label(top, text="Presiona Analizar para leer datos SMART...", font=("Segoe UI", 10))
        self.lbl_status.pack(side="left", padx=16)
        self._last_disks_info = []

        self.scroll = ScrolledFrame(self, autohide=True, padding=10)
        self.scroll.grid(row=1, column=0, padx=16, pady=(0, 14), sticky="nsew")

    def analyze(self):
        for w in self.scroll.winfo_children():
            w.destroy()
        self.lbl_status.configure(text="Extrayendo datos de WMI/CIM...")
        self.btn_refresh.configure(state="disabled")

        def task():
            cmd_smart = "Get-WmiObject -Namespace root\\wmi -Class MSStorageDriver_ATAPISmartData | Select-Object InstanceName, VendorSpecific | ConvertTo-Json -Depth 3"
            try:
                out = subprocess.check_output(
                    ["powershell", "-Command", cmd_smart],
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                d = out.decode("mbcs", "ignore").strip()
                smart_raw = json.loads(d) if d else []
                if isinstance(smart_raw, dict):
                    smart_raw = [smart_raw]
            except Exception:
                smart_raw = []

            cmd_rel = "Get-PhysicalDisk | Get-StorageReliabilityCounter | Select-Object DeviceId, Temperature, PowerOnHours, ReadErrorsTotal, WriteErrorsTotal, Wear | ConvertTo-Json -Depth 3"
            try:
                out_rel = subprocess.check_output(
                    ["powershell", "-Command", cmd_rel],
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                d_rel = out_rel.decode("mbcs", "ignore").strip()
                rel_data = json.loads(d_rel) if d_rel else []
                if isinstance(rel_data, dict):
                    rel_data = [rel_data]
            except Exception:
                rel_data = []

            cmd_phys = "Get-PhysicalDisk | Select-Object DeviceId, FriendlyName, MediaType, HealthStatus, Temperature | ConvertTo-Json -Depth 3"
            try:
                out = subprocess.check_output(
                    ["powershell", "-Command", cmd_phys],
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                d = out.decode("mbcs", "ignore").strip()
                phys_data = json.loads(d) if d else []
                if isinstance(phys_data, dict):
                    phys_data = [phys_data]
            except Exception:
                phys_data = []

            disks_info = []
            for phys in phys_data:
                name = phys.get("FriendlyName", "Unknown")
                status = phys.get("HealthStatus", "Unknown")
                temp = phys.get("Temperature")
                media = phys.get("MediaType", "Unknown")
                dev_id = str(phys.get("DeviceId", ""))

                matching_smart = None
                clean_name = re.sub(r"[^A-Z0-9]", "", name.upper())

                for sr in smart_raw:
                    inst = sr.get("InstanceName", "")
                    clean_inst = re.sub(r"[^A-Z0-9]", "", inst.upper())
                    if len(clean_name) > 5 and clean_name[:int(len(clean_name) / 1.5)] in clean_inst:
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

                disk_rel = next((r for r in rel_data if str(r.get("DeviceId")) == dev_id), None)
                if disk_rel:
                    existing_ids = [a["id"] for a in parsed_attrs]
                    if disk_rel.get("PowerOnHours") is not None and 9 not in existing_ids:
                        parsed_attrs.append({"id": 9, "current": 100, "worst": 100, "raw": disk_rel["PowerOnHours"]})
                    if disk_rel.get("Wear") is not None and 232 not in existing_ids:
                        parsed_attrs.append({"id": 232, "current": 100 - disk_rel["Wear"], "worst": 100, "raw": disk_rel["Wear"]})
                    if disk_rel.get("ReadErrorsTotal") is not None and 1 not in existing_ids:
                        parsed_attrs.append({"id": 1, "current": 100, "worst": 100, "raw": disk_rel["ReadErrorsTotal"]})
                    if disk_rel.get("Temperature") is not None and 194 not in existing_ids:
                        parsed_attrs.append({"id": 194, "current": 100, "worst": 100, "raw": disk_rel["Temperature"]})

                parsed_attrs.sort(key=lambda x: x["id"])
                disks_info.append({
                    "name": name,
                    "media": media,
                    "status": status,
                    "temp": temp,
                    "smart": parsed_attrs,
                })

            self.after(0, self.done, disks_info)

        threading.Thread(target=task, daemon=True).start()

    def done(self, disks_info):
        self.btn_refresh.configure(state="normal")
        self._last_disks_info = disks_info or []
        if not disks_info:
            self.btn_ai_smart.configure(state="disabled")
            self.lbl_status.configure(text="No se pudo obtener información SMART. Asegúrate de ejecutar como Administrador.")
            return

        self.btn_ai_smart.configure(state="normal")
        self.lbl_status.configure(text=f"Análisis completado ({len(disks_info)} unidades detectadas).")

        for disk in disks_info:
            is_healthy = disk["status"] == "Healthy"
            card_style = "success" if is_healthy else "danger"
            card = tb.Labelframe(self.scroll, text=f"{disk['name']} ({disk['media']})", padding=10, bootstyle=card_style)
            card.pack(fill="x", pady=8, padx=4)

            top_bar = tb.Frame(card)
            top_bar.pack(fill="x", pady=(0, 8))

            tb.Label(
                top_bar,
                text=f"Salud: {disk['status']}",
                font=("Segoe UI", 11, "bold"),
                bootstyle="success" if is_healthy else "danger",
            ).pack(side="left")

            final_temp = disk["temp"]
            for attr in disk["smart"]:
                if attr["id"] == 194:
                    t_val = attr["raw"] & 0xFF
                    if 0 < t_val < 100:
                        final_temp = t_val
                        break

            if final_temp:
                t_style = "danger" if final_temp >= 55 else ("warning" if final_temp >= 45 else "info")
                tb.Label(top_bar, text=f"Temperatura: {final_temp} °C", font=("Segoe UI", 11, "bold"), bootstyle=t_style).pack(side="right")
            else:
                tb.Label(top_bar, text="Temperatura: N/A", font=("Segoe UI", 10), bootstyle="secondary").pack(side="right")

            if disk["smart"]:
                cols = ("id", "atributo", "actual", "peor", "crudo")
                tree = tb.Treeview(card, columns=cols, show="headings", height=min(12, len(disk["smart"])), bootstyle=card_style)
                tree.heading("id", text="ID")
                tree.heading("atributo", text="Atributo SMART")
                tree.heading("actual", text="Actual")
                tree.heading("peor", text="Peor")
                tree.heading("crudo", text="Valor Crudo")

                tree.column("id", width=60, anchor="center")
                tree.column("atributo", width=360, anchor="w")
                tree.column("actual", width=90, anchor="center")
                tree.column("peor", width=90, anchor="center")
                tree.column("crudo", width=160, anchor="e")

                tree.tag_configure("danger", foreground="#F87171")
                tree.tag_configure("warning", foreground="#FBBF24")

                for attr in disk["smart"]:
                    a_id = attr["id"]
                    name = KNOWN_ATTRIBUTES.get(a_id, f"Atributo Desconocido ({a_id})")
                    tag = ()
                    if "Peligro" in name and attr["raw"] > 0:
                        tag = ("danger",)
                    elif "Precaución" in name and attr["raw"] > 0:
                        tag = ("warning",)
                    tree.insert("", "end", values=(f"{a_id:02X}", name, attr["current"], attr["worst"], attr["raw"]), tags=tag)

                tree.pack(fill="x")
            else:
                tb.Label(card, text="Detalles SMART no disponibles para esta unidad.", bootstyle="secondary").pack(anchor="w", pady=4)

    def interpret_with_ai(self):
        if not self._last_disks_info:
            return
        lines = ["REPORTE DE SALUD SMART DE DISCOS", "=" * 50]
        for disk in self._last_disks_info:
            lines.append(f"Disco: {disk['name']} | Tipo: {disk['media']} | Salud: {disk['status']} | Temp: {disk.get('temp') or 'N/A'} C")
            for attr in disk.get("smart", []):
                a_id = attr["id"]
                aname = KNOWN_ATTRIBUTES.get(a_id, f"Atributo ({a_id})")
                lines.append(f"  - ID {a_id:02X} ({aname}): Actual={attr['current']}, Peor={attr['worst']}, Raw={attr['raw']}")
            lines.append("")
        from functions.interpreter_addon import InterpreterApp
        InterpreterApp(self, initial_text="\n".join(lines), domain="storage")


if __name__ == "__main__":
    app = SmartInfoApp()
    app.mainloop()
