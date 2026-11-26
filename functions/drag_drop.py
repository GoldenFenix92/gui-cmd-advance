import ctypes
import json
import mimetypes
import os
import queue
import sys
from ctypes import wintypes
from pathlib import Path

from functions.utils import get_user_data_path

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".3gp", ".mpeg", ".mpg", ".ts"}

DEFAULT_DROPPED_BATCH_FILE = "dropped_files_batch.json"

EXTENSION_TYPE_LABELS = {
    ".jpg": "Imagen JPEG",
    ".jpeg": "Imagen JPEG",
    ".png": "Imagen PNG",
    ".webp": "Imagen WebP",
    ".bmp": "Imagen BMP",
    ".tif": "Imagen TIFF",
    ".tiff": "Imagen TIFF",
    ".gif": "Imagen animada GIF",
    ".svg": "Gráfico vectorial SVG",
    ".heic": "Imagen HEIC",
    ".ico": "Icono de Windows",
    ".mp4": "Video MP4",
    ".mkv": "Video Matroska (MKV)",
    ".avi": "Video AVI",
    ".mov": "Video QuickTime (MOV)",
    ".wmv": "Video Windows Media (WMV)",
    ".flv": "Video Flash (FLV)",
    ".webm": "Video WebM",
    ".m4v": "Video M4V",
    ".3gp": "Video 3GP",
    ".mpeg": "Video MPEG",
    ".mpg": "Video MPEG",
    ".ts": "Video Transport Stream (TS)",
    ".mp3": "Audio MP3",
    ".wav": "Audio WAV",
    ".flac": "Audio FLAC",
    ".aac": "Audio AAC",
    ".ogg": "Audio OGG",
    ".m4a": "Audio M4A",
    ".pdf": "Documento PDF",
    ".txt": "Archivo de Texto",
    ".md": "Documento Markdown",
    ".doc": "Documento Word",
    ".docx": "Documento Word",
    ".xls": "Hoja de Cálculo Excel",
    ".xlsx": "Hoja de Cálculo Excel",
    ".csv": "Archivo CSV",
    ".ppt": "Presentación PowerPoint",
    ".pptx": "Presentación PowerPoint",
    ".zip": "Archivo Comprimido ZIP",
    ".rar": "Archivo Comprimido RAR",
    ".7z": "Archivo Comprimido 7-Zip",
    ".tar": "Archivo Empaquetado TAR",
    ".gz": "Archivo Comprimido GZ",
    ".exe": "Ejecutable de Windows",
    ".msi": "Instalador de Windows",
    ".bat": "Script por Lotes (BAT)",
    ".ps1": "Script de PowerShell",
    ".py": "Script de Python",
    ".json": "Archivo JSON",
    ".xml": "Archivo XML",
    ".html": "Documento HTML",
    ".iso": "Imagen de Disco ISO",
}

UNSUPPORTED_SERVICE_MESSAGE = (
    "Este tipo de archivo no es compatible con ningún servicio disponible "
    "por el momento desde GUI CMD ADVANCE."
)


def format_file_size(num_bytes):
    """Formatea bytes a una cadena legible (B, KB, MB, GB)."""
    try:
        size = float(num_bytes)
    except (TypeError, ValueError):
        return "0 B"
    if size < 0:
        size = 0.0
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024.0 or unit == "TB":
            if unit == "B":
                return f"{int(size)} B"
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} TB"


def _describe_file_type(path_obj, is_dir, ext):
    if is_dir:
        return "Carpeta de archivos"
    if ext in EXTENSION_TYPE_LABELS:
        return f"{EXTENSION_TYPE_LABELS[ext]} ({ext})"
    mime, _ = mimetypes.guess_type(str(path_obj))
    if mime:
        main_type = mime.split("/")[0].lower()
        sub_type = mime.split("/")[-1].upper()
        if main_type == "image":
            return f"Imagen {sub_type} ({ext})" if ext else f"Imagen {sub_type}"
        if main_type == "video":
            return f"Video {sub_type} ({ext})" if ext else f"Video {sub_type}"
        if main_type == "audio":
            return f"Audio {sub_type} ({ext})" if ext else f"Audio {sub_type}"
        if main_type == "text":
            return f"Texto {sub_type} ({ext})" if ext else f"Texto {sub_type}"
    if ext:
        return f"Archivo {ext.lstrip('.').upper()} ({ext})"
    return "Archivo sin extensión"


