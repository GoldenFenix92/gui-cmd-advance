import customtkinter as ctk
import os
import re
import json
from tkinter import filedialog, messagebox
import threading
import sys
import urllib.request
import urllib.error
import ctypes
from functions.utils import get_user_data_path

def get_base_path():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def center_window(window, width, height):
    window.update_idletasks()
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    x = int((screen_width / 2) - (width / 2))
    y = int((screen_height / 2) - (height / 2))
    window.geometry(f"{width}x{height}+{x}+{y}")

def apply_dark_titlebar(window):
    try:
        window.update()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        # 1 for dark mode, 2 for some win11 builds. We try 1 or 2.
        value = ctypes.c_int(2)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(value), ctypes.sizeof(value))
    except:
        pass

def get_api_settings():
    old_settings_path = get_user_data_path("ai_settings.json")
    tools_dir = get_user_data_path("tools")
    os.makedirs(tools_dir, exist_ok=True)
    settings_path = os.path.join(tools_dir, "ai_settings.json")
    
    # Migrate old settings if present
    if os.path.exists(old_settings_path) and not os.path.exists(settings_path):
        import shutil
        try: shutil.move(old_settings_path, settings_path)
        except: pass

    default_settings = {
        "providers": {
            "Google Gemini": {"api_key": "", "model": "", "cached_models": []},
            "OpenAI": {"api_key": "", "model": "", "cached_models": []},
            "Anthropic Claude": {"api_key": "", "model": "", "cached_models": []},
            "Groq": {"api_key": "", "model": "", "cached_models": []},
            "Deepseek": {"api_key": "", "model": "", "cached_models": []},
            "Personalizado": {"api_key": "", "model": "", "base_url": "", "cached_models": []}
        },
        "current_provider": "Google Gemini",
        "free_only": True,
        "model_train": []
    }
    try:
        if os.path.exists(settings_path):
            with open(settings_path, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if "providers" not in saved:
                    prov = saved.get("provider", "Google Gemini")
                    default_settings["current_provider"] = prov
                    default_settings["providers"][prov]["api_key"] = saved.get("api_key", "")
                    default_settings["providers"][prov]["model"] = saved.get("model", "")
                    default_settings["providers"][prov]["cached_models"] = saved.get("cached_models", [])
                    if "base_url" in saved: default_settings["providers"][prov]["base_url"] = saved["base_url"]
                    if "free_only" in saved: default_settings["free_only"] = saved["free_only"]
                else:
                    for k, v in saved.items():
                        if k == "providers":
                            for pk, pv in v.items():
                                if pk in default_settings["providers"]:
                                    default_settings["providers"][pk].update(pv)
                        else:
                            default_settings[k] = v
    except:
        pass
    return default_settings

class InterpreterApp(ctk.CTkToplevel):
    def __init__(self, parent, initial_text=""):
        super().__init__(parent)
        self.title("✨ Intérprete Asistido de Reportes (Premium)")
        center_window(self, 1100, 650)
        
        def _set_icon_and_theme():
            try:
                self.iconbitmap(os.path.join(get_base_path(), "resources", "app_icon.ico"))
            except: pass
            if ctk.get_appearance_mode().lower() == "dark":
                apply_dark_titlebar(self)
        self.after(200, _set_icon_and_theme)

        self.transient(parent)
        self.grab_set()

        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self.top_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.top_frame.grid(row=0, column=0, columnspan=2, padx=15, pady=15, sticky="ew")

        self.btn_load = ctk.CTkButton(self.top_frame, text="📁 Cargar Archivo (.txt/.log)", width=160, fg_color="#2E86C1", hover_color="#21618C", command=self.load_file)
        self.btn_load.pack(side="left", padx=(0, 10))

        self.btn_offline = ctk.CTkButton(self.top_frame, text="⚡ Analizar (Básico Offline)", width=160, fg_color="#F39C12", hover_color="#D68910", command=self.run_offline)
        self.btn_offline.pack(side="left", padx=(0, 10))

        self.btn_online = ctk.CTkButton(self.top_frame, text="🧠 Analizar con IA (Online)", width=160, fg_color="#8E44AD", hover_color="#9B59B6", command=self.run_online)
        self.btn_online.pack(side="left", padx=(0, 10))

        self.btn_config = ctk.CTkButton(self.top_frame, text="⚙️ Configurar API (IA)", width=150, fg_color="#475569", hover_color="#334155", command=self.config_api)
        self.btn_config.pack(side="right")

        self.lbl_raw = ctk.CTkLabel(self, text="Reporte Original (Consola):", font=("Arial", 14, "bold"))
        self.lbl_raw.grid(row=1, column=0, padx=15, pady=(0, 5), sticky="nw")

        self.txt_raw = ctk.CTkTextbox(self, font=("Consolas", 12))
        self.txt_raw.grid(row=2, column=0, padx=15, pady=(0, 15), sticky="nsew")
        if initial_text.strip():
            self.txt_raw.insert("1.0", initial_text)

        self.lbl_out = ctk.CTkLabel(self, text="Interpretación en Lenguaje Natural:", font=("Arial", 14, "bold"), text_color=("#1f6aa5", "#3B8ED0"))
        self.lbl_out.grid(row=1, column=1, padx=15, pady=(0, 5), sticky="nw")

        self.txt_out = ctk.CTkTextbox(self, font=("Arial", 14), wrap="word")
        self.txt_out.grid(row=2, column=1, padx=15, pady=(0, 15), sticky="nsew")
        self.txt_out.configure(state="disabled")

        # Bottom Frame for Status and Export Buttons
        self.bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.bottom_frame.grid(row=3, column=0, columnspan=2, padx=15, pady=(0, 10), sticky="ew")
        
        self.lbl_status = ctk.CTkLabel(self.bottom_frame, text="Listo.", text_color="gray")
        self.lbl_status.pack(side="left")

        self.btn_export = ctk.CTkButton(self.bottom_frame, text="💾 Exportar Interpretación", width=160, fg_color="#27AE60", hover_color="#2ECC71", command=self.export_interpretation)
        self.btn_export.pack(side="right", padx=(10, 0))


    def export_interpretation(self):
        content = self.txt_out.get("1.0", "end").strip()
        if not content:
            messagebox.showwarning("Vacío", "No hay nada que exportar.")
            return
        file_path = filedialog.asksaveasfilename(defaultextension=".html", filetypes=[("HTML Document", "*.html"), ("Markdown", "*.md"), ("Texto plano", "*.txt")], title="Guardar Interpretación")
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    if file_path.endswith(".html"):
                        html = content
                        html = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', html)
                        html = re.sub(r'\*(.*?)\*', r'<i>\1</i>', html)
                        html = html.replace('\n', '<br>')
                        f.write(f"<!DOCTYPE html><html><head><meta charset='utf-8'><style>body{{font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 20px; line-height: 1.6; color: #eee; background-color: #1e1e1e;}} .container{{max-width: 800px; margin: 0 auto; background: #2d2d2d; padding: 30px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.3);}} h2{{color: #4da6ff;}}</style></head><body><div class='container'><h2>✨ Reporte Interpretado</h2>{html}</div></body></html>")
                    else:
                        f.write(content)
                messagebox.showinfo("Guardado", f"Interpretación exportada exitosamente.\n{file_path}")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo guardar: {e}")

    def load_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Archivos de texto/log", "*.txt *.log"), ("Todos los archivos", "*.*")])
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                self.txt_raw.delete("1.0", "end")
                self.txt_raw.insert("1.0", content)
                self.lbl_status.configure(text=f"Archivo cargado: {os.path.basename(file_path)}")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo leer el archivo: {e}")

    def run_offline(self):
        content = self.txt_raw.get("1.0", "end").strip()
        if not content: return
        self.lbl_status.configure(text="Analizando localmente...")
        output = []
        lower_content = content.lower()

        if "ping" in lower_content and "ttl=" in lower_content:
            output.append("🟢 **Comando Ping Detectado**")
            perdidos = re.search(r"(?:perdidos|lost)\s*=\s*(\d+)", lower_content)
            if perdidos:
                num = int(perdidos.group(1))
                if num == 0: output.append("✅ Tu conexión hacia el destino es estable y no hay pérdida de datos.")
                else: output.append(f"⚠️ Alerta: Se detectó una pérdida de {num} paquetes.")
            media = re.search(r"(?:media|average)\s*=\s*(\d+)ms", lower_content)
            if media:
                ms = int(media.group(1))
                if ms < 50: output.append(f"⚡ Tu latencia promedio es excelente ({ms} ms).")
                elif ms < 150: output.append(f"🟡 Tu latencia promedio es normal ({ms} ms).")
                else: output.append(f"🔴 Tu latencia es muy alta ({ms} ms).")
            output.append("\n---\n")

        if "ipconfig" in lower_content or "lan" in lower_content or "ethernet" in lower_content:
            ip = re.search(r"(?:direcci.n ipv4|ipv4 address)[^:]*: ([\d\.]+)", lower_content)
            gw = re.search(r"(?:puerta de enlace predeterminada|default gateway)[^:]*: ([\d\.]+)", lower_content)
            if ip or gw:
                output.append("🟢 **Configuración de Red (IPConfig) Detectada**")
                if ip: output.append(f"✅ Estás conectado correctamente. Tu dirección IP local en esta red es: **{ip.group(1)}**.")
                if gw: output.append(f"✅ La dirección de tu router principal (Puerta de enlace) es: **{gw.group(1)}**.")
                output.append("\n---\n")

        if not output:
            output.append("ℹ️ **Análisis Local Finalizado**\n\nNo se detectó un patrón conocido.")

        self.set_output("\n".join(output))
        self.lbl_status.configure(text="Análisis offline completado.")

    def run_online(self):
        content = self.txt_raw.get("1.0", "end").strip()
        if not content: return
        settings = get_api_settings()
        if not settings.get("api_key") or not settings.get("model"):
            if messagebox.askyesno("API Key", "Falta configurar la API o el modelo. ¿Deseas configurarlos ahora?"):
                self.config_api()
            return
        self.lbl_status.configure(text="Conectando con IA... Por favor espera.")
        self.set_output("Analizando con IA... ⏳\n\nSi el reporte es muy largo, esto puede tomar unos segundos.")
        threading.Thread(target=self._call_api, args=(settings, content), daemon=True).start()

    def _call_api(self, settings, content):
        provider = settings.get("current_provider", "Google Gemini")
        prov_data = settings.get("providers", {}).get(provider, {})
        api_key = prov_data.get("api_key", "")
        model = prov_data.get("model", "")
        base_url = prov_data.get("base_url", "")

        prompt = "Instrucción estricta: Traduce este resultado crudo de consola a lenguaje natural, indicando proceso, significado y errores. Usa emojis. ESTÁ ESTRICTAMENTE PROHIBIDO usar formato Markdown (sin asteriscos **, sin numerales ##, sin cursivas). Devuelve texto plano totalmente limpio.\n\n" + content
        try:
            if provider == "Google Gemini":
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
                headers = {'Content-Type': 'application/json'}
                data = {"contents": [{"parts":[{"text": prompt}]}]}
                req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')
                with urllib.request.urlopen(req) as response:
                    result = json.loads(response.read().decode())
                    text_response = result['candidates'][0]['content']['parts'][0]['text']
                    
            elif provider == "Anthropic Claude":
                url = "https://api.anthropic.com/v1/messages"
                headers = {'Content-Type': 'application/json', 'x-api-key': api_key, 'anthropic-version': '2023-06-01'}
                data = {"model": model, "max_tokens": 1024, "messages": [{"role": "user", "content": prompt}]}
                req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')
                with urllib.request.urlopen(req) as response:
                    result = json.loads(response.read().decode())
                    text_response = result['content'][0]['text']
                    
            elif provider in ["OpenAI", "Groq", "Deepseek", "Personalizado"]:
                if provider == "OpenAI": url = "https://api.openai.com/v1/chat/completions"
                elif provider == "Groq": url = "https://api.groq.com/openai/v1/chat/completions"
                elif provider == "Deepseek": url = "https://api.deepseek.com/chat/completions"
                else: url = base_url
                headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}'}
                data = {"model": model, "messages": [{"role": "user", "content": prompt}]}
                req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')
                with urllib.request.urlopen(req) as response:
                    result = json.loads(response.read().decode())
                    text_response = result['choices'][0]['message']['content']

            signature = f"🤖 [Analizado por {provider} - {model}]\n\n"
            self.after(0, self.set_output, signature + text_response)
            self.after(0, lambda: self.lbl_status.configure(text=f"Análisis completado usando {provider} ({model})."))

        except Exception as e:
            self.after(0, self.set_output, f"🔴 Error de conexión: {str(e)}")
            self.after(0, lambda: self.lbl_status.configure(text="Error al conectar con IA."))

    def set_output(self, text):
        self.txt_out.configure(state="normal")
        self.txt_out.delete("1.0", "end")
        self.txt_out.insert("1.0", text)
        self.txt_out.configure(state="disabled")

    def config_api(self):
        ConfigAPIWindow(self)

