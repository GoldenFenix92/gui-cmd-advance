import os
import re
import sys
import threading
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, simpledialog

import ttkbootstrap as tb
from ttkbootstrap.widgets.scrolled import ScrolledText

from functions import ai_engine, ui_theme
from functions.utils import center_window


def get_base_path():
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_api_settings():
    """Wrapper retrocompatible que delega en ai_engine.load_ai_settings()."""
    return ai_engine.load_ai_settings()


class InterpreterApp(tb.Toplevel):
    def __init__(self, parent, initial_text="", domain=None):
        super().__init__(parent)
        self.title("Intérprete Asistido de Reportes (Premium)")
        center_window(self, 1140, 680)
        self._domain = domain
        ui_theme.apply_window_chrome(self)

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self._icon_ai = ui_theme.get_bootstrap_icon("ai", size=14, color="#FFFFFF", master=self)
        self._icon_copy = ui_theme.get_bootstrap_icon("copy", size=14, color="#FFFFFF", master=self)

        self.top_frame = tb.Frame(self, padding=(14, 12))
        self.top_frame.grid(row=0, column=0, columnspan=2, sticky="ew")

        self.btn_load = tb.Button(
            self.top_frame, text="Cargar Archivo (.txt/.log)", bootstyle="info", command=self.load_file
        )
        self.btn_load.pack(side="left", padx=(0, 8))

        self.btn_offline = tb.Button(
            self.top_frame, text="Analizar (Offline)", bootstyle="warning", command=self.run_offline
        )
        self.btn_offline.pack(side="left", padx=(0, 8))

        self.btn_online = tb.Button(
            self.top_frame, text=" Analizar con IA", image=self._icon_ai, compound="left",
            bootstyle="primary", command=self.run_online,
        )
        self.btn_online.pack(side="left", padx=(0, 10))

        self.var_style = tk.StringVar(value="Técnico")
        self.opt_style = tb.Combobox(
            self.top_frame,
            textvariable=self.var_style,
            values=["Técnico", "Simple", "Solo Errores"],
            state="readonly",
            width=14,
        )
        self.opt_style.pack(side="left", padx=(0, 10))

        self.var_use_train = tk.BooleanVar(value=True)
        self.chk_train = tb.Checkbutton(
            self.top_frame, text="Tren de Modelos", variable=self.var_use_train, bootstyle="round-toggle"
        )
        self.chk_train.pack(side="left", padx=(0, 8))

        self.btn_config = tb.Button(
            self.top_frame, text="Configurar API (IA)", bootstyle="secondary", command=self.config_api
        )
        self.btn_config.pack(side="right")

        raw_card = tb.Labelframe(self, text="Reporte Original (Consola)", padding=8, bootstyle="secondary")
        raw_card.grid(row=1, column=0, padx=(14, 7), pady=(0, 10), sticky="nsew")
        self.txt_raw = ScrolledText(raw_card, font=("Consolas", 10), auto_hide=True)
        self.txt_raw.pack(fill="both", expand=True)
        if initial_text.strip():
            self.txt_raw.text.insert("1.0", initial_text)

        out_card = tb.Labelframe(self, text="Interpretación en Lenguaje Natural", padding=8, bootstyle="info")
        out_card.grid(row=1, column=1, padx=(7, 14), pady=(0, 10), sticky="nsew")
        self.txt_out = ScrolledText(out_card, font=("Segoe UI", 11), wrap="word", auto_hide=True)
        self.txt_out.pack(fill="both", expand=True)
        self.txt_out.text.configure(state="disabled")

        self.bottom_frame = tb.Frame(self, padding=(14, 0, 14, 12))
        self.bottom_frame.grid(row=2, column=0, columnspan=2, sticky="ew")

        self.lbl_status = tb.Label(self.bottom_frame, text="Listo.", bootstyle="secondary")
        self.lbl_status.pack(side="left")

        self.btn_export = tb.Button(
            self.bottom_frame, text="Exportar Interpretación", bootstyle="success", command=self.export_interpretation
        )
        self.btn_export.pack(side="right", padx=(8, 0))

        self.btn_copy = tb.Button(
            self.bottom_frame, text=" Copiar Resultado", image=self._icon_copy, compound="left",
            bootstyle="info", command=self.copy_interpretation,
        )
        self.btn_copy.pack(side="right")

        self.after(20, self.bring_to_front)

    def bring_to_front(self):
        ui_theme.bring_to_front(self)

    def copy_interpretation(self):
        content = self.txt_out.text.get("1.0", "end").strip()
        if not content:
            messagebox.showwarning("Vacío", "No hay texto para copiar.", parent=self)
            return
        self.clipboard_clear()
        self.clipboard_append(content)
        self.lbl_status.configure(text="Interpretación copiada al portapapeles.")

    def export_interpretation(self):
        content = self.txt_out.text.get("1.0", "end").strip()
        if not content:
            messagebox.showwarning("Vacío", "No hay nada que exportar.", parent=self)
            return
        file_path = filedialog.asksaveasfilename(
            parent=self,
            defaultextension=".html",
            filetypes=[("HTML Document", "*.html"), ("Markdown", "*.md"), ("Texto plano", "*.txt")],
            title="Guardar Interpretación",
        )
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    if file_path.endswith(".html"):
                        safe_html = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                        safe_html = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", safe_html)
                        safe_html = safe_html.replace("\n", "<br>")
                        f.write(
                            "<!DOCTYPE html><html><head><meta charset='utf-8'>"
                            "<style>body{font-family:'Segoe UI',sans-serif;padding:20px;line-height:1.6;color:#e6edf3;background:#0d1117;}"
                            ".container{max-width:860px;margin:0 auto;background:#161b22;padding:28px;border-radius:10px;border:1px solid #30363d;}"
                            "h2{color:#58a6ff;margin-top:0;}</style></head>"
                            f"<body><div class='container'><h2>Reporte Interpretado</h2>{safe_html}</div></body></html>"
                        )
                    else:
                        f.write(content)
                messagebox.showinfo("Guardado", f"Interpretación exportada exitosamente.\n{file_path}", parent=self)
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo guardar: {e}", parent=self)

    def load_file(self):
        file_path = filedialog.askopenfilename(
            parent=self,
            filetypes=[("Archivos de texto/log", "*.txt *.log"), ("Todos los archivos", "*.*")],
        )
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                self.txt_raw.text.delete("1.0", "end")
                self.txt_raw.text.insert("1.0", content)
                self.lbl_status.configure(text=f"Archivo cargado: {os.path.basename(file_path)}")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo leer el archivo: {e}", parent=self)

    def run_offline(self):
        content = self.txt_raw.text.get("1.0", "end").strip()
        if not content:
            return
        self.lbl_status.configure(text="Analizando localmente...")
        result = ai_engine.analyze_offline(content)
        self.set_output(result)
        self.lbl_status.configure(text="Análisis offline completado.")

    def run_online(self):
        content = self.txt_raw.text.get("1.0", "end").strip()
        if not content:
            return
        settings = ai_engine.load_ai_settings()
        use_train = bool(self.var_use_train.get())
        train = settings.get("model_train", []) if use_train else []
        if not train:
            prov = settings.get("current_provider", "Google Gemini")
            pdata = settings.get("providers", {}).get(prov, {})
            needs_key = ai_engine.provider_requires_api_key(prov, pdata.get("base_url", ""))
            if (needs_key and not pdata.get("api_key")) or not pdata.get("model"):
                if messagebox.askyesno("Configuración IA", "Falta configurar el proveedor o el modelo. ¿Deseas configurarlos ahora?", parent=self):
                    self.config_api()
                return

        style_map = {"Técnico": "tecnico", "Simple": "simple", "Solo Errores": "errores"}
        style_key = style_map.get(self.var_style.get(), "tecnico")
        prompt = ai_engine.build_analysis_prompt(content, style=style_key, domain=self._domain)

        self.btn_online.configure(state="disabled")
        self.lbl_status.configure(text="Conectando con IA... Por favor espera.")
        self.set_output("Analizando con IA...\n\nSi el reporte es extenso, se aplicó recorte inteligente para optimizar tokens.")

        def _worker():
            def on_status(msg):
                self.after(0, lambda m=msg: self.lbl_status.configure(text=m))

            res = ai_engine.run_model_train(settings, prompt, use_train=use_train, status_cb=on_status, timeout=25)

            def _finish():
                self.btn_online.configure(state="normal")
                if res["ok"]:
                    signature = f"[Analizado por {res['provider']} - {res['model']}]\n\n"
                    self.set_output(signature + res["text"])
                    self.lbl_status.configure(text=f"Análisis completado usando {res['provider']} ({res['model']}).")
                else:
                    err_detail = "\n".join(f"- {e}" for e in res.get("errors", []))
                    msg = (
                        "[ERROR] No se pudo completar el análisis con IA.\n\n"
                        f"Detalle de intentos:\n{err_detail}\n\n"
                        "[TIP] Verifica tus llaves API, la conexión a Ollama/LM Studio local o intenta nuevamente."
                    )
                    self.set_output(msg)
                    self.lbl_status.configure(text="Error en el análisis con IA.")

            self.after(0, _finish)

        threading.Thread(target=_worker, daemon=True).start()

    def set_output(self, text):
        self.txt_out.text.configure(state="normal")
        self.txt_out.text.delete("1.0", "end")
        self.txt_out.text.insert("1.0", text)
        self.txt_out.text.configure(state="disabled")

    def config_api(self):
        ConfigAPIWindow(self)


