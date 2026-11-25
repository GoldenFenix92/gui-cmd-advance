import os
import threading
import subprocess
import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as tb
from ttkbootstrap.widgets.scrolled import ScrolledText
from functions.utils import center_window, get_user_data_path
from functions import ui_theme


def get_channel_for_suite(suite_id):
    if "2024" in suite_id:
        return "PerpetualVL2024"
    if "2019" in suite_id:
        return "PerpetualVL2019"
    return "PerpetualVL2021"


def build_office_xml(suite_id, arch, lang, include_visio=False, include_project=False):
    channel = get_channel_for_suite(suite_id)
    xml_content = f"""<Configuration>
  <Add OfficeClientEdition="{arch}" Channel="{channel}">
    <Product ID="{suite_id}">
      <Language ID="{lang}" />
    </Product>"""

    if include_visio:
        visio_id = "VisioPro2021Volume" if "2021" in suite_id else ("VisioPro2024Volume" if "2024" in suite_id else "VisioPro2019Volume")
        xml_content += f"""\n    <Product ID="{visio_id}">
      <Language ID="{lang}" />
    </Product>"""

    if include_project:
        proj_id = "ProjectPro2021Volume" if "2021" in suite_id else ("ProjectPro2024Volume" if "2024" in suite_id else "ProjectPro2019Volume")
        xml_content += f"""\n    <Product ID="{proj_id}">
      <Language ID="{lang}" />
    </Product>"""

    xml_content += """
  </Add>
  <Property Name="SharedComputerLicensing" Value="0" />
  <Property Name="FORCEAPPSHUTDOWN" Value="TRUE" />
  <Property Name="DeviceBasedLicensing" Value="0" />
  <Property Name="SCLCacheOverride" Value="0" />
  <RemoveMSI />
  <Display Level="Full" AcceptEULA="TRUE" />
</Configuration>"""
    return xml_content


def get_config_xml_path():
    tools_dir = get_user_data_path("tools")
    os.makedirs(tools_dir, exist_ok=True)
    return os.path.join(tools_dir, "config.xml")


