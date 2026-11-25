import os
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import ttkbootstrap as tb
from ttkbootstrap.widgets.scrolled import ScrolledFrame, ScrolledText
from functions.utils import center_window
from functions import ui_theme


class MultiSelectDropdown(tb.Button):
    def __init__(self, master, options, **kwargs):
        kwargs.setdefault("bootstyle", "secondary")
        super().__init__(master, text="Todas (*.*)", command=self.toggle_dropdown, **kwargs)
        self.options = options
        self.vars = {opt: tk.BooleanVar(value=(opt == "*.*")) for opt in options}
        self.dropdown_window = None

    def toggle_dropdown(self):
        if self.dropdown_window is None or not self.dropdown_window.winfo_exists():
            self.dropdown_window = tb.Toplevel(self)
            self.dropdown_window.title("Seleccionar Extensiones")
            self.dropdown_window.attributes("-topmost", True)
            self.dropdown_window.resizable(False, False)

            x = self.winfo_rootx()
            y = self.winfo_rooty() + self.winfo_height()
            self.dropdown_window.geometry(f"210x260+{x}+{y}")
            self.dropdown_window.overrideredirect(True)

            frame = tb.Frame(self.dropdown_window, padding=6, bootstyle="secondary")
            frame.pack(fill="both", expand=True)

            inner = tb.Frame(frame, padding=4)
            inner.pack(fill="both", expand=True)

            scroll = ScrolledFrame(inner, auto_hide=True)
            scroll.pack(fill="both", expand=True, padx=2, pady=2)

            for opt in self.options:
                cb = tb.Checkbutton(scroll, text=opt, variable=self.vars[opt], command=self.update_text, bootstyle="primary")
                cb.pack(anchor="w", pady=2, padx=4)

            btn_close = tb.Button(inner, text="Cerrar", command=self.dropdown_window.destroy, bootstyle="danger")
            btn_close.pack(fill="x", pady=(6, 0))
        else:
            self.dropdown_window.destroy()

    def update_text(self):
        selected = [opt for opt, var in self.vars.items() if var.get()]
        if not selected:
            self.configure(text="Ninguna")
        elif "*.*" in selected:
            self.configure(text="Todas (*.*)")
        else:
            self.configure(text=f"{len(selected)} seleccionadas")

    def get_selected(self):
        selected = [opt for opt, var in self.vars.items() if var.get()]
        if "*.*" in selected or not selected:
            return ["*.*"]
        return selected