class CustomDropdownWindow(ctk.CTkToplevel):
    def __init__(self, master, button, variable, values):
        super().__init__(master)
        self.overrideredirect(True)
        height = min(len(values) * 32 + 10, 320)  # Max ~10 items
        
        x = button.winfo_rootx()
        y = button.winfo_rooty() + button.winfo_height()
        width = button.winfo_width()
        
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.attributes("-topmost", True)
        self.grab_set()
        
        frame = ctk.CTkScrollableFrame(self, fg_color=("#e0e0e0", "#2b2b2b"), corner_radius=0)
        frame.pack(fill="both", expand=True)
        
        for val in values:
            b = ctk.CTkButton(frame, text=val, fg_color="transparent", hover_color=("#c8c8c8", "#334155"), 
                              text_color=("#111", "#eee"), anchor="w", command=lambda v=val: self.select(v, variable))
            b.pack(fill="x", padx=2, pady=1)
            
        self.bind("<FocusOut>", lambda e: self.destroy())
        self.bind("<Escape>", lambda e: self.destroy())

    def select(self, val, variable):
        variable.set(val)
        self.destroy()


class ConfigAPIWindow(ctk.CTkToplevel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.title("⚙️ Configuración API Avanzada (Bóveda IA)")
        center_window(self, 700, 550)
        
        def _set_icon_and_theme():
            try:
                self.iconbitmap(os.path.join(get_base_path(), "resources", "app_icon.ico"))
            except: pass
            if ctk.get_appearance_mode().lower() == "dark":
                apply_dark_titlebar(self)
        self.after(200, _set_icon_and_theme)

        if parent:
            self.transient(parent)
        self.grab_set()

        self.settings = get_api_settings()
        
        curr_prov = self.settings.get("current_provider", "Google Gemini")
        prov_data = self.settings.get("providers", {}).get(curr_prov, {})
        self.cached_models = prov_data.get("cached_models", [])

        lbl1 = ctk.CTkLabel(self, text="Gestor de Modelos de Lenguaje (LLM)", font=("Arial", 18, "bold"))
        lbl1.pack(pady=(20, 10))

        # 1. Provider
        frame_prov = ctk.CTkFrame(self, fg_color="transparent")
        frame_prov.pack(fill="x", padx=40, pady=10)
        ctk.CTkLabel(frame_prov, text="Proveedor:", width=100, anchor="w").pack(side="left")
        self.var_provider = ctk.StringVar(value=curr_prov)
        self.menu_provider = ctk.CTkOptionMenu(frame_prov, variable=self.var_provider, values=["Google Gemini", "OpenAI", "Anthropic Claude", "Groq", "Deepseek", "Personalizado"], command=self.on_provider_change)
        self.menu_provider.pack(side="left", fill="x", expand=True)

        # Base URL (Hidden by default)
        self.frame_url = ctk.CTkFrame(self, fg_color="transparent")
        ctk.CTkLabel(self.frame_url, text="URL Base:", width=100, anchor="w").pack(side="left")
        self.var_url = ctk.StringVar(value=prov_data.get("base_url", ""))
        self.entry_url = ctk.CTkEntry(self.frame_url, textvariable=self.var_url)
        self.entry_url.pack(side="left", fill="x", expand=True)

        # 2. API Key
        frame_key = ctk.CTkFrame(self, fg_color="transparent")
        frame_key.pack(fill="x", padx=40, pady=10)
        ctk.CTkLabel(frame_key, text="API Key:", width=100, anchor="w").pack(side="left")
        self.var_key = ctk.StringVar(value=prov_data.get("api_key", ""))
        self.entry_key = ctk.CTkEntry(frame_key, textvariable=self.var_key, show="*")
        self.entry_key.pack(side="left", fill="x", expand=True)
        
        self.btn_link = ctk.CTkButton(self, text="👉 Obtener API Key", fg_color="transparent", text_color="#3498DB", hover_color="#2C3E50", command=self.open_link)
        self.btn_link.pack(pady=(0, 5))

        self.var_free_only = ctk.BooleanVar(value=self.settings.get("free_only", True))
        self.chk_free = ctk.CTkCheckBox(self, text="Solo mostrar modelos gratuitos/ligeros (evitar Error 429)", variable=self.var_free_only, text_color="gray")
        self.chk_free.pack(pady=5)

        # 3. Load Models Button
        self.btn_fetch = ctk.CTkButton(self, text="🔄 Cargar Modelos Disponibles", fg_color="#F39C12", hover_color="#D68910", command=self.fetch_models)
        self.btn_fetch.pack(pady=(10, 20))
        
        self.lbl_verify = ctk.CTkLabel(self, text="Ingresa tu API Key y carga los modelos para verificar.", text_color="gray")
        self.lbl_verify.pack(pady=5)

        # 4. Model Dropdown
        self.frame_mod = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_mod.pack(fill="x", padx=40, pady=10)
        ctk.CTkLabel(self.frame_mod, text="Modelo:", width=100, anchor="w").pack(side="left")
        self.var_model = ctk.StringVar(value=prov_data.get("model", ""))
        
        initial_vals = self.cached_models if self.cached_models else (
            [self.var_model.get()] if self.var_model.get() else ["--- Carga los modelos primero ---"]
        )
        if not self.var_model.get(): self.var_model.set(initial_vals[0])
        
        self.menu_model = ctk.CTkButton(self.frame_mod, textvariable=self.var_model, fg_color=("#d9d9d9", "#34495e"), 
                                        text_color=("#111", "#eee"), hover_color=("#c8c8c8", "#2c3e50"), 
                                        anchor="w", command=self.open_model_dropdown)
        self.menu_model.pack(side="left", fill="x", expand=True)
        
        self.entry_model = ctk.CTkEntry(self.frame_mod, textvariable=self.var_model)

        # Buttons
        frame_btns = ctk.CTkFrame(self, fg_color="transparent")
        frame_btns.pack(pady=20)

        btn_save = ctk.CTkButton(frame_btns, text="💾 Guardar en Bóveda Local", fg_color="#27AE60", hover_color="#2ECC71", command=self.save)
        btn_save.pack(side="left", padx=10)

        btn_train = ctk.CTkButton(frame_btns, text="🚂 Configurar Tren de Modelos", fg_color="#8E44AD", hover_color="#9B59B6", command=self.open_train)
        btn_train.pack(side="left", padx=10)

        self.on_provider_change(self.var_provider.get(), initial_load=True)

    def on_provider_change(self, val, initial_load=False):
        prov_data = self.settings.get("providers", {}).get(val, {})
        
        if not initial_load:
            self.var_key.set(prov_data.get("api_key", ""))
            self.var_url.set(prov_data.get("base_url", ""))
            self.cached_models = prov_data.get("cached_models", [])
            initial_vals = self.cached_models if self.cached_models else ["--- Carga los modelos primero ---"]
            self.var_model.set(prov_data.get("model", initial_vals[0] if initial_vals else ""))
            
        if val == "Personalizado":
            self.frame_url.pack(fill="x", padx=40, pady=5, after=self.menu_provider.master)
            self.btn_fetch.pack_forget()
            self.lbl_verify.pack_forget()
            self.btn_link.configure(text="👉 Escribe tu modelo de forma manual", command=lambda: None)
            self.menu_model.pack_forget()
            self.entry_model.pack(side="left", fill="x", expand=True)
            if not initial_load: self.var_model.set("")
        else:
            self.frame_url.pack_forget()
            self.btn_fetch.pack(pady=(10, 20), before=self.lbl_verify)
            self.lbl_verify.pack(pady=5, before=self.frame_mod)
            self.entry_model.pack_forget()
            self.menu_model.pack(side="left", fill="x", expand=True)

            if val == "Google Gemini":
                self.btn_link.configure(text="👉 Obtener API Key Gratuita (Google AI Studio)", command=lambda: __import__('webbrowser').open("https://aistudio.google.com/app/apikey"))
            elif val == "OpenAI":
                self.btn_link.configure(text="👉 Obtener API Key (Plataforma OpenAI)", command=lambda: __import__('webbrowser').open("https://platform.openai.com/api-keys"))
            elif val == "Anthropic Claude":
                self.btn_link.configure(text="👉 Obtener API Key (Anthropic Console)", command=lambda: __import__('webbrowser').open("https://console.anthropic.com/settings/keys"))
            elif val == "Groq":
                self.btn_link.configure(text="👉 Obtener API Key Gratuita (Groq Cloud)", command=lambda: __import__('webbrowser').open("https://console.groq.com/keys"))
            elif val == "Deepseek":
                self.btn_link.configure(text="👉 Obtener API Key (Deepseek Platform)", command=lambda: __import__('webbrowser').open("https://platform.deepseek.com/api_keys"))

    def open_model_dropdown(self):
        vals = self.cached_models if self.cached_models else ["--- Carga los modelos primero ---"]
        CustomDropdownWindow(self, self.menu_model, self.var_model, vals)

    def open_link(self):
        __import__('webbrowser').open("https://aistudio.google.com/app/apikey")

    def fetch_models(self):
        provider = self.var_provider.get()
        api_key = self.var_key.get().strip()

        if not api_key:
            self.lbl_verify.configure(text="⚠️ Por favor ingresa tu API Key primero.", text_color="#E74C3C")
            return

        self.lbl_verify.configure(text="Obteniendo modelos oficiales... ⏳", text_color="#F39C12")
        self.btn_fetch.configure(state="disabled")
        
        def _fetch():
            models = []
            try:
                if provider == "Google Gemini":
                    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
                    req = urllib.request.Request(url)
                    with urllib.request.urlopen(req) as response:
                        res = json.loads(response.read().decode())
                        for m in res.get("models", []):
                            name = m.get("name", "").replace("models/", "")
                            if "vision" not in name and "embedding" not in name:
                                models.append(name)
                                
                elif provider in ["OpenAI", "Groq", "Deepseek"]:
                    if provider == "OpenAI": url = "https://api.openai.com/v1/models"
                    elif provider == "Groq": url = "https://api.groq.com/openai/v1/models"
                    else: url = "https://api.deepseek.com/models"
                    req = urllib.request.Request(url, headers={'Authorization': f'Bearer {api_key}'})
                    with urllib.request.urlopen(req) as response:
                        res = json.loads(response.read().decode())
                        for m in res.get("data", []):
                            models.append(m.get("id", ""))
                            
                elif provider == "Anthropic Claude":
                    models = ["claude-3-5-sonnet-20240620", "claude-3-opus-20240229", "claude-3-haiku-20240307", "claude-2.1"]
                    # Anthropic doesn't have a public models list endpoint natively accessible without specific headers that might block.
                    # Hardcoded fallback list if successful API key.
                    url = "https://api.anthropic.com/v1/messages"
                    data = {"model": "claude-3-haiku-20240307", "max_tokens": 1, "messages": [{"role": "user", "content": "hi"}]}
                    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers={'x-api-key': api_key, 'anthropic-version': '2023-06-01'})
                    urllib.request.urlopen(req)

                if models:
                    models = sorted(list(set(models)), reverse=True)
                    if self.var_free_only.get():
                        models = [m for m in models if not any(x in m.lower() for x in ["pro", "opus", "gpt-4", "advanced", "sonnet", "image", "video", "veo", "sora", "audio", "whisper", "embedding", "realtime", "tts"])]
                        
                    self.cached_models = models
                    if self.var_model.get() not in models:
                        if provider == "Google Gemini" and "gemini-1.5-flash" in models: self.after(0, lambda: self.var_model.set("gemini-1.5-flash"))
                        else: self.after(0, lambda: self.var_model.set(models[0]))
                    self.after(0, lambda: self.lbl_verify.configure(text=f"✅ ¡Éxito! Se cargaron {len(models)} modelos disponibles.", text_color="#2ECC71"))
                else:
                    self.after(0, lambda: self.lbl_verify.configure(text="⚠️ No se encontraron modelos.", text_color="#E74C3C"))

            except urllib.error.HTTPError as e:
                self.after(0, lambda: self.lbl_verify.configure(text=f"🔴 Error de clave (HTTP {e.code}): La API Key no es válida.", text_color="#E74C3C"))
            except Exception as e:
                self.after(0, lambda: self.lbl_verify.configure(text=f"🔴 Error de red: {str(e)[:40]}", text_color="#E74C3C"))
            finally:
                self.after(0, lambda: self.btn_fetch.configure(state="normal"))
                
        threading.Thread(target=_fetch, daemon=True).start()

    def open_train(self):
        messagebox.showinfo("Próximamente", "La interfaz del Tren de Modelos se implementará en la siguiente fase.")

    def save(self):
        settings_path = get_user_data_path(os.path.join("tools", "ai_settings.json"))
        model = self.var_model.get().strip()
        if not model or model.startswith("---"):
            messagebox.showwarning("Modelo Inválido", "Por favor carga y selecciona un modelo válido.")
            return

        prov = self.var_provider.get()
        self.settings["current_provider"] = prov
        self.settings["free_only"] = self.var_free_only.get()
        if prov not in self.settings["providers"]:
            self.settings["providers"][prov] = {}
        
        self.settings["providers"][prov]["api_key"] = self.var_key.get().strip()
        self.settings["providers"][prov]["base_url"] = self.var_url.get().strip()
        self.settings["providers"][prov]["model"] = model
        self.settings["providers"][prov]["cached_models"] = self.cached_models

        try:
            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=4)
            messagebox.showinfo("Bóveda IA", "Clave y configuración guardadas correctamente en la bóveda local.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar la configuración: {e}")
