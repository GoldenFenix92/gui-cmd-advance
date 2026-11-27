import argparse
import io
import os
import re
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

import ttkbootstrap as tb
from PIL import Image, ImageTk
from ttkbootstrap.widgets.floodgauge import Floodgauge

from functions import ui_theme
from functions.media_studio import VIDEO_EXTS, get_ffmpeg_path, probe_media
from functions.utils import center_window, safe_print


def _creation_flags():
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def format_timestamp(seconds):
    """Formatea segundos a HH:MM:SS.cc."""
    try:
        val = max(0.0, float(seconds))
    except (TypeError, ValueError):
        val = 0.0
    total_cs = int(round(val * 100))
    cs = total_cs % 100
    total_s = total_cs // 100
    s = total_s % 60
    total_m = total_s // 60
    m = total_m % 60
    h = total_m // 60
    return f"{h:02d}:{m:02d}:{s:02d}.{cs:02d}"


def parse_timestamp(text):
    """Parsea segundos, MM:SS o HH:MM:SS(.cc) a float en segundos."""
    raw = str(text or "").strip()
    if not raw:
        return None
    parts = raw.split(":")
    try:
        if len(parts) == 1:
            val = float(parts[0])
        elif len(parts) == 2:
            val = int(parts[0]) * 60 + float(parts[1])
        elif len(parts) == 3:
            val = int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        else:
            return None
        return max(0.0, val)
    except ValueError:
        return None


def extract_frame_pil(video_path, seconds, max_size=(760, 428)):
    """Extrae un fotograma exacto en memoria usando FFmpeg sin archivos temporales."""
    t = max(0.0, float(seconds))
    cmd = [
        get_ffmpeg_path(),
        "-nostdin",
        "-ss", f"{t:.3f}",
        "-i", str(video_path),
        "-frames:v", "1",
        "-f", "image2pipe",
        "-vcodec", "png",
        "-",
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            creationflags=_creation_flags(),
            timeout=10,
        )
        if proc.returncode != 0 or not proc.stdout:
            return None
        img = Image.open(io.BytesIO(proc.stdout))
        img.load()
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        return img
    except Exception:
        return None


def extract_filmstrip_pil(video_path, duration_s, count=10, thumb_w=92, thumb_h=52):
    """Genera una tira horizontal de miniaturas del video en una sola llamada de FFmpeg."""
    dur = max(0.1, float(duration_s or 0.1))
    fps_val = max(0.01, count / dur)
    vf = f"fps={fps_val:.5f},scale={thumb_w}:{thumb_h}:force_original_aspect_ratio=increase,crop={thumb_w}:{thumb_h},tile={count}x1"
    cmd = [
        get_ffmpeg_path(),
        "-nostdin",
        "-i", str(video_path),
        "-vf", vf,
        "-frames:v", "1",
        "-f", "image2pipe",
        "-vcodec", "png",
        "-",
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            creationflags=_creation_flags(),
            timeout=25,
        )
        if proc.returncode != 0 or not proc.stdout:
            return None
        img = Image.open(io.BytesIO(proc.stdout))
        img.load()
        return img
    except Exception:
        return None


def build_trim_export_command(input_path, output_path, start_s, end_s, mode="copy", output_format="mp4"):
    """Construye el comando FFmpeg seguro para exportar el recorte (MP4 sin pérdida, MP4 preciso o GIF)."""
    start_val = max(0.0, float(start_s))
    end_val = max(start_val + 0.05, float(end_s))
    dur_val = end_val - start_val
    ffmpeg = get_ffmpeg_path()

    if output_format.lower() == "gif":
        return [
            ffmpeg, "-y", "-nostdin",
            "-ss", f"{start_val:.3f}",
            "-t", f"{dur_val:.3f}",
            "-i", str(input_path),
            "-vf", "fps=12,scale=480:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
            str(output_path),
        ]

    if mode == "accurate":
        return [
            ffmpeg, "-y", "-nostdin",
            "-ss", f"{start_val:.3f}",
            "-t", f"{dur_val:.3f}",
            "-i", str(input_path),
            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            "-c:v", "libx264", "-crf", "20", "-preset", "fast",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            str(output_path),
        ]

    return [
        ffmpeg, "-y", "-nostdin",
        "-ss", f"{start_val:.3f}",
        "-i", str(input_path),
        "-t", f"{dur_val:.3f}",
        "-c", "copy",
        "-movflags", "+faststart",
        str(output_path),
    ]


