import ctypes
import json
import os
import re
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog

import customtkinter as ctk

from functions import ai_engine
from functions.utils import apply_window_theme


def get_base_path():
    if getattr(sys, "frozen", False):
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
        value = ctypes.c_int(2)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(value), ctypes.sizeof(value))
    except Exception:
        pass


def get_api_settings():
    """Wrapper retrocompatible que delega en ai_engine.load_ai_settings()."""
    return ai_engine.load_ai_settings()


class InterpreterApp(ctk.CTkToplevel):
    def __init__(self, parent, initial_text="", domain=None):
        super().__init__(parent)
        self.title("Intérprete Asistido de Reportes (Premium)")
        center_window(self, 1120, 660)
        self._domain = domain
        self.lift()
        self.focus_force()

        def _set_icon_and_theme():
            try:
                if not self.winfo_exists():
                    return
                self.iconbitmap(os.path.join(get_base_path(), "resources", "app_icon.ico"))
            except Exception:
                pass
            if ctk.get_appearance_mode().lower() == "dark":
                apply_dark_titlebar(self)
            self.bring_to_front()

        self.after(200, _set_icon_and_theme)

        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self.top_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.top_frame.grid(row=0, column=0, columnspan=2, padx=15, pady=12, sticky="ew")

        self.btn_load = ctk.CTkButton(
            self.top_frame, text="Cargar Archivo (.txt/.log)", width=155,
            fg_color="#2E86C1", hover_color="#21618C", command=self.load_file,
        )
        self.btn_load.pack(side="left", padx=(0, 8))

        self.btn_offline = ctk.CTkButton(
            self.top_frame, text="Analizar (Offline)", width=130,
            fg_color="#D97706", hover_color="#B45309", command=self.run_offline,
        )
        self.btn_offline.pack(side="left", padx=(0, 8))

        self.btn_online = ctk.CTkButton(
            self.top_frame, text="Analizar con IA", width=135,
            fg_color="#8E44AD", hover_color="#9B59B6", command=self.run_online,
        )
        self.btn_online.pack(side="left", padx=(0, 8))

        self.var_style = ctk.StringVar(value="Técnico")
        self.opt_style = ctk.CTkOptionMenu(
            self.top_frame,
            variable=self.var_style,
            values=["Técnico", "Simple", "Solo Errores"],
            width=120,
        )
        self.opt_style.pack(side="left", padx=(0, 8))

        self.var_use_train = ctk.BooleanVar(value=True)
        self.chk_train = ctk.CTkCheckBox(self.top_frame, text="Tren de Modelos", variable=self.var_use_train)
        self.chk_train.pack(side="left", padx=(0, 8))

        self.btn_config = ctk.CTkButton(
            self.top_frame, text="Configurar API (IA)", width=145,
            fg_color="#475569", hover_color="#334155", command=self.config_api,
        )
        self.btn_config.pack(side="right")

        self.lbl_raw = ctk.CTkLabel(self, text="Reporte Original (Consola):", font=("Arial", 14, "bold"))
        self.lbl_raw.grid(row=1, column=0, padx=15, pady=(0, 5), sticky="nw")

        self.txt_raw = ctk.CTkTextbox(self, font=("Consolas", 12))
        self.txt_raw.grid(row=2, column=0, padx=15, pady=(0, 15), sticky="nsew")
        if initial_text.strip():
            self.txt_raw.insert("1.0", initial_text)

        self.lbl_out = ctk.CTkLabel(
            self, text="Interpretación en Lenguaje Natural:",
            font=("Arial", 14, "bold"), text_color=("#1f6aa5", "#3B8ED0"),
        )
        self.lbl_out.grid(row=1, column=1, padx=15, pady=(0, 5), sticky="nw")

        self.txt_out = ctk.CTkTextbox(self, font=("Arial", 13), wrap="word")
        self.txt_out.grid(row=2, column=1, padx=15, pady=(0, 15), sticky="nsew")
        self.txt_out.configure(state="disabled")

        self.bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.bottom_frame.grid(row=3, column=0, columnspan=2, padx=15, pady=(0, 10), sticky="ew")

        self.lbl_status = ctk.CTkLabel(self.bottom_frame, text="Listo.", text_color="gray")
        self.lbl_status.pack(side="left")

        self.btn_export = ctk.CTkButton(
            self.bottom_frame, text="Exportar Interpretación", width=165,
            fg_color="#27AE60", hover_color="#2ECC71", command=self.export_interpretation,
        )
        self.btn_export.pack(side="right", padx=(8, 0))

        self.btn_copy = ctk.CTkButton(
            self.bottom_frame, text="Copiar Resultado", width=130,
            fg_color="#2E86C1", hover_color="#21618C", command=self.copy_interpretation,
        )
        self.btn_copy.pack(side="right")

        self.after(10, self.bring_to_front)

    def bring_to_front(self):
        """Asegura que la ventana del Intérprete aparezca y mantenga el foco sobre la ventana principal."""
        try:
            if not self.winfo_exists():
                return
            self.deiconify()
            self.lift()
            self.attributes("-topmost", True)
            self.focus_force()
            self.after(150, self._release_topmost)
        except Exception:
            pass

    def _release_topmost(self):
        try:
            if self.winfo_exists():
                self.attributes("-topmost", False)
        except Exception:
            pass

    def copy_interpretation(self):
        content = self.txt_out.get("1.0", "end").strip()
        if not content:
            messagebox.showwarning("Vacío", "No hay texto para copiar.", parent=self)
            return
        self.clipboard_clear()
        self.clipboard_append(content)
        self.lbl_status.configure(text="Interpretación copiada al portapapeles.")

    def export_interpretation(self):
        content = self.txt_out.get("1.0", "end").strip()
        if not content:
            messagebox.showwarning("Vacío", "No hay nada que exportar.", parent=self)
            return
        file_path = filedialog.asksaveasfilename(
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
            filetypes=[("Archivos de texto/log", "*.txt *.log"), ("Todos los archivos", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                self.txt_raw.delete("1.0", "end")
                self.txt_raw.insert("1.0", content)
                self.lbl_status.configure(text=f"Archivo cargado: {os.path.basename(file_path)}")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo leer el archivo: {e}", parent=self)

    def run_offline(self):
        content = self.txt_raw.get("1.0", "end").strip()
        if not content:
            return
        self.lbl_status.configure(text="Analizando localmente...")
        result = ai_engine.analyze_offline(content)
        self.set_output(result)
        self.lbl_status.configure(text="Análisis offline completado.")

    def run_online(self):
        content = self.txt_raw.get("1.0", "end").strip()
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
        self.txt_out.configure(state="normal")
        self.txt_out.delete("1.0", "end")
        self.txt_out.insert("1.0", text)
        self.txt_out.configure(state="disabled")

    def config_api(self):
        ConfigAPIWindow(self)


class ModelTrainWindow(ctk.CTkToplevel):
    def __init__(self, master, settings_ref, save_callback):
        super().__init__(master)
        self.title("Configuración de Tren de Modelos (Fallback)")
        center_window(self, 720, 460)
        self.attributes("-topmost", True)
        self.grab_set()
        apply_window_theme(self)

        self.settings = settings_ref
        self.save_callback = save_callback
        self.train_list = list(self.settings.get("model_train", []))

        left_frame = ctk.CTkFrame(self)
        left_frame.pack(side="left", fill="both", expand=True, padx=15, pady=15)

        mid_frame = ctk.CTkFrame(self, fg_color="transparent")
        mid_frame.pack(side="left", fill="y", padx=5, pady=50)

        right_frame = ctk.CTkFrame(self)
        right_frame.pack(side="left", fill="both", expand=True, padx=15, pady=15)

        valid_provs = [
            p for p, d in self.settings.get("providers", {}).items()
            if d.get("api_key") or not ai_engine.provider_requires_api_key(p, d.get("base_url", ""))
        ]
        if not valid_provs:
            valid_provs = ["Ninguno"]

        self.var_prov = ctk.StringVar(value=valid_provs[0])
        opt_prov = ctk.CTkOptionMenu(left_frame, variable=self.var_prov, values=valid_provs, command=self.load_models)
        opt_prov.pack(fill="x", padx=10, pady=10)

        self.lb_avail = tk.Listbox(
            left_frame, bg="#1e1e1e", fg="#e0e0e0", selectbackground="#3498db",
            font=("Segoe UI", 11), highlightthickness=0, borderwidth=0,
        )
        self.lb_avail.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        btn_add = ctk.CTkButton(mid_frame, text="Añadir >", width=85, fg_color="#3498DB", hover_color="#2980B9", command=self.add_to_train)
        btn_add.pack(pady=10)
        btn_rem = ctk.CTkButton(mid_frame, text="< Quitar", width=85, fg_color="#E74C3C", hover_color="#C0392B", command=self.rem_from_train)
        btn_rem.pack(pady=10)

        ctk.CTkLabel(right_frame, text="Vagones del Tren (Orden de ejecución):", font=("Arial", 12, "bold")).pack(pady=10)
        self.lb_train = tk.Listbox(
            right_frame, bg="#1e1e1e", fg="#e0e0e0", selectbackground="#3498db",
            font=("Segoe UI", 11), highlightthickness=0, borderwidth=0,
        )
        self.lb_train.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        btn_test = ctk.CTkButton(right_frame, text="Testear Tren (Reporte)", fg_color="#D97706", hover_color="#B45309", command=self.test_train)
        btn_test.pack(pady=5)

        btn_save = ctk.CTkButton(self, text="Guardar Tren", fg_color="#27AE60", hover_color="#2ECC71", command=self.save)
        btn_save.pack(side="bottom", pady=15)

        self.load_models(self.var_prov.get())
        self.render_train()

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

        test_win = ctk.CTkToplevel(self)
        test_win.title("Reporte de Efectividad de Modelos")
        center_window(test_win, 660, 410)
        test_win.attributes("-topmost", True)
        test_win.grab_set()
        apply_window_theme(test_win)

        txt = ctk.CTkTextbox(test_win, font=("Consolas", 12))
        txt.pack(fill="both", expand=True, padx=15, pady=15)
        txt.insert("end", "Iniciando Test de Conectividad y Cuotas del Tren (timeout 15s por modelo)...\n\n")

        def append_safe(msg):
            try:
                if test_win.winfo_exists():
                    txt.insert("end", msg)
                    txt.see("end")
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
                    status = "[OK] EFECTIVO (Respuesta Exitosa)"
                except Exception as exc:
                    status = f"[ERROR] {ai_engine.classify_http_error(exc)}"

                test_win.after(0, append_safe, f"{status}\n")

            def _finish_test():
                append_safe("\n--- Test Finalizado ---")
                try:
                    if test_win.winfo_exists():
                        txt.configure(state="disabled")
                except Exception:
                    pass

            test_win.after(0, _finish_test)

        threading.Thread(target=_run_test, daemon=True).start()

    def save(self):
        self.settings["model_train"] = self.train_list
        self.save_callback()
        self.destroy()


class CustomDropdownWindow(ctk.CTkToplevel):
    def __init__(self, master, button, variable, values):
        super().__init__(master)
        self.overrideredirect(True)
        height = min(len(values) * 32 + 10, 320)

        x = button.winfo_rootx()
        y = button.winfo_rooty() + button.winfo_height()
        width = button.winfo_width()

        self.geometry(f"{width}x{height}+{x}+{y}")
        self.attributes("-topmost", True)
        self.grab_set()

        frame = ctk.CTkScrollableFrame(self, fg_color=("#e0e0e0", "#2b2b2b"), corner_radius=0)
        frame.pack(fill="both", expand=True)

        for val in values:
            b = ctk.CTkButton(
                frame, text=val, fg_color="transparent", hover_color=("#c8c8c8", "#334155"),
                text_color=("#111", "#eee"), anchor="w", command=lambda v=val: self.select(v, variable),
            )
            b.pack(fill="x", padx=2, pady=1)

        self.bind("<FocusOut>", lambda e: self.destroy())
        self.bind("<Escape>", lambda e: self.destroy())

    def select(self, val, variable):
        variable.set(val)
        self.destroy()


class ConfigAPIWindow(ctk.CTkToplevel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.title("Configuración API Avanzada (Bóveda IA)")
        center_window(self, 730, 610)
        apply_window_theme(self)

        if parent:
            self.transient(parent)
        self.grab_set()

        self.settings = ai_engine.load_ai_settings()
        curr_prov = self.settings.get("current_provider", "Google Gemini")
        if curr_prov not in ai_engine.PROVIDERS_ORDER:
            curr_prov = "Google Gemini"
        prov_data = self.settings.get("providers", {}).get(curr_prov, {})
        self.cached_models = prov_data.get("cached_models", [])

        ctk.CTkLabel(self, text="Gestor de Modelos de Lenguaje (Bóveda IA + Local)", font=("Arial", 17, "bold")).pack(pady=(16, 8))

        # 1. Proveedor
        frame_prov = ctk.CTkFrame(self, fg_color="transparent")
        frame_prov.pack(fill="x", padx=36, pady=8)
        ctk.CTkLabel(frame_prov, text="Proveedor:", width=100, anchor="w").pack(side="left")
        self.var_provider = ctk.StringVar(value=curr_prov)
        self.menu_provider = ctk.CTkOptionMenu(
            frame_prov, variable=self.var_provider, values=ai_engine.PROVIDERS_ORDER, command=self.on_provider_change
        )
        self.menu_provider.pack(side="left", fill="x", expand=True)

        # URL Base (visible en Ollama, LM Studio y Personalizado)
        self.frame_url = ctk.CTkFrame(self, fg_color="transparent")
        ctk.CTkLabel(self.frame_url, text="URL Base:", width=100, anchor="w").pack(side="left")
        self.var_url = ctk.StringVar(value=prov_data.get("base_url", ""))
        self.entry_url = ctk.CTkEntry(self.frame_url, textvariable=self.var_url)
        self.entry_url.pack(side="left", fill="x", expand=True)

        # 2. API Key
        frame_key = ctk.CTkFrame(self, fg_color="transparent")
        frame_key.pack(fill="x", padx=36, pady=8)
        ctk.CTkLabel(frame_key, text="API Key:", width=100, anchor="w").pack(side="left")
        self.var_key = ctk.StringVar(value=prov_data.get("api_key", ""))
        self.entry_key = ctk.CTkEntry(frame_key, textvariable=self.var_key, show="*")
        self.entry_key.pack(side="left", fill="x", expand=True)

        self.btn_link = ctk.CTkButton(
            self, text="Obtener API Key", fg_color="transparent", text_color="#3498DB",
            hover_color="#2C3E50", command=self.open_link,
        )
        self.btn_link.pack(pady=(0, 4))

        self.var_free_only = ctk.BooleanVar(value=self.settings.get("free_only", True))
        self.chk_free = ctk.CTkCheckBox(
            self, text="Solo mostrar modelos gratuitos/ligeros (evitar Error 429)",
            variable=self.var_free_only, text_color="gray",
        )
        self.chk_free.pack(pady=4)

        # 3. Cargar modelos
        self.btn_fetch = ctk.CTkButton(
            self, text="Cargar Modelos Disponibles", fg_color="#D97706", hover_color="#B45309",
            command=self.fetch_models,
        )
        self.btn_fetch.pack(pady=(8, 8))

        self.lbl_verify = ctk.CTkLabel(
            self, text="Ingresa tu API Key (o inicia Ollama/LM Studio local) y carga los modelos.",
            text_color="gray",
        )
        self.lbl_verify.pack(pady=4)

        # 4. Modelo
        self.frame_mod = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_mod.pack(fill="x", padx=36, pady=8)
        ctk.CTkLabel(self.frame_mod, text="Modelo:", width=100, anchor="w").pack(side="left")
        self.var_model = ctk.StringVar(value=prov_data.get("model", ""))

        initial_vals = self.cached_models if self.cached_models else (
            [self.var_model.get()] if self.var_model.get() else ["--- Carga los modelos primero ---"]
        )
        if not self.var_model.get():
            self.var_model.set(initial_vals[0])

        self.menu_model = ctk.CTkButton(
            self.frame_mod, textvariable=self.var_model, fg_color=("#d5dfeb", "#34495e"),
            text_color=("#1e293b", "#eee"), hover_color=("#c2d0e0", "#2c3e50"),
            anchor="w", command=self.open_model_dropdown,
        )
        self.menu_model.pack(side="left", fill="x", expand=True)
        self.entry_model = ctk.CTkEntry(self.frame_mod, textvariable=self.var_model)

        # Botones principales
        frame_btns = ctk.CTkFrame(self, fg_color="transparent")
        frame_btns.pack(pady=(14, 6))

        ctk.CTkButton(frame_btns, text="Guardar en Bóveda (DPAPI)", fg_color="#27AE60", hover_color="#2ECC71", command=self.save).pack(side="left", padx=8)
        ctk.CTkButton(frame_btns, text="Configurar Tren de Modelos", fg_color="#8E44AD", hover_color="#9B59B6", command=self.open_train).pack(side="left", padx=8)

        # Respaldo portátil cifrado (.aivault)
        frame_backup = ctk.CTkFrame(self, fg_color="transparent")
        frame_backup.pack(pady=(4, 14))
        ctk.CTkButton(frame_backup, text="Exportar Respaldo (.aivault)", width=190, fg_color="#2E86C1", hover_color="#21618C", command=self.export_vault_backup).pack(side="left", padx=8)
        ctk.CTkButton(frame_backup, text="Importar Respaldo (.aivault)", width=190, fg_color="#475569", hover_color="#334155", command=self.import_vault_backup).pack(side="left", padx=8)

        self.on_provider_change(self.var_provider.get(), initial_load=True)

    def on_provider_change(self, val, initial_load=False):
        prov_data = self.settings.get("providers", {}).get(val, {})
        default_url = ai_engine.DEFAULT_ENDPOINTS.get(val, "")

        if not initial_load:
            self.var_key.set(prov_data.get("api_key", ""))
            self.var_url.set(prov_data.get("base_url") or default_url)
            self.cached_models = prov_data.get("cached_models", [])
            initial_vals = self.cached_models if self.cached_models else ["--- Carga los modelos primero ---"]
            self.var_model.set(prov_data.get("model") or (initial_vals[0] if initial_vals else ""))
        elif val in ai_engine.LOCAL_PROVIDERS and not self.var_url.get():
            self.var_url.set(default_url)

        if val in ai_engine.LOCAL_PROVIDERS or val == "Personalizado":
            self.frame_url.pack(fill="x", padx=36, pady=5, after=self.menu_provider.master)
        else:
            self.frame_url.pack_forget()

        if val == "Personalizado":
            self.menu_model.pack_forget()
            self.entry_model.pack(side="left", fill="x", expand=True)
            self.btn_link.configure(text="Endpoint OpenAI-compatible (API Key opcional en localhost)", command=lambda: None)
        else:
            self.entry_model.pack_forget()
            self.menu_model.pack(side="left", fill="x", expand=True)

            if val == "Google Gemini":
                self.btn_link.configure(text="Obtener API Key Gratuita (Google AI Studio)", command=lambda: __import__("webbrowser").open("https://aistudio.google.com/app/apikey"))
            elif val == "OpenAI":
                self.btn_link.configure(text="Obtener API Key (Plataforma OpenAI)", command=lambda: __import__("webbrowser").open("https://platform.openai.com/api-keys"))
            elif val == "Anthropic Claude":
                self.btn_link.configure(text="Obtener API Key (Anthropic Console)", command=lambda: __import__("webbrowser").open("https://console.anthropic.com/settings/keys"))
            elif val == "Groq":
                self.btn_link.configure(text="Obtener API Key Gratuita (Groq Cloud)", command=lambda: __import__("webbrowser").open("https://console.groq.com/keys"))
            elif val == "Deepseek":
                self.btn_link.configure(text="Obtener API Key (Deepseek Platform)", command=lambda: __import__("webbrowser").open("https://platform.deepseek.com/api_keys"))
            elif val == "Ollama (Local)":
                self.btn_link.configure(text="IA Local Ollama (sin API Key — usa http://localhost:11434)", command=lambda: __import__("webbrowser").open("https://ollama.com"))
            elif val == "LM Studio (Local)":
                self.btn_link.configure(text="IA Local LM Studio (sin API Key — usa http://localhost:1234)", command=lambda: __import__("webbrowser").open("https://lmstudio.ai"))

    def open_model_dropdown(self):
        vals = self.cached_models if self.cached_models else ["--- Carga los modelos primero ---"]
        CustomDropdownWindow(self, self.menu_model, self.var_model, vals)

    def open_link(self):
        __import__("webbrowser").open("https://aistudio.google.com/app/apikey")

    def fetch_models(self):
        provider = self.var_provider.get()
        api_key = self.var_key.get().strip()
        base_url = self.var_url.get().strip()

        if ai_engine.provider_requires_api_key(provider, base_url) and not api_key:
            self.lbl_verify.configure(text="[AVISO] Por favor ingresa tu API Key primero.", text_color="#E74C3C")
            return

        self.lbl_verify.configure(text="Obteniendo modelos disponibles...", text_color="#D97706")
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
                    if self.var_model.get() not in models:
                        preferred = "gemini-2.0-flash" if "gemini-2.0-flash" in models else (
                            "gemini-1.5-flash" if "gemini-1.5-flash" in models else models[0]
                        )
                        self.after(0, lambda p=preferred: self.var_model.set(p))
                    self.after(0, lambda n=len(models): self.lbl_verify.configure(text=f"[OK] Se cargaron {n} modelos disponibles.", text_color="#2ECC71"))
                else:
                    self.after(0, lambda: self.lbl_verify.configure(text="[AVISO] No se encontraron modelos en este servidor.", text_color="#E74C3C"))
            except Exception as exc:
                msg = ai_engine.classify_http_error(exc)
                self.after(0, lambda m=msg: self.lbl_verify.configure(text=f"[ERROR] {m}", text_color="#E74C3C"))
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
