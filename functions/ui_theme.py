import ctypes
import json
import math
import os
import tkinter as tk
from PIL import Image, ImageDraw, ImageTk
import ttkbootstrap as tb
from ttkbootstrap.themes import standard as _tb_standard
from ttkbootstrap.widgets.tooltip import ToolTip

from functions.utils import get_resource_path, get_user_data_path

DEFAULT_DARK_THEME = "bootstrap-dark"
DEFAULT_LIGHT_THEME = "bootstrap-light"
DEFAULT_THEME = DEFAULT_DARK_THEME

# Temas nativos de ttkbootstrap 2.x (sin DeprecationWarning)
DARK_THEMES = (
    "bootstrap-dark",
    "tokyo-night-dark",
    "catppuccin-dark",
    "one-dark",
    "nord-dark",
    "dracula-dark",
    "gruvbox-dark",
    "everforest-dark",
    "solarized-dark",
    "pydata-dark",
    "minty-dark",
    "pulse-dark",
    "sandstone-dark",
    "united-dark",
    "vapor-dark",
)

LIGHT_THEMES = (
    "bootstrap-light",
    "tokyo-night-light",
    "catppuccin-light",
    "one-light",
    "nord-light",
    "dracula-light",
    "gruvbox-light",
    "everforest-light",
    "solarized-light",
    "pydata-light",
    "minty-light",
    "pulse-light",
    "sandstone-light",
    "united-light",
    "vapor-light",
)

ALL_THEMES = DARK_THEMES + LIGHT_THEMES

UI_SETTINGS_FILENAME = "ui_settings.json"

# Mantiene referencias vivas a PhotoImage para evitar recolección de basura en Tk
_ICON_CACHE = {}


def get_available_themes():
    """Retorna los 30 temas nativos de ttkbootstrap 2.x (oscuros primero, luego claros)."""
    return list(ALL_THEMES)


def get_theme_type(theme_name):
    """Retorna 'dark' o 'light' para un nombre de tema de ttkbootstrap."""
    name = str(theme_name or "").strip().lower()
    if name in LIGHT_THEMES or name.endswith("-light"):
        return "light"
    if name in DARK_THEMES or name.endswith("-dark"):
        return "dark"
    meta = _tb_standard.STANDARD_THEMES.get(name)
    if meta:
        return meta.get("type", "dark")
    return "dark"


def is_dark_theme(theme_name=None):
    """Indica si el tema activo o especificado es oscuro."""
    if theme_name is None:
        theme_name = get_saved_theme()
    return get_theme_type(theme_name) == "dark"


def _settings_path():
    return get_user_data_path(UI_SETTINGS_FILENAME)


def load_ui_settings():
    """Carga configuración visual persistente (tema seleccionado)."""
    path = _settings_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {"theme": DEFAULT_THEME}


def save_ui_settings(settings):
    """Guarda configuración visual persistente en C:\\GuiCmdAdvance\\ui_settings.json."""
    try:
        path = _settings_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False


def get_saved_theme():
    """Obtiene el tema guardado validando que exista en ttkbootstrap 2.x."""
    theme = str(load_ui_settings().get("theme", DEFAULT_THEME)).strip().lower()
    if theme in ALL_THEMES:
        return theme
    return DEFAULT_THEME


def set_saved_theme(theme_name):
    """Persiste un tema válido de ttkbootstrap 2.x."""
    name = str(theme_name or "").strip().lower()
    if name not in ALL_THEMES:
        name = DEFAULT_THEME
    settings = load_ui_settings()
    settings["theme"] = name
    save_ui_settings(settings)
    return name


def apply_dwm_titlebar(window, dark=True):
    """Sincroniza la barra de título nativa de Windows 10/11 con el modo oscuro/claro."""
    if os.name != "nt":
        return
    try:
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        if not hwnd:
            hwnd = window.winfo_id()
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        val = ctypes.c_int(1 if dark else 0)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(val), ctypes.sizeof(val)
        )
    except Exception:
        pass


def apply_window_chrome(window, theme_name=None):
    """Aplica el ícono de la aplicación y la barra de título Win32 acorde al tema."""
    def _apply():
        try:
            if not window.winfo_exists():
                return
            icon_path = get_resource_path("resources/app_icon.ico")
            if os.path.exists(icon_path):
                window.iconbitmap(icon_path)
        except Exception:
            pass
        dark = is_dark_theme(theme_name)
        apply_dwm_titlebar(window, dark=dark)

    try:
        window.after(80, _apply)
    except Exception:
        pass