class ModelTrainWindow(tb.Toplevel):
    def __init__(self, master, settings_ref, save_callback):
        super().__init__(master)
        self.title("Configuración de Tren de Modelos (Fallback)")
        center_window(self, 740, 480)
        self.transient(master)
        self.grab_set()
        ui_theme.apply_window_chrome(self)

        self.settings = settings_ref
        self.save_callback = save_callback
        self.train_list = list(self.settings.get("model_train", []))

        content = tb.Frame(self, padding=12)
        content.pack(fill="both", expand=True)

        left_frame = tb.Labelframe(content, text="Modelos Disponibles", padding=10, bootstyle="info")
        left_frame.pack(side="left", fill="both", expand=True)

        mid_frame = tb.Frame(content, padding=(10, 40))
        mid_frame.pack(side="left", fill="y")

        right_frame = tb.Labelframe(content, text="Vagones del Tren (Orden)", padding=10, bootstyle="primary")
        right_frame.pack(side="left", fill="both", expand=True)

        valid_provs = [
            p for p, d in self.settings.get("providers", {}).items()
            if d.get("api_key") or not ai_engine.provider_requires_api_key(p, d.get("base_url", ""))
        ]
        if not valid_provs:
            valid_provs = ["Ninguno"]

        self.var_prov = tk.StringVar(value=valid_provs[0])
        opt_prov = tb.Combobox(left_frame, textvariable=self.var_prov, values=valid_provs, state="readonly")
        opt_prov.pack(fill="x", pady=(0, 8))
        opt_prov.bind("<<ComboboxSelected>>", lambda _e: self.load_models(self.var_prov.get()))

        lb_bg = "#1e1e1e" if ui_theme.is_dark_theme() else "#f8fafc"
        lb_fg = "#e0e0e0" if ui_theme.is_dark_theme() else "#1e293b"

        self.lb_avail = tk.Listbox(
            left_frame, bg=lb_bg, fg=lb_fg, selectbackground="#3498db",
            font=("Segoe UI", 10), highlightthickness=0, borderwidth=1,
        )
        self.lb_avail.pack(fill="both", expand=True)

        tb.Button(mid_frame, text="Añadir >", width=11, bootstyle="info", command=self.add_to_train).pack(pady=8)
        tb.Button(mid_frame, text="< Quitar", width=11, bootstyle="danger", command=self.rem_from_train).pack(pady=8)

        self.lb_train = tk.Listbox(
            right_frame, bg=lb_bg, fg=lb_fg, selectbackground="#3498db",
            font=("Segoe UI", 10), highlightthickness=0, borderwidth=1,
        )
        self.lb_train.pack(fill="both", expand=True, pady=(0, 8))

        tb.Button(right_frame, text="Testear Tren (Reporte)", bootstyle="warning", command=self.test_train).pack(fill="x")

        tb.Button(self, text="Guardar Tren", bootstyle="success", command=self.save, width=20).pack(pady=(0, 12))

        self.load_models(self.var_prov.get())
        self.render_train()
        ui_theme.bring_to_front(self)

    def load_models(self, prov):
        self.lb_avail.delete(0, tk.END)
        pdata = self.settings.get("providers", {}).get(prov, {})
        models = list(pdata.get("cached_models", []))
        if pdata.get("model") and pdata["model"] not in models:
            models.insert(0, pdata["model"])
        for m in models:
            self.lb_avail.insert(tk.END, m)

    def render_train(self):
        self.lb_train.delete(0, tk.END)
        for item in self.train_list:
            self.lb_train.insert(tk.END, f"[{item['provider']}] {item['model']}")

    def add_to_train(self):
        sel = self.lb_avail.curselection()
        if sel:
            mod = self.lb_avail.get(sel[0])
            self.train_list.append({"provider": self.var_prov.get(), "model": mod})
            self.render_train()

    def rem_from_train(self):
        sel = self.lb_train.curselection()
        if sel:
            self.train_list.pop(sel[0])
            self.render_train()

    def test_train(self):
        if not self.train_list:
            messagebox.showwarning("Tren Vacío", "No hay modelos en el tren para testear.", parent=self)
            return

        test_win = tb.Toplevel(self)
        test_win.title("Reporte de Efectividad de Modelos")
        center_window(test_win, 660, 420)
        test_win.transient(self)
        test_win.grab_set()
        ui_theme.apply_window_chrome(test_win)

        txt = ScrolledText(test_win, font=("Consolas", 10), auto_hide=True)
        txt.pack(fill="both", expand=True, padx=14, pady=14)
        txt.text.insert("end", "Iniciando Test de Conectividad y Cuotas del Tren (timeout 15s por modelo)...\n\n")
        ui_theme.bring_to_front(test_win)

        def append_safe(msg):
            try:
                if test_win.winfo_exists():
                    txt.text.insert("end", msg)
                    txt.text.see("end")
            except Exception:
                pass

        def _run_test():
            for idx, item in enumerate(self.train_list):
                prov = item["provider"]
                mod = item["model"]
                pdata = self.settings.get("providers", {}).get(prov, {})
                api_key = pdata.get("api_key", "")
                base_url = pdata.get("base_url", "")

                test_win.after(0, append_safe, f"[{idx + 1}] Probando {prov} ({mod})... ")
                if ai_engine.provider_requires_api_key(prov, base_url) and not api_key:
                    test_win.after(0, append_safe, "[ERROR] SIN LLAVE API\n")
                    continue

                try:
                    ai_engine.call_provider(
                        provider=prov,
                        model=mod,
                        api_key=api_key,
                        prompt="Responde únicamente con la palabra OK.",
                        base_url=base_url,
                        timeout=15,
                        max_tokens=16,
                    )
                    test_win.after(0, append_safe, "[OK] ACTIVO\n")
                except Exception as exc:
                    test_win.after(0, append_safe, f"[ERROR] {ai_engine.classify_http_error(exc)}\n")

            def _finish_test():
                append_safe("\n--- Test Finalizado ---")
                try:
                    if test_win.winfo_exists():
                        txt.text.configure(state="disabled")
                except Exception:
                    pass

            test_win.after(0, _finish_test)

        threading.Thread(target=_run_test, daemon=True).start()

    def save(self):
        self.settings["model_train"] = self.train_list
        self.save_callback()
        self.destroy()


