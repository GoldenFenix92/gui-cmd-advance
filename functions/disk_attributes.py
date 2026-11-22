import argparse
import ctypes
import json
import re
import subprocess
import sys


VALID_ACTIONS = ("inspect", "clear", "set")
VALID_SCOPES = ("disk", "volume", "both")
VALID_ATTRIBUTES = ("readonly", "hidden", "nodefaultdriveletter")
DISK_SUPPORTED_ATTRIBUTES = ("readonly",)


def safe_print(text=""):
    """Imprime texto evitando errores de codificación en consolas Windows."""
    try:
        print(text, flush=True)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or "utf-8"
        safe_text = str(text).encode(enc, errors="replace").decode(enc, errors="replace")
        print(safe_text, flush=True)


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _get_oem_encoding():
    try:
        cp = ctypes.windll.kernel32.GetOEMCP()
        if cp:
            return f"cp{cp}"
    except Exception:
        pass
    return "cp850"


def _decode_windows_output(raw_bytes):
    if not raw_bytes:
        return ""
    for enc in (_get_oem_encoding(), "utf-8", "mbcs"):
        try:
            return raw_bytes.decode(enc)
        except Exception:
            continue
    return raw_bytes.decode("utf-8", errors="replace")


def _creation_flags():
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def format_size_gb(size_bytes):
    try:
        size_val = float(size_bytes)
        if size_val <= 0:
            return "Desconocido"
        gb = size_val / (1024 ** 3)
        if gb >= 1024:
            return f"{gb / 1024:.2f} TB ({gb:.1f} GB)"
        return f"{gb:.1f} GB"
    except Exception:
        return "Desconocido"


def classify_drive_type(bus_type, media_type):
    bus = (bus_type or "").strip()
    media = (media_type or "").strip()
    bus_upper = bus.upper()
    media_upper = media.upper()

    if bus_upper == "USB":
        return "Memoria USB / Disco USB"
    if media_upper == "SSD":
        return f"SSD ({bus})" if bus and bus_upper != "UNSPECIFIED" else "SSD"
    if media_upper == "HDD":
        return f"HDD ({bus})" if bus and bus_upper != "UNSPECIFIED" else "HDD"
    if bus and bus_upper not in ("UNSPECIFIED", "UNKNOWN"):
        return f"Unidad {bus}"
    return "Disco Físico"


