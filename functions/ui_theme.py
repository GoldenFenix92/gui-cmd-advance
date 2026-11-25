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

DEFAULT_DARK_THEME = "pulse-dark"
DEFAULT_LIGHT_THEME = "pulse-light"
DEFAULT_THEME = DEFAULT_DARK_THEME

DARK_THEMES = (
    "pulse-dark",
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
    "pulse-light",
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
    "sandstone-light",
    "united-light",
    "vapor-light",
)

ALL_THEMES = tuple(dict.fromkeys(DARK_THEMES + LIGHT_THEMES))

PULSE_PALETTES = {
    "dark": {
        "bg": "#17141F",
        "card_bg": "#211D2E",
        "card_border": "#3A334E",
        "well_bg": "#120F1A",
        "well_border": "#352F47",
        "fg": "#EDEBF5",
        "muted": "#A39CB8",
        "primary": "#7A5AAB",
        "primary_hover": "#8E6EC2",
        "primary_press": "#664994",
        "secondary": "#4B455C",
        "secondary_hover": "#5B546E",
        "secondary_press": "#3D384B",
        "success": "#34B86B",
        "success_hover": "#42C777",
        "success_press": "#299B58",
        "info": "#29A3D6",
        "info_hover": "#3BB4E6",
        "info_press": "#1E88B5",
        "warning": "#E5A535",
        "warning_hover": "#F2B54A",
        "warning_press": "#C98D24",
        "danger": "#E85050",
        "danger_hover": "#FD6161",
        "danger_press": "#C93D3D",
        "disabled_bg": "#2C273A",
        "disabled_fg": "#716B82",
        "trough": "#2C263D",
        "btn_fg": "#FFFFFF",
        "warning_fg": "#17141F",
    },
    "light": {
        "bg": "#F1EEF7",
        "card_bg": "#FFFFFF",
        "card_border": "#DDD6EC",
        "well_bg": "#FAF9FD",
        "well_border": "#CFC6E2",
        "fg": "#2D2640",
        "muted": "#6B6380",
        "primary": "#5B3299",
        "primary_hover": "#6D40B3",
        "primary_press": "#472778",
        "secondary": "#5E586E",
        "secondary_hover": "#706982",
        "secondary_press": "#4A4557",
        "success": "#148F47",
        "success_hover": "#19A854",
        "success_press": "#0F7338",
        "info": "#008CC7",
        "info_hover": "#00A0E3",
        "info_press": "#0073A3",
        "warning": "#D98A00",
        "warning_hover": "#EB9B0E",
        "warning_press": "#B87400",
        "danger": "#C93030",
        "danger_hover": "#DE3E3E",
        "danger_press": "#A62424",
        "disabled_bg": "#E5E0EE",
        "disabled_fg": "#9A93AD",
        "trough": "#E2DCEB",
        "btn_fg": "#FFFFFF",
        "warning_fg": "#FFFFFF",
    },
}

UI_SETTINGS_FILENAME = "ui_settings.json"

_ICON_CACHE = {}
_ROUNDED_IMG_CACHE = {}
_ROUNDED_ELEMENTS_CREATED = set()


def get_available_themes():
    """Retorna los temas nativos de ttkbootstrap 2.x (oscuros primero, luego claros)."""
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


def get_pulse_palette(theme_name=None):
    """Retorna el diccionario de tokens Pulse para modo oscuro o claro."""
    return PULSE_PALETTES["dark" if is_dark_theme(theme_name) else "light"]


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
    """Obtiene el tema guardado (por defecto pulse-dark; mapea legacy a pulse-dark/pulse-light)."""
    theme = str(load_ui_settings().get("theme", DEFAULT_THEME)).strip().lower()
    if theme in (DEFAULT_DARK_THEME, DEFAULT_LIGHT_THEME):
        return theme
    if theme.endswith("-light"):
        return DEFAULT_LIGHT_THEME
    return DEFAULT_DARK_THEME