class AdvancedSearchApp(tb.Window):
    def __init__(self):
        theme = ui_theme.get_saved_theme()
        super().__init__(themename=theme)
        self.title("Búsqueda Avanzada de Texto (FindStr Ultra)")
        center_window(self, 920, 620)
        ui_theme.apply_window_chrome(self, theme)

        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        top_frame = tb.Labelframe(self, text="Filtros de Búsqueda", padding=12, bootstyle="info")
        top_frame.grid(row=0, column=0, padx=16, pady=(12, 6), sticky="ew")
        top_frame.grid_columnconfigure(1, weight=1)
        top_frame.grid_columnconfigure(4, weight=1)

        tb.Label(top_frame, text="Directorio:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.dir_var = tk.StringVar()
        self.dir_entry = ui_theme.PlaceholderEntry(top_frame, textvariable=self.dir_var, placeholder="Selecciona una carpeta...")
        self.dir_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        self.btn_browse = tb.Button(top_frame, text="Examinar", command=self.browse, bootstyle="info")
        self.btn_browse.grid(row=0, column=2, padx=5, pady=5)

        tb.Label(top_frame, text="Texto a buscar:").grid(row=0, column=3, padx=(14, 5), pady=5, sticky="w")
        self.term_var = tk.StringVar()
        self.term_entry = ui_theme.PlaceholderEntry(top_frame, textvariable=self.term_var, placeholder="Palabra o patrón...")
        self.term_entry.grid(row=0, column=4, padx=5, pady=5, sticky="ew")

        tb.Label(top_frame, text="Extensiones:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        exts = [
            "*.*", "*.txt", "*.log", "*.json", "*.py", "*.csv", "*.xml", "*.md",
            "*.ini", "*.cfg", "*.html", "*.css", "*.js", "*.php", "*.cpp", "*.java", "*.bat", "*.pdf",
        ]
        self.ext_dropdown = MultiSelectDropdown(top_frame, options=exts, width=18)
        self.ext_dropdown.grid(row=1, column=1, padx=5, pady=5, sticky="w")

        self.ignore_case_var = tk.BooleanVar(value=True)
        tb.Checkbutton(top_frame, text="Ignorar Mayúsculas (/i)", variable=self.ignore_case_var, bootstyle="primary").grid(row=1, column=3, padx=5, pady=5, sticky="w")

        self.regex_var = tk.BooleanVar(value=False)
        tb.Checkbutton(top_frame, text="Expresión Regular (/r)", variable=self.regex_var, bootstyle="primary").grid(row=1, column=4, padx=5, pady=5, sticky="w")

        self.btn_search = tb.Button(self, text="Buscar Ahora", command=self.run_search, bootstyle="success", width=22)
        self.btn_search.grid(row=1, column=0, padx=16, pady=6)

        self.results_frame = ScrolledFrame(self, auto_hide=True, padding=8)
        self.results_frame.grid(row=2, column=0, padx=16, pady=(4, 14), sticky="nsew")

    def browse(self):
        f = filedialog.askdirectory(parent=self)
        if f:
            self.dir_entry.set_value(f.replace("/", "\\"))

    def run_search(self):
        d = self.dir_entry.get_value().strip()
        t = self.term_entry.get_value().strip()
        if not d or not t:
            return
        self.btn_search.configure(state="disabled")

        for w in self.results_frame.winfo_children():
            w.destroy()

        tb.Label(self.results_frame, text="Buscando coincidencias...", font=("Segoe UI", 12), bootstyle="info").pack(pady=20)

        def task():
            exts = self.ext_dropdown.get_selected()
            flags = "/s /n "
            if self.ignore_case_var.get():
                flags += "/i "
            if self.regex_var.get():
                flags += "/r "
            else:
                flags += "/c:"

            paths = " ".join([f'"{d}\\{ext}"' for ext in exts])
            cmd = f'findstr {flags}"{t}" {paths}'

            try:
                out = subprocess.check_output(
                    cmd,
                    shell=True,
                    stderr=subprocess.STDOUT,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                text = out.decode("mbcs", "ignore")
            except subprocess.CalledProcessError as err:
                text = err.output.decode("mbcs", "ignore") if err.output else ""

            self.after(0, self.done, text)

        threading.Thread(target=task, daemon=True).start()

    def done(self, text):
        for w in self.results_frame.winfo_children():
            w.destroy()
        self.btn_search.configure(state="normal")

        if not text.strip():
            tb.Label(self.results_frame, text="No se encontraron coincidencias.", font=("Segoe UI", 12), bootstyle="secondary").pack(pady=20)
            return

        lines = text.strip().split("\n")
        grouped = {}

        for line in lines:
            line = line.strip()
            if not line or line.startswith("FINDSTR:"):
                continue

            parts = line.split(":", 2)
            if len(parts) >= 3:
                if len(parts[0]) == 1 and parts[0].isalpha() and "\\" in parts[1]:
                    path = parts[0] + ":" + parts[1]
                    rem = parts[2].split(":", 1)
                    if len(rem) == 2:
                        line_num, content = rem[0], rem[1]
                    else:
                        line_num, content = "?", parts[2]
                else:
                    path, line_num, content = parts[0], parts[1], parts[2]

                grouped.setdefault(path, []).append((line_num, content))

        for path, matches in grouped.items():
            card = tb.Labelframe(self.results_frame, text=f"{path} ({len(matches)} coincidencias)", padding=8, bootstyle="warning")
            card.pack(fill="x", pady=8, padx=4)

            header = tb.Frame(card)
            header.pack(fill="x", pady=(0, 6))
            tb.Button(header, text="Abrir Archivo", command=lambda p=path: self.open_file(p), bootstyle="info-outline").pack(side="right")

            matches_text = "".join(f"Línea {line_num:>5} |  {content}\n" for line_num, content in matches)
            box_h = min(10, max(2, len(matches) + 1))
            box = ScrolledText(card, font=("Consolas", 10), height=box_h, auto_hide=True)
            box.pack(fill="x")
            box.text.insert("1.0", matches_text)
            box.text.configure(state="disabled")

    def open_file(self, path):
        clean_path = path.strip()
        if not os.path.exists(clean_path):
            messagebox.showerror("Error", f"Windows no puede encontrar la ruta:\n{clean_path}", parent=self)
            return
        try:
            subprocess.Popen(
                ["explorer.exe", clean_path],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception:
            try:
                os.startfile(clean_path)
            except Exception as e2:
                messagebox.showerror("Error Crítico", f"No se pudo abrir el archivo.\n{e2}", parent=self)


if __name__ == "__main__":
    app = AdvancedSearchApp()
    app.mainloop()