def inspect_dropped_path(path):
    """Inspecciona una ruta arrastrada y determina su tipo y compatibilidad Multimedia."""
    raw = str(path or "").strip().strip('"')
    p = Path(raw)
    is_dir = p.is_dir()
    ext = "" if is_dir else p.suffix.lower()
    size_bytes = 0
    if not is_dir and p.is_file():
        try:
            size_bytes = p.stat().st_size
        except OSError:
            size_bytes = 0

    if not is_dir and ext in VIDEO_EXTS:
        media_kind = "video"
    elif not is_dir and ext in IMAGE_EXTS:
        media_kind = "image"
    else:
        media_kind = "unsupported"

    return {
        "name": p.name or raw,
        "path": os.path.normpath(raw),
        "is_dir": is_dir,
        "extension": ext,
        "size_bytes": size_bytes,
        "size_human": "Carpeta" if is_dir else format_file_size(size_bytes),
        "file_type_label": _describe_file_type(p, is_dir, ext),
        "media_kind": media_kind,
        "is_compatible": media_kind in ("video", "image"),
    }


def inspect_dropped_batch(paths):
    """Analiza uno o varios elementos arrastrados y clasifica compatibles vs. no compatibles."""
    seen = set()
    items = []
    for raw in paths or []:
        cleaned = str(raw or "").strip().strip('"')
        if not cleaned:
            continue
        norm = os.path.normcase(os.path.normpath(cleaned))
        if norm in seen:
            continue
        seen.add(norm)
        items.append(inspect_dropped_path(cleaned))

    compatible_items = [it for it in items if it["is_compatible"]]
    unsupported_items = [it for it in items if not it["is_compatible"]]
    video_count = sum(1 for it in compatible_items if it["media_kind"] == "video")
    image_count = sum(1 for it in compatible_items if it["media_kind"] == "image")

    if video_count > 0 and image_count > 0:
        detected_media_type = "all"
    elif video_count > 0:
        detected_media_type = "videos"
    elif image_count > 0:
        detected_media_type = "images"
    else:
        detected_media_type = None

    return {
        "items": items,
        "compatible_items": compatible_items,
        "unsupported_items": unsupported_items,
        "total_count": len(items),
        "compatible_count": len(compatible_items),
        "unsupported_count": len(unsupported_items),
        "video_count": video_count,
        "image_count": image_count,
        "detected_media_type": detected_media_type,
    }


def get_compatible_services(batch_info):
    """Devuelve los servicios Multimedia compatibles para el lote arrastrado (solo imágenes/videos)."""
    if not batch_info or batch_info.get("compatible_count", 0) <= 0:
        return []

    media_type = batch_info.get("detected_media_type")
    if media_type == "videos":
        repair_type_label = "Solo Videos"
    elif media_type == "images":
        repair_type_label = "Solo Imágenes"
    else:
        repair_type_label = "Videos e Imágenes (Todos)"

    return [
        {
            "command_name": "Compresor de Multimedia",
            "category": "Multimedia",
            "description": "Reduce el peso de las imágenes y/o videos seleccionados con aceleración por hardware.",
            "single_arg": "Seleccionar Archivo (Individual)",
            "presets": {},
        },
        {
            "command_name": "Reparador de Multimedia",
            "category": "Multimedia",
            "description": "Repara imágenes y/o videos dañados o corruptos conservando los archivos originales.",
            "single_arg": "Archivos / Carpeta Origen",
            "presets": {"Tipo de Archivos a Reparar": repair_type_label},
        },
    ]