def set_saved_theme(theme_name):
    """Persiste un tema válido de ttkbootstrap 2.x."""
    name = str(theme_name or "").strip().lower()
    if name not in ALL_THEMES:
        name = DEFAULT_THEME
    settings = load_ui_settings()
    settings["theme"] = name
    save_ui_settings(settings)
    return name


def _make_rounded_9slice(master, width, height, radius, fill_color, border_color=None, border_width=1, bg_color=None):
    """Genera una imagen PhotoImage 9-slice con esquinas redondeadas suavizadas (3x supersampling)."""
    key = (id(master), width, height, radius, fill_color, border_color, border_width, bg_color)
    if key in _ROUNDED_IMG_CACHE:
        return _ROUNDED_IMG_CACHE[key]

    scale = 3
    sw, sh = width * scale, height * scale
    sr = radius * scale
    sbw = max(1, border_width * scale)

    base_rgba = (0, 0, 0, 0)
    if bg_color and bg_color.startswith("#") and len(bg_color) == 7:
        base_rgba = (int(bg_color[1:3], 16), int(bg_color[3:5], 16), int(bg_color[5:7], 16), 255)

    img = Image.new("RGBA", (sw, sh), base_rgba)
    draw = ImageDraw.Draw(img)

    pad = 1
    rect = [pad, pad, sw - 1 - pad, sh - 1 - pad]
    if border_color:
        draw.rounded_rectangle(rect, radius=sr, fill=fill_color, outline=border_color, width=sbw)
    else:
        draw.rounded_rectangle(rect, radius=sr, fill=fill_color)

    out = img.resize((width, height), Image.Resampling.LANCZOS)
    photo = ImageTk.PhotoImage(out, master=master)
    _ROUNDED_IMG_CACHE[key] = photo
    return photo


def _ensure_image_element(style, elem_name, default_img, states, border, padding=None):
    """Crea un elemento ttk 'image' de forma idempotente (evita TclError en cambios de tema)."""
    master_id = id(style.master)
    key = (master_id, style.theme_use(), elem_name)
    if key in _ROUNDED_ELEMENTS_CREATED:
        return
    try:
        spec = [default_img]
        for state_spec, img in states:
            spec.append((state_spec, img))
        kwargs = {"border": border, "sticky": "nsew"}
        if padding is not None:
            kwargs["padding"] = padding
        style.element_create(elem_name, "image", *spec, **kwargs)
        _ROUNDED_ELEMENTS_CREATED.add(key)
    except Exception:
        _ROUNDED_ELEMENTS_CREATED.add(key)