def bring_to_front(window):
    """Lleva una ventana secundaria al frente y le da foco sin bloquearla permanentemente."""
    try:
        if not window.winfo_exists():
            return
        window.deiconify()
        window.lift()
        window.attributes("-topmost", True)
        window.focus_force()

        def _release():
            try:
                if window.winfo_exists():
                    window.attributes("-topmost", False)
            except Exception:
                pass

        window.after(150, _release)
    except Exception:
        pass


def add_tooltip(widget, text, bootstyle=None):
    """Adjunta un ToolTip nativo de ttkbootstrap a cualquier widget."""
    if not text:
        return None
    try:
        kwargs = {"text": str(text), "delay": 350}
        if bootstyle:
            kwargs["bootstyle"] = bootstyle
        return ToolTip(widget, **kwargs)
    except Exception:
        return None


class PlaceholderEntry(tb.Entry):
    """Entry de ttkbootstrap con soporte transparente de placeholder_text."""

    def __init__(self, master=None, placeholder="", textvariable=None, **kwargs):
        self._placeholder = str(placeholder or "")
        self._has_placeholder = False
        self._external_var = textvariable
        self._internal_guard = False

        if self._external_var is not None:
            kwargs["textvariable"] = self._external_var

        super().__init__(master, **kwargs)

        self.bind("<FocusIn>", self._on_focus_in, add="+")
        self.bind("<FocusOut>", self._on_focus_out, add="+")

        initial = self._external_var.get() if self._external_var is not None else super().get()
        if not initial and self._placeholder:
            self._show_placeholder()

    def _show_placeholder(self):
        if not self._placeholder:
            return
        self._internal_guard = True
        self._has_placeholder = True
        try:
            self.delete(0, "end")
            self.insert(0, self._placeholder)
            self.configure(foreground="#8892A0")
        finally:
            self._internal_guard = False

    def _clear_placeholder(self):
        if not self._has_placeholder:
            return
        self._internal_guard = True
        self._has_placeholder = False
        try:
            self.delete(0, "end")
            self.configure(foreground="")
        finally:
            self._internal_guard = False

    def _on_focus_in(self, _event=None):
        if self._has_placeholder:
            self._clear_placeholder()

    def _on_focus_out(self, _event=None):
        if not super().get() and self._placeholder:
            self._show_placeholder()

    def get_value(self):
        if self._has_placeholder:
            return ""
        return super().get()

    def is_placeholder_active(self):
        return self._has_placeholder

    def set_value(self, value):
        self._clear_placeholder()
        self.delete(0, "end")
        if value:
            self.insert(0, str(value))
            self.configure(foreground="")
        elif self._placeholder:
            self._show_placeholder()