def get_disk_metadata(disk_number):
    """Obtiene metadatos del disco (básico o dinámico) y sus particiones usando PowerShell/WMI."""
    num = int(disk_number)
    ps_script = (
        f"$num = {num}; "
        "$d = Get-Disk -Number $num -ErrorAction SilentlyContinue; "
        "$pd = Get-PhysicalDisk -ErrorAction SilentlyContinue | Where-Object { $_.DeviceId -eq [string]$num } | Select-Object -First 1; "
        "$wmi = Get-CimInstance Win32_DiskDrive -ErrorAction SilentlyContinue | Where-Object { $_.Index -eq $num } | Select-Object -First 1; "
        "if (-not $d -and -not $pd -and -not $wmi) { exit 0 }; "
        "$parts = @(); "
        "if ($d) { "
        "  $parts = @(Get-Partition -DiskNumber $num -ErrorAction SilentlyContinue | ForEach-Object { "
        "    $vol = $_ | Get-Volume -ErrorAction SilentlyContinue; "
        "    [PSCustomObject]@{ "
        "      PartitionNumber = $_.PartitionNumber; "
        "      DriveLetter = if ($_.DriveLetter) { [string]$_.DriveLetter } else { '' }; "
        "      Type = [string]$_.Type; "
        "      Size = $_.Size; "
        "      FileSystemLabel = if ($vol) { [string]$vol.FileSystemLabel } else { '' }; "
        "      FileSystem = if ($vol) { [string]$vol.FileSystem } else { '' } "
        "    } "
        "  }); "
        "}; "
        "$wmiParts = @(Get-CimInstance Win32_DiskPartition -ErrorAction SilentlyContinue | Where-Object { $_.DiskIndex -eq $num }); "
        "$isDynamic = ($null -eq $d) -and ($wmiParts | Where-Object { $_.Type -match 'Logical Disk Manager' } | Measure-Object).Count -gt 0; "
        "$friendly = if ($d -and $d.FriendlyName) { [string]$d.FriendlyName } elseif ($pd -and $pd.FriendlyName) { [string]$pd.FriendlyName } elseif ($wmi -and $wmi.Model) { [string]$wmi.Model } else { 'Disco ' + $num }; "
        "$bus = if ($d -and $d.BusType) { [string]$d.BusType } elseif ($pd -and $pd.BusType) { [string]$pd.BusType } elseif ($wmi -and $wmi.InterfaceType) { [string]$wmi.InterfaceType } else { 'Unspecified' }; "
        "$media = if ($pd -and $pd.MediaType) { [string]$pd.MediaType } else { 'Unspecified' }; "
        "$size = if ($d -and $d.Size) { $d.Size } elseif ($pd -and $pd.Size) { $pd.Size } elseif ($wmi -and $wmi.Size) { $wmi.Size } else { 0 }; "
        "$pStyle = if ($d -and $d.PartitionStyle) { [string]$d.PartitionStyle } elseif ($isDynamic) { 'Din' + [char]0x00E1 + 'mico (LDM)' } else { 'Desconocido' }; "
        "$opStatus = if ($d -and $d.OperationalStatus) { [string]$d.OperationalStatus } elseif ($pd -and $pd.OperationalStatus) { [string]$pd.OperationalStatus } elseif ($wmi -and $wmi.Status) { [string]$wmi.Status } else { 'Desconocido' }; "
        "[PSCustomObject]@{ "
        "  Number = $num; "
        "  FriendlyName = $friendly; "
        "  BusType = $bus; "
        "  MediaType = $media; "
        "  Size = $size; "
        "  PartitionStyle = $pStyle; "
        "  OperationalStatus = $opStatus; "
        "  IsDynamic = [bool]$isDynamic; "
        "  IsReadOnly = if ($d) { [bool]$d.IsReadOnly } else { $false }; "
        "  IsOffline = if ($d) { [bool]$d.IsOffline } else { $false }; "
        "  IsSystem = if ($d) { [bool]$d.IsSystem } else { $false }; "
        "  IsBoot = if ($d) { [bool]$d.IsBoot } else { $false }; "
        "  Partitions = $parts "
        "} | ConvertTo-Json -Depth 4 -Compress"
    )
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            creationflags=_creation_flags(),
            timeout=20,
        )
        raw = proc.stdout.decode("utf-8", errors="ignore").strip()
        if not raw:
            raw = proc.stdout.decode("mbcs", errors="ignore").strip()
        if not raw:
            return None
        data = json.loads(raw)
        if isinstance(data, dict):
            parts = data.get("Partitions")
            if isinstance(parts, dict):
                data["Partitions"] = [parts]
            elif parts is None:
                data["Partitions"] = []
        return data
    except Exception:
        return None


def run_diskpart_script(commands):
    """Ejecuta una lista de comandos en diskpart pasando el script por stdin."""
    script_text = "\n".join(commands) + "\nexit\n"
    try:
        proc = subprocess.run(
            ["diskpart"],
            input=script_text.encode("ascii", errors="ignore"),
            capture_output=True,
            creationflags=_creation_flags(),
            timeout=30,
        )
        stdout_text = _decode_windows_output(proc.stdout)
        stderr_text = _decode_windows_output(proc.stderr)
        combined = stdout_text
        if stderr_text.strip():
            combined = f"{stdout_text}\n{stderr_text}"
        return proc.returncode, combined
    except FileNotFoundError:
        return 1, "Error: No se encontró 'diskpart' en el sistema."
    except subprocess.TimeoutExpired:
        return 1, "Error: Tiempo de espera agotado al ejecutar diskpart."
    except Exception as e:
        return 1, f"Error ejecutando diskpart: {e}"


def _parse_yes_no(value):
    val = (value or "").strip().lower()
    if val in ("yes", "sí", "si", "true"):
        return True
    if val in ("no", "false"):
        return False
    return None


def _strip_diskpart_prompt(line):
    """Elimina uno o más prefijos 'DISKPART>' que diskpart antepone a la primera línea de salida."""
    return re.sub(r"^(?:\s*DISKPART>\s*)+", "", line or "", flags=re.IGNORECASE).strip()


