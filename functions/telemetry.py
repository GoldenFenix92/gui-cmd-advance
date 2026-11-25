from functions.utils import safe_print
import os
import re
import sys
import json
import urllib.request
import threading
import subprocess
import ctypes
import traceback
import webbrowser
import ttkbootstrap as tb
from ttkbootstrap.widgets.scrolled import ScrolledText
from tkinter import messagebox
from functions.utils import get_user_data_path
from functions import ui_theme
try:
    from version import __version__
except ImportError:
    __version__ = "0.0.0"

# ==============================================================
# CONFIGURACIÓN DEL DESARROLLADOR
# ==============================================================
GITHUB_REPO = "GoldenFenix92/gui-cmd-advance"
# Se lee desde variable de entorno para no exponer secretos en el repositorio.
DISCORD_WEBHOOK_URL = os.environ.get("GUI_CMD_DISCORD_WEBHOOK", "")
# ==============================================================

def check_for_updates(master_win):
    """
    Comprueba de forma asíncrona si hay actualizaciones en GitHub.
    Si hay una versión mayor, muestra un diálogo de actualización.
    """
    def _check():
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                
            latest_tag = data.get("tag_name", "").replace("v", "").replace("-beta", "")
            current = __version__
            
            # Comparación muy básica (solo por si es diferente)
            if latest_tag and latest_tag != current:
                assets = data.get("assets", [])
                exe_url = None
                for asset in assets:
                    if asset["name"].endswith(".exe"):
                        exe_url = asset["browser_download_url"]
                        break
                
                if exe_url:
                    master_win.after(0, lambda: _prompt_update(master_win, data.get("tag_name"), data.get("body", ""), exe_url))
        except Exception as e:
            safe_print(f"Error comprobando actualizaciones: {e}")

    threading.Thread(target=_check, daemon=True).start()

_INLINE_MD_PATTERN = re.compile(
    r"`([^`\n]+)`"
    r"|\[([^\]]+)\]\((https?://[^\s)]+)\)"
    r"|\*\*\*([^*\n]+?)\*\*\*"
    r"|\*\*([^*\n]+?)\*\*"
    r"|~~([^~\n]+?)~~"
    r"|(?<!\*)\*(?!\s)([^*\n]+?)(?<!\s)\*(?!\*)"
    r"|(?<!\w)_(?!\s)([^_\n]+?)(?<!\s)_(?!\w)"
    r"|(https?://[^\s<>)\]]+)"
)


def parse_inline_markdown(text):
    """Divide una línea Markdown en tokens (tipo, texto, extra) para renderizar con estilo."""
    if not text:
        return []
    tokens = []
    pos = 0
    for match in _INLINE_MD_PATTERN.finditer(text):
        if match.start() > pos:
            tokens.append(("text", text[pos:match.start()], None))
        if match.group(1) is not None:
            tokens.append(("code", match.group(1), None))
        elif match.group(2) is not None:
            tokens.append(("link", match.group(2), match.group(3)))
        elif match.group(4) is not None:
            tokens.append(("bold_italic", match.group(4), None))
        elif match.group(5) is not None:
            tokens.append(("bold", match.group(5), None))
        elif match.group(6) is not None:
            tokens.append(("strike", match.group(6), None))
        elif match.group(7) is not None:
            tokens.append(("italic", match.group(7), None))
        elif match.group(8) is not None:
            tokens.append(("italic", match.group(8), None))
        elif match.group(9) is not None:
            url = match.group(9).rstrip(".,;:")
            tokens.append(("link", url, url))
            trailing = match.group(9)[len(url):]
            if trailing:
                tokens.append(("text", trailing, None))
        pos = match.end()
    if pos < len(text):
        tokens.append(("text", text[pos:], None))
    return tokens


