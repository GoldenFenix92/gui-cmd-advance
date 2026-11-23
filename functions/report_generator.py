import datetime
import html
import json
import os
import re

from functions.utils import get_resource_path


PROFILES = {
    "multimedia": {
        "id": "multimedia",
        "label": "Laboratorio Multimedia",
        "subtitle": "Compresión, reparación y verificación de imágenes y video",
    },
    "storage": {
        "id": "storage",
        "label": "Diagnóstico de Almacenamiento",
        "subtitle": "Discos físicos, volúmenes, particiones y atributos de unidad",
    },
    "network": {
        "id": "network",
        "label": "Operaciones de Red",
        "subtitle": "Conectividad, enrutamiento, latencia y adaptadores",
    },
    "security": {
        "id": "security",
        "label": "Auditoría de Seguridad",
        "subtitle": "Credenciales, firewall, eventos críticos y control de acceso",
    },
    "system": {
        "id": "system",
        "label": "Consola de Sistema",
        "subtitle": "Mantenimiento, integridad del sistema y gestión de archivos",
    },
}


def detect_report_profile(category="", title="", command=""):
    """Determina la plantilla/perfil visual más adecuado según la función ejecutada."""
    blob = f"{category} {title} {command}".lower()

    if any(k in blob for k in (
        "multimedia", "compresor", "reparador", "duplicados", "salud multimedia",
        "--run-compressor", "--run-media-repair", "--run-health-analyzer", "--run-duplicate-finder", "ffmpeg",
    )):
        return "multimedia"

    if any(k in blob for k in (
        "almacenamiento", "formateo y gestión", "formateo y gestion", "diagnóstico y salud", "diagnostico y salud",
        "recuperación de datos", "recuperacion de datos", "diskpart",
        "--run-disk-attributes", "--run-usb-audit", "autenticidad", "get-disk", "get-physicaldisk",
        "get-volume", "clear-disk", "format-volume", "initialize-disk", "optimize-volume",
        "chkdsk", "winfr", "photorec", "smart",
    )):
        return "storage"

    if any(k in blob for k in (
        "redes", "conectividad", "ipconfig", "ping", "tracert", "netstat", "getmac", "arp",
        "nslookup", "pathping", "enrutamiento", "tcp", "wifi", "wlan", "netadapter", "dns",
    )):
        return "network"

    if any(k in blob for k in (
        "seguridad", "privacidad", "permisos", "--run-vault", "firewall",
        "icacls", "takeown", "attrib", "eventos de seguridad", "cmdkey", "credenciales",
    )):
        return "security"

    return "system"