def parse_disk_attributes(output):
    """Parsea la salida de 'attributes disk' en español o inglés."""
    result = {
        "current_readonly": None,
        "readonly": None,
        "boot_disk": None,
        "pagefile_disk": None,
        "hibernation_disk": None,
        "crashdump_disk": None,
        "clustered_disk": None,
        "hardware_write_protected": False,
        "raw_attributes": [],
    }

    patterns = [
        ("current_readonly", r"^(?:current\s+read[- ]?only\s+state|estado\s+actual\s+de\s+solo\s+lectura)\s*:\s*(.+)$"),
        ("readonly", r"^(?:read[- ]?only|solo\s+lectura)\s*:\s*(.+)$"),
        ("boot_disk", r"^(?:boot\s+disk|disco\s+de\s+arranque)\s*:\s*(.+)$"),
        ("pagefile_disk", r"^(?:pagefile\s+disk|disco\s+de\s+archivo\s+de\s+paginaci[oó]n)\s*:\s*(.+)$"),
        ("hibernation_disk", r"^(?:hibernation\s+file\s+disk|disco\s+de\s+archivo\s+de\s+hibernaci[oó]n)\s*:\s*(.+)$"),
        ("crashdump_disk", r"^(?:crashdump\s+disk|disco\s+de\s+volcado\s+de\s+memoria)\s*:\s*(.+)$"),
        ("clustered_disk", r"^(?:clustered\s+disk|disco\s+en\s+cl[uú]ster)\s*:\s*(.+)$"),
    ]

    for line in (output or "").splitlines():
        stripped = _strip_diskpart_prompt(line)
        if not stripped or ":" not in stripped:
            continue
        for key, pattern in patterns:
            m = re.match(pattern, stripped, flags=re.IGNORECASE)
            if m:
                parsed = _parse_yes_no(m.group(1))
                result[key] = parsed
                result["raw_attributes"].append(stripped)
                break

    if result["current_readonly"] is True and result["readonly"] is False:
        result["hardware_write_protected"] = True

    return result


def parse_volume_attributes(output):
    """Parsea la salida de 'attributes volume' en español o inglés."""
    result = {
        "readonly": None,
        "hidden": None,
        "nodefaultdriveletter": None,
        "shadowcopy": None,
        "raw_attributes": [],
    }

    patterns = [
        ("readonly", r"^(?:read[- ]?only|solo\s+lectura)\s*:\s*(.+)$"),
        ("hidden", r"^(?:hidden|oculto)\s*:\s*(.+)$"),
        (
            "nodefaultdriveletter",
            r"^(?:no\s+default\s+drive\s+letter|sin\s+letra\s+de\s+unidad\s+predeterminada)\s*:\s*(.+)$",
        ),
        ("shadowcopy", r"^(?:shadow\s+copy|instant[aá]nea)\s*:\s*(.+)$"),
    ]

    for line in (output or "").splitlines():
        stripped = _strip_diskpart_prompt(line)
        if not stripped or ":" not in stripped:
            continue
        for key, pattern in patterns:
            m = re.match(pattern, stripped, flags=re.IGNORECASE)
            if m:
                result[key] = _parse_yes_no(m.group(1))
                result["raw_attributes"].append(stripped)
                break

    return result


def parse_detail_disk_volumes(output):
    """Extrae los números de volumen y letras asociados al disco desde 'detail disk'."""
    volumes = []
    vol_pattern = re.compile(
        r"^\s*\*?\s*(?:Volume|Volumen)\s+(\d+)\s+(?:([A-Z])\s+)?(.*)$",
        flags=re.IGNORECASE,
    )
    for line in (output or "").splitlines():
        cleaned = _strip_diskpart_prompt(line)
        m = vol_pattern.match(cleaned)
        if not m:
            continue
        vol_num = int(m.group(1))
        letter = (m.group(2) or "").upper()
        rest = m.group(3).strip()
        volumes.append({
            "volume_number": vol_num,
            "drive_letter": letter,
            "summary": rest,
            "raw_line": cleaned,
        })
    return volumes


def get_disk_volumes_via_diskpart(disk_number):
    rc, output = run_diskpart_script([f"select disk {int(disk_number)}", "detail disk"])
    if rc != 0 and not output:
        return []
    return parse_detail_disk_volumes(output)