class TimelineCanvas(tk.Canvas):
    """Línea de tiempo visual con tira de miniaturas y doble tirador Inicio/Fin + cabezal."""

    PAD_X = 16
    TRACK_TOP = 16
    TRACK_H = 58
    HANDLE_W = 12

    def __init__(self, master, on_change_callback=None, **kwargs):
        super().__init__(master, height=96, highlightthickness=0, cursor="hand2", **kwargs)
        self.on_change_callback = on_change_callback
        self.duration = 0.0
        self.start_s = 0.0
        self.end_s = 0.0
        self.playhead_s = 0.0
        self._filmstrip_pil = None
        self._filmstrip_tk = None
        self._drag_target = None

        self.bind("<Configure>", lambda _e: self.redraw())
        self.bind("<Button-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)

    def set_duration(self, duration_s):
        self.duration = max(0.0, float(duration_s or 0.0))
        self.start_s = 0.0
        self.end_s = self.duration
        self.playhead_s = 0.0
        self._filmstrip_pil = None
        self._filmstrip_tk = None
        self.redraw()

    def set_filmstrip(self, pil_img):
        self._filmstrip_pil = pil_img
        self.redraw()

    def set_range(self, start_s=None, end_s=None, playhead_s=None, notify=False):
        if self.duration <= 0:
            return
        min_gap = min(0.1, self.duration * 0.05)
        if start_s is not None:
            self.start_s = max(0.0, min(float(start_s), self.end_s - min_gap))
        if end_s is not None:
            self.end_s = min(self.duration, max(float(end_s), self.start_s + min_gap))
        if playhead_s is not None:
            self.playhead_s = max(0.0, min(float(playhead_s), self.duration))
        self.redraw()
        if notify and callable(self.on_change_callback):
            self.on_change_callback(self.start_s, self.end_s, self.playhead_s)

    def _track_bounds(self):
        w = max(200, self.winfo_width())
        return self.PAD_X, w - self.PAD_X

    def _time_to_x(self, t):
        x0, x1 = self._track_bounds()
        if self.duration <= 0:
            return x0
        frac = max(0.0, min(1.0, float(t) / self.duration))
        return x0 + frac * (x1 - x0)

    def _x_to_time(self, x):
        x0, x1 = self._track_bounds()
        if self.duration <= 0 or x1 <= x0:
            return 0.0
        frac = max(0.0, min(1.0, (x - x0) / (x1 - x0)))
        return frac * self.duration

    def _on_press(self, event):
        if self.duration <= 0:
            return
        xs = self._time_to_x(self.start_s)
        xe = self._time_to_x(self.end_s)
        if abs(event.x - xs) <= self.HANDLE_W + 4:
            self._drag_target = "start"
        elif abs(event.x - xe) <= self.HANDLE_W + 4:
            self._drag_target = "end"
        else:
            self._drag_target = "playhead"
        self._apply_drag_x(event.x)

    def _on_drag(self, event):
        if self._drag_target:
            self._apply_drag_x(event.x)

    def _on_release(self, _event):
        self._drag_target = None

    def _apply_drag_x(self, x):
        t = self._x_to_time(x)
        if self._drag_target == "start":
            self.set_range(start_s=t, playhead_s=t, notify=True)
        elif self._drag_target == "end":
            self.set_range(end_s=t, playhead_s=t, notify=True)
        else:
            self.set_range(playhead_s=t, notify=True)

    def redraw(self):
        self.delete("all")
        w = max(200, self.winfo_width())
        x0, x1 = self._track_bounds()
        y0 = self.TRACK_TOP
        y1 = y0 + self.TRACK_H
        track_w = max(10, int(x1 - x0))

        # Fondo base de la pista
        self.create_rectangle(x0, y0, x1, y1, fill="#1F1B2B", outline="#4B3F6B", width=1)

        if self._filmstrip_pil is not None and track_w > 20:
            try:
                resized = self._filmstrip_pil.resize((track_w, self.TRACK_H), Image.Resampling.BILINEAR)
                self._filmstrip_tk = ImageTk.PhotoImage(resized)
                self.create_image(x0, y0, anchor="nw", image=self._filmstrip_tk)
            except Exception:
                pass

        if self.duration <= 0:
            self.create_text(
                (x0 + x1) / 2, (y0 + y1) / 2,
                text="Carga un video para visualizar la línea de tiempo",
                fill="#A1A1AA", font=("Segoe UI", 9),
            )
            return

        xs = self._time_to_x(self.start_s)
        xe = self._time_to_x(self.end_s)
        xp = self._time_to_x(self.playhead_s)

        # Sombrear zonas excluidas (antes de Inicio y después de Fin)
        if xs > x0:
            self.create_rectangle(x0, y0, xs, y1, fill="#0D0B14", stipple="gray50", outline="")
        if xe < x1:
            self.create_rectangle(xe, y0, x1, y1, fill="#0D0B14", stipple="gray50", outline="")

        # Marco resaltado del tramo activo
        self.create_rectangle(xs, y0, xe, y1, outline="#8B5CF6", width=3)

        # Tirador Inicio (izquierda)
        hw = self.HANDLE_W // 2
        self.create_rectangle(xs - hw, y0 - 4, xs + hw, y1 + 4, fill="#7C3AED", outline="#EDE9FE", width=1)
        self.create_text(xs, y0 - 10, text="IN", fill="#C4B5FD", font=("Segoe UI", 7, "bold"))

        # Tirador Fin (derecha)
        self.create_rectangle(xe - hw, y0 - 4, xe + hw, y1 + 4, fill="#7C3AED", outline="#EDE9FE", width=1)
        self.create_text(xe, y0 - 10, text="OUT", fill="#C4B5FD", font=("Segoe UI", 7, "bold"))

        # Cabezal (Playhead)
        self.create_line(xp, y0 - 6, xp, y1 + 6, fill="#F59E0B", width=2)
        self.create_polygon(xp - 5, y0 - 6, xp + 5, y0 - 6, xp, y0 + 1, fill="#F59E0B", outline="")

        # Etiquetas de tiempo inferior
        self.create_text(x0, y1 + 14, text="00:00:00", anchor="w", fill="#9CA3AF", font=("Consolas", 8))
        self.create_text((x0 + x1) / 2, y1 + 14, text=f"Cabezal: {format_timestamp(self.playhead_s)}", anchor="center", fill="#FDE68A", font=("Consolas", 8, "bold"))
        self.create_text(x1, y1 + 14, text=format_timestamp(self.duration), anchor="e", fill="#9CA3AF", font=("Consolas", 8))


class VideoTrimmerApp:
    """Interfaz visual moderna para recortar videos con vista previa en vivo y línea de tiempo."""

    def __init__(self, master=None, video_path="", video_queue=None):
        self._owns_root = master is None
        if master is None:
            theme = ui_theme.get_saved_theme()
            self.win = tb.Window(themename=theme)
        else:
            self.win = tb.Toplevel(master)
            self.win.transient(master)

        self.win.title("Recortador Visual de Video - GUI CMD Advance")
        center_window(self.win, 920, 740)
        self.win.minsize(820, 660)
        ui_theme.apply_window_chrome(self.win)

        self.video_path = ""
        self.video_queue = [p for p in (video_queue or []) if p and os.path.isfile(p)]
        if video_path and os.path.isfile(video_path) and video_path not in self.video_queue:
            self.video_queue.insert(0, video_path)
        self.media_info = None
        self._preview_tk = None
        self._debounce_job = None
        self._frame_req_id = 0
        self._is_exporting = False
        self._last_output_path = ""

        self._build_ui()
        self._bind_shortcuts()
        self.win.protocol("WM_DELETE_WINDOW", self._on_close)
        ui_theme.bring_to_front(self.win)

        initial = video_path or (self.video_queue[0] if self.video_queue else "")
        if initial and os.path.isfile(initial):
            self.load_video(initial)

    def _build_ui(self):
        root = tb.Frame(self.win, padding=14)
        root.pack(fill="both", expand=True)
        root.grid_rowconfigure(1, weight=1)
        root.grid_columnconfigure(0, weight=1)

        # ---- 1) Barra superior: Selección de Video + Metadatos ----
        top_bar = tb.Frame(root)
        top_bar.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        tb.Button(top_bar, text="Abrir Video...", bootstyle="primary", command=self._browse_video).pack(side="left", padx=(0, 8))

        if len(self.video_queue) > 1:
            tb.Label(top_bar, text="Cola:").pack(side="left", padx=(0, 4))
            self.queue_var = tk.StringVar(value=os.path.basename(self.video_queue[0]))
            self._queue_map = {os.path.basename(p): p for p in self.video_queue}
            q_combo = tb.Combobox(
                top_bar, values=list(self._queue_map.keys()), textvariable=self.queue_var, state="readonly", width=26
            )
            q_combo.pack(side="left", padx=(0, 8))
            q_combo.bind("<<ComboboxSelected>>", lambda _e: self.load_video(self._queue_map[self.queue_var.get()]))

        self.lbl_video_info = tb.Label(
            top_bar, text="Ningún video cargado. Haz clic en 'Abrir Video...' para comenzar.",
            font=("Segoe UI", 9), bootstyle="secondary",
        )
        self.lbl_video_info.pack(side="left", fill="x", expand=True)

        # ---- 2) Monitor de Vista Previa ----
        preview_card = ui_theme.RoundedCard(root, title="Vista Previa en Vivo", padding=(8, 6))
        preview_card.grid(row=1, column=0, sticky="nsew", pady=(0, 8))
        preview_card.body.grid_rowconfigure(0, weight=1)
        preview_card.body.grid_columnconfigure(0, weight=1)

        self.preview_canvas = tk.Canvas(preview_card.body, bg="#0F0D16", highlightthickness=0, height=310)
        self.preview_canvas.grid(row=0, column=0, sticky="nsew")
        self.preview_canvas.bind("<Configure>", lambda _e: self._draw_placeholder_if_empty())

        # Barra de navegación precisa debajo del monitor
        nav_bar = tb.Frame(preview_card.body, style="PulseCardInner.TFrame")
        nav_bar.grid(row=1, column=0, sticky="ew", pady=(8, 0))

        nav_buttons = [
            ("-5s", lambda: self._nudge_playhead(-5.0), "secondary"),
            ("-1s", lambda: self._nudge_playhead(-1.0), "secondary"),
            ("-0.1s", lambda: self._nudge_playhead(-0.1), "secondary"),
            ("Marcar Inicio [I]", self._mark_in, "info"),
            ("Marcar Fin [O]", self._mark_out, "info"),
            ("+0.1s", lambda: self._nudge_playhead(0.1), "secondary"),
            ("+1s", lambda: self._nudge_playhead(1.0), "secondary"),
            ("+5s", lambda: self._nudge_playhead(5.0), "secondary"),
        ]
        nav_inner = tb.Frame(nav_bar, style="PulseCardInner.TFrame")
        nav_inner.pack(anchor="center")
        for txt, cmd_fn, style_name in nav_buttons:
            tb.Button(nav_inner, text=txt, bootstyle=style_name, command=cmd_fn).pack(side="left", padx=3)

        # ---- 3) Línea de Tiempo Interactiva ----
        tl_card = ui_theme.RoundedCard(root, title="Línea de Tiempo (Arrastra IN / OUT o haz clic)", padding=(8, 6))
        tl_card.grid(row=2, column=0, sticky="ew", pady=(0, 8))

        self.timeline = TimelineCanvas(tl_card.body, bg="#17141F", on_change_callback=self._on_timeline_change)
        self.timeline.pack(fill="x", expand=True)

        times_row = tb.Frame(tl_card.body, style="PulseCardInner.TFrame")
        times_row.pack(fill="x", pady=(6, 0))

        self.start_var = tk.StringVar(value="00:00:00.00")
        self.end_var = tk.StringVar(value="00:00:00.00")
        self.dur_var = tk.StringVar(value="Duración del recorte: 00:00:00.00")

        tb.Label(times_row, text="Inicio:", font=("Segoe UI", 9, "bold"), style="PulseCard.TLabel").pack(side="left", padx=(0, 4))
        ent_s = tb.Entry(times_row, textvariable=self.start_var, width=13)
        ent_s.pack(side="left", padx=(0, 10))
        ent_s.bind("<Return>", lambda _e: self._apply_manual_times())
        ent_s.bind("<FocusOut>", lambda _e: self._apply_manual_times())

        tb.Label(times_row, text="Fin:", font=("Segoe UI", 9, "bold"), style="PulseCard.TLabel").pack(side="left", padx=(0, 4))
        ent_e = tb.Entry(times_row, textvariable=self.end_var, width=13)
        ent_e.pack(side="left", padx=(0, 14))
        ent_e.bind("<Return>", lambda _e: self._apply_manual_times())
        ent_e.bind("<FocusOut>", lambda _e: self._apply_manual_times())

        tb.Label(times_row, textvariable=self.dur_var, font=("Consolas", 9, "bold"), bootstyle="info", style="PulseCard.TLabel").pack(side="right")

        # ---- 4) Opciones de Exportación y Progreso ----
        exp_card = ui_theme.RoundedCard(root, title="Exportación del Recorte", padding=(8, 6))
        exp_card.grid(row=3, column=0, sticky="ew")

        opts_row = tb.Frame(exp_card.body, style="PulseCardInner.TFrame")
        opts_row.pack(fill="x", pady=(0, 6))

        self.mode_var = tk.StringVar(value="copy")
        tb.Label(opts_row, text="Modo:", font=("Segoe UI", 9, "bold"), style="PulseCard.TLabel").pack(side="left", padx=(0, 6))
        tb.Radiobutton(opts_row, text="Rápido sin pérdida (-c copy)", variable=self.mode_var, value="copy", bootstyle="primary").pack(side="left", padx=(0, 12))
        tb.Radiobutton(opts_row, text="Preciso al fotograma (H.264)", variable=self.mode_var, value="accurate", bootstyle="primary").pack(side="left", padx=(0, 18))

        self.fmt_var = tk.StringVar(value="mp4")
        tb.Label(opts_row, text="Formato:", font=("Segoe UI", 9, "bold"), style="PulseCard.TLabel").pack(side="left", padx=(0, 6))
        tb.Radiobutton(opts_row, text="Video MP4", variable=self.fmt_var, value="mp4", bootstyle="info").pack(side="left", padx=(0, 10))
        tb.Radiobutton(opts_row, text="GIF Animado", variable=self.fmt_var, value="gif", bootstyle="info").pack(side="left")

        action_row = tb.Frame(exp_card.body, style="PulseCardInner.TFrame")
        action_row.pack(fill="x")

        self.progress = Floodgauge(action_row, maximum=100, value=0, mask="{}%", bootstyle="info")
        self.progress.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.btn_open_dir = tb.Button(action_row, text="Abrir Carpeta", bootstyle="secondary", command=self._open_output_dir, state="disabled")
        self.btn_open_dir.pack(side="right", padx=(6, 0))

        self.btn_export = tb.Button(action_row, text="Exportar Recorte", bootstyle="success", command=self._start_export, state="disabled")
        self.btn_export.pack(side="right")

        self.status_var = tk.StringVar(value="Listo.")
        tb.Label(exp_card.body, textvariable=self.status_var, font=("Segoe UI", 8), bootstyle="secondary", style="PulseCard.TLabel").pack(anchor="w", pady=(4, 0))

    def _bind_shortcuts(self):
        self.win.bind("<Left>", lambda _e: self._nudge_playhead(-1.0))
        self.win.bind("<Right>", lambda _e: self._nudge_playhead(1.0))
        self.win.bind("<Shift-Left>", lambda _e: self._nudge_playhead(-0.1))
        self.win.bind("<Shift-Right>", lambda _e: self._nudge_playhead(0.1))
        self.win.bind("i", lambda _e: self._mark_in())
        self.win.bind("I", lambda _e: self._mark_in())
        self.win.bind("o", lambda _e: self._mark_out())
        self.win.bind("O", lambda _e: self._mark_out())

    def _draw_placeholder_if_empty(self):
        if self._preview_tk is None and self.preview_canvas.winfo_exists():
            self.preview_canvas.delete("all")
            w = max(100, self.preview_canvas.winfo_width())
            h = max(100, self.preview_canvas.winfo_height())
            self.preview_canvas.create_text(
                w / 2, h / 2,
                text="Vista previa del fotograma actual",
                fill="#71717A", font=("Segoe UI", 11),
            )

    def _browse_video(self):
        exts = " ".join(f"*{e}" for e in sorted(VIDEO_EXTS))
        chosen = filedialog.askopenfilename(
            parent=self.win,
            title="Seleccionar Video para Recortar",
            filetypes=[("Archivos de Video", exts), ("Todos los archivos", "*.*")],
        )
        if chosen:
            self.load_video(chosen)

    def load_video(self, path):
        info = probe_media(path)
        if not info or not info.get("has_video") or info.get("duration_s", 0) <= 0:
            messagebox.showerror(
                "Video no compatible",
                f"No se pudo leer la pista de video o duración con ffprobe:\n{path}",
                parent=self.win,
            )
            return

        self.video_path = os.path.abspath(path)
        self.media_info = info
        self.lbl_video_info.configure(
            text=(
                f"{info['name']}  |  {info['width']}x{info['height']} @ {info['fps']} fps  |  "
                f"{format_timestamp(info['duration_s'])}  |  {info['size_mb']:.2f} MB"
            )
        )
        self.timeline.set_duration(info["duration_s"])
        self._sync_time_labels(0.0, info["duration_s"])
        self.btn_export.configure(state="normal")
        self.status_var.set("Generando tira de miniaturas y cargando vista previa...")

        self._request_preview_frame(0.0)
        self._request_filmstrip(self.video_path, info["duration_s"])

    def _request_filmstrip(self, video_path, duration_s):
        def worker():
            strip = extract_filmstrip_pil(video_path, duration_s, count=10)
            try:
                if self.win.winfo_exists() and self.video_path == video_path:
                    self.win.after(0, lambda: self._on_filmstrip_ready(strip))
            except Exception:
                pass
        threading.Thread(target=worker, daemon=True).start()

    def _on_filmstrip_ready(self, strip):
        if not self.win.winfo_exists():
            return
        if strip is not None:
            self.timeline.set_filmstrip(strip)
        self.status_var.set("Listo. Arrastra los tiradores IN / OUT o usa las teclas I y O para marcar el recorte.")

    def _on_timeline_change(self, start_s, end_s, playhead_s):
        self._sync_time_labels(start_s, end_s)
        if self._debounce_job is not None:
            try:
                self.win.after_cancel(self._debounce_job)
            except Exception:
                pass
        self._debounce_job = self.win.after(85, lambda t=playhead_s: self._request_preview_frame(t))

    def _sync_time_labels(self, start_s, end_s):
        self.start_var.set(format_timestamp(start_s))
        self.end_var.set(format_timestamp(end_s))
        self.dur_var.set(f"Duración del recorte: {format_timestamp(max(0.0, end_s - start_s))}")

    def _apply_manual_times(self):
        if not self.media_info:
            return
        s = parse_timestamp(self.start_var.get())
        e = parse_timestamp(self.end_var.get())
        if s is not None and e is not None and e > s:
            self.timeline.set_range(start_s=s, end_s=e, playhead_s=s, notify=True)
        else:
            self._sync_time_labels(self.timeline.start_s, self.timeline.end_s)

    def _nudge_playhead(self, delta_s):
        if not self.media_info:
            return
        target = max(0.0, min(self.timeline.duration, self.timeline.playhead_s + delta_s))
        self.timeline.set_range(playhead_s=target, notify=True)

    def _mark_in(self):
        if not self.media_info:
            return
        self.timeline.set_range(start_s=self.timeline.playhead_s, notify=True)

    def _mark_out(self):
        if not self.media_info:
            return
        self.timeline.set_range(end_s=self.timeline.playhead_s, notify=True)

    def _request_preview_frame(self, seconds):
        if not self.video_path:
            return
        self._frame_req_id += 1
        req_id = self._frame_req_id
        vpath = self.video_path
        cw = max(320, self.preview_canvas.winfo_width() - 8)
        ch = max(180, self.preview_canvas.winfo_height() - 8)

        def worker():
            img = extract_frame_pil(vpath, seconds, max_size=(cw, ch))
            try:
                if self.win.winfo_exists() and req_id == self._frame_req_id:
                    self.win.after(0, lambda: self._render_preview_image(img))
            except Exception:
                pass
        threading.Thread(target=worker, daemon=True).start()

    def _render_preview_image(self, pil_img):
        if not self.win.winfo_exists() or pil_img is None:
            return
        self.preview_canvas.delete("all")
        self._preview_tk = ImageTk.PhotoImage(pil_img)
        cw = max(100, self.preview_canvas.winfo_width())
        ch = max(100, self.preview_canvas.winfo_height())
        self.preview_canvas.create_image(cw / 2, ch / 2, anchor="center", image=self._preview_tk)

    def _start_export(self):
        if self._is_exporting or not self.video_path or not self.media_info:
            return
        start_s = self.timeline.start_s
        end_s = self.timeline.end_s
        if end_s - start_s < 0.05:
            messagebox.showwarning("Rango inválido", "La duración del recorte debe ser mayor a 0.05 segundos.", parent=self.win)
            return

        fmt = self.fmt_var.get()
        mode = self.mode_var.get()
        src = Path(self.video_path)
        ext = ".gif" if fmt == "gif" else ".mp4"
        default_name = f"{src.stem}_recortado{ext}"
        out_path = filedialog.asksaveasfilename(
            parent=self.win,
            title="Guardar Recorte",
            initialdir=str(src.parent),
            initialfile=default_name,
            defaultextension=ext,
            filetypes=[("GIF Animado", "*.gif")] if fmt == "gif" else [("Video MP4", "*.mp4")],
        )
        if not out_path:
            return
        if os.path.abspath(out_path).lower() == os.path.abspath(self.video_path).lower():
            messagebox.showerror("Archivo protegido", "No puedes sobrescribir el video original. Elige otro nombre.", parent=self.win)
            return

        self._is_exporting = True
        self.btn_export.configure(state="disabled", text="Exportando...")
        self.btn_open_dir.configure(state="disabled")
        self.progress.configure(value=10, bootstyle="info")
        self.status_var.set(f"Exportando tramo {format_timestamp(start_s)} -> {format_timestamp(end_s)}...")

        cmd = build_trim_export_command(self.video_path, out_path, start_s, end_s, mode=mode, output_format=fmt)
        expected_dur = max(0.1, end_s - start_s)

        def worker():
            time_re = re.compile(r"time=(\d{2}):(\d{2}):(\d{2}\.\d{2})")
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=_creation_flags(),
                )
                err_lines = []
                for line in proc.stdout:
                    m = time_re.search(line)
                    if m:
                        cur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
                        pct = min(98, max(10, int((cur / expected_dur) * 100)))
                        try:
                            self.win.after(0, lambda p=pct: self.progress.configure(value=p))
                        except Exception:
                            pass
                    elif line.strip():
                        err_lines.append(line.strip())
                rc = proc.wait()
                ok = rc == 0 and os.path.isfile(out_path) and os.path.getsize(out_path) > 0
                err_msg = " | ".join(err_lines[-3:]) if not ok else ""
            except Exception as e:
                ok = False
                err_msg = str(e)

            try:
                if self.win.winfo_exists():
                    self.win.after(0, lambda: self._on_export_done(ok, out_path, err_msg))
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def _on_export_done(self, ok, out_path, err_msg):
        self._is_exporting = False
        if not self.win.winfo_exists():
            return
        self.btn_export.configure(state="normal", text="Exportar Recorte")
        if ok:
            self._last_output_path = out_path
            self.progress.configure(value=100, bootstyle="success")
            size_mb = os.path.getsize(out_path) / (1024 ** 2)
            self.status_var.set(f"Recorte guardado exitosamente: {out_path} ({size_mb:.2f} MB)")
            self.btn_open_dir.configure(state="normal")
            messagebox.showinfo("Recorte Completado", f"Archivo guardado en:\n{out_path}\n({size_mb:.2f} MB)", parent=self.win)
        else:
            self.progress.configure(value=0, bootstyle="danger")
            self.status_var.set(f"Error al exportar: {err_msg}")
            messagebox.showerror("Error en Exportación", f"FFmpeg no pudo completar el recorte:\n{err_msg}", parent=self.win)

    def _open_output_dir(self):
        if self._last_output_path and os.path.exists(self._last_output_path):
            try:
                subprocess.Popen(
                    ["explorer", "/select,", os.path.abspath(self._last_output_path)],
                    creationflags=_creation_flags(),
                )
            except Exception:
                pass

    def _on_close(self):
        if self._debounce_job is not None:
            try:
                self.win.after_cancel(self._debounce_job)
            except Exception:
                pass
        self.win.destroy()

    def mainloop(self):
        self.win.mainloop()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Recortador Visual de Video con Línea de Tiempo.")
    parser.add_argument("--input", default="", help="Ruta del video inicial a cargar (opcional).")
    args, _ = parser.parse_known_args(argv)
    if args.input and not os.path.isfile(args.input):
        safe_print(f"[AVISO] No se encontró el archivo inicial: {args.input}")
    app = VideoTrimmerApp(video_path=args.input)
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
