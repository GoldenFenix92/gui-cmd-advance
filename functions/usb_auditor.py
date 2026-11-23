import argparse
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import time
import zlib

from functions.task_memory import TaskMemory
from functions.utils import safe_print

for _stream in (sys.stdout, sys.stderr):
    if _stream is not None and hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

# Base de Vendor IDs (VID) oficiales USB-IF de fabricantes reconocidos
KNOWN_USB_VENDORS = {
    "0781": "SanDisk / Western Digital",
    "0951": "Kingston Technology",
    "04E8": "Samsung Electronics",
    "0930": "Toshiba / Kioxia",
    "054C": "Sony",
    "1B1C": "Corsair",
    "154B": "PNY Technologies",
    "05DC": "Lexar Media",
    "8564": "Transcend Information",
    "18A5": "Verbatim",
    "125F": "ADATA Technology",
    "03F0": "HP Inc.",
    "0634": "Micron / Crucial",
    "0BC2": "Seagate Technology",
    "1058": "Western Digital",
    "0480": "Toshiba America",
    "0BDA": "Realtek Semiconductor (Lector/Puente)",
    "174C": "ASMedia Technology (Puente SATA/NVMe-USB)",
    "152D": "JMicron Technology (Puente SATA/NVMe-USB)",
    "090C": "Silicon Motion (Controlador OEM)",
    "13FE": "Phison Electronics (Controlador OEM)",
    "1F75": "Innostor Technology (Controlador OEM)",
}

# VIDs de controladores genéricos o inválidos frecuentes en memorias USB falsificadas
GENERIC_CONTROLLER_VIDS = {
    "0000": "VID nulo (0000) — Altamente sospechoso",
    "FFFF": "VID inválido (FFFF) — Altamente sospechoso",
    "ABCD": "VID de prueba/genérico (ABCD)",
    "048D": "Integrated Technology Express / Chipsbank genérico",
    "058F": "Alcor Micro (controlador genérico frecuente en clones)",
    "1E3D": "Chipsbank Microelectronics (controlador genérico frecuente en clones)",
    "1221": "Flash Disk genérico (sin fabricante)",
    "1908": "GEMBIRD / Genérico",
    "2009": "Genérico sin registrar",
    "AAAA": "MXT / Genérico (frecuente en clones)",
}

# Mapeo marca declarada -> VIDs esperados (si es pendrive directo de esa marca)
BRAND_EXPECTED_VIDS = {
    "sandisk": {"0781", "1058"},
    "kingston": {"0951", "13FE", "090C"},
    "samsung": {"04E8"},
    "toshiba": {"0930", "0480"},
    "kioxia": {"0930"},
    "corsair": {"1B1C", "13FE"},
    "pny": {"154B", "13FE", "090C"},
    "lexar": {"05DC", "090C"},
    "transcend": {"8564", "090C"},
    "adata": {"125F", "090C", "1F75"},
    "sony": {"054C"},
    "verbatim": {"18A5", "13FE"},
    "seagate": {"0BC2"},
    "western digital": {"1058", "0781"},
    "crucial": {"0634"},
}

SUSPICIOUS_SERIAL_PATTERNS = (
    r"^0+$",
    r"^f+$",
    r"^12345678",
    r"^aa0{6,}",
    r"^20090815198100000",
    r"^(?:0123456789|abcdef)",
)

BLOCK_MAGIC = b"GCAUSB01"
BLOCK_SIZE = 1024 * 1024  # 1 MiB
MAX_FILE_MB = 256


def _creation_flags():
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def parse_vid_pid(pnp_id):
    """Extrae (VID, PID) en mayúsculas de una cadena PnP como USB\\VID_0951&PID_1666\\..."""
    if not pnp_id:
        return None, None
    m = re.search(r"VID_([0-9A-Fa-f]{4})&PID_([0-9A-Fa-f]{4})", str(pnp_id), flags=re.IGNORECASE)
    if not m:
        return None, None
    return m.group(1).upper(), m.group(2).upper()


def is_suspicious_serial(serial):
    s = (serial or "").strip()
    if not s or len(s) < 6:
        return True, "Número de serie ausente o demasiado corto"
    low = s.lower()
    if len(set(low)) <= 2:
        return True, f"Número de serie repetitivo ('{s}')"
    for pat in SUSPICIOUS_SERIAL_PATTERNS:
        if re.match(pat, low):
            return True, f"Número de serie genérico/clonado ('{s}')"
    return False, ""