class ConfigAPIWindow(tb.Toplevel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.title("Configuración API Avanzada (Bóveda IA)")
        center_window(self, 740, 620)
        ui_theme.apply_window_chrome(self)

        if parent:
            self.transient(parent)
        self.grab_set()

        self.settings = ai_engine.load_ai_settings()
        curr_prov = self.settings.get("current_provider", "Google Gemini")
        if curr_prov not in ai_engine.PROVIDERS_ORDER:
            curr_prov = "Google Gemini"
        prov_data = self.settings.get("providers", {}).get(curr_prov, {})
        self.cached_models = prov_data.get("cached_models", [])

        tb.Label(
            self,
            text="Gestor de Modelos de Lenguaje (Bóveda IA + Local)",
            font=("Segoe UI", 14, "bold"),
            bootstyle="primary",
        ).pack(pady=(16, 10))

        form = tb.Labelframe(self, text="Credenciales y Conexión", padding=14, bootstyle="info")
        form.pack(fill="x", padx=28, pady=6)

        frame_prov = tb.Frame(form)
        frame_prov.pack(fill="x", pady=6)
        tb.Label(frame_prov, text="Proveedor:", width=13, anchor="w").pack(side="left")
        self.var_provider = tk.StringVar(value=curr_prov)
        self.menu_provider = tb.Combobox(
            frame_prov, textvariable=self.var_provider, values=ai_engine.PROVIDERS_ORDER, state="readonly"
        )
        self.menu_provider.pack(side="left", fill="x", expand=True)
        self.menu_provider.bind("<<ComboboxSelected>>", lambda _e: self.on_provider_change(self.var_provider.get()))
        self._frame_prov = frame_prov

        self.frame_url = tb.Frame(form)
        tb.Label(self.frame_url, text="URL Base:", width=13, anchor="w").pack(side="left")
        self.var_url = tk.StringVar(value=prov_data.get("base_url", ""))
        self.entry_url = tb.Entry(self.frame_url, textvariable=self.var_url)
        self.entry_url.pack(side="left", fill="x", expand=True)

        frame_key = tb.Frame(form)
        frame_key.pack(fill="x", pady=6)
        tb.Label(frame_key, text="API Key:", width=13, anchor="w").pack(side="left")
        self.var_key = tk.StringVar(value=prov_data.get("api_key", ""))
        self.entry_key = tb.Entry(frame_key, textvariable=self.var_key, show="*")
        self.entry_key.pack(side="left", fill="x", expand=True)

        self.btn_link = tb.Button(form, text="Obtener API Key", bootstyle="link", command=self.open_link)
        self.btn_link.pack(pady=(2, 4))

        self.var_free_only = tk.BooleanVar(value=self.settings.get("free_only", True))
        self.chk_free = tb.Checkbutton(
            form,
            text="Solo mostrar modelos gratuitos/ligeros (evitar Error 429)",
            variable=self.var_free_only,
            bootstyle="round-toggle",
        )
        self.chk_free.pack(pady=4)

        self.btn_fetch = tb.Button(form, text="Cargar Modelos Disponibles", bootstyle="warning", command=self.fetch_models)
        self.btn_fetch.pack(pady=(8, 6))

        self.lbl_verify = tb.Label(
            form,
            text="Ingresa tu API Key (o inicia Ollama/LM Studio local) y carga los modelos.",
            bootstyle="secondary",
        )
        self.lbl_verify.pack(pady=4)

        self.frame_mod = tb.Frame(form)
        self.frame_mod.pack(fill="x", pady=6)
        tb.Label(self.frame_mod, text="Modelo:", width=13, anchor="w").pack(side="left")
        self.var_model = tk.StringVar(value=prov_data.get("model", ""))

        initial_vals = self.cached_models if self.cached_models else (
            [self.var_model.get()] if self.var_model.get() else ["--- Carga los modelos primero ---"]
        )
        if not self.var_model.get():
            self.var_model.set(initial_vals[0])

        self.menu_model = tb.Combobox(self.frame_mod, textvariable=self.var_model, values=initial_vals, state="readonly")
        self.menu_model.pack(side="left", fill="x", expand=True)
        self.entry_model = tb.Entry(self.frame_mod, textvariable=self.var_model)

        frame_btns = tb.Frame(self)
        frame_btns.pack(pady=(14, 6))

        tb.Button(frame_btns, text="Guardar en Bóveda (DPAPI)", bootstyle="success", command=self.save).pack(side="left", padx=8)
        tb.Button(frame_btns, text="Configurar Tren de Modelos", bootstyle="primary", command=self.open_train).pack(side="left", padx=8)

        frame_backup = tb.Labelframe(self, text="Respaldo Portátil Cifrado (.aivault)", padding=10, bootstyle="secondary")
        frame_backup.pack(pady=(6, 14), padx=28, fill="x")
        inner_bk = tb.Frame(frame_backup)
        inner_bk.pack()
        tb.Button(inner_bk, text="Exportar Respaldo (.aivault)", bootstyle="info-outline", command=self.export_vault_backup).pack(side="left", padx=8)
        tb.Button(inner_bk, text="Importar Respaldo (.aivault)", bootstyle="secondary-outline", command=self.import_vault_backup).pack(side="left", padx=8)

        self.on_provider_change(self.var_provider.get(), initial_load=True)
        ui_theme.bring_to_front(self)

    def on_provider_change(self, val, initial_load=False):
        prov_data = self.settings.get("providers", {}).get(val, {})
        default_url = ai_engine.DEFAULT_ENDPOINTS.get(val, "")

        if not initial_load:
            self.var_key.set(prov_data.get("api_key", ""))
            self.var_url.set(prov_data.get("base_url") or default_url)
            self.cached_models = prov_data.get("cached_models", [])
            initial_vals = self.cached_models if self.cached_models else ["--- Carga los modelos primero ---"]
            self.menu_model.configure(values=initial_vals)
            self.var_model.set(prov_data.get("model") or (initial_vals[0] if initial_vals else ""))
        elif val in ai_engine.LOCAL_PROVIDERS and not self.var_url.get():
            self.var_url.set(default_url)

        if val in ai_engine.LOCAL_PROVIDERS or val == "Personalizado":
            self.frame_url.pack(fill="x", pady=6, after=self._frame_prov)
        else:
            self.frame_url.pack_forget()

        if val == "Personalizado":
            self.menu_model.pack_forget()
            self.entry_model.pack(side="left", fill="x", expand=True)
            self.btn_link.configure(text="Endpoint OpenAI-compatible (API Key opcional en localhost)", command=lambda: None)
        else:
            self.entry_model.pack_forget()
            self.menu_model.pack(side="left", fill="x", expand=True)

            urls = {
                "Google Gemini": ("Obtener API Key Gratuita (Google AI Studio)", "https://aistudio.google.com/app/apikey"),
                "OpenAI": ("Obtener API Key (Plataforma OpenAI)", "https://platform.openai.com/api-keys"),
                "Anthropic Claude": ("Obtener API Key (Anthropic Console)", "https://console.anthropic.com/settings/keys"),
                "Groq": ("Obtener API Key Gratuita (Groq Cloud)", "https://console.groq.com/keys"),
                "Deepseek": ("Obtener API Key (Deepseek Platform)", "https://platform.deepseek.com/api_keys"),
                "Ollama (Local)": ("IA Local Ollama (sin API Key — usa http://localhost:11434)", "https://ollama.com"),
                "LM Studio (Local)": ("IA Local LM Studio (sin API Key — usa http://localhost:1234)", "https://lmstudio.ai"),
            }
            if val in urls:
                txt, url = urls[val]
                self.btn_link.configure(text=txt, command=lambda u=url: webbrowser.open(u))

    def open_link(self):
        webbrowser.open("https://aistudio.google.com/app/apikey")

    def fetch_models(self):
        provider = self.var_provider.get()
        api_key = self.var_key.get().strip()
        base_url = self.var_url.get().strip()

        if ai_engine.provider_requires_api_key(provider, base_url) and not api_key:
            self.lbl_verify.configure(text="[AVISO] Por favor ingresa tu API Key primero.", bootstyle="danger")
            return

        self.lbl_verify.configure(text="Obteniendo modelos disponibles...", bootstyle="warning")
        self.btn_fetch.configure(state="disabled")

        def _fetch():
            try:
                models = ai_engine.fetch_provider_models(
                    provider=provider,
                    api_key=api_key,
                    base_url=base_url,
                    free_only=bool(self.var_free_only.get()),
                    timeout=15,
                )
                if models:
                    self.cached_models = models

                    def _apply_models():
                        self.menu_model.configure(values=models)
                        if self.var_model.get() not in models:
                            preferred = "gemini-2.0-flash" if "gemini-2.0-flash" in models else (
                                "gemini-1.5-flash" if "gemini-1.5-flash" in models else models[0]
                            )
                            self.var_model.set(preferred)
                        self.lbl_verify.configure(text=f"[OK] Se cargaron {len(models)} modelos disponibles.", bootstyle="success")

                    self.after(0, _apply_models)
                else:
                    self.after(0, lambda: self.lbl_verify.configure(text="[AVISO] No se encontraron modelos en este servidor.", bootstyle="danger"))
            except Exception as exc:
                msg = ai_engine.classify_http_error(exc)
                self.after(0, lambda m=msg: self.lbl_verify.configure(text=f"[ERROR] {m}", bootstyle="danger"))
            finally:
                self.after(0, lambda: self.btn_fetch.configure(state="normal"))

        threading.Thread(target=_fetch, daemon=True).start()

    def open_train(self):
        ModelTrainWindow(self, self.settings, self.save_silent)

    def save_silent(self):
        try:
            ai_engine.save_ai_settings(self.settings)
        except Exception:
            pass

    def save(self):
        model = self.var_model.get().strip()
        if not model or model.startswith("---"):
            messagebox.showwarning("Modelo Inválido", "Por favor carga o escribe un modelo válido.", parent=self)
            return

        prov = self.var_provider.get()
        self.settings["current_provider"] = prov
        self.settings["free_only"] = bool(self.var_free_only.get())
        if prov not in self.settings["providers"]:
            self.settings["providers"][prov] = {}

        self.settings["providers"][prov]["api_key"] = self.var_key.get().strip()
        self.settings["providers"][prov]["base_url"] = self.var_url.get().strip()
        self.settings["providers"][prov]["model"] = model
        self.settings["providers"][prov]["cached_models"] = self.cached_models

        try:
            ai_engine.save_ai_settings(self.settings)
            messagebox.showinfo(
                "Bóveda IA",
                "Configuración guardada y protegida con Windows DPAPI en tu bóveda local.",
                parent=self,
            )
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar la configuración: {e}", parent=self)

    def export_vault_backup(self):
        pw1 = simpledialog.askstring("Exportar Respaldo (.aivault)", "Crea una contraseña maestra (mín. 4 caracteres):", show="*", parent=self)
        if not pw1:
            return
        pw2 = simpledialog.askstring("Confirmar Contraseña", "Repite la contraseña maestra:", show="*", parent=self)
        if pw1 != pw2:
            messagebox.showerror("Error", "Las contraseñas no coinciden.", parent=self)
            return
        out_path = filedialog.asksaveasfilename(
            parent=self,
            defaultextension=".aivault",
            filetypes=[("Respaldo Bóveda IA", "*.aivault")],
            initialfile="respaldo_boveda_ia.aivault",
            title="Guardar Respaldo Cifrado de Bóveda IA",
        )
        if not out_path:
            return
        try:
            blob = ai_engine.export_encrypted_vault(self.settings, pw1)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(blob)
            messagebox.showinfo(
                "Respaldo Exportado",
                f"Bóveda cifrada exportada correctamente:\n{out_path}\n\nGuarda tu contraseña maestra para importarla en cualquier otra PC.",
                parent=self,
            )
        except Exception as exc:
            messagebox.showerror("Error", f"No se pudo exportar: {exc}", parent=self)

    def import_vault_backup(self):
        in_path = filedialog.askopenfilename(
            parent=self,
            filetypes=[("Respaldo Bóveda IA", "*.aivault"), ("Todos los archivos", "*.*")],
            title="Seleccionar Respaldo Cifrado (.aivault)",
        )
        if not in_path:
            return
        pw = simpledialog.askstring("Importar Respaldo (.aivault)", "Ingresa la contraseña maestra del respaldo:", show="*", parent=self)
        if not pw:
            return
        try:
            with open(in_path, "r", encoding="utf-8") as f:
                raw = f.read()
            imported = ai_engine.import_encrypted_vault(raw, pw)
            ai_engine.save_ai_settings(imported)
            self.settings = ai_engine.load_ai_settings()
            curr = self.settings.get("current_provider", "Google Gemini")
            if curr in ai_engine.PROVIDERS_ORDER:
                self.var_provider.set(curr)
                self.on_provider_change(curr, initial_load=False)
            messagebox.showinfo(
                "Respaldo Importado",
                "Bóveda IA restaurada y re-protegida con DPAPI en este equipo.",
                parent=self,
            )
        except Exception as exc:
            messagebox.showerror("Error al Importar", str(exc), parent=self)