def _bool_label(val):
    if val is True:
        return "SÍ (Activo)"
    if val is False:
        return "NO"
    return "Desconocido"


def build_diskpart_commands(disk_number, action, scope, attribute, target_volumes=None):
    """Construye la lista de comandos diskpart para modificar atributos."""
    cmds = []
    disk_num = int(disk_number)

    if scope in ("disk", "both") and attribute in DISK_SUPPORTED_ATTRIBUTES:
        cmds.append(f"select disk {disk_num}")
        cmds.append(f"attributes disk {action} {attribute}")

    if scope in ("volume", "both"):
        for vol in (target_volumes or []):
            cmds.append(f"select volume {vol}")
            cmds.append(f"attributes volume {action} {attribute}")

    return cmds


def inspect_disk(disk_number, metadata=None):
    """Muestra un reporte completo del disco y sus atributos."""
    if metadata is None:
        metadata = get_disk_metadata(disk_number)

    safe_print("=" * 68)
    safe_print(f"  INSPECCIÓN DE ATRIBUTOS - DISCO {disk_number}")
    safe_print("=" * 68)

    if metadata:
        drive_type = classify_drive_type(metadata.get("BusType"), metadata.get("MediaType"))
        safe_print(f"  Modelo             : {metadata.get('FriendlyName', 'Desconocido')}")
        safe_print(f"  Tipo de Unidad     : {drive_type}")
        safe_print(f"  Capacidad          : {format_size_gb(metadata.get('Size', 0))}")
        safe_print(f"  Estilo Partición   : {metadata.get('PartitionStyle', 'Desconocido')}")
        safe_print(f"  Estado Operativo   : {metadata.get('OperationalStatus', 'Desconocido')}")
        flags = []
        if metadata.get("IsSystem"):
            flags.append("SISTEMA")
        if metadata.get("IsBoot"):
            flags.append("ARRANQUE")
        if metadata.get("IsOffline"):
            flags.append("OFFLINE")
        if metadata.get("IsReadOnly"):
            flags.append("SOLO LECTURA")
        safe_print(f"  Banderas Windows   : {', '.join(flags) if flags else 'Normal'}")
    else:
        safe_print("  [Aviso] No se pudieron leer los metadatos vía PowerShell. Consultando directamente con Diskpart...")

    safe_print("\n[1] Atributos del Disco (diskpart -> attributes disk)")
    safe_print("-" * 68)
    rc, dp_out = run_diskpart_script([f"select disk {int(disk_number)}", "attributes disk"])
    disk_attrs = parse_disk_attributes(dp_out)

    if disk_attrs["raw_attributes"]:
        safe_print(f"  Estado actual de solo lectura : {_bool_label(disk_attrs['current_readonly'])}")
        safe_print(f"  Atributo Solo Lectura (Disk)  : {_bool_label(disk_attrs['readonly'])}")
        if disk_attrs["hardware_write_protected"]:
            wp_summary = "SÍ (Bloqueo físico / hardware)"
        elif disk_attrs["readonly"] is True or disk_attrs["current_readonly"] is True:
            wp_summary = "SÍ (Protegido contra escritura por software - se puede quitar con 'clear readonly')"
        elif disk_attrs["current_readonly"] is False and disk_attrs["readonly"] is False:
            wp_summary = "NO (Escritura habilitada)"
        else:
            wp_summary = "Desconocido"
        safe_print(f"  Protección contra escritura   : {wp_summary}")
        if disk_attrs["boot_disk"] is not None:
            safe_print(f"  Disco de arranque             : {_bool_label(disk_attrs['boot_disk'])}")
        if disk_attrs["pagefile_disk"] is not None:
            safe_print(f"  Archivo de paginación         : {_bool_label(disk_attrs['pagefile_disk'])}")
        if disk_attrs["hibernation_disk"] is not None:
            safe_print(f"  Archivo de hibernación        : {_bool_label(disk_attrs['hibernation_disk'])}")
        if disk_attrs["crashdump_disk"] is not None:
            safe_print(f"  Volcado de memoria            : {_bool_label(disk_attrs['crashdump_disk'])}")
        if disk_attrs["clustered_disk"] is not None:
            safe_print(f"  Disco en clúster              : {_bool_label(disk_attrs['clustered_disk'])}")
    else:
        safe_print("  No se pudieron interpretar los atributos del disco. Salida de Diskpart:")
        safe_print(dp_out.strip())

    if disk_attrs["hardware_write_protected"]:
        safe_print("\n  [!] DIAGNÓSTICO DE BLOQUEO POR HARDWARE DETECTADO:")
        safe_print("      'Estado actual de solo lectura' está en SÍ, pero el atributo lógico 'Solo lectura' está en NO.")
        safe_print("      Esto indica que la unidad (USB/SD/SSD) tiene protección contra escritura física")
        safe_print("      (interruptor físico bloqueado o controlador flash en modo de solo lectura por fallo).")
        safe_print("      Ningún comando de software podrá desactivar un bloqueo físico/controlador dañado.")

    safe_print("\n[2] Volúmenes Asociados y sus Atributos (diskpart -> attributes volume)")
    safe_print("-" * 68)
    volumes = get_disk_volumes_via_diskpart(disk_number)
    if not volumes:
        safe_print("  No se encontraron volúmenes montados o reconocidos en este disco.")
    else:
        for vol in volumes:
            vol_num = vol["volume_number"]
            letter_str = f"{vol['drive_letter']}:\\" if vol["drive_letter"] else "(Sin letra)"
            _, vol_out = run_diskpart_script([f"select volume {vol_num}", "attributes volume"])
            v_attrs = parse_volume_attributes(vol_out)
            safe_print(f"  • Volumen {vol_num} [{letter_str}] — {vol['summary']}")
            if v_attrs["raw_attributes"]:
                safe_print(
                    f"      Solo Lectura: {_bool_label(v_attrs['readonly'])} | "
                    f"Oculto: {_bool_label(v_attrs['hidden'])} | "
                    f"Sin letra auto: {_bool_label(v_attrs['nodefaultdriveletter'])}"
                )
            else:
                safe_print("      (Sin atributos de volumen legibles)")

    safe_print("=" * 68)
    return rc