def apply_rounded_styles(style, theme_name=None):
    """Aplica esquinas redondeadas 9-slice a botones, entradas, comboboxes y tarjetas en el estilo activo."""
    if theme_name is None:
        theme_name = style.theme_use()
    pal = get_pulse_palette(theme_name)
    master = style.master
    mode_tag = "dark" if is_dark_theme(theme_name) else "light"

    # Fondo base y tarjetas
    try:
        master.configure(background=pal["bg"])
    except Exception:
        pass
    style.configure("TFrame", background=pal["bg"])
    style.configure("TLabel", background=pal["bg"], foreground=pal["fg"])
    style.configure("TCheckbutton", background=pal["bg"], foreground=pal["fg"])
    style.configure("TRadiobutton", background=pal["bg"], foreground=pal["fg"])

    # 1. Tarjeta elevada redondeada (12px)
    card_img = _make_rounded_9slice(
        master, 44, 44, radius=12, fill_color=pal["card_bg"], border_color=pal["card_border"], border_width=1, bg_color=pal["bg"]
    )
    card_elem = f"PulseCard.{mode_tag}.border"
    _ensure_image_element(style, card_elem, card_img, [], border=(13, 13, 13, 13))
    style.layout("PulseCard.TFrame", [(card_elem, {"sticky": "nsew"})])
    style.configure("PulseCard.TFrame", background=pal["card_bg"], padding=10)
    style.configure("PulseCardInner.TFrame", background=pal["card_bg"])
    style.configure("PulseCardTitle.TLabel", background=pal["card_bg"], foreground=pal["primary"], font=("Segoe UI", 10, "bold"))
    style.configure("PulseCard.TLabel", background=pal["card_bg"], foreground=pal["fg"])
    style.configure("PulseCardMuted.TLabel", background=pal["card_bg"], foreground=pal["muted"])
    style.configure("PulseCard.TCheckbutton", background=pal["card_bg"], foreground=pal["fg"])
    style.configure("PulseCard.TRadiobutton", background=pal["card_bg"], foreground=pal["fg"])

    # 2. TLabelframe redondeado (12px) para ventanas secundarias
    lf_img = _make_rounded_9slice(
        master, 44, 44, radius=12, fill_color=pal["card_bg"], border_color=pal["card_border"], border_width=1, bg_color=pal["bg"]
    )
    lf_elem = f"PulseLF.{mode_tag}.border"
    _ensure_image_element(style, lf_elem, lf_img, [], border=(13, 13, 13, 13))
    for lf_style in ("TLabelframe", "primary.TLabelframe", "secondary.TLabelframe", "info.TLabelframe", "success.TLabelframe", "warning.TLabelframe", "danger.TLabelframe"):
        try:
            style.layout(lf_style, [(lf_elem, {"sticky": "nsew"})])
            style.configure(lf_style, background=pal["card_bg"])
            style.configure(f"{lf_style}.Label", background=pal["card_bg"], foreground=pal["primary"], font=("Segoe UI", 9, "bold"))
        except Exception:
            pass

    # 3. Botones sólidos y outline con esquinas redondeadas (8px)
    r_btn = 8
    btn_specs = {
        "TButton": ("primary", pal["btn_fg"]),
        "primary.TButton": ("primary", pal["btn_fg"]),
        "secondary.TButton": ("secondary", pal["btn_fg"]),
        "success.TButton": ("success", pal["btn_fg"]),
        "info.TButton": ("info", pal["btn_fg"]),
        "warning.TButton": ("warning", pal["warning_fg"]),
        "danger.TButton": ("danger", pal["btn_fg"]),
    }
    img_disabled = _make_rounded_9slice(master, 34, 30, r_btn, pal["disabled_bg"], bg_color=pal["card_bg"])

    for style_name, (color_key, fg_col) in btn_specs.items():
        img_norm = _make_rounded_9slice(master, 34, 30, r_btn, pal[color_key], bg_color=pal["card_bg"])
        img_hov = _make_rounded_9slice(master, 34, 30, r_btn, pal[f"{color_key}_hover"], bg_color=pal["card_bg"])
        img_prs = _make_rounded_9slice(master, 34, 30, r_btn, pal[f"{color_key}_press"], bg_color=pal["card_bg"])
        elem_name = f"PulseBtn.{mode_tag}.{color_key}.border"
        _ensure_image_element(
            style,
            elem_name,
            img_norm,
            [("disabled", img_disabled), ("pressed", img_prs), ("active", img_hov)],
            border=(9, 9, 9, 9),
            padding=(10, 5),
        )
        try:
            style.layout(
                style_name,
                [(elem_name, {"sticky": "nswe", "children": [("Button.label", {"sticky": "nswe"})]})],
            )
            style.configure(style_name, foreground=fg_col, background=pal[color_key], relief="flat", borderwidth=0)
            style.map(
                style_name,
                foreground=[("disabled", pal["disabled_fg"]), ("active", fg_col), ("pressed", fg_col)],
                background=[("disabled", pal["disabled_bg"]), ("pressed", pal[f"{color_key}_press"]), ("active", pal[f"{color_key}_hover"])],
            )
        except Exception:
            pass

    # Botones Outline redondeados (8px)
    for color_key in ("primary", "secondary", "success", "info", "warning", "danger"):
        outline_style = f"{color_key}.Outline.TButton"
        img_norm = _make_rounded_9slice(master, 34, 30, r_btn, pal["card_bg"], border_color=pal[color_key], border_width=1, bg_color=pal["card_bg"])
        img_hov = _make_rounded_9slice(master, 34, 30, r_btn, pal[color_key], bg_color=pal["card_bg"])
        img_prs = _make_rounded_9slice(master, 34, 30, r_btn, pal[f"{color_key}_press"], bg_color=pal["card_bg"])
        elem_name = f"PulseOutBtn.{mode_tag}.{color_key}.border"
        _ensure_image_element(
            style,
            elem_name,
            img_norm,
            [("disabled", img_disabled), ("pressed", img_prs), ("active", img_hov)],
            border=(9, 9, 9, 9),
            padding=(10, 5),
        )
        fg_hover = pal["warning_fg"] if color_key == "warning" else pal["btn_fg"]
        fg_rest = pal["fg"] if color_key == "secondary" else pal[color_key]
        try:
            style.layout(
                outline_style,
                [(elem_name, {"sticky": "nswe", "children": [("Button.label", {"sticky": "nswe"})]})],
            )
            style.configure(outline_style, foreground=fg_rest, background=pal["card_bg"], relief="flat", borderwidth=0)
            style.map(
                outline_style,
                foreground=[("disabled", pal["disabled_fg"]), ("active", fg_hover), ("pressed", fg_hover)],
                background=[("disabled", pal["disabled_bg"]), ("pressed", pal[f"{color_key}_press"]), ("active", pal[color_key])],
            )
        except Exception:
            pass

    # 4. Entry y Combobox con esquinas redondeadas (8px) + anillo de foco Pulse
    ent_norm = _make_rounded_9slice(master, 34, 30, 8, pal["well_bg"], border_color=pal["well_border"], border_width=1, bg_color=pal["card_bg"])
    ent_focus = _make_rounded_9slice(master, 34, 30, 8, pal["well_bg"], border_color=pal["primary"], border_width=2, bg_color=pal["card_bg"])
    ent_dis = _make_rounded_9slice(master, 34, 30, 8, pal["disabled_bg"], border_color=pal["well_border"], border_width=1, bg_color=pal["card_bg"])
    ent_elem = f"PulseEntry.{mode_tag}.field"
    _ensure_image_element(
        style,
        ent_elem,
        ent_norm,
        [("disabled", ent_dis), ("focus", ent_focus)],
        border=(9, 9, 9, 9),
        padding=(8, 5),
    )
    for ent_style in ("TEntry", "primary.TEntry", "info.TEntry", "success.TEntry", "danger.TEntry"):
        try:
            style.layout(
                ent_style,
                [(ent_elem, {"sticky": "nswe", "children": [("Entry.textarea", {"sticky": "nswe"})]})],
            )
            style.configure(ent_style, fieldbackground=pal["well_bg"], foreground=pal["fg"], insertcolor=pal["fg"])
        except Exception:
            pass

    cb_elem = f"PulseCombo.{mode_tag}.field"
    _ensure_image_element(
        style,
        cb_elem,
        ent_norm,
        [("disabled", ent_dis), ("focus", ent_focus)],
        border=(9, 9, 9, 9),
        padding=(8, 5),
    )
    try:
        style.layout(
            "TCombobox",
            [(cb_elem, {"side": "top", "sticky": "we", "children": [("Combobox.downarrow", {"side": "right", "sticky": ""}), ("Combobox.textarea", {"sticky": "nswe"})]})],
        )
        style.configure("TCombobox", fieldbackground=pal["well_bg"], foreground=pal["fg"])
    except Exception:
        pass