def format_capacity(size_bytes):
    try:
        b = float(size_bytes)
        if b <= 0:
            return "0 GB"
        gb_dec = b / 1e9
        gib_bin = b / (1024 ** 3)
        return f"{gib_bin:.2f} GiB ({gb_dec:.1f} GB comerciales)"
    except Exception:
        return "Desconocido"


def evaluate_hardware_authenticity(info):
    """Evalúa la autenticidad a partir de metadatos de hardware (VID/PID, marca, serie, capacidad)."""
    findings_ok = []
    warnings = []
    critical = []

    model = (info.get("FriendlyName") or info.get("Model") or "").strip()
    bus = (info.get("BusType") or info.get("InterfaceType") or "").strip().upper()
    media = (info.get("MediaType") or "").strip().upper()
    serial = (info.get("SerialNumber") or "").strip()
    size_bytes = int(info.get("Size") or 0)
    vid = (info.get("VID") or "").upper()
    pid = (info.get("PID") or "").upper()
    is_usb = bus == "USB" or bool(vid)

    vendor_name = KNOWN_USB_VENDORS.get(vid) or GENERIC_CONTROLLER_VIDS.get(vid) or ("Desconocido" if vid else "N/A (Bus interno)")

    if is_usb:
        if vid in GENERIC_CONTROLLER_VIDS:
            warnings.append(f"VID {vid} corresponde a un controlador genérico/sospechoso: {GENERIC_CONTROLLER_VIDS[vid]}.")
        elif vid in KNOWN_USB_VENDORS:
            findings_ok.append(f"VID {vid} reconocido oficialmente: {KNOWN_USB_VENDORS[vid]}.")
        elif vid:
            warnings.append(f"VID {vid} (PID {pid}) no está en la lista de fabricantes principales USB-IF.")
        else:
            warnings.append("No se pudo leer el VID/PID USB del dispositivo (puede estar detrás de un puente o sin controlador padre).")

        # Detectar Brand Spoofing
        model_lower = model.lower()
        for brand, expected_vids in BRAND_EXPECTED_VIDS.items():
            if brand in model_lower and vid:
                if vid in expected_vids:
                    findings_ok.append(f"La marca declarada ('{brand.title()}') coincide con el VID de hardware ({vid}).")
                elif vid in GENERIC_CONTROLLER_VIDS:
                    critical.append(
                        f"Posible suplantación de marca (Brand Spoofing): el dispositivo se anuncia como '{model}', "
                        f"pero su VID real ({vid}) pertenece a un controlador genérico ({GENERIC_CONTROLLER_VIDS[vid]})."
                    )
                else:
                    warnings.append(
                        f"Discrepancia de marca: el modelo dice '{model}', pero el VID real es {vid} ({vendor_name})."
                    )
                break

        # Detectar capacidad inflada típica de estafas en pendrives flash
        tb = size_bytes / 1e12
        if tb >= 1.9 and (vid in GENERIC_CONTROLLER_VIDS or not vid) and media != "HDD":
            critical.append(
                f"Capacidad altamente sospechosa ({tb:.2f} TB) combinada con controlador genérico ({vid or 'desconocido'}). "
                "Es un patrón muy común en memorias USB falsificadas."
            )
    else:
        findings_ok.append(f"Unidad conectada por bus interno ({bus or 'SATA/NVMe'} | Tipo: {media or 'Disco'}).")

    bad_serial, serial_reason = is_suspicious_serial(serial)
    if bad_serial:
        warnings.append(serial_reason + ".")
    else:
        findings_ok.append(f"Número de serie válido y estructurado ({serial}).")

    if info.get("IsOffline"):
        warnings.append("La unidad se encuentra actualmente Fuera de Línea (Offline).")
    if info.get("IsReadOnly"):
        warnings.append("La unidad tiene activo el atributo de Solo Lectura.")

    if critical:
        verdict = "ALTA PROBABILIDAD DE FALSIFICACIÓN"
    elif len(warnings) >= 2:
        verdict = "SOSPECHOSO / REVISAR"
    elif warnings:
        verdict = "CONSISTENTE CON OBSERVACIONES"
    else:
        verdict = "ORIGINAL / CONSISTENTE"

    return {
        "verdict": verdict,
        "vendor_name": vendor_name,
        "findings_ok": findings_ok,
        "warnings": warnings,
        "critical": critical,
        "is_usb": is_usb,
    }