def save_dropped_batch_file(paths, target_path=None):
    """Guarda la lista de archivos multimedia en un JSON temporal mediante escritura atómica."""
    out_path = target_path or get_user_data_path(DEFAULT_DROPPED_BATCH_FILE)
    parent = os.path.dirname(out_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    payload = {
        "count": len(paths),
        "files": [os.path.abspath(str(p)) for p in paths],
    }
    tmp_path = f"{out_path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, out_path)
    return out_path


def load_input_list_file(list_path):
    """Carga una lista de rutas desde un archivo JSON ({'files': [...]}) o texto plano."""
    if not list_path or not os.path.exists(list_path):
        return []
    with open(list_path, "r", encoding="utf-8") as f:
        raw = f.read().strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            files = data.get("files", [])
        elif isinstance(data, list):
            files = data
        else:
            files = []
        return [str(p).strip() for p in files if p and str(p).strip()]
    except json.JSONDecodeError:
        return [line.strip().strip('"') for line in raw.splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# Motor Nativo Win32 Drag & Drop (SetWindowSubclass + WM_DROPFILES + UIPI)
# ---------------------------------------------------------------------------
WM_DROPFILES = 0x0233
WM_NCDESTROY = 0x0082
WM_COPYDATA = 0x004A
WM_COPYGLOBALDATA = 0x0049
MSGFLT_ALLOW = 1

_LRESULT = ctypes.c_ssize_t
_UINT_PTR = ctypes.c_size_t
_DWORD_PTR = ctypes.c_size_t
_SUBCLASSPROC = ctypes.WINFUNCTYPE(
    _LRESULT,
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
    _UINT_PTR,
    _DWORD_PTR,
)


class WindowsFileDropHandler:
    """Habilita Drag & Drop nativo de Windows en cualquier ventana Tk sin librerías externas.

    Usa comctl32.SetWindowSubclass y una cola Python (queue.Queue) drenada desde el
    bucle principal de Tk (.after) para no invocar nunca a Tcl/Tk dentro de un WndProc C.
    """

    _SUBCLASS_ID = 0x47434401

    def __init__(self, widget, on_drop_callback, poll_interval_ms=80):
        self.widget = widget
        self.on_drop_callback = on_drop_callback
        self.poll_interval_ms = poll_interval_ms
        self._hwnd = None
        self._subclass_proc_ref = None
        self._attached = False
        self._pending_drops = queue.Queue()
        self._poll_after_id = None
        self._user32 = None
        self._shell32 = None
        self._comctl32 = None

    def attach(self):
        """Registra la ventana para aceptar archivos soltados (incluyendo sesiones como Administrador)."""
        if self._attached or sys.platform != "win32":
            return False
        try:
            self.widget.update_idletasks()
            inner_hwnd = int(self.widget.winfo_id())
            if not inner_hwnd:
                return False

            # Instancias privadas WinDLL para no mutar argtypes globales de ctypes.windll
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            shell32 = ctypes.WinDLL("shell32", use_last_error=True)
            comctl32 = ctypes.WinDLL("comctl32", use_last_error=True)
            self._user32 = user32
            self._shell32 = shell32
            self._comctl32 = comctl32

            user32.GetParent.argtypes = [wintypes.HWND]
            user32.GetParent.restype = wintypes.HWND
            top_hwnd = int(user32.GetParent(inner_hwnd) or 0)
            target_hwnd = top_hwnd if top_hwnd else inner_hwnd
            if not target_hwnd:
                return False

            # Permitir mensajes de arrastre desde Explorador no elevado hacia ventana elevada (UIPI)
            if hasattr(user32, "ChangeWindowMessageFilterEx"):
                user32.ChangeWindowMessageFilterEx.argtypes = [
                    wintypes.HWND,
                    wintypes.UINT,
                    wintypes.DWORD,
                    ctypes.c_void_p,
                ]
                user32.ChangeWindowMessageFilterEx.restype = wintypes.BOOL
                for msg in (WM_DROPFILES, WM_COPYDATA, WM_COPYGLOBALDATA):
                    user32.ChangeWindowMessageFilterEx(target_hwnd, msg, MSGFLT_ALLOW, None)
                    if inner_hwnd != target_hwnd:
                        user32.ChangeWindowMessageFilterEx(inner_hwnd, msg, MSGFLT_ALLOW, None)

            shell32.DragAcceptFiles.argtypes = [wintypes.HWND, wintypes.BOOL]
            shell32.DragAcceptFiles.restype = None
            shell32.DragAcceptFiles(target_hwnd, True)

            shell32.DragQueryFileW.argtypes = [wintypes.HANDLE, wintypes.UINT, ctypes.c_void_p, wintypes.UINT]
            shell32.DragQueryFileW.restype = wintypes.UINT
            shell32.DragFinish.argtypes = [wintypes.HANDLE]
            shell32.DragFinish.restype = None

            comctl32.SetWindowSubclass.argtypes = [wintypes.HWND, _SUBCLASSPROC, _UINT_PTR, _DWORD_PTR]
            comctl32.SetWindowSubclass.restype = wintypes.BOOL
            comctl32.DefSubclassProc.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
            comctl32.DefSubclassProc.restype = _LRESULT
            comctl32.RemoveWindowSubclass.argtypes = [wintypes.HWND, _SUBCLASSPROC, _UINT_PTR]
            comctl32.RemoveWindowSubclass.restype = wintypes.BOOL

            def _subclass_proc(hwnd, msg, wparam, lparam, uid_subclass, ref_data):
                try:
                    if msg == WM_DROPFILES:
                        hdrop = wintypes.HANDLE(wparam)
                        dropped = []
                        try:
                            count = shell32.DragQueryFileW(hdrop, 0xFFFFFFFF, None, 0)
                            for idx in range(count):
                                length = shell32.DragQueryFileW(hdrop, idx, None, 0)
                                if length > 0:
                                    buf = ctypes.create_unicode_buffer(length + 1)
                                    shell32.DragQueryFileW(hdrop, idx, ctypes.addressof(buf), length + 1)
                                    if buf.value:
                                        dropped.append(buf.value)
                        finally:
                            shell32.DragFinish(hdrop)

                        # Encolar en memoria Python pura (NUNCA llamar a Tcl/Tk desde el WndProc)
                        if dropped:
                            self._pending_drops.put(dropped)
                        return 0

                    if msg == WM_NCDESTROY:
                        try:
                            comctl32.RemoveWindowSubclass(hwnd, self._subclass_proc_ref, uid_subclass)
                        except Exception:
                            pass
                        self._attached = False
                        self._hwnd = None
                except Exception:
                    pass
                return comctl32.DefSubclassProc(hwnd, msg, wparam, lparam)

            self._subclass_proc_ref = _SUBCLASSPROC(_subclass_proc)
            ok = bool(comctl32.SetWindowSubclass(target_hwnd, self._subclass_proc_ref, self._SUBCLASS_ID, 0))
            if not ok:
                shell32.DragAcceptFiles(target_hwnd, False)
                self._subclass_proc_ref = None
                return False

            self._hwnd = target_hwnd
            self._attached = True
            self._schedule_poll()
            return True
        except Exception:
            self._attached = False
            return False

    def _schedule_poll(self):
        if not self._attached:
            return
        try:
            self._poll_after_id = self.widget.after(self.poll_interval_ms, self._poll_queue)
        except Exception:
            self._poll_after_id = None

    def _poll_queue(self):
        self._poll_after_id = None
        if not self._attached:
            return
        try:
            if not self.widget.winfo_exists():
                self.detach()
                return
            while True:
                try:
                    paths = self._pending_drops.get_nowait()
                except queue.Empty:
                    break
                if paths and callable(self.on_drop_callback):
                    try:
                        self.on_drop_callback(paths)
                    except Exception:
                        pass
        finally:
            if self._attached:
                self._schedule_poll()

    def detach(self):
        """Remueve el subclass y desactiva DragAcceptFiles limpiamente."""
        if self._poll_after_id is not None:
            try:
                self.widget.after_cancel(self._poll_after_id)
            except Exception:
                pass
            self._poll_after_id = None

        if not self._attached or sys.platform != "win32":
            self._attached = False
            return
        try:
            if self._hwnd and self._comctl32 and self._subclass_proc_ref:
                self._comctl32.RemoveWindowSubclass(self._hwnd, self._subclass_proc_ref, self._SUBCLASS_ID)
            if self._hwnd and self._shell32:
                self._shell32.DragAcceptFiles(self._hwnd, False)
        except Exception:
            pass
        finally:
            self._attached = False
            self._subclass_proc_ref = None
            self._hwnd = None