class OfficeDeployApp(tb.Window):
    def __init__(self):
        theme = ui_theme.get_saved_theme()
        super().__init__(themename=theme)
        self.title("Despliegue de Microsoft Office (ODT)")
        center_window(self, 720, 620)
        ui_theme.apply_window_chrome(self, theme)

        self.office_suites = {
            "Office LTSC Professional Plus 2024": "ProPlus2024Volume",
            "Office LTSC Professional Plus 2021": "ProPlus2021Volume",
            "Office Professional Plus 2019": "ProPlus2019Volume",
        }
        self.languages = {
            "Español (España)": "es-es",
            "Español (México)": "es-mx",
            "Inglés (Estados Unidos)": "en-us",
        }

        self.setup_ui()

    def setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        title = tb.Label(self, text="Configurador de Instalación Office", font=("Segoe UI", 16, "bold"), bootstyle="primary")
        title.grid(row=0, column=0, pady=(16, 8))

        main_frame = tb.Labelframe(self, text="Configuración de Suite", padding=14, bootstyle="info")
        main_frame.grid(row=1, column=0, padx=20, pady=8, sticky="nsew")
        main_frame.grid_columnconfigure(1, weight=1)

        tb.Label(main_frame, text="Versión de Office:").grid(row=0, column=0, padx=8, pady=10, sticky="w")
        self.suite_var = tk.StringVar(value=list(self.office_suites.keys())[0])
        self.suite_menu = tb.Combobox(main_frame, textvariable=self.suite_var, values=list(self.office_suites.keys()), state="readonly")
        self.suite_menu.grid(row=0, column=1, padx=8, pady=10, sticky="ew")

        tb.Label(main_frame, text="Arquitectura:").grid(row=1, column=0, padx=8, pady=10, sticky="w")
        self.arch_var = tk.StringVar(value="64")
        self.arch_menu = tb.Combobox(main_frame, textvariable=self.arch_var, values=["64", "32"], state="readonly")
        self.arch_menu.grid(row=1, column=1, padx=8, pady=10, sticky="ew")

        tb.Label(main_frame, text="Idioma:").grid(row=2, column=0, padx=8, pady=10, sticky="w")
        self.lang_var = tk.StringVar(value=list(self.languages.keys())[0])
        self.lang_menu = tb.Combobox(main_frame, textvariable=self.lang_var, values=list(self.languages.keys()), state="readonly")
        self.lang_menu.grid(row=2, column=1, padx=8, pady=10, sticky="ew")

        self.visio_var = tk.BooleanVar(value=False)
        tb.Checkbutton(main_frame, text="Incluir Visio LTSC Pro", variable=self.visio_var, bootstyle="round-toggle").grid(row=3, column=0, padx=8, pady=10, sticky="w")

        self.project_var = tk.BooleanVar(value=False)
        tb.Checkbutton(main_frame, text="Incluir Project LTSC Pro", variable=self.project_var, bootstyle="round-toggle").grid(row=3, column=1, padx=8, pady=10, sticky="w")

        action_frame = tb.Frame(self)
        action_frame.grid(row=2, column=0, pady=12)

        self.btn_generate = tb.Button(action_frame, text="1. Generar config.xml", command=self.generate_xml, bootstyle="primary")
        self.btn_generate.grid(row=0, column=0, padx=8)

        self.btn_download = tb.Button(action_frame, text="2. Descargar ODT (setup.exe)", command=self.download_odt, bootstyle="secondary")
        self.btn_download.grid(row=0, column=1, padx=8)

        self.btn_install = tb.Button(action_frame, text="3. Instalar Office", command=self.install_office, bootstyle="success")
        self.btn_install.grid(row=0, column=2, padx=8)

        self.log_textbox = ScrolledText(self, height=10, font=("Consolas", 10), auto_hide=True)
        self.log_textbox.grid(row=3, column=0, padx=20, pady=(4, 16), sticky="nsew")
        self.log("Sistema listo. Elige tu configuración y genera el XML.")

    def log(self, text):
        def _append():
            self.log_textbox.text.insert("end", text + "\n")
            self.log_textbox.text.see("end")
        if threading.current_thread() is threading.main_thread():
            _append()
        else:
            self.after(0, _append)

    def generate_xml(self):
        try:
            suite_id = self.office_suites[self.suite_var.get()]
            arch = self.arch_var.get()
            lang = self.languages[self.lang_var.get()]

            xml_content = build_office_xml(
                suite_id=suite_id,
                arch=arch,
                lang=lang,
                include_visio=self.visio_var.get(),
                include_project=self.project_var.get(),
            )

            config_path = get_config_xml_path()
            with open(config_path, "w", encoding="utf-8") as f:
                f.write(xml_content)

            self.log(f"[+] config.xml generado exitosamente en: {config_path}")
            messagebox.showinfo("Éxito", f"config.xml ha sido generado correctamente en:\n{config_path}", parent=self)
        except Exception as e:
            self.log(f"[-] Error al generar XML: {str(e)}")

    def download_odt(self):
        self.log("[*] Abriendo página oficial para descargar ODT...")
        subprocess.Popen(
            ["powershell", "-Command", "Start-Process 'https://www.microsoft.com/en-us/download/details.aspx?id=49117'"],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        self.log("Por favor, descarga la herramienta, ejecútala y extrae el archivo 'setup.exe' en la carpeta de herramientas del programa.")

    def install_office(self):
        setup_path = get_user_data_path(os.path.join("tools", "setup.exe"))
        if not os.path.exists(setup_path) and os.path.exists("setup.exe"):
            setup_path = "setup.exe"

        if not os.path.exists(setup_path):
            messagebox.showerror("Error", "No se encontró 'setup.exe'. Por favor asegúrate de instalar el complemento ODT.", parent=self)
            return

        config_path = get_config_xml_path()
        if not os.path.exists(config_path):
            messagebox.showerror("Error", "Primero debes generar el archivo config.xml.", parent=self)
            return

        self.log("[*] Iniciando instalación de Office. Esto tomará varios minutos...")

        def run_install():
            try:
                subprocess.run(
                    [setup_path, "/configure", config_path],
                    check=True,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                self.log("[+] Instalación finalizada exitosamente (o proceso delegado a Windows).")
            except Exception as e:
                self.log(f"[-] Ocurrió un error en la instalación: {str(e)}")

        threading.Thread(target=run_install, daemon=True).start()


def main():
    app = OfficeDeployApp()
    app.mainloop()


if __name__ == "__main__":
    main()