class RoundedCard(tb.Frame):
    """Contenedor moderno con esquinas redondeadas (12px) y superficie elevada Pulse."""

    def __init__(self, master, title="", padding=(10, 8), **kwargs):
        super().__init__(master, style="PulseCard.TFrame", **kwargs)
        self.grid_columnconfigure(0, weight=1)
        row_idx = 0
        self.title_label = None
        if title:
            self.title_label = tb.Label(self, text=title, style="PulseCardTitle.TLabel")
            self.title_label.grid(row=0, column=0, sticky="w", padx=(4, 4), pady=(0, 6))
            row_idx = 1

        self.grid_rowconfigure(row_idx, weight=1)
        self.body = tb.Frame(self, style="PulseCardInner.TFrame", padding=padding)
        self.body.grid(row=row_idx, column=0, sticky="nsew")


class RoundedProgressBar(tk.Canvas):
    """Barra de progreso moderna tipo píldora (esquinas redondeadas 10px) con colores semánticos."""

    def __init__(self, master, maximum=100, value=0, height=24, radius=10, theme_name=None, **kwargs):
        self._palette = get_pulse_palette(theme_name)
        bg = kwargs.pop("bg", self._palette["card_bg"])
        super().__init__(master, height=height, highlightthickness=0, bd=0, bg=bg, **kwargs)
        self._maximum = max(1, float(maximum))
        self._value = max(0.0, min(self._maximum, float(value)))
        self._radius = radius
        self._height = height
        self._mode = "determinate"
        self._bootstyle = "info"
        self._anim_id = None
        self._anim_pos = 0.0
        self._text = "0%"
        self.bind("<Configure>", lambda _e: self._redraw())

    def apply_palette(self, theme_name=None):
        self._palette = get_pulse_palette(theme_name)
        self.configure(bg=self._palette["card_bg"])
        self._redraw()

    def set_progress(self, value=None, mode=None, bootstyle=None, text=None):
        if value is not None:
            self._value = max(0.0, min(self._maximum, float(value)))
        if mode is not None:
            self._mode = mode
        if bootstyle is not None:
            self._bootstyle = bootstyle
        if text is not None:
            self._text = text
        elif self._mode == "determinate":
            pct = int(round((self._value / self._maximum) * 100))
            self._text = f"{pct}%"
        self._redraw()

    def start(self, interval_ms=35):
        self._mode = "indeterminate"
        self.stop()
        self._animate(interval_ms)

    def stop(self):
        if self._anim_id is not None:
            try:
                self.after_cancel(self._anim_id)
            except Exception:
                pass
            self._anim_id = None

    def _animate(self, interval_ms):
        if self._mode != "indeterminate":
            return
        self._anim_pos = (self._anim_pos + 0.035) % 1.35
        self._redraw()
        self._anim_id = self.after(interval_ms, lambda: self._animate(interval_ms))

    def _draw_pill(self, x1, y1, x2, y2, r, fill, outline=""):
        r = min(r, (x2 - x1) / 2.0, (y2 - y1) / 2.0)
        if r < 1:
            return
        pts = [
            x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
            x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
            x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
        ]
        self.create_polygon(pts, smooth=True, splinesteps=24, fill=fill, outline=outline)

    def _redraw(self):
        self.delete("all")
        w = max(self.winfo_width(), 60)
        h = max(self.winfo_height(), self._height)
        pal = self._palette
        fill_col = pal.get(self._bootstyle, pal["info"])

        self._draw_pill(1, 2, w - 1, h - 2, self._radius, fill=pal["trough"], outline=pal["card_border"])

        if self._mode == "indeterminate":
            seg_w = max(48, w * 0.28)
            start_x = (self._anim_pos - 0.30) * w
            x1 = max(2, start_x)
            x2 = min(w - 2, start_x + seg_w)
            if x2 - x1 > 10:
                self._draw_pill(x1, 3, x2, h - 3, max(4, self._radius - 1), fill=fill_col)
            label_txt = "Procesando..."
        else:
            frac = self._value / self._maximum
            if frac > 0.005:
                bar_w = max(self._radius * 2, (w - 4) * frac)
                self._draw_pill(2, 3, min(w - 2, 2 + bar_w), h - 3, max(4, self._radius - 1), fill=fill_col)
            label_txt = self._text

        txt_col = pal["fg"]
        if self._mode == "determinate" and (self._value / self._maximum) >= 0.48:
            txt_col = pal["warning_fg"] if self._bootstyle == "warning" else "#FFFFFF"
        self.create_text(w / 2.0, h / 2.0, text=label_txt, fill=txt_col, font=("Segoe UI", 9, "bold"))