def parse_markdown_blocks(markdown_text):
    """Parsea notas Markdown (formato GitHub Releases) en bloques estructurados."""
    if not markdown_text or not markdown_text.strip():
        return [("paragraph", "No se incluyeron notas de la versión.")]

    normalized = markdown_text.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")
    blocks = []
    in_code_block = False
    code_lines = []
    idx = 0

    while idx < len(lines):
        raw_line = lines[idx]
        stripped = raw_line.strip()

        if stripped.startswith("```"):
            if in_code_block:
                blocks.append(("code_block", "\n".join(code_lines)))
                code_lines = []
                in_code_block = False
            else:
                in_code_block = True
                code_lines = []
            idx += 1
            continue

        if in_code_block:
            code_lines.append(raw_line)
            idx += 1
            continue

        if not stripped:
            if blocks and blocks[-1][0] != "blank":
                blocks.append(("blank", ""))
            idx += 1
            continue

        if re.match(r"^([-*_])\1{2,}\s*$", stripped):
            blocks.append(("hr", ""))
            idx += 1
            continue

        heading_match = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if heading_match:
            level = len(heading_match.group(1))
            blocks.append((f"h{level}", heading_match.group(2).strip()))
            idx += 1
            continue

        if stripped.startswith(">"):
            quote_text = re.sub(r"^>\s?", "", stripped)
            blocks.append(("quote", quote_text))
            idx += 1
            continue

        bullet_match = re.match(r"^(\s*)[-*+]\s+(.*)$", raw_line)
        if bullet_match:
            indent_level = min(len(bullet_match.group(1).replace("\t", "  ")) // 2, 2)
            blocks.append(("bullet", (indent_level, bullet_match.group(2).strip())))
            idx += 1
            continue

        ordered_match = re.match(r"^(\s*)(\d+)\.\s+(.*)$", raw_line)
        if ordered_match:
            indent_level = min(len(ordered_match.group(1).replace("\t", "  ")) // 2, 2)
            blocks.append(("ordered", (indent_level, ordered_match.group(2), ordered_match.group(3).strip())))
            idx += 1
            continue

        if stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 2:
            if re.match(r"^\|[\s:\-|]+\|$", stripped):
                idx += 1
                continue
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            next_is_sep = (
                idx + 1 < len(lines)
                and bool(re.match(r"^\|[\s:\-|]+\|$", lines[idx + 1].strip()))
            )
            blocks.append(("table_header" if next_is_sep else "table_row", cells))
            idx += 1
            continue

        blocks.append(("paragraph", stripped))
        idx += 1

    if in_code_block and code_lines:
        blocks.append(("code_block", "\n".join(code_lines)))

    while blocks and blocks[-1][0] == "blank":
        blocks.pop()

    return blocks


def _get_markdown_palette(appearance_mode=None):
    if appearance_mode is not None:
        is_dark = str(appearance_mode).strip().lower() != "light"
    else:
        is_dark = ui_theme.is_dark_theme()
    if not is_dark:
        return {
            "text": "#1E293B",
            "muted": "#64748B",
            "h1": "#0F172A",
            "h2": "#0969DA",
            "h3": "#1E40AF",
            "h4": "#334155",
            "bold": "#0F172A",
            "code_fg": "#9A3412",
            "code_bg": "#E2E8F0",
            "block_code_fg": "#1E293B",
            "block_code_bg": "#E2E8F0",
            "hr": "#CBD5E1",
            "bullet": "#0969DA",
            "quote_bar": "#0969DA",
            "quote_fg": "#475569",
            "link": "#0969DA",
        }
    return {
        "text": "#C9D1D9",
        "muted": "#8B949E",
        "h1": "#F0F6FC",
        "h2": "#58A6FF",
        "h3": "#79C0FF",
        "h4": "#D2A8FF",
        "bold": "#F0F6FC",
        "code_fg": "#FFA657",
        "code_bg": "#21262D",
        "block_code_fg": "#E6EDF3",
        "block_code_bg": "#161B22",
        "hr": "#30363D",
        "bullet": "#58A6FF",
        "quote_bar": "#58A6FF",
        "quote_fg": "#8B949E",
        "link": "#58A6FF",
    }


def render_markdown_to_textbox(textbox, markdown_text, appearance_mode=None):
    """Renderiza Markdown con jerarquía visual, negritas, cursivas, código y enlaces en un ScrolledText/Text."""
    palette = _get_markdown_palette(appearance_mode)
    tk_text = getattr(textbox, "text", getattr(textbox, "_textbox", textbox))

    tk_text.configure(state="normal", wrap="word", padx=12, pady=10, spacing2=2)
    tk_text.delete("1.0", "end")

    base_family = "Segoe UI"
    mono_family = "Consolas"

    tk_text.tag_config("body", font=(base_family, 10), foreground=palette["text"], spacing3=4)
    tk_text.tag_config("bold", font=(base_family, 10, "bold"), foreground=palette["bold"])
    tk_text.tag_config("italic", font=(base_family, 10, "italic"), foreground=palette["text"])
    tk_text.tag_config("bold_italic", font=(base_family, 10, "bold italic"), foreground=palette["bold"])
    tk_text.tag_config("strike", font=(base_family, 10, "overstrike"), foreground=palette["muted"])
    tk_text.tag_config(
        "inline_code",
        font=(mono_family, 9),
        foreground=palette["code_fg"],
        background=palette["code_bg"],
    )

    tk_text.tag_config("h1", font=(base_family, 15, "bold"), foreground=palette["h1"], spacing1=6, spacing3=6)
    tk_text.tag_config("h2", font=(base_family, 13, "bold"), foreground=palette["h2"], spacing1=10, spacing3=4)
    tk_text.tag_config("h3", font=(base_family, 11, "bold"), foreground=palette["h3"], spacing1=8, spacing3=3)
    tk_text.tag_config("h4", font=(base_family, 10, "bold"), foreground=palette["h4"], spacing1=6, spacing3=2)

    tk_text.tag_config("hr", font=(mono_family, 8), foreground=palette["hr"], spacing1=4, spacing3=6)
    tk_text.tag_config("bullet_mark", font=(base_family, 10, "bold"), foreground=palette["bullet"])
    tk_text.tag_config("bullet_l0", lmargin1=12, lmargin2=26, spacing1=2, spacing3=4)
    tk_text.tag_config("bullet_l1", lmargin1=28, lmargin2=42, spacing1=1, spacing3=3)
    tk_text.tag_config("bullet_l2", lmargin1=44, lmargin2=58, spacing1=1, spacing3=3)

    tk_text.tag_config("quote_bar", font=(base_family, 10, "bold"), foreground=palette["quote_bar"], lmargin1=10, lmargin2=24)
    tk_text.tag_config("quote_text", font=(base_family, 10, "italic"), foreground=palette["quote_fg"], lmargin1=10, lmargin2=24, spacing3=4)

    tk_text.tag_config(
        "code_block",
        font=(mono_family, 9),
        foreground=palette["block_code_fg"],
        background=palette["block_code_bg"],
        lmargin1=14,
        lmargin2=14,
        rmargin=14,
        spacing1=4,
        spacing3=6,
    )
    tk_text.tag_config("table_header", font=(mono_family, 9, "bold"), foreground=palette["bold"], lmargin1=8, spacing1=4, spacing3=2)
    tk_text.tag_config("table_row", font=(mono_family, 9), foreground=palette["text"], lmargin1=8, spacing3=2)

    link_counter = [0]

    def _insert_inline(text, base_tags):
        for tok_type, content, extra in parse_inline_markdown(text):
            if tok_type == "text":
                tk_text.insert("end", content, base_tags)
            elif tok_type == "code":
                tk_text.insert("end", f" {content} ", base_tags + ("inline_code",))
            elif tok_type == "bold":
                tk_text.insert("end", content, base_tags + ("bold",))
            elif tok_type == "italic":
                tk_text.insert("end", content, base_tags + ("italic",))
            elif tok_type == "bold_italic":
                tk_text.insert("end", content, base_tags + ("bold_italic",))
            elif tok_type == "strike":
                tk_text.insert("end", content, base_tags + ("strike",))
            elif tok_type == "link":
                link_counter[0] += 1
                tag_name = f"md_link_{link_counter[0]}"
                tk_text.tag_config(
                    tag_name,
                    font=(base_family, 10, "underline"),
                    foreground=palette["link"],
                )
                url = extra or content
                tk_text.tag_bind(tag_name, "<Button-1>", lambda _e, u=url: webbrowser.open(u))
                tk_text.tag_bind(tag_name, "<Enter>", lambda _e: tk_text.configure(cursor="hand2"))
                tk_text.tag_bind(tag_name, "<Leave>", lambda _e: tk_text.configure(cursor=""))
                tk_text.insert("end", content, base_tags + (tag_name,))

    blocks = parse_markdown_blocks(markdown_text)
    for btype, payload in blocks:
        if btype == "blank":
            tk_text.insert("end", "\n")
        elif btype in ("h1", "h2", "h3", "h4"):
            _insert_inline(payload, (btype,))
            tk_text.insert("end", "\n", (btype,))
        elif btype == "hr":
            tk_text.insert("end", ("─" * 62) + "\n", ("hr",))
        elif btype == "bullet":
            level, text = payload
            level_tag = f"bullet_l{min(level, 2)}"
            symbol = "• " if level == 0 else "◦ "
            tk_text.insert("end", symbol, (level_tag, "bullet_mark"))
            _insert_inline(text, ("body", level_tag))
            tk_text.insert("end", "\n", ("body", level_tag))
        elif btype == "ordered":
            level, num_str, text = payload
            level_tag = f"bullet_l{min(level, 2)}"
            tk_text.insert("end", f"{num_str}. ", (level_tag, "bullet_mark"))
            _insert_inline(text, ("body", level_tag))
            tk_text.insert("end", "\n", ("body", level_tag))
        elif btype == "quote":
            tk_text.insert("end", "▎ ", ("quote_bar",))
            _insert_inline(payload, ("quote_text",))
            tk_text.insert("end", "\n", ("quote_text",))
        elif btype == "code_block":
            tk_text.insert("end", payload + "\n", ("code_block",))
        elif btype == "table_header":
            tk_text.insert("end", " | ".join(payload) + "\n", ("table_header",))
        elif btype == "table_row":
            tk_text.insert("end", " | ".join(payload) + "\n", ("table_row",))
        else:
            _insert_inline(payload, ("body",))
            tk_text.insert("end", "\n", ("body",))

    tk_text.configure(state="disabled")


def _prompt_update(master_win, tag_name, release_notes, download_url):
    update_win = tb.Toplevel(master_win)
    update_win.title("¡Nueva versión disponible!")
    win_w, win_h = 660, 550
    update_win.geometry(f"{win_w}x{win_h}")
    update_win.minsize(500, 400)
    update_win.transient(master_win)
    update_win.grab_set()
    ui_theme.apply_window_chrome(update_win)

    update_win.update_idletasks()
    x = int(master_win.winfo_x() + (master_win.winfo_width() / 2) - (win_w / 2))
    y = int(master_win.winfo_y() + (master_win.winfo_height() / 2) - (win_h / 2))
    update_win.geometry(f"+{x}+{y}")

    lbl_title = tb.Label(update_win, text=f"Actualización detectada: {tag_name}", font=("Segoe UI", 16, "bold"), bootstyle="primary")
    lbl_title.pack(pady=(14, 2))

    lbl_sub = tb.Label(update_win, text="Notas de la versión", font=("Segoe UI", 10), bootstyle="secondary")
    lbl_sub.pack(pady=(0, 8))

    txt_notes = ScrolledText(update_win, auto_hide=True)
    txt_notes.pack(fill="both", expand=True, padx=20, pady=(0, 12))
    render_markdown_to_textbox(txt_notes, release_notes)

    btn_frame = tb.Frame(update_win)
    btn_frame.pack(pady=(0, 14))

    def do_update():
        update_win.destroy()
        _download_and_apply_update(master_win, download_url)

    btn_yes = tb.Button(btn_frame, text="Descargar e Instalar", bootstyle="success", command=do_update, width=20)
    btn_yes.pack(side="left", padx=10)

    btn_no = tb.Button(btn_frame, text="Más tarde", bootstyle="danger-outline", command=update_win.destroy, width=14)
    btn_no.pack(side="left", padx=10)
    ui_theme.bring_to_front(update_win)


def _download_and_apply_update(master_win, download_url):
    dl_win = tb.Toplevel(master_win)
    dl_win.title("Actualizando...")
    dl_win.geometry("420x160")
    dl_win.transient(master_win)
    dl_win.grab_set()
    ui_theme.apply_window_chrome(dl_win)

    dl_win.update_idletasks()
    x = int(master_win.winfo_x() + (master_win.winfo_width() / 2) - 210)
    y = int(master_win.winfo_y() + (master_win.winfo_height() / 2) - 80)
    dl_win.geometry(f"+{x}+{y}")

    lbl = tb.Label(dl_win, text="Descargando la nueva versión...\nPor favor espera, el programa se reiniciará automáticamente.", font=("Segoe UI", 10), justify="center")
    lbl.pack(pady=18)

    progress = tb.Progressbar(dl_win, mode="indeterminate", bootstyle="info-striped", length=320)
    progress.pack(pady=10)
    progress.start(12)
    ui_theme.bring_to_front(dl_win)
    
    def dl_thread():
        try:
            update_exe = get_user_data_path("update_temp.exe")
            urllib.request.urlretrieve(download_url, update_exe)
            
            # Generar el script de actualización
            current_exe = sys.executable
            bat_path = get_user_data_path("apply_update.bat")
            
            bat_content = f'''@echo off
timeout /t 2 /nobreak >nul
del "{current_exe}"
move /Y "{update_exe}" "{current_exe}"
start "" "{current_exe}"
del "%~f0"
'''
            with open(bat_path, "w") as f:
                f.write(bat_content)
                
            master_win.after(0, lambda: _restart_and_update(bat_path))
        except Exception as e:
            safe_print(f"Error descargando actualización: {e}")
            master_win.after(0, lambda: messagebox.showerror("Error", "No se pudo descargar la actualización."))
            master_win.after(0, dl_win.destroy)
            
    threading.Thread(target=dl_thread, daemon=True).start()

def _restart_and_update(bat_path):
    # Ejecuta el script BAT de forma independiente y cierra la app actual
    ctypes.windll.shell32.ShellExecuteW(None, "open", bat_path, "", None, 0)
    os._exit(0)

# ==============================================================
# CRASH REPORTER
# ==============================================================

def check_for_crashes(master_win):
    """
    Comprueba si existe el archivo crash.log de un cierre inesperado previo.
    """
    crash_file = get_user_data_path("crash.log")
    if os.path.exists(crash_file):
        with open(crash_file, "r") as f:
            content = f.read().strip()
            
        if content:
            _prompt_crash_report(master_win, content, crash_file)
        else:
            try: os.remove(crash_file)
            except Exception: pass

def _prompt_crash_report(master_win, crash_data, crash_file):
    crash_win = tb.Toplevel(master_win)
    crash_win.title("Reporte de Error")
    crash_win.geometry("500x240")
    crash_win.transient(master_win)
    ui_theme.apply_window_chrome(crash_win)

    crash_win.update_idletasks()
    x = int(master_win.winfo_x() + (master_win.winfo_width() / 2) - 250)
    y = int(master_win.winfo_y() + (master_win.winfo_height() / 2) - 120)
    crash_win.geometry(f"+{x}+{y}")

    lbl = tb.Label(
        crash_win,
        text="El programa se cerró inesperadamente la última vez.\n¿Deseas enviar el reporte de error de forma anónima\nal desarrollador para que pueda solucionarlo?",
        font=("Segoe UI", 10),
        justify="center",
    )
    lbl.pack(pady=28)

    btn_frame = tb.Frame(crash_win)
    btn_frame.pack(pady=10)

    def send_report():
        crash_win.destroy()
        if not DISCORD_WEBHOOK_URL:
            messagebox.showinfo("Reporte", "El Webhook no está configurado, no se pudo enviar el reporte.")
            _cleanup_crash(crash_file)
            return

        def _send():
            try:
                payload = {
                    "content": f"[CRASH REPORT] **Nuevo Crash Report - v{__version__}**\n```python\n{crash_data[:1800]}\n```"
                }
                req = urllib.request.Request(DISCORD_WEBHOOK_URL, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
                urllib.request.urlopen(req, timeout=5)
            except Exception as e:
                safe_print(f"Error enviando crash report: {e}")
            finally:
                _cleanup_crash(crash_file)

        threading.Thread(target=_send, daemon=True).start()

    def cancel_report():
        crash_win.destroy()
        _cleanup_crash(crash_file)

    btn_yes = tb.Button(btn_frame, text="Enviar Reporte", bootstyle="warning", command=send_report, width=16)
    btn_yes.pack(side="left", padx=10)

    btn_no = tb.Button(btn_frame, text="Ignorar", bootstyle="secondary", command=cancel_report, width=12)
    btn_no.pack(side="left", padx=10)
    ui_theme.bring_to_front(crash_win)

def _cleanup_crash(crash_file):
    try:
        os.remove(crash_file)
    except Exception:
        pass
