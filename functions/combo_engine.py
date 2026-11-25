import re


def extract_command_context(cmd_str):
    """Extrae contexto reutilizable (disk, drive, path, recursive_flag, media_type) del comando principal actual."""
    ctx = {"disk": "", "drive": "", "path": "", "recursive_flag": "", "media_type": "all"}
    if not cmd_str:
        return ctx

    m_disk = re.search(r"(?:-num|--disk)\s+(\d+)", cmd_str, flags=re.IGNORECASE)
    if m_disk:
        ctx["disk"] = m_disk.group(1)

    m_drive = re.search(r"(?:-letra|--drive)\s+([A-Za-z]):?", cmd_str, flags=re.IGNORECASE)
    if m_drive:
        ctx["drive"] = m_drive.group(1).upper() + ":"

    if re.search(r"(?:^|\s)--recursive(?:\s|$)", cmd_str, flags=re.IGNORECASE):
        ctx["recursive_flag"] = "--recursive"

    m_mtype = re.search(r"--media-type\s+(all|videos|images)\b", cmd_str, flags=re.IGNORECASE)
    if m_mtype:
        ctx["media_type"] = m_mtype.group(1).lower()

    # Ruta entre comillas o ruta Windows tipo C:\...
    m_quoted = re.search(r'"([A-Za-z]:\\[^"]+)"', cmd_str)
    if m_quoted:
        ctx["path"] = m_quoted.group(1)
    else:
        m_plain = re.search(r"(?:^|\s)([A-Za-z]:\\[^\s\"']+)", cmd_str)
        if m_plain:
            ctx["path"] = m_plain.group(1)

    return ctx


def resolve_step_command(item, context=None):
    """Resuelve el auto_command de un combo sustituyendo placeholders de contexto.

    Retorna '' si no tiene auto_command o si falta algún placeholder obligatorio (disk/drive/path).
    """
    tmpl = (item.get("auto_command") or "").strip()
    if not tmpl:
        return ""
    ctx = context or {}
    required_keys = {"disk", "drive", "path"}
    needed = set(re.findall(r"\{(disk|drive|path|recursive_flag|media_type)\}", tmpl))
    for key in needed & required_keys:
        if not ctx.get(key):
            return ""
    resolved = tmpl
    for key in needed:
        resolved = resolved.replace("{" + key + "}", str(ctx.get(key, "")))
    return re.sub(r"\s{2,}", " ", resolved).strip()


def get_command_combos(cmd_data, context=None):
    """Devuelve (before_list, after_list) de sugerencias de combo configuradas para un comando."""
    if not cmd_data or not isinstance(cmd_data, dict):
        return [], []
    raw = cmd_data.get("combos") or []
    before_list = []
    after_list = []
    for item in raw:
        if not isinstance(item, dict) or not item.get("command"):
            continue
        when = str(item.get("when", "after")).lower()
        resolved = resolve_step_command(item, context)
        normalized = {
            "command": item["command"],
            "when": "before" if when == "before" else "after",
            "reason": item.get("reason", ""),
            "auto_command": item.get("auto_command") or "",
            "resolved_command": resolved,
            "mode": "auto" if resolved else "navigate",
        }
        if normalized["when"] == "before":
            before_list.append(normalized)
        else:
            after_list.append(normalized)
    return before_list, after_list


def build_execution_queue(
    main_name,
    main_cmd_str,
    selected_before=None,
    selected_after=None,
    auto_execute=True,
    context=None,
):
    """Construye la cola ordenada de pasos: [before...] -> [main] -> [after...].

    Si auto_execute=True, los pasos con comando resoluble corren automáticamente en cola.
    Si auto_execute=False, los pasos acompañantes se abren en modo guiado (navigate).
    """
    ctx = context if context is not None else extract_command_context(main_cmd_str)
    queue = []

    for item in (selected_before or []):
        resolved = item.get("resolved_command") or resolve_step_command(item, ctx)
        can_auto = bool(auto_execute and resolved)
        queue.append({
            "name": item["command"],
            "cmd_str": resolved if can_auto else "",
            "mode": "auto" if can_auto else "navigate",
            "role": "before",
        })

    has_health_before = any(
        s["role"] == "before" and s["mode"] == "auto" and "--run-health-analyzer" in s["cmd_str"]
        for s in queue
    )
    effective_main_cmd = main_cmd_str
    if has_health_before and "--run-media-repair" in effective_main_cmd and "--from-manifest" not in effective_main_cmd:
        effective_main_cmd = f"{effective_main_cmd} --from-manifest"

    queue.append({
        "name": main_name,
        "cmd_str": effective_main_cmd,
        "mode": "auto",
        "role": "main",
    })

    for item in (selected_after or []):
        resolved = item.get("resolved_command") or resolve_step_command(item, ctx)
        can_auto = bool(auto_execute and resolved)
        queue.append({
            "name": item["command"],
            "cmd_str": resolved if can_auto else "",
            "mode": "auto" if can_auto else "navigate",
            "role": "after",
        })
    return queue


def build_unified_warning(queue, all_cmds_by_name):
    """Construye una advertencia unificada si algún paso de la cola tiene warning configurado."""
    if not queue:
        return None
    highest_level = None
    step_lines = []
    for idx, step in enumerate(queue, 1):
        cmd_meta = all_cmds_by_name.get(step["name"]) or {}
        w = cmd_meta.get("warning")
        role_txt = "ANTES" if step["role"] == "before" else ("PRINCIPAL" if step["role"] == "main" else "DESPUÉS")
        mode_txt = "Automático" if step["mode"] == "auto" else "Abrir para configurar"
        step_lines.append(f"{idx}. [{role_txt} - {mode_txt}] {step['name']}")
        if w and isinstance(w, dict):
            lvl = w.get("level", "caution")
            if lvl == "danger":
                highest_level = "danger"
            elif highest_level is None:
                highest_level = "caution"

    if highest_level is None:
        return None

    return {
        "level": highest_level,
        "title": f"Servicio Encadenado ({len(queue)} pasos)",
        "message": (
            "Se ejecutará el siguiente plan completo en orden. "
            "Al menos uno de los pasos realiza cambios en el sistema o en tus archivos:\n\n"
            + "\n".join(step_lines)
        ),
    }