class ThemeToggleSwitch(tk.Canvas):
    """Interruptor animado Sol/Luna para alternar entre pulse-dark y pulse-light."""

    def __init__(self, master, is_dark=True, command=None, **kwargs):
        self._is_dark = bool(is_dark)
        self._command = command
        self._pos = 1.0 if self._is_dark else 0.0
        self._anim_id = None
        pal = get_pulse_palette(DEFAULT_DARK_THEME if self._is_dark else DEFAULT_LIGHT_THEME)
        super().__init__(master, width=62, height=28, highlightthickness=0, bd=0, bg=pal["bg"], cursor="hand2", **kwargs)
        self.bind("<Button-1>", self._on_click)
        self._redraw()

    def is_dark(self):
        return self._is_dark

    def set_dark(self, dark, notify=False):
        self._is_dark = bool(dark)
        self._animate_to(1.0 if self._is_dark else 0.0)
        if notify and self._command:
            self._command(self._is_dark)

    def apply_bg(self, theme_name=None):
        pal = get_pulse_palette(theme_name)
        self.configure(bg=pal["bg"])
        self._redraw()

    def _on_click(self, _event=None):
        self.set_dark(not self._is_dark, notify=True)

    def _animate_to(self, target):
        if self._anim_id is not None:
            try:
                self.after_cancel(self._anim_id)
            except Exception:
                pass
            self._anim_id = None

        def _step():
            diff = target - self._pos
            if abs(diff) < 0.06:
                self._pos = target
                self._redraw()
                self._anim_id = None
                return
            self._pos += diff * 0.38
            self._redraw()
            self._anim_id = self.after(16, _step)

        _step()

    def _redraw(self):
        self.delete("all")
        w, h = 62, 28
        r = 13
        track_col = "#7A5AAB" if self._is_dark else "#E5A535"
        border_col = "#9B7CD0" if self._is_dark else "#C98D24"

        pts = [
            1 + r, 1, w - 1 - r, 1, w - 1, 1, w - 1, 1 + r,
            w - 1, h - 1 - r, w - 1, h - 1, w - 1 - r, h - 1, 1 + r, h - 1,
            1, h - 1, 1, h - 1 - r, 1, 1 + r, 1, 1,
        ]
        self.create_polygon(pts, smooth=True, splinesteps=24, fill=track_col, outline=border_col)

        # Ícono Sol a la izquierda y Luna a la derecha (vectorial puro, cero emojis)
        sx, sy = 15, h / 2.0
        self.create_oval(sx - 3.5, sy - 3.5, sx + 3.5, sy + 3.5, fill="#FFF8E1", outline="")
        for deg in range(0, 360, 45):
            rad = math.radians(deg)
            self.create_line(
                sx + 5.2 * math.cos(rad), sy + 5.2 * math.sin(rad),
                sx + 7.2 * math.cos(rad), sy + 7.2 * math.sin(rad),
                fill="#FFF8E1", width=1.2,
            )

        mx, my = w - 15, h / 2.0
        self.create_oval(mx - 5, my - 5, mx + 5, my + 5, fill="#EDEBF5", outline="")
        self.create_oval(mx - 1.5, my - 5.5, mx + 6.5, my + 3.5, fill=track_col, outline="")

        # Perilla deslizante
        knob_r = 10
        kx = (4 + knob_r) + self._pos * ((w - 4 - knob_r) - (4 + knob_r))
        ky = h / 2.0
        self.create_oval(kx - knob_r, ky - knob_r, kx + knob_r, ky + knob_r, fill="#FFFFFF", outline="#D8D2E8", width=1)


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
    """Aplica el ícono de la aplicación, estilos redondeados Pulse y barra de título Win32."""
    try:
        style = getattr(window, "style", None)
        if style is None:
            style = tb.Style()
        apply_rounded_styles(style, theme_name)
    except Exception:
        pass

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