def _render_vector_icon_image(name, size=16, color="#FFFFFF"):
    """Genera un ícono vectorial estilo Bootstrap con antialiasing 4x (cero emojis hardcodeados)."""
    scale = 4
    s = size * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    w = max(2, int(round(s * 0.10)))
    m = int(round(s * 0.12))
    cx = s / 2.0
    cy = s / 2.0

    if name == "info":
        d.ellipse([m, m, s - m, s - m], outline=color, width=w)
        dot_r = max(2, int(s * 0.065))
        d.ellipse([cx - dot_r, s * 0.28 - dot_r, cx + dot_r, s * 0.28 + dot_r], fill=color)
        d.line([cx, s * 0.44, cx, s * 0.72], fill=color, width=w)
    elif name == "help":
        d.ellipse([m, m, s - m, s - m], outline=color, width=w)
        d.arc([s * 0.34, s * 0.24, s * 0.66, s * 0.52], start=180, end=45, fill=color, width=w)
        d.line([cx, s * 0.50, cx, s * 0.60], fill=color, width=w)
        dot_r = max(2, int(s * 0.055))
        d.ellipse([cx - dot_r, s * 0.73 - dot_r, cx + dot_r, s * 0.73 + dot_r], fill=color)
    elif name in ("star", "star_filled"):
        pts = []
        r_out = s * 0.40
        r_in = s * 0.17
        for i in range(10):
            angle = math.radians(-90 + i * 36)
            r = r_out if i % 2 == 0 else r_in
            pts.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
        if name == "star_filled":
            d.polygon(pts, fill=color)
        else:
            d.polygon(pts, outline=color, width=w)
    elif name == "trash":
        d.line([s * 0.20, s * 0.28, s * 0.80, s * 0.28], fill=color, width=w)
        d.rectangle([s * 0.38, s * 0.16, s * 0.62, s * 0.28], outline=color, width=w)
        d.rectangle([s * 0.26, s * 0.28, s * 0.74, s * 0.84], outline=color, width=w)
        d.line([s * 0.42, s * 0.40, s * 0.42, s * 0.72], fill=color, width=max(2, w - 1))
        d.line([s * 0.58, s * 0.40, s * 0.58, s * 0.72], fill=color, width=max(2, w - 1))
    elif name in ("eye", "eye_off"):
        d.arc([s * 0.10, s * 0.26, s * 0.90, s * 0.88], start=200, end=340, fill=color, width=w)
        d.arc([s * 0.10, s * 0.12, s * 0.90, s * 0.74], start=20, end=160, fill=color, width=w)
        r = s * 0.12
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
        if name == "eye_off":
            d.line([s * 0.16, s * 0.84, s * 0.84, s * 0.16], fill=color, width=w)
    elif name == "play":
        d.polygon([(s * 0.28, s * 0.18), (s * 0.82, cy), (s * 0.28, s * 0.82)], fill=color)
    elif name == "stop":
        d.rectangle([s * 0.22, s * 0.22, s * 0.78, s * 0.78], fill=color)
    elif name == "pause":
        d.rectangle([s * 0.24, s * 0.20, s * 0.42, s * 0.80], fill=color)
        d.rectangle([s * 0.58, s * 0.20, s * 0.76, s * 0.80], fill=color)
    elif name == "search":
        d.ellipse([s * 0.16, s * 0.16, s * 0.66, s * 0.66], outline=color, width=w)
        d.line([s * 0.59, s * 0.59, s * 0.84, s * 0.84], fill=color, width=w)
    elif name == "copy":
        d.rectangle([s * 0.34, s * 0.30, s * 0.80, s * 0.84], outline=color, width=w)
        d.line([s * 0.20, s * 0.66, s * 0.20, s * 0.16, s * 0.64, s * 0.16], fill=color, width=w)
    elif name == "refresh":
        d.arc([s * 0.18, s * 0.18, s * 0.82, s * 0.82], start=40, end=320, fill=color, width=w)
        d.polygon([(s * 0.72, s * 0.16), (s * 0.86, s * 0.34), (s * 0.64, s * 0.36)], fill=color)
    elif name == "table":
        d.rectangle([m, m, s - m, s - m], outline=color, width=w)
        d.line([m, s * 0.38, s - m, s * 0.38], fill=color, width=w)
        d.line([m, s * 0.64, s - m, s * 0.64], fill=color, width=max(2, w - 1))
        d.line([s * 0.48, s * 0.38, s * 0.48, s - m], fill=color, width=max(2, w - 1))
    else:
        # Sparkle / AI / genérico (estrella de 4 puntas estilo Bootstrap Stars)
        pts = [
            (cx, m),
            (cx + s * 0.10, cy - s * 0.10),
            (s - m, cy),
            (cx + s * 0.10, cy + s * 0.10),
            (cx, s - m),
            (cx - s * 0.10, cy + s * 0.10),
            (m, cy),
            (cx - s * 0.10, cy - s * 0.10),
        ]
        d.polygon(pts, fill=color)

    return img.resize((size, size), Image.Resampling.LANCZOS)


def get_bootstrap_icon(name, size=16, color="#FFFFFF", master=None):
    """Retorna un ImageTk.PhotoImage cacheado con ícono estilo Bootstrap (sin emojis)."""
    master_key = id(master) if master is not None else 0
    cache_key = (name, int(size), str(color), master_key)
    if cache_key in _ICON_CACHE:
        return _ICON_CACHE[cache_key]
    pil_img = _render_vector_icon_image(name, size=int(size), color=str(color))
    photo = ImageTk.PhotoImage(pil_img, master=master)
    _ICON_CACHE[cache_key] = photo
    return photo