def list_all_storage_units():
    """Consulta todas las unidades de almacenamiento (USB, HDD, SSD, Online y Offline)."""
    ps_script = (
        "$pDisks = @{}; try { Get-PhysicalDisk -ErrorAction SilentlyContinue | ForEach-Object { $pDisks[[string]$_.DeviceId] = $_ } } catch {}; "
        "$msftDisks = @{}; try { Get-Disk -ErrorAction SilentlyContinue | ForEach-Object { $msftDisks[[string]$_.Number] = $_ } } catch {}; "
        "$wmiDisks = @{}; try { Get-CimInstance Win32_DiskDrive -ErrorAction SilentlyContinue | ForEach-Object { $wmiDisks[[string]$_.Index] = $_ } } catch {}; "
        "$allIds = @($pDisks.Keys + $msftDisks.Keys + $wmiDisks.Keys) | Sort-Object { [int]$_ } -Unique; "
        "$res = foreach ($id in $allIds) { "
        "  $d = $msftDisks[$id]; $pd = $pDisks[$id]; $wmi = $wmiDisks[$id]; "
        "  $pnp = if ($wmi) { [string]$wmi.PNPDeviceID } else { '' }; "
        "  $usbParent = ''; "
        "  if ($pnp) { "
        "    $curr = $pnp; "
        "    for ($lvl = 0; $lvl -lt 4; $lvl++) { "
        "      if ($curr -match 'VID_[0-9A-Fa-f]{4}&PID_[0-9A-Fa-f]{4}') { $usbParent = $curr; break }; "
        "      $nxt = (Get-PnpDeviceProperty -InstanceId $curr -KeyName 'DEVPKEY_Device_Parent' -ErrorAction SilentlyContinue).Data; "
        "      if (-not $nxt) { break }; "
        "      $curr = [string]$nxt "
        "    } "
        "  }; "
        "  $busDesc = if ($usbParent) { [string](Get-PnpDeviceProperty -InstanceId $usbParent -KeyName 'DEVPKEY_Device_BusReportedDeviceDesc' -ErrorAction SilentlyContinue).Data } else { '' }; "
        "  $drvMfr = if ($usbParent) { [string](Get-PnpDeviceProperty -InstanceId $usbParent -KeyName 'DEVPKEY_Device_Manufacturer' -ErrorAction SilentlyContinue).Data } else { '' }; "
        "  $vols = @(); "
        "  try { "
        "    $vols = @(Get-Partition -DiskNumber ([int]$id) -ErrorAction SilentlyContinue | Get-Volume -ErrorAction SilentlyContinue | ForEach-Object { "
        "      [PSCustomObject]@{ DriveLetter = if ($_.DriveLetter) { [string]$_.DriveLetter } else { '' }; Label = [string]$_.FileSystemLabel; FileSystem = [string]$_.FileSystem; Size = $_.Size; SizeRemaining = $_.SizeRemaining; Health = [string]$_.HealthStatus } "
        "    }) "
        "  } catch {}; "
        "  [PSCustomObject]@{ "
        "    Number = [int]$id; "
        "    FriendlyName = if ($d -and $d.FriendlyName) { [string]$d.FriendlyName } elseif ($pd -and $pd.FriendlyName) { [string]$pd.FriendlyName } elseif ($wmi) { [string]$wmi.Model } else { 'Disco ' + $id }; "
        "    Model = if ($wmi) { [string]$wmi.Model } else { '' }; "
        "    BusType = if ($d -and $d.BusType) { [string]$d.BusType } elseif ($pd -and $pd.BusType) { [string]$pd.BusType } elseif ($wmi) { [string]$wmi.InterfaceType } else { 'Unspecified' }; "
        "    MediaType = if ($pd -and $pd.MediaType) { [string]$pd.MediaType } else { 'Unspecified' }; "
        "    Size = if ($d -and $d.Size) { $d.Size } elseif ($pd -and $pd.Size) { $pd.Size } elseif ($wmi) { $wmi.Size } else { 0 }; "
        "    SerialNumber = if ($d -and $d.SerialNumber) { ([string]$d.SerialNumber).Trim() } elseif ($pd -and $pd.SerialNumber) { ([string]$pd.SerialNumber).Trim() } elseif ($wmi) { ([string]$wmi.SerialNumber).Trim() } else { '' }; "
        "    FirmwareRevision = if ($d -and $d.FirmwareVersion) { [string]$d.FirmwareVersion } elseif ($pd -and $pd.FirmwareVersion) { [string]$pd.FirmwareVersion } elseif ($wmi) { [string]$wmi.FirmwareRevision } else { '' }; "
        "    PartitionStyle = if ($d -and $d.PartitionStyle) { [string]$d.PartitionStyle } else { 'Dinamico/Desconocido' }; "
        "    OperationalStatus = if ($d -and $d.OperationalStatus) { [string]$d.OperationalStatus } elseif ($pd) { [string]$pd.OperationalStatus } elseif ($wmi) { [string]$wmi.Status } else { 'Desconocido' }; "
        "    HealthStatus = if ($pd -and $pd.HealthStatus) { [string]$pd.HealthStatus } else { 'Desconocido' }; "
        "    IsOffline = if ($d) { [bool]$d.IsOffline } else { $false }; "
        "    IsReadOnly = if ($d) { [bool]$d.IsReadOnly } else { $false }; "
        "    IsSystem = if ($d) { [bool]$d.IsSystem } else { $false }; "
        "    IsBoot = if ($d) { [bool]$d.IsBoot } else { $false }; "
        "    PNPDeviceID = $pnp; "
        "    USBParentID = $usbParent; "
        "    BusReportedDesc = $busDesc; "
        "    DriverManufacturer = $drvMfr; "
        "    Volumes = $vols "
        "  } "
        "}; "
        "@($res) | ConvertTo-Json -Depth 5 -Compress"
    )
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            creationflags=_creation_flags(),
            timeout=25,
        )
        raw = proc.stdout.decode("utf-8", errors="ignore").strip() or proc.stdout.decode("mbcs", errors="ignore").strip()
        if not raw:
            return []
        data = json.loads(raw)
        units = data if isinstance(data, list) else [data]
        for u in units:
            vid, pid = parse_vid_pid(u.get("USBParentID") or u.get("PNPDeviceID"))
            u["VID"] = vid or ""
            u["PID"] = pid or ""
            vols = u.get("Volumes")
            if isinstance(vols, dict):
                u["Volumes"] = [vols]
            elif vols is None:
                u["Volumes"] = []
        return units
    except Exception:
        return []