def modify_attributes(disk_number, action, scope, attribute, volume_letter=None, metadata=None):
    """Aplica o quita atributos de disco y/o volumen mediante diskpart."""
    if action not in ("clear", "set"):
        safe_print(f"[ERROR] Acción inválida: {action}")
        return 1
    if scope not in VALID_SCOPES:
        safe_print(f"[ERROR] Ámbito inválido: {scope}")
        return 1
    if attribute not in VALID_ATTRIBUTES:
        safe_print(f"[ERROR] Atributo inválido: {attribute}")
        return 1

    # Validar compatibilidad atributo <-> ámbito
    if scope == "disk" and attribute not in DISK_SUPPORTED_ATTRIBUTES:
        safe_print(
            f"[AVISO] El atributo '{attribute}' NO existe a nivel de disco completo en Diskpart.\n"
            f"        En Diskpart, 'attributes disk' solo soporta el atributo 'readonly'.\n"
            f"        Para gestionar '{attribute}', selecciona el ámbito 'Solo Volúmenes del disco (attributes volume)'."
        )
        return 1

    if metadata is None:
        metadata = get_disk_metadata(disk_number)

    if metadata is None:
        safe_print(f"[ERROR] No se encontró el Disco {disk_number}. Verifica que la unidad esté conectada.")
        return 1

    # Protección contra bloqueo accidental del disco del sistema operativo
    if action == "set" and (metadata.get("IsSystem") or metadata.get("IsBoot")):
        safe_print("=" * 68)
        safe_print("  [BLOQUEADO POR SEGURIDAD]")
        safe_print(f"  El Disco {disk_number} ({metadata.get('FriendlyName', '')}) contiene el sistema operativo o arranque.")
        safe_print(f"  No se permite aplicar 'set {attribute}' sobre la unidad del sistema para evitar dejar Windows inoperable.")
        safe_print("  (Solo se permite Inspeccionar o Quitar solo lectura 'clear readonly').")
        safe_print("=" * 68)
        return 1

    # Resolver volúmenes objetivo si el ámbito incluye volumen
    target_volumes = []
    if scope in ("volume", "both"):
        disk_volumes = get_disk_volumes_via_diskpart(disk_number)
        if volume_letter:
            clean_letter = volume_letter.strip().rstrip(":\\").upper()
            matched = [v["volume_number"] for v in disk_volumes if v["drive_letter"] == clean_letter]
            if not matched:
                safe_print(
                    f"[ERROR] No se encontró la letra '{clean_letter}:' en el Disco {disk_number}.\n"
                    f"        Usa primero la acción 'Leer / Inspeccionar atributos actuales' para ver los volúmenes disponibles."
                )
                return 1
            target_volumes = matched
        else:
            target_volumes = [v["volume_number"] for v in disk_volumes]
            if not target_volumes and scope == "volume":
                safe_print(f"[AVISO] El Disco {disk_number} no tiene volúmenes detectados por Diskpart.")
                return 1

    if scope == "both" and attribute not in DISK_SUPPORTED_ATTRIBUTES:
        safe_print(
            f"[INFO] El atributo '{attribute}' solo aplica a volúmenes; se omitirá 'attributes disk' y se aplicará a los volúmenes del Disco {disk_number}."
        )

    commands = build_diskpart_commands(
        disk_number=disk_number,
        action=action,
        scope=scope,
        attribute=attribute,
        target_volumes=target_volumes,
    )

    if not commands:
        safe_print("[AVISO] No se generaron comandos para ejecutar.")
        return 1

    safe_print("=" * 68)
    safe_print(f"  EJECUTANDO DISKPART EN DISCO {disk_number} ({metadata.get('FriendlyName', '')})")
    safe_print("=" * 68)
    safe_print("  Comandos enviados a Diskpart:")
    for cmd in commands:
        safe_print(f"    DISKPART> {cmd}")
    safe_print("-" * 68)

    rc, output = run_diskpart_script(commands)

    # Mostrar salida relevante de diskpart (filtrando banner inicial repetitivo)
    cleaned_lines = []
    for line in output.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("Microsoft DiskPart") or s.startswith("Copyright (C)") or s.startswith("On computer:") or s.startswith("En el equipo:"):
            continue
        cleaned_lines.append(s)

    for line in cleaned_lines:
        safe_print(f"  {line}")

    if rc == 0:
        safe_print("\n[OK] Operación de Diskpart completada. Verificando estado actual...\n")
    else:
        safe_print(f"\n[ERROR] Diskpart finalizó con código {rc}. Revisa el mensaje anterior.\n")

    inspect_disk(disk_number, metadata=get_disk_metadata(disk_number))
    return rc


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Gestor de atributos de discos duros (HDD), SSD y memorias USB mediante Diskpart."
    )
    parser.add_argument("--disk", required=True, help="Número de disco físico (ej. 0, 1, 2).")
    parser.add_argument(
        "--action",
        default="inspect",
        choices=VALID_ACTIONS,
        help="Acción a realizar: inspect (leer), clear (quitar), set (colocar).",
    )
    parser.add_argument(
        "--scope",
        default="disk",
        choices=VALID_SCOPES,
        help="Ámbito del cambio: disk, volume o both.",
    )
    parser.add_argument(
        "--attr",
        default="readonly",
        choices=VALID_ATTRIBUTES,
        help="Atributo a modificar: readonly, hidden o nodefaultdriveletter.",
    )
    parser.add_argument(
        "--volume",
        default="",
        help="Letra de volumen específica (opcional, ej. E).",
    )

    args, _ = parser.parse_known_args(argv)

    if not is_admin():
        safe_print("[ADVERTENCIA] Esta herramienta requiere privilegios de Administrador para ejecutar Diskpart.")

    try:
        disk_num = int(str(args.disk).strip().split()[0])
    except ValueError:
        safe_print(f"[ERROR] Número de disco inválido: '{args.disk}'. Selecciona un disco válido.")
        sys.exit(1)

    if args.action == "inspect":
        rc = inspect_disk(disk_num)
    else:
        rc = modify_attributes(
            disk_number=disk_num,
            action=args.action,
            scope=args.scope,
            attribute=args.attr,
            volume_letter=args.volume,
        )

    sys.exit(rc)


if __name__ == "__main__":
    main()