def _count_log_severities(content):
    total = 0
    errors = 0
    warnings = 0
    successes = 0
    in_error_section = False

    for raw in (content or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        total += 1
        low = line.lower()
        if "[ archivos con errores" in low:
            in_error_section = True
            continue
        if "====" in low or "[ archivos completados" in low or "[ resumen" in low:
            in_error_section = False

        if in_error_section or any(k in low for k in ("[error]", "error:", "fallo definitivo", "failed", "acceso denegado", "access is denied", "truncated", "[corrupto]")):
            errors += 1
        elif any(k in low for k in ("[warn]", "[warning]", "[aviso]", "advertencia", "bloqueado por seguridad")):
            warnings += 1
        elif any(k in low for k in ("[success]", "[ok]", "completado con éxito", "finalizado con éxito", "guardado en:")):
            successes += 1

    return {
        "total_lines": total,
        "errors": errors,
        "warnings": warnings,
        "successes": successes,
    }


def extract_report_metrics(profile, content):
    """Extrae métricas estructuradas específicas de cada dominio desde la salida de consola."""
    text = content or ""
    counts = _count_log_severities(text)
    metrics = {"profile": profile, "counts": counts}

    if profile == "multimedia":
        m_time = re.search(r"Tiempo total:\s*(.+)", text)
        m_orig = re.search(r"Peso Original\s*:\s*([^\r\n]+)", text)
        m_final = re.search(r"Peso Final\s*:\s*([^\r\n]+)", text)
        m_saved = re.search(r"Espacio Ahorrado:\s*([^\r\n(]+)\(([\d.,]+)%\)", text)
        m_inc = re.search(r"Incremento de Peso:\s*([^\r\n(]+)\(\+?([\d.,]+)%\)", text)
        m_imgs = re.search(r"Im[áa]genes\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)", text)
        m_vids = re.search(r"Videos\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)", text)
        m_rep_ok = re.search(r"Exitosos:\s*(\d+)", text)
        m_rep_fail = re.search(r"Fallidos:\s*(\d+)", text)
        m_sanos = re.search(r"Archivos Sanos:\s*(\d+)", text)
        m_corrupt = re.search(r"Archivos Corruptos:\s*(\d+)", text)

        error_rows = []
        in_err_tbl = False
        for line in text.splitlines():
            s = line.strip()
            if "[ ARCHIVOS CON ERRORES" in s.upper():
                in_err_tbl = True
                continue
            if in_err_tbl:
                if s.startswith("===="):
                    break
                if s.startswith("ARCHIVO") or s.startswith("----") or not s:
                    continue
                if "|" in s:
                    left, right = s.split("|", 1)
                    error_rows.append({"file": left.strip(), "reason": right.strip()})

        metrics.update({
            "duration": m_time.group(1).strip() if m_time else None,
            "orig_size": m_orig.group(1).strip() if m_orig else None,
            "final_size": m_final.group(1).strip() if m_final else None,
            "saved_label": m_saved.group(1).strip() if m_saved else (m_inc.group(1).strip() if m_inc else None),
            "saved_pct": float(m_saved.group(2).replace(",", ".")) if m_saved else (-float(m_inc.group(2).replace(",", ".")) if m_inc else None),
            "images": {"ok": int(m_imgs.group(1)), "fail": int(m_imgs.group(2)), "total": int(m_imgs.group(3))} if m_imgs else None,
            "videos": {"ok": int(m_vids.group(1)), "fail": int(m_vids.group(2)), "total": int(m_vids.group(3))} if m_vids else None,
            "repair_ok": int(m_rep_ok.group(1)) if m_rep_ok else (int(m_sanos.group(1)) if m_sanos else None),
            "repair_fail": int(m_rep_fail.group(1)) if m_rep_fail else (int(m_corrupt.group(1)) if m_corrupt else None),
            "error_rows": error_rows,
        })

    elif profile == "storage":
        m_model = re.search(r"Modelo\s*:\s*([^\r\n]+)", text)
        m_type = re.search(r"Tipo de Unidad\s*:\s*([^\r\n]+)", text)
        m_cap = re.search(r"Capacidad\s*:\s*([^\r\n]+)", text)
        m_style = re.search(r"Estilo Partici[oó]n\s*:\s*([^\r\n]+)", text)
        m_wp = re.search(r"Protecci[oó]n contra escritura\s*:\s*([^\r\n]+)", text)
        m_state = re.search(r"Estado Operativo\s*:\s*([^\r\n]+)", text)
        m_verdict = re.search(r"Veredicto de Autenticidad\s*:\s*([^\r\n]+)", text)
        m_vidpid = re.search(r"VID / PID USB\s*:\s*([^\r\n]+)", text)
        m_speed = re.search(r"Velocidad Medida\s*:\s*([^\r\n]+)", text)
        vols = re.findall(r"Volumen\s+(\d+)\s+\[([^\]]+)\]", text)

        metrics.update({
            "model": m_model.group(1).strip() if m_model else None,
            "drive_type": m_type.group(1).strip() if m_type else None,
            "capacity": m_cap.group(1).strip() if m_cap else None,
            "partition_style": m_style.group(1).strip() if m_style else None,
            "write_protect": m_wp.group(1).strip() if m_wp else None,
            "op_status": m_state.group(1).strip() if m_state else None,
            "verdict": m_verdict.group(1).strip() if m_verdict else None,
            "vid_pid": m_vidpid.group(1).strip() if m_vidpid else None,
            "speed": m_speed.group(1).strip() if m_speed else None,
            "volumes_count": len(vols),
        })

    elif profile == "network":
        ips = sorted(set(re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", text)))
        latencies = [int(x) for x in re.findall(r"(?:tiempo|time)[=<]\s*(\d+)\s*ms", text, flags=re.I)]
        m_loss = re.search(r"\((\d+)%\s*(?:perdidos|loss)", text, flags=re.I)

        metrics.update({
            "unique_ips": ips[:12],
            "total_ips": len(ips),
            "avg_ms": round(sum(latencies) / len(latencies), 1) if latencies else None,
            "max_ms": max(latencies) if latencies else None,
            "packet_loss_pct": int(m_loss.group(1)) if m_loss else None,
        })

    elif profile == "security":
        m_creds = re.search(r"encontrado\s+(\d+)\s+credenciales", text, flags=re.I)
        metrics.update({
            "credentials_count": int(m_creds.group(1)) if m_creds else None,
        })

    else:
        m_freed = re.search(r"Se liberaron\s+([\d.,]+\s*[KMGT]?B)", text, flags=re.I)
        m_analyzed = re.search(r"Total analizados:\s*(\d+)\s*\|\s*Renombrados:\s*(\d+)\s*\|\s*Errores:\s*(\d+)", text)
        metrics.update({
            "freed_space": m_freed.group(1) if m_freed else None,
            "sanitized": {
                "analyzed": int(m_analyzed.group(1)),
                "renamed": int(m_analyzed.group(2)),
                "errors": int(m_analyzed.group(3)),
            } if m_analyzed else None,
        })

    return metrics


def _build_hero_widget(profile, metrics):
    """Genera el bloque HTML de métricas/visualización único para cada perfil."""
    counts = metrics["counts"]

    if profile == "multimedia":
        cards = []
        if metrics.get("images") or metrics.get("videos"):
            img_info = metrics.get("images") or {"ok": 0, "fail": 0, "total": 0}
            vid_info = metrics.get("videos") or {"ok": 0, "fail": 0, "total": 0}
            total_ok = img_info["ok"] + vid_info["ok"]
            total_fail = img_info["fail"] + vid_info["fail"]
            cards.append(f'<div class="metric-item"><span class="metric-label">Completados</span><strong class="metric-val ok">{total_ok:,}</strong><span class="metric-sub">{img_info["ok"]:,} imágenes · {vid_info["ok"]:,} videos</span></div>')
            cards.append(f'<div class="metric-item"><span class="metric-label">Con errores (conservados)</span><strong class="metric-val {"err" if total_fail else "ok"}">{total_fail:,}</strong><span class="metric-sub">{img_info["fail"]:,} imágenes · {vid_info["fail"]:,} videos</span></div>')
        elif metrics.get("repair_ok") is not None:
            cards.append(f'<div class="metric-item"><span class="metric-label">Procesados sin error</span><strong class="metric-val ok">{metrics["repair_ok"]:,}</strong><span class="metric-sub">Archivos verificados</span></div>')
            cards.append(f'<div class="metric-item"><span class="metric-label">Fallidos / Corruptos</span><strong class="metric-val {"err" if metrics["repair_fail"] else "ok"}">{metrics["repair_fail"]:,}</strong><span class="metric-sub">Requieren revisión</span></div>')
        else:
            cards.append(f'<div class="metric-item"><span class="metric-label">Éxitos detectados</span><strong class="metric-val ok">{counts["successes"]:,}</strong><span class="metric-sub">Registros exitosos</span></div>')
            cards.append(f'<div class="metric-item"><span class="metric-label">Errores detectados</span><strong class="metric-val {"err" if counts["errors"] else "ok"}">{counts["errors"]:,}</strong><span class="metric-sub">Incidencias en el proceso</span></div>')

        if metrics.get("orig_size") and metrics.get("final_size"):
            cards.append(f'<div class="metric-item"><span class="metric-label">Peso original → final</span><strong class="metric-val">{html.escape(metrics["orig_size"])} → {html.escape(metrics["final_size"])}</strong><span class="metric-sub">Duración: {html.escape(metrics.get("duration") or "N/D")}</span></div>')

        savings_bar = ""
        pct = metrics.get("saved_pct")
        if pct is not None:
            if pct >= 0:
                clamped = max(0.0, min(100.0, pct))
                savings_bar = f"""
                <div class="domain-visual">
                    <div class="visual-head">
                        <span>Reducción de almacenamiento</span>
                        <strong>{html.escape(metrics.get("saved_label") or "")} ({pct:.1f}% ahorrado)</strong>
                    </div>
                    <div class="ratio-track"><div class="ratio-fill" style="width: {clamped:.1f}%"></div></div>
                </div>"""
            else:
                savings_bar = f"""
                <div class="domain-visual">
                    <div class="visual-head">
                        <span>Cambio de tamaño</span>
                        <strong>+{html.escape(metrics.get("saved_label") or "")} (+{abs(pct):.1f}%)</strong>
                    </div>
                    <div class="ratio-track"><div class="ratio-fill warn" style="width: 100%"></div></div>
                </div>"""

        err_table = ""
        if metrics.get("error_rows"):
            rows_html = "".join(
                f"<tr><td class='mono'>{html.escape(r['file'])}</td><td>{html.escape(r['reason'])}</td></tr>"
                for r in metrics["error_rows"]
            )
            err_table = f"""
            <details class="error-drawer" open>
                <summary>Archivos con error conservados intactos ({len(metrics['error_rows'])})</summary>
                <div class="table-wrap">
                    <table class="data-table">
                        <thead><tr><th>Archivo</th><th>Motivo detectado</th></tr></thead>
                        <tbody>{rows_html}</tbody>
                    </table>
                </div>
            </details>"""

        return f'<section class="domain-panel"><div class="metrics-strip">{"".join(cards)}</div>{savings_bar}{err_table}</section>'

    if profile == "storage":
        cards = []
        if metrics.get("verdict"):
            v = metrics["verdict"]
            v_cls = "ok" if "ORIGINAL" in v.upper() else ("err" if "FALSA" in v.upper() or "FALSIFICACI" in v.upper() else "warn")
            cards.append(f'<div class="metric-item"><span class="metric-label">Veredicto de autenticidad</span><strong class="metric-val {v_cls}">{html.escape(v)}</strong><span class="metric-sub">{html.escape(metrics.get("vid_pid") or "Inspección de unidad")}</span></div>')
        if metrics.get("model"):
            cards.append(f'<div class="metric-item"><span class="metric-label">Unidad inspeccionada</span><strong class="metric-val">{html.escape(metrics["model"])}</strong><span class="metric-sub">{html.escape(metrics.get("drive_type") or "Almacenamiento")} · {html.escape(metrics.get("capacity") or "")}</span></div>')
        if metrics.get("speed"):
            cards.append(f'<div class="metric-item"><span class="metric-label">Velocidad medida</span><strong class="metric-val ok">{html.escape(metrics["speed"])}</strong><span class="metric-sub">Prueba secuencial verificada</span></div>')
        if metrics.get("partition_style"):
            cards.append(f'<div class="metric-item"><span class="metric-label">Esquema y estado</span><strong class="metric-val">{html.escape(metrics["partition_style"])}</strong><span class="metric-sub">Estado: {html.escape(metrics.get("op_status") or "N/D")} · Volúmenes: {metrics.get("volumes_count", 0)}</span></div>')
        if metrics.get("write_protect"):
            wp = metrics["write_protect"]
            cls = "ok" if wp.upper().startswith("NO") else "err"
            cards.append(f'<div class="metric-item"><span class="metric-label">Protección contra escritura</span><strong class="metric-val {cls}">{html.escape(wp.split("(")[0].strip())}</strong><span class="metric-sub">{html.escape(wp)}</span></div>')
        if not cards:
            cards.append(f'<div class="metric-item"><span class="metric-label">Registros analizados</span><strong class="metric-val">{counts["total_lines"]:,}</strong><span class="metric-sub">Salida de diagnóstico de discos</span></div>')
            cards.append(f'<div class="metric-item"><span class="metric-label">Advertencias / Errores</span><strong class="metric-val {"err" if counts["errors"] else "ok"}">{counts["warnings"]} / {counts["errors"]}</strong><span class="metric-sub">Revisar consola inferior</span></div>')
        return f'<section class="domain-panel"><div class="metrics-strip">{"".join(cards)}</div></section>'

    if profile == "network":
        cards = [
            f'<div class="metric-item"><span class="metric-label">Direcciones IP detectadas</span><strong class="metric-val">{metrics.get("total_ips", 0)}</strong><span class="metric-sub">Haz clic en un chip para filtrar</span></div>',
        ]
        if metrics.get("avg_ms") is not None:
            cards.append(f'<div class="metric-item"><span class="metric-label">Latencia media / máxima</span><strong class="metric-val ok">{metrics["avg_ms"]} ms / {metrics["max_ms"]} ms</strong><span class="metric-sub">Medición ICMP</span></div>')
        if metrics.get("packet_loss_pct") is not None:
            loss = metrics["packet_loss_pct"]
            cards.append(f'<div class="metric-item"><span class="metric-label">Pérdida de paquetes</span><strong class="metric-val {"err" if loss > 0 else "ok"}">{loss}%</strong><span class="metric-sub">Estabilidad del enlace</span></div>')
        cards.append(f'<div class="metric-item"><span class="metric-label">Errores de red</span><strong class="metric-val {"err" if counts["errors"] else "ok"}">{counts["errors"]}</strong><span class="metric-sub">Líneas con fallo</span></div>')

        chips = ""
        if metrics.get("unique_ips"):
            chip_btns = "".join(
                f'<button type="button" class="ip-chip" onclick="quickSearch(\'{html.escape(ip)}\')">{html.escape(ip)}</button>'
                for ip in metrics["unique_ips"]
            )
            chips = f'<div class="chip-bar"><span class="chip-title">Filtrar por IP:</span>{chip_btns}</div>'
        return f'<section class="domain-panel"><div class="metrics-strip">{"".join(cards)}</div>{chips}</section>'

    if profile == "security":
        cards = []
        if metrics.get("credentials_count") is not None:
            cards.append(f'<div class="metric-item"><span class="metric-label">Credenciales encontradas</span><strong class="metric-val">{metrics["credentials_count"]}</strong><span class="metric-sub">Bóveda local de Windows</span></div>')
        cards.append(f'<div class="metric-item"><span class="metric-label">Hallazgos de error</span><strong class="metric-val {"err" if counts["errors"] else "ok"}">{counts["errors"]}</strong><span class="metric-sub">Eventos críticos o denegados</span></div>')
        cards.append(f'<div class="metric-item"><span class="metric-label">Advertencias</span><strong class="metric-val {"warn" if counts["warnings"] else "ok"}">{counts["warnings"]}</strong><span class="metric-sub">Puntos a revisar</span></div>')
        cards.append(f'<div class="metric-item"><span class="metric-label">Líneas auditadas</span><strong class="metric-val">{counts["total_lines"]:,}</strong><span class="metric-sub">Salida íntegra capturada</span></div>')
        return f'<section class="domain-panel"><div class="metrics-strip">{"".join(cards)}</div></section>'

    # Perfil 'system' (default)
    cards = []
    if metrics.get("freed_space"):
        cards.append(f'<div class="metric-item"><span class="metric-label">Espacio liberado</span><strong class="metric-val ok">{html.escape(metrics["freed_space"])}</strong><span class="metric-sub">Limpieza completada</span></div>')
    if metrics.get("sanitized"):
        sn = metrics["sanitized"]
        cards.append(f'<div class="metric-item"><span class="metric-label">Archivos analizados</span><strong class="metric-val">{sn["analyzed"]:,}</strong><span class="metric-sub">Renombrados: {sn["renamed"]:,}</span></div>')
    cards.append(f'<div class="metric-item"><span class="metric-label">Líneas registradas</span><strong class="metric-val">{counts["total_lines"]:,}</strong><span class="metric-sub">Éxitos: {counts["successes"]:,}</span></div>')
    cards.append(f'<div class="metric-item"><span class="metric-label">Errores / Advertencias</span><strong class="metric-val {"err" if counts["errors"] else "ok"}">{counts["errors"]} / {counts["warnings"]}</strong><span class="metric-sub">Estado de ejecución</span></div>')
    return f'<section class="domain-panel"><div class="metrics-strip">{"".join(cards)}</div></section>'


def generate_html_report(content, title="Reporte de Ejecución", command="Desconocido", category="", timestamp=None):
    """Genera un reporte HTML interactivo autocontenido con plantilla adaptada a la función ejecutada."""
    ts = timestamp or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    profile_id = detect_report_profile(category=category, title=title, command=command)
    profile_meta = PROFILES[profile_id]
    metrics = extract_report_metrics(profile_id, content)
    hero_widget = _build_hero_widget(profile_id, metrics)

    template_path = get_resource_path(os.path.join("resources", "templates", "base_report.html"))
    if not os.path.exists(template_path):
        safe_content = html.escape(content or "")
        return f"<!DOCTYPE html><html lang='es'><body><h1>{html.escape(title)}</h1><pre>{safe_content}</pre></body></html>"

    with open(template_path, "r", encoding="utf-8") as tf:
        tpl = tf.read()

    # Escapar contenido para bloque <script type="application/json"> sin romper </script>
    safe_json_content = json.dumps(content or "", ensure_ascii=False).replace("</", "<\\/")

    replacements = {
        "{{PROFILE_ID}}": html.escape(profile_id),
        "{{PROFILE_LABEL}}": html.escape(profile_meta["label"]),
        "{{PROFILE_SUBTITLE}}": html.escape(profile_meta["subtitle"]),
        "{{TITLE}}": html.escape(title or "Reporte de Ejecución"),
        "{{COMMAND}}": html.escape(command or ""),
        "{{TIMESTAMP}}": html.escape(ts),
        "{{HERO_WIDGET}}": hero_widget,
        "{{RAW_CONTENT_JSON}}": safe_json_content,
    }
    for key, val in replacements.items():
        tpl = tpl.replace(key, val)

    return tpl