def _make_signed_block(block_index, nonce_bytes, block_size=BLOCK_SIZE):
    """Genera un bloque de 1 MiB determinista con firma única + índice + CRC32."""
    # Cabecera de 24 bytes: MAGIC(8) + block_index(Q=8) + nonce(4) + crc32(I=4)
    # Patrón repetitivo rápido pero único por bloque (evita compresión trivial y detecta wrap-around)
    seed = struct.pack("<QI", block_index, struct.unpack("<I", nonce_bytes)[0])
    pattern = (seed * 86)[:1024]  # 1 KiB único por bloque
    payload_len = block_size - 24
    payload = (pattern * ((payload_len // len(pattern)) + 1))[:payload_len]
    crc = zlib.crc32(seed + payload) & 0xFFFFFFFF
    header = BLOCK_MAGIC + struct.pack("<Q4sI", block_index, nonce_bytes, crc)
    return header + payload


def _verify_signed_block(data, expected_index, expected_nonce):
    if len(data) < 24:
        return False, "Bloque incompleto/truncado"
    if data[:8] != BLOCK_MAGIC:
        return False, "Firma mágica corrupta (posible sobrescritura en bucle / wrap-around)"
    idx, nonce, stored_crc = struct.unpack("<Q4sI", data[8:24])
    if idx != expected_index:
        return False, f"Índice sobrescrito (esperado bloque #{expected_index}, leído bloque #{idx} — CAPACIDAD INFLADA)"
    if nonce != expected_nonce:
        return False, "Nonce inválido (datos de otra sesión o corruptos)"
    seed = struct.pack("<QI", idx, struct.unpack("<I", nonce)[0])
    calc_crc = zlib.crc32(seed + data[24:]) & 0xFFFFFFFF
    if calc_crc != stored_crc:
        return False, "Checksum CRC32 inválido (corrupción de datos)"
    return True, ""


def run_capacity_test(root_dir, mode="quick", max_mb_override=None, block_size=BLOCK_SIZE):
    """
    Ejecuta prueba de escritura y lectura verificada en espacio libre (sin tocar archivos del usuario).
    mode='quick': 64 MB | mode='full': todo el espacio libre dejando 64 MB de margen.
    """
    audit_dir = os.path.join(root_dir, "_usb_audit_tmp")
    nonce_bytes = os.urandom(4)

    usage = shutil.disk_usage(root_dir)
    free_mb = int(usage.free // block_size)

    if max_mb_override is not None:
        target_blocks = max(1, min(int(max_mb_override), max(1, free_mb)))
    elif mode == "quick":
        target_blocks = min(64, max(0, free_mb - 8))
    else:
        target_blocks = max(0, free_mb - 64)

    if target_blocks <= 0:
        return {
            "status": "skipped",
            "reason": f"Espacio libre insuficiente en {root_dir} ({free_mb} MB disponibles).",
        }

    os.makedirs(audit_dir, exist_ok=True)
    created_files = []
    written_blocks = 0
    verified_blocks = 0
    first_corrupt_block = None
    corrupt_reason = ""
    write_mb_s = 0.0
    read_mb_s = 0.0
    aborted = False

    try:
        safe_print(f"\n[FASE 1/2] Escribiendo {target_blocks} MB de bloques firmados en {audit_dir}...")
        t_write_start = time.perf_counter()

        file_idx = 0
        while written_blocks < target_blocks:
            blocks_in_file = min(MAX_FILE_MB, target_blocks - written_blocks)
            fpath = os.path.join(audit_dir, f"audit_{file_idx:04d}.bin")
            created_files.append((fpath, written_blocks, blocks_in_file))
            with open(fpath, "wb") as f:
                for _ in range(blocks_in_file):
                    blk = _make_signed_block(written_blocks, nonce_bytes, block_size=block_size)
                    f.write(blk)
                    written_blocks += 1
                    pct = int((written_blocks / (target_blocks * 2)) * 100)
                    if written_blocks % 8 == 0 or written_blocks == target_blocks:
                        safe_print(f"Progreso Total: {pct}%\r", end="", flush=True)
                    if TaskMemory.check_pause_signal():
                        aborted = True
                        break
                f.flush()
                os.fsync(f.fileno())
            file_idx += 1
            if aborted:
                break

        write_elapsed = max(0.001, time.perf_counter() - t_write_start)
        write_mb_s = (written_blocks * (block_size / (1024 * 1024))) / write_elapsed
        safe_print(f"\n  Escritura completada: {written_blocks} MB en {write_elapsed:.2f}s ({write_mb_s:.2f} MB/s)")

        if aborted:
            return {
                "status": "aborted",
                "written_mb": written_blocks,
                "verified_mb": 0,
                "write_mb_s": round(write_mb_s, 2),
                "read_mb_s": 0.0,
            }

        safe_print(f"\n[FASE 2/2] Verificando integridad de {written_blocks} MB leídos desde el inicio...")
        t_read_start = time.perf_counter()

        for fpath, start_block, count in created_files:
            if first_corrupt_block is not None or aborted:
                break
            with open(fpath, "rb") as f:
                for offset in range(count):
                    expected_idx = start_block + offset
                    data = f.read(block_size)
                    ok_blk, reason = _verify_signed_block(data, expected_idx, nonce_bytes)
                    if not ok_blk:
                        first_corrupt_block = expected_idx
                        corrupt_reason = reason
                        break
                    verified_blocks += 1
                    pct = int(((written_blocks + verified_blocks) / (written_blocks * 2)) * 100)
                    if verified_blocks % 8 == 0 or verified_blocks == written_blocks:
                        safe_print(f"Progreso Total: {pct}%\r", end="", flush=True)
                    if TaskMemory.check_pause_signal():
                        aborted = True
                        break

        read_elapsed = max(0.001, time.perf_counter() - t_read_start)
        read_mb_s = (max(1, verified_blocks) * (block_size / (1024 * 1024))) / read_elapsed
        safe_print(f"\n  Lectura verificada: {verified_blocks}/{written_blocks} MB en {read_elapsed:.2f}s ({read_mb_s:.2f} MB/s)")

        if first_corrupt_block is not None:
            return {
                "status": "fake_detected",
                "written_mb": written_blocks,
                "verified_mb": verified_blocks,
                "first_corrupt_mb": first_corrupt_block,
                "corrupt_reason": corrupt_reason,
                "write_mb_s": round(write_mb_s, 2),
                "read_mb_s": round(read_mb_s, 2),
            }

        return {
            "status": "verified",
            "written_mb": written_blocks,
            "verified_mb": verified_blocks,
            "write_mb_s": round(write_mb_s, 2),
            "read_mb_s": round(read_mb_s, 2),
        }
    except Exception as e:
        return {"status": "error", "reason": str(e)}
    finally:
        # Limpiar siempre la carpeta temporal de prueba sin tocar archivos del usuario
        try:
            if os.path.exists(audit_dir):
                shutil.rmtree(audit_dir, ignore_errors=True)
        except Exception:
            pass


def audit_disk(disk_number, mode="hardware", units=None):
    if units is None:
        units = list_all_storage_units()

    target = next((u for u in units if int(u.get("Number", -1)) == int(disk_number)), None)
    if target is None:
        safe_print(f"[ERROR] No se encontró la unidad de disco #{disk_number}. Verifica que esté conectada.")
        return 1

    hw_eval = evaluate_hardware_authenticity(target)

    safe_print("=" * 72)
    safe_print(f"  AUDITORÍA DE AUTENTICIDAD DE UNIDAD - DISCO {disk_number}")
    safe_print("=" * 72)
    safe_print(f"  Modelo             : {target.get('FriendlyName', 'Desconocido')}")
    safe_print(f"  Tipo de Unidad     : {target.get('MediaType', 'Unspecified')} ({target.get('BusType', 'Unspecified')})")
    safe_print(f"  Capacidad          : {format_capacity(target.get('Size', 0))}")
    safe_print(f"  Estilo Partición   : {target.get('PartitionStyle', 'Desconocido')}")
    safe_print(f"  Estado Operativo   : {target.get('OperationalStatus', 'Desconocido')} ({'Offline' if target.get('IsOffline') else 'Online'})")
    safe_print(f"  Salud Reportada    : {target.get('HealthStatus', 'Desconocido')}")
    safe_print(f"  Número de Serie    : {target.get('SerialNumber') or '(No reportado)'}")
    safe_print(f"  Firmware           : {target.get('FirmwareRevision') or '(No reportado)'}")
    if target.get("VID") or hw_eval["is_usb"]:
        vid_pid = f"VID_{target.get('VID') or '????'} & PID_{target.get('PID') or '????'}"
        safe_print(f"  VID / PID USB      : {vid_pid} ({hw_eval['vendor_name']})")
        if target.get("BusReportedDesc"):
            safe_print(f"  Descriptor USB     : {target['BusReportedDesc']}")
        if target.get("DriverManufacturer"):
            safe_print(f"  Fabricante Driver  : {target['DriverManufacturer']}")

    vols = target.get("Volumes") or []
    safe_print("\n[1] Volúmenes Detectados")
    safe_print("-" * 72)
    mounted_letter = None
    if not vols:
        safe_print("  Sin volúmenes montados (unidad sin letra, RAW u Offline).")
    else:
        for v in vols:
            ltr = f"{v['DriveLetter']}:\\" if v.get("DriveLetter") else "(Sin letra)"
            if v.get("DriveLetter") and not mounted_letter:
                mounted_letter = f"{v['DriveLetter']}:\\"
            lbl = v.get("Label") or "Sin etiqueta"
            fs = v.get("FileSystem") or "RAW"
            free_gb = round((v.get("SizeRemaining") or 0) / (1024 ** 3), 2)
            tot_gb = round((v.get("Size") or 0) / (1024 ** 3), 2)
            safe_print(f"  • {ltr} [{lbl}] — {fs} | Libre: {free_gb} GiB / {tot_gb} GiB | Salud: {v.get('Health', 'N/D')}")

    safe_print("\n[2] Análisis de Identidad y Hardware")
    safe_print("-" * 72)
    for ok_msg in hw_eval["findings_ok"]:
        safe_print(f"  [OK] {ok_msg}")
    for warn_msg in hw_eval["warnings"]:
        safe_print(f"  [WARN] {warn_msg}")
    for crit_msg in hw_eval["critical"]:
        safe_print(f"  [ERROR] {crit_msg}")

    final_verdict = hw_eval["verdict"]

    if mode in ("quick", "full"):
        safe_print(f"\n[3] Prueba Real de Capacidad y Velocidad (Modo: {mode.upper()})")
        safe_print("-" * 72)
        if target.get("IsOffline"):
            safe_print("  [WARN] La unidad está Offline. Conéctala (Online) antes de ejecutar pruebas de lectura/escritura.")
        elif target.get("IsReadOnly"):
            safe_print("  [WARN] La unidad está en Solo Lectura. Quita el atributo readonly para ejecutar pruebas de escritura.")
        elif not mounted_letter:
            safe_print("  [WARN] La unidad no tiene letra asignada. Asigna una letra primero para probar el espacio libre.")
        else:
            test_res = run_capacity_test(mounted_letter, mode=mode)
            st = test_res.get("status")
            if st == "verified":
                safe_print(f"  [OK] Integridad 100% verificada: {test_res['verified_mb']} MB escritos y releídos sin corrupción.")
                safe_print(f"  Velocidad Medida   : Escritura {test_res['write_mb_s']} MB/s | Lectura {test_res['read_mb_s']} MB/s")
                if test_res["write_mb_s"] < 6.0 and hw_eval["is_usb"]:
                    safe_print("  [WARN] Velocidad de escritura muy baja (< 6 MB/s); típico de memoria USB 2.0 económica o chip lento.")
            elif st == "fake_detected":
                final_verdict = "FALSA / CAPACIDAD INFLADA CONFIRMADA"
                safe_print(f"  [ERROR] CORRUPCIÓN DETECTADA en el MB #{test_res['first_corrupt_mb']}!")
                safe_print(f"  [ERROR] Motivo: {test_res['corrupt_reason']}")
                safe_print(f"  [ERROR] Capacidad real verificada antes del fallo: ~{test_res['verified_mb']} MB.")
                safe_print(f"  Velocidad Medida   : Escritura {test_res['write_mb_s']} MB/s | Lectura {test_res['read_mb_s']} MB/s")
            elif st == "aborted":
                safe_print("  [WARN] Prueba pausada/detenida por el usuario. Carpeta temporal limpiada.")
            else:
                safe_print(f"  [WARN] No se pudo completar la prueba: {test_res.get('reason', 'Desconocido')}")

    safe_print("\n" + "=" * 72)
    safe_print(f"  Veredicto de Autenticidad : {final_verdict}")
    safe_print("=" * 72)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Auditor de Autenticidad de Unidades de Almacenamiento (USB / SSD / HDD)")
    parser.add_argument("--disk", help="Número de disco físico a auditar (ej. 0, 1, 2, 3).")
    parser.add_argument("--mode", default="hardware", choices=("hardware", "quick", "full"), help="Nivel de auditoría.")
    parser.add_argument("--list", action="store_true", help="Lista todas las unidades conectadas y sale.")
    args, _ = parser.parse_known_args(argv)

    units = list_all_storage_units()
    if args.list or not args.disk:
        safe_print("========================================================================")
        safe_print("  UNIDADES DE ALMACENAMIENTO DETECTADAS (USB / SSD / HDD)")
        safe_print("========================================================================")
        if not units:
            safe_print("  No se detectaron unidades de almacenamiento.")
            sys.exit(0)
        for u in units:
            st = "Offline" if u.get("IsOffline") else "Online"
            vols = ", ".join(f"{v['DriveLetter']}:\\ [{v.get('Label') or ''}]" for v in u.get("Volumes", []) if v.get("DriveLetter"))
            vid_tag = f" | VID:{u['VID']} PID:{u['PID']}" if u.get("VID") else ""
            safe_print(f"  Disco {u['Number']} - {u['FriendlyName']} [{u['BusType']} / {u['MediaType']} | {format_capacity(u['Size'])} | {st}{vid_tag}] {('(' + vols + ')') if vols else ''}")
        if not args.list:
            safe_print("\n[AVISO] Selecciona una unidad específica en el desplegable para auditarla.")
        sys.exit(0)

    try:
        disk_num = int(str(args.disk).strip().split()[0])
    except ValueError:
        safe_print(f"[ERROR] Número de disco inválido: '{args.disk}'.")
        sys.exit(1)

    rc = audit_disk(disk_num, mode=args.mode, units=units)
    sys.exit(rc)


if __name__ == "__main__":
    main()
