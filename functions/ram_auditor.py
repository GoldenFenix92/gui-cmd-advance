import argparse
import ctypes
import datetime
import gc
import html
import json
import os
import subprocess
import sys
import threading
import time
import tkinter as tk
from ctypes import wintypes
from tkinter import filedialog, messagebox

import psutil
import ttkbootstrap as tb

from functions import ui_theme
from functions.utils import center_window, get_user_data_path, safe_print

# Procesos críticos del kernel y sistema Windows que NUNCA se deben recortar
PROTECTED_KERNEL_PROCESSES = {
    "system",
    "system idle process",
    "registry",
    "memory compression",
    "smss.exe",
    "csrss.exe",
    "wininit.exe",
    "winlogon.exe",
    "services.exe",
    "lsass.exe",
    "lsaiso.exe",
    "svchost.exe",
    "dwm.exe",
    "audiodg.exe",
    "fontdrvhost.exe",
    "sihost.exe",
    "msmpeng.exe",
    "securityhealthservice.exe",
}

BROWSER_PROCESSES = {
    "chrome.exe",
    "msedge.exe",
    "firefox.exe",
    "brave.exe",
    "opera.exe",
    "vivaldi.exe",
    "arc.exe",
}

SMBIOS_MEMORY_TYPES = {
    0: "Desconocido",
    20: "DDR",
    21: "DDR2",
    22: "DDR2 FB-DIMM",
    24: "DDR3",
    26: "DDR4",
    27: "LPDDR",
    28: "LPDDR2",
    29: "LPDDR3",
    30: "LPDDR4",
    34: "DDR5",
    35: "LPDDR5",
}

FORM_FACTORS = {
    0: "Desconocido",
    8: "DIMM (Escritorio)",
    12: "SODIMM (Laptop)",
    13: "SRIMM",
    15: "FB-DIMM",
}

HISTORY_FILENAME = "ram_audit_history.json"

# Constantes Win32 / NT para gestión de memoria
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_SET_QUOTA = 0x0100
TOKEN_ADJUST_PRIVILEGES = 0x0020
TOKEN_QUERY = 0x0008
SE_PRIVILEGE_ENABLED = 0x00000002

SYSTEM_MEMORY_LIST_INFORMATION = 80
MEM_FLUSH_MODIFIED_LIST = 3
MEM_PURGE_STANDBY_LIST = 4
MEM_PURGE_LOW_PRIORITY_STANDBY_LIST = 5
MEM_COMBINE_PHYSICAL_MEMORY = 6


class _LUID(ctypes.Structure):
    _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]


class _LUID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Luid", _LUID), ("Attributes", wintypes.DWORD)]


class _TOKEN_PRIVILEGES(ctypes.Structure):
    _fields_ = [("PrivilegeCount", wintypes.DWORD), ("Privileges", _LUID_AND_ATTRIBUTES * 1)]


class _PERFORMANCE_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("CommitTotal", ctypes.c_size_t),
        ("CommitLimit", ctypes.c_size_t),
        ("CommitPeak", ctypes.c_size_t),
        ("PhysicalTotal", ctypes.c_size_t),
        ("PhysicalAvailable", ctypes.c_size_t),
        ("SystemCache", ctypes.c_size_t),
        ("KernelTotal", ctypes.c_size_t),
        ("KernelPaged", ctypes.c_size_t),
        ("KernelNonpaged", ctypes.c_size_t),
        ("PageSize", ctypes.c_size_t),
        ("HandleCount", wintypes.DWORD),
        ("ProcessCount", wintypes.DWORD),
        ("ThreadCount", wintypes.DWORD),
    ]


def format_bytes(num_bytes):
    """Formatea bytes a una cadena legible (MB / GB)."""
    try:
        val = float(num_bytes)
    except (TypeError, ValueError):
        return "0 MB"
    if val < 0:
        val = 0.0
    gb = val / (1024 ** 3)
    if gb >= 1.0:
        return f"{gb:.2f} GB"
    mb = val / (1024 ** 2)
    return f"{mb:.1f} MB"


def _creation_flags():
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def is_admin():
    if sys.platform != "win32":
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def enable_memory_privileges():
    """Habilita SeProfileSingleProcessPrivilege y SeIncreaseQuotaPrivilege en el token actual."""
    results = {
        "SeProfileSingleProcessPrivilege": False,
        "SeIncreaseQuotaPrivilege": False,
    }
    if sys.platform != "win32":
        return results
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)

        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

        advapi32.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
        advapi32.OpenProcessToken.restype = wintypes.BOOL
        advapi32.LookupPrivilegeValueW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.POINTER(_LUID)]
        advapi32.LookupPrivilegeValueW.restype = wintypes.BOOL
        advapi32.AdjustTokenPrivileges.argtypes = [
            wintypes.HANDLE,
            wintypes.BOOL,
            ctypes.POINTER(_TOKEN_PRIVILEGES),
            wintypes.DWORD,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        advapi32.AdjustTokenPrivileges.restype = wintypes.BOOL

        token = wintypes.HANDLE()
        if not advapi32.OpenProcessToken(
            kernel32.GetCurrentProcess(),
            TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY,
            ctypes.byref(token),
        ):
            return results

        try:
            for priv_name in list(results.keys()):
                luid = _LUID()
                if not advapi32.LookupPrivilegeValueW(None, priv_name, ctypes.byref(luid)):
                    continue
                tp = _TOKEN_PRIVILEGES()
                tp.PrivilegeCount = 1
                tp.Privileges[0].Luid = luid
                tp.Privileges[0].Attributes = SE_PRIVILEGE_ENABLED
                ok = advapi32.AdjustTokenPrivileges(token, False, ctypes.byref(tp), 0, None, None)
                err = ctypes.get_last_error()
                results[priv_name] = bool(ok) and err == 0
        finally:
            kernel32.CloseHandle(token)
    except Exception:
        pass
    return results


def get_kernel_memory_counters():
    """Lee métricas del kernel Windows mediante psapi.GetPerformanceInfo."""
    empty = {
        "commit_total_bytes": 0,
        "commit_limit_bytes": 0,
        "commit_percent": 0.0,
        "system_cache_bytes": 0,
        "kernel_total_bytes": 0,
        "kernel_paged_bytes": 0,
        "kernel_nonpaged_bytes": 0,
        "handle_count": 0,
        "process_count": 0,
        "thread_count": 0,
    }
    if sys.platform != "win32":
        return empty
    try:
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        psapi.GetPerformanceInfo.argtypes = [ctypes.POINTER(_PERFORMANCE_INFORMATION), wintypes.DWORD]
        psapi.GetPerformanceInfo.restype = wintypes.BOOL

        pi = _PERFORMANCE_INFORMATION()
        pi.cb = ctypes.sizeof(_PERFORMANCE_INFORMATION)
        if not psapi.GetPerformanceInfo(ctypes.byref(pi), pi.cb):
            return empty

        page = int(pi.PageSize or 4096)
        commit_total = int(pi.CommitTotal) * page
        commit_limit = int(pi.CommitLimit) * page
        commit_pct = (commit_total / commit_limit * 100.0) if commit_limit > 0 else 0.0
        return {
            "commit_total_bytes": commit_total,
            "commit_limit_bytes": commit_limit,
            "commit_percent": round(commit_pct, 1),
            "system_cache_bytes": int(pi.SystemCache) * page,
            "kernel_total_bytes": int(pi.KernelTotal) * page,
            "kernel_paged_bytes": int(pi.KernelPaged) * page,
            "kernel_nonpaged_bytes": int(pi.KernelNonpaged) * page,
            "handle_count": int(pi.HandleCount),
            "process_count": int(pi.ProcessCount),
            "thread_count": int(pi.ThreadCount),
        }
    except Exception:
        return empty


def get_memory_snapshot():
    """Captura una fotografía completa del estado de la RAM física, paginación y kernel."""
    vm = psutil.virtual_memory()
    sw = psutil.swap_memory()
    kernel = get_kernel_memory_counters()

    return {
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_bytes": int(vm.total),
        "used_bytes": int(vm.used),
        "available_bytes": int(vm.available),
        "free_bytes": int(vm.free),
        "percent": round(float(vm.percent), 1),
        "swap_total_bytes": int(sw.total),
        "swap_used_bytes": int(sw.used),
        "swap_percent": round(float(sw.percent), 1),
        **kernel,
    }


def get_physical_ram_hardware():
    """Audita los módulos físicos DIMM/SODIMM instalados y ranuras de la placa base vía CIM."""
    fallback = {
        "total_slots": 0,
        "used_slots": 0,
        "max_capacity_gb": 0.0,
        "modules": [],
        "error": None,
    }
    if sys.platform != "win32":
        return fallback

    ps_script = (
        "$arr = Get-CimInstance Win32_PhysicalMemoryArray -ErrorAction SilentlyContinue | Select-Object -First 1; "
        "$mods = @(Get-CimInstance Win32_PhysicalMemory -ErrorAction SilentlyContinue | ForEach-Object { "
        "  [PSCustomObject]@{ "
        "    Slot = [string]$_.DeviceLocator; "
        "    Bank = [string]$_.BankLabel; "
        "    Manufacturer = [string]$_.Manufacturer; "
        "    PartNumber = ([string]$_.PartNumber).Trim(); "
        "    Capacity = [int64]$_.Capacity; "
        "    Speed = [int]$_.Speed; "
        "    ConfiguredClockSpeed = [int]$_.ConfiguredClockSpeed; "
        "    SMBIOSMemoryType = [int]$_.SMBIOSMemoryType; "
        "    FormFactor = [int]$_.FormFactor; "
        "    Voltage = [int]$_.ConfiguredVoltage "
        "  } "
        "}); "
        "$maxKb = if ($arr -and $arr.MaxCapacity) { [int64]$arr.MaxCapacity } else { 0 }; "
        "$slots = if ($arr -and $arr.MemoryDevices) { [int]$arr.MemoryDevices } else { $mods.Count }; "
        "[PSCustomObject]@{ TotalSlots = $slots; MaxCapacityKB = $maxKb; Modules = $mods } | ConvertTo-Json -Depth 4 -Compress"
    )
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            creationflags=_creation_flags(),
            timeout=15,
        )
        raw = proc.stdout.decode("utf-8", errors="ignore").strip()
        if not raw:
            raw = proc.stdout.decode("mbcs", errors="ignore").strip()
        if not raw:
            return fallback
        data = json.loads(raw)
        raw_mods = data.get("Modules") or []
        if isinstance(raw_mods, dict):
            raw_mods = [raw_mods]

        modules = []
        for m in raw_mods:
            cap_bytes = int(m.get("Capacity") or 0)
            cap_gb = round(cap_bytes / (1024 ** 3), 2) if cap_bytes > 0 else 0.0
            mem_type_id = int(m.get("SMBIOSMemoryType") or 0)
            ff_id = int(m.get("FormFactor") or 0)
            voltage_mv = int(m.get("Voltage") or 0)
            modules.append({
                "slot": (m.get("Slot") or m.get("Bank") or "DIMM").strip(),
                "manufacturer": (m.get("Manufacturer") or "Desconocido").strip(),
                "part_number": (m.get("PartNumber") or "N/D").strip(),
                "capacity_gb": cap_gb,
                "speed_mhz": int(m.get("Speed") or 0),
                "configured_mhz": int(m.get("ConfiguredClockSpeed") or m.get("Speed") or 0),
                "memory_type": SMBIOS_MEMORY_TYPES.get(mem_type_id, f"Tipo {mem_type_id}" if mem_type_id else "Desconocido"),
                "form_factor": FORM_FACTORS.get(ff_id, "Desconocido"),
                "voltage_v": round(voltage_mv / 1000.0, 2) if voltage_mv > 0 else 0.0,
            })

        max_kb = int(data.get("MaxCapacityKB") or 0)
        return {
            "total_slots": int(data.get("TotalSlots") or len(modules)),
            "used_slots": len(modules),
            "max_capacity_gb": round(max_kb / (1024 ** 2), 1) if max_kb > 0 else 0.0,
            "modules": modules,
            "error": None,
        }
    except Exception as e:
        fallback["error"] = str(e)
        return fallback


def classify_process_name(name):
    low = (name or "").strip().lower()
    if low in PROTECTED_KERNEL_PROCESSES:
        return "Sistema Crítico"
    if low in BROWSER_PROCESSES:
        return "Navegador"
    return "Aplicación"


def get_process_memory_audit(limit=30):
    """Obtiene el ranking de procesos consumidores de RAM (agrupados por aplicación y por PID)."""
    total_ram = max(1, psutil.virtual_memory().total)
    grouped_map = {}
    by_pid = []

    for proc in psutil.process_iter(["pid", "name", "memory_info"]):
        try:
            info = proc.info
            pid = int(info.get("pid") or 0)
            name = (info.get("name") or f"PID {pid}").strip()
            mem = info.get("memory_info")
            if not mem:
                continue
            rss = int(getattr(mem, "rss", 0) or 0)
            private = int(getattr(mem, "private", rss) or rss)
            pct = round((rss / total_ram) * 100.0, 2)
            category = classify_process_name(name)

            by_pid.append({
                "pid": pid,
                "name": name,
                "rss_bytes": rss,
                "rss_mb": round(rss / (1024 ** 2), 1),
                "private_mb": round(private / (1024 ** 2), 1),
                "percent": pct,
                "category": category,
                "protected": name.lower() in PROTECTED_KERNEL_PROCESSES or pid == os.getpid(),
            })

            key = name.lower()
            if key not in grouped_map:
                grouped_map[key] = {
                    "name": name,
                    "instances": 0,
                    "pids": [],
                    "rss_bytes": 0,
                    "private_bytes": 0,
                    "category": category,
                    "protected": key in PROTECTED_KERNEL_PROCESSES,
                }
            g = grouped_map[key]
            g["instances"] += 1
            g["pids"].append(pid)
            g["rss_bytes"] += rss
            g["private_bytes"] += private
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
        except Exception:
            continue

    grouped = []
    for g in grouped_map.values():
        grouped.append({
            "name": g["name"],
            "instances": g["instances"],
            "pids": g["pids"],
            "rss_bytes": g["rss_bytes"],
            "rss_mb": round(g["rss_bytes"] / (1024 ** 2), 1),
            "private_mb": round(g["private_bytes"] / (1024 ** 2), 1),
            "percent": round((g["rss_bytes"] / total_ram) * 100.0, 2),
            "category": g["category"],
            "protected": g["protected"],
        })

    grouped.sort(key=lambda x: x["rss_bytes"], reverse=True)
    by_pid.sort(key=lambda x: x["rss_bytes"], reverse=True)
    return {
        "grouped": grouped[:limit],
        "by_pid": by_pid[:limit],
        "total_processes": len(by_pid),
    }


def evaluate_ram_health(snapshot, hardware, process_audit):
    """Evalúa la salud general de la memoria RAM y genera hallazgos accionables."""
    findings = []
    score = 100

    pct = float(snapshot.get("percent", 0.0))
    if pct >= 85.0:
        score -= 35
        findings.append({
            "level": "danger",
            "title": f"Presión crítica de memoria ({pct:.1f}%)",
            "detail": "La RAM física está casi saturada. Ejecuta una liberación profunda o cierra aplicaciones pesadas.",
        })
    elif pct >= 70.0:
        score -= 15
        findings.append({
            "level": "warning",
            "title": f"Uso elevado de memoria ({pct:.1f}%)",
            "detail": "Conviene ejecutar una liberación segura para recuperar memoria inactiva y caché.",
        })
    else:
        findings.append({
            "level": "ok",
            "title": f"Uso de memoria saludable ({pct:.1f}%)",
            "detail": f"Disponible actualmente: {format_bytes(snapshot.get('available_bytes', 0))}.",
        })

    commit_pct = float(snapshot.get("commit_percent", 0.0))
    if commit_pct >= 85.0:
        score -= 20
        findings.append({
            "level": "danger",
            "title": f"Carga confirmada (Commit) muy alta ({commit_pct:.1f}%)",
            "detail": "Windows está cerca del límite de RAM + archivo de paginación; podrían fallar asignaciones de memoria.",
        })

    nonpaged = int(snapshot.get("kernel_nonpaged_bytes", 0))
    total_b = max(1, int(snapshot.get("total_bytes", 1)))
    if nonpaged > 1536 * 1024 * 1024 or (nonpaged / total_b) > 0.12:
        score -= 20
        findings.append({
            "level": "warning",
            "title": f"Non-Paged Pool elevado ({format_bytes(nonpaged)})",
            "detail": "Un Non-Paged Pool inusualmente grande suele indicar fuga de memoria en algún controlador (driver).",
        })

    modules = (hardware or {}).get("modules") or []
    if len(modules) == 1 and int((hardware or {}).get("total_slots", 0)) >= 2:
        score -= 10
        findings.append({
            "level": "warning",
            "title": "Configuración Single-Channel detectada (1 módulo instalado)",
            "detail": "Agregar un segundo módulo idéntico habilitaría Dual-Channel y mejoraría el ancho de banda.",
        })
    elif len(modules) >= 2:
        speeds = {m.get("configured_mhz") for m in modules if m.get("configured_mhz")}
        if len(speeds) > 1:
            score -= 10
            findings.append({
                "level": "warning",
                "title": "Módulos con velocidades diferentes",
                "detail": f"Se detectaron velocidades configuradas distintas ({sorted(speeds)} MHz).",
            })
        for m in modules:
            nom = int(m.get("speed_mhz") or 0)
            cfg = int(m.get("configured_mhz") or 0)
            if nom > 0 and cfg > 0 and cfg < nom - 100:
                findings.append({
                    "level": "warning",
                    "title": f"Velocidad reducida en {m.get('slot', 'DIMM')} ({cfg} vs {nom} MHz)",
                    "detail": "Verifica si el perfil XMP/EXPO está habilitado en BIOS.",
                })
                break

    grouped = (process_audit or {}).get("grouped") or []
    if grouped:
        top = grouped[0]
        if top.get("percent", 0.0) >= 20.0:
            findings.append({
                "level": "warning",
                "title": f"Mayor consumidor: {top['name']} ({top['rss_mb']:.0f} MB / {top['percent']:.1f}%)",
                "detail": f"Ejecutando {top['instances']} instancia(s). Puedes recortar su Working Set desde la pestaña Procesos.",
            })

    score = max(0, min(100, score))
    if score >= 80:
        status = "ÓPTIMO"
    elif score >= 55:
        status = "ATENCIÓN"
    else:
        status = "CRÍTICO"

    return {"status": status, "score": score, "findings": findings}


def trim_process_working_sets(exclude_names=None, target_pids=None):
    """Recorta los Working Sets inactivos de procesos de usuario vía Win32 EmptyWorkingSet."""
    excluded = set(PROTECTED_KERNEL_PROCESSES)
    for n in (exclude_names or []):
        if n:
            excluded.add(str(n).strip().lower())

    my_pid = os.getpid()
    trimmed = 0
    skipped = 0
    failed = 0
    trimmed_pids = []

    if sys.platform != "win32":
        return {"trimmed": 0, "skipped": 0, "failed": 0, "trimmed_pids": []}

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    psapi.EmptyWorkingSet.argtypes = [wintypes.HANDLE]
    psapi.EmptyWorkingSet.restype = wintypes.BOOL

    target_set = set(int(p) for p in target_pids) if target_pids else None

    for proc in psutil.process_iter(["pid", "name"]):
        try:
            pid = int(proc.info.get("pid") or 0)
            name = (proc.info.get("name") or "").strip().lower()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

        if target_set is not None and pid not in target_set:
            continue
        if pid <= 4 or pid == my_pid or name in excluded:
            skipped += 1
            continue

        handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_SET_QUOTA, False, pid)
        if not handle:
            failed += 1
            continue
        try:
            if psapi.EmptyWorkingSet(handle):
                trimmed += 1
                trimmed_pids.append(pid)
            else:
                failed += 1
        finally:
            kernel32.CloseHandle(handle)

    return {"trimmed": trimmed, "skipped": skipped, "failed": failed, "trimmed_pids": trimmed_pids}


def purge_standby_list(deep=False):
    """Purga listas en espera (Standby List) del gestor de memoria de Windows vía NtSetSystemInformation."""
    if sys.platform != "win32":
        return {"ok": False, "commands_ok": [], "commands_failed": []}

    commands = (
        [
            ("FlushModifiedList", MEM_FLUSH_MODIFIED_LIST),
            ("PurgeStandbyList", MEM_PURGE_STANDBY_LIST),
            ("CombinePhysicalMemory", MEM_COMBINE_PHYSICAL_MEMORY),
        ]
        if deep
        else [("PurgeLowPriorityStandbyList", MEM_PURGE_LOW_PRIORITY_STANDBY_LIST)]
    )

    ntdll = ctypes.WinDLL("ntdll", use_last_error=True)
    ntdll.NtSetSystemInformation.argtypes = [wintypes.ULONG, ctypes.c_void_p, wintypes.ULONG]
    ntdll.NtSetSystemInformation.restype = ctypes.c_long

    ok_list = []
    fail_list = []
    for label, cmd_code in commands:
        val = ctypes.c_int(cmd_code)
        status = ntdll.NtSetSystemInformation(
            SYSTEM_MEMORY_LIST_INFORMATION,
            ctypes.byref(val),
            ctypes.sizeof(val),
        )
        if status == 0:
            ok_list.append(label)
        else:
            fail_list.append(f"{label} (0x{status & 0xFFFFFFFF:08X})")

    return {"ok": len(ok_list) > 0, "commands_ok": ok_list, "commands_failed": fail_list}


def flush_system_file_cache():
    """Vacía la caché de archivos del kernel Windows mediante SetSystemFileCacheSize(-1, -1, 0)."""
    if sys.platform != "win32":
        return False
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.SetSystemFileCacheSize.argtypes = [ctypes.c_size_t, ctypes.c_size_t, wintypes.DWORD]
        kernel32.SetSystemFileCacheSize.restype = wintypes.BOOL
        neg_one = ctypes.c_size_t(-1).value
        return bool(kernel32.SetSystemFileCacheSize(neg_one, neg_one, 0))
    except Exception:
        return False


def _save_optimization_history(record, history_path=None):
    path = history_path or get_user_data_path(HISTORY_FILENAME)
    items = []
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, list):
                    items = loaded
        except Exception:
            items = []
    items.insert(0, record)
    items = items[:50]
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def optimize_ram(mode="safe", options=None, target_pids=None, save_history=True, history_path=None):
    """Ejecuta una liberación de RAM profesional, segura y medible (Antes vs. Después)."""
    start_t = time.time()
    before = get_memory_snapshot()
    privileges = enable_memory_privileges()
    gc.collect()

    if mode == "deep":
        cfg = {
            "working_sets": True,
            "standby_low": False,
            "standby_full": True,
            "file_cache": True,
        }
    elif mode == "custom" and isinstance(options, dict):
        cfg = {
            "working_sets": bool(options.get("working_sets", True)),
            "standby_low": bool(options.get("standby_low", False)),
            "standby_full": bool(options.get("standby_full", False)),
            "file_cache": bool(options.get("file_cache", False)),
        }
    else:
        cfg = {
            "working_sets": True,
            "standby_low": True,
            "standby_full": False,
            "file_cache": False,
        }

    steps_executed = []
    warnings = []
    trim_stats = {"trimmed": 0, "skipped": 0, "failed": 0, "trimmed_pids": []}

    if cfg["working_sets"]:
        trim_stats = trim_process_working_sets(target_pids=target_pids)
        steps_executed.append(f"Working Sets recortados ({trim_stats['trimmed']} procesos)")

    if cfg["standby_full"]:
        res = purge_standby_list(deep=True)
        if res["ok"]:
            steps_executed.append("Standby List + Modified List purgadas")
        else:
            warnings.append("No se pudo purgar Standby List completa (requiere privilegios de Administrador).")
    elif cfg["standby_low"]:
        res = purge_standby_list(deep=False)
        if res["ok"]:
            steps_executed.append("Standby List (baja prioridad) liberada")
        else:
            warnings.append("No se pudo purgar Standby List de baja prioridad (requiere privilegios de Administrador).")

    if cfg["file_cache"]:
        if flush_system_file_cache():
            steps_executed.append("Caché de archivos del sistema vaciada")
        else:
            warnings.append("No se pudo vaciar la caché de archivos del sistema (SeIncreaseQuotaPrivilege).")

    time.sleep(0.2)
    after = get_memory_snapshot()
    duration_s = round(time.time() - start_t, 2)

    freed_used_bytes = max(0, before["used_bytes"] - after["used_bytes"])
    avail_gain_bytes = max(0, after["available_bytes"] - before["available_bytes"])
    effective_freed_bytes = max(freed_used_bytes, avail_gain_bytes)
    cache_freed_bytes = max(0, before["system_cache_bytes"] - after["system_cache_bytes"])

    result = {
        "timestamp": after["timestamp"],
        "mode": mode,
        "duration_s": duration_s,
        "privileges": privileges,
        "before": before,
        "after": after,
        "freed_bytes": effective_freed_bytes,
        "freed_mb": round(effective_freed_bytes / (1024 ** 2), 1),
        "cache_freed_mb": round(cache_freed_bytes / (1024 ** 2), 1),
        "processes_trimmed": trim_stats["trimmed"],
        "processes_skipped": trim_stats["skipped"],
        "steps_executed": steps_executed,
        "warnings": warnings,
    }

    if save_history:
        _save_optimization_history(
            {
                "timestamp": result["timestamp"],
                "mode": mode,
                "used_before_pct": before["percent"],
                "used_after_pct": after["percent"],
                "freed_mb": result["freed_mb"],
                "processes_trimmed": result["processes_trimmed"],
                "steps": steps_executed,
            },
            history_path=history_path,
        )

    return result


def export_ram_audit_html(snapshot, hardware, process_audit, health, last_opt=None, output_path=None):
    """Exporta un reporte HTML profesional con la auditoría completa de memoria RAM."""
    if not output_path:
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        target_dir = desktop if os.path.isdir(desktop) else get_user_data_path("reports")
        os.makedirs(target_dir, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(target_dir, f"Reporte_Auditor_RAM_{stamp}.html")

    dimm_rows = ""
    for m in (hardware or {}).get("modules") or []:
        dimm_rows += (
            f"<tr><td>{html.escape(str(m.get('slot', '')))}</td>"
            f"<td>{html.escape(str(m.get('manufacturer', '')))}</td>"
            f"<td>{m.get('capacity_gb', 0)} GB</td>"
            f"<td>{html.escape(str(m.get('memory_type', '')))}</td>"
            f"<td>{m.get('configured_mhz', 0)} MHz (Nom: {m.get('speed_mhz', 0)} MHz)</td>"
            f"<td>{html.escape(str(m.get('part_number', '')))}</td></tr>"
        )
    if not dimm_rows:
        dimm_rows = "<tr><td colspan='6'>No se pudieron consultar módulos físicos DIMM.</td></tr>"

    proc_rows = ""
    for p in ((process_audit or {}).get("grouped") or [])[:15]:
        proc_rows += (
            f"<tr><td>{html.escape(str(p.get('name', '')))}</td>"
            f"<td>{p.get('instances', 1)}</td>"
            f"<td>{p.get('rss_mb', 0):.1f} MB</td>"
            f"<td>{p.get('percent', 0):.1f}%</td>"
            f"<td>{html.escape(str(p.get('category', '')))}</td></tr>"
        )

    finding_items = ""
    for f_item in (health or {}).get("findings") or []:
        lvl = f_item.get("level", "ok")
        finding_items += (
            f"<li class='lvl-{lvl}'><strong>{html.escape(str(f_item.get('title', '')))}:</strong> "
            f"{html.escape(str(f_item.get('detail', '')))}</li>"
        )

    opt_html = ""
    if last_opt:
        opt_html = (
            f"<div class='card'><h2>Última Liberación de RAM</h2>"
            f"<p>Modo: <strong>{html.escape(str(last_opt.get('mode', '')))}</strong> | "
            f"Liberado: <strong>{last_opt.get('freed_mb', 0):.1f} MB</strong> | "
            f"Procesos recortados: <strong>{last_opt.get('processes_trimmed', 0)}</strong> | "
            f"Uso: {last_opt['before']['percent']}% -&gt; {last_opt['after']['percent']}%</p></div>"
        )

    doc = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Reporte Auditor de RAM - GUI CMD Advance</title>
<style>
body {{ font-family: 'Segoe UI', sans-serif; background: #17141F; color: #F5F3FF; margin: 24px; }}
.card {{ background: #221D2E; border: 1px solid #3A3250; border-radius: 12px; padding: 18px; margin-bottom: 16px; }}
h1, h2 {{ margin-top: 0; color: #C4B5FD; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }}
.metric {{ background: #17141F; border: 1px solid #3A3250; border-radius: 8px; padding: 12px; }}
.metric .val {{ font-size: 1.3em; font-weight: bold; color: #A78BFA; }}
table {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
th, td {{ border-bottom: 1px solid #3A3250; padding: 8px; text-align: left; font-size: 0.92em; }}
th {{ color: #C4B5FD; }}
.lvl-danger {{ color: #FCA5A5; }}
.lvl-warning {{ color: #FDE68A; }}
.lvl-ok {{ color: #86EFAC; }}
</style>
</head>
<body>
<h1>Reporte de Auditoría de Memoria RAM</h1>
<p>Generado: {html.escape(str(snapshot.get('timestamp', '')))} | Salud: <strong>{html.escape(str(health.get('status', '')))} ({health.get('score', 0)}/100)</strong></p>
<div class="card">
  <h2>Telemetría de Memoria y Kernel</h2>
  <div class="grid">
    <div class="metric"><div>RAM Total</div><div class="val">{format_bytes(snapshot.get('total_bytes', 0))}</div></div>
    <div class="metric"><div>En Uso ({snapshot.get('percent', 0)}%)</div><div class="val">{format_bytes(snapshot.get('used_bytes', 0))}</div></div>
    <div class="metric"><div>Disponible</div><div class="val">{format_bytes(snapshot.get('available_bytes', 0))}</div></div>
    <div class="metric"><div>Caché del Sistema</div><div class="val">{format_bytes(snapshot.get('system_cache_bytes', 0))}</div></div>
    <div class="metric"><div>Commit ({snapshot.get('commit_percent', 0)}%)</div><div class="val">{format_bytes(snapshot.get('commit_total_bytes', 0))}</div></div>
    <div class="metric"><div>Non-Paged Pool</div><div class="val">{format_bytes(snapshot.get('kernel_nonpaged_bytes', 0))}</div></div>
  </div>
</div>
{opt_html}
<div class="card"><h2>Diagnóstico Automático</h2><ul>{finding_items}</ul></div>
<div class="card">
  <h2>Hardware Físico (Ranuras: {hardware.get('used_slots', 0)}/{hardware.get('total_slots', 0)} | Máx: {hardware.get('max_capacity_gb', 0)} GB)</h2>
  <table><thead><tr><th>Ranura</th><th>Fabricante</th><th>Capacidad</th><th>Tipo</th><th>Velocidad</th><th>N.º Parte</th></tr></thead>
  <tbody>{dimm_rows}</tbody></table>
</div>
<div class="card">
  <h2>Top 15 Aplicaciones Consumidoras</h2>
  <table><thead><tr><th>Aplicación</th><th>Instancias</th><th>RAM Física</th><th>% RAM</th><th>Categoría</th></tr></thead>
  <tbody>{proc_rows}</tbody></table>
</div>
</body>
</html>"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(doc)
    return output_path


# ---------------------------------------------------------------------------
# Interfaz Gráfica Profesional (ttkbootstrap + Pulse Rounded UI)
# ---------------------------------------------------------------------------
class RamAuditorApp:
    """Ventana dedicada de Auditoría y Optimización Profesional de Memoria RAM."""

    def __init__(self, master=None):
        self._owns_root = master is None
        if master is None:
            theme = ui_theme.get_saved_theme()
            self.win = tb.Window(themename=theme)
        else:
            self.win = tb.Toplevel(master)
            self.win.transient(master)

        self.win.title("Auditor y Optimizador de Memoria RAM - GUI CMD Advance")
        center_window(self.win, 980, 690)
        self.win.minsize(860, 580)
        ui_theme.apply_window_chrome(self.win)

        self._refresh_job = None
        self._busy = False
        self._last_auto_clean_ts = 0.0
        self._snapshot = get_memory_snapshot()
        self._hardware = {"total_slots": 0, "used_slots": 0, "max_capacity_gb": 0.0, "modules": [], "error": None}
        self._process_audit = {"grouped": [], "by_pid": [], "total_processes": 0}
        self._health = {"status": "ÓPTIMO", "score": 100, "findings": []}
        self._last_opt = None

        self._build_ui()
        self.win.protocol("WM_DELETE_WINDOW", self._on_close)
        ui_theme.bring_to_front(self.win)

        self._load_hardware_async()
        self._refresh_live_data()

    def _build_ui(self):
        root_frame = tb.Frame(self.win, padding=14)
        root_frame.pack(fill="both", expand=True)
        root_frame.grid_rowconfigure(1, weight=1)
        root_frame.grid_columnconfigure(0, weight=1)

        # ---- Encabezado con Medidor en Vivo y Tarjetas Clave ----
        top_card = ui_theme.RoundedCard(root_frame, title="Estado de Memoria RAM en Tiempo Real", padding=(10, 6))
        top_card.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        top_body = top_card.body

        meter_box = tb.Frame(top_body, style="PulseCardInner.TFrame")
        meter_box.pack(side="left", padx=(4, 16))
        self.ram_meter = tb.Meter(
            meter_box,
            metersize=116,
            padding=4,
            amountused=int(self._snapshot["percent"]),
            amounttotal=100,
            metertype="semi",
            subtext="RAM En Uso",
            textright="%",
            bootstyle="info",
            stripethickness=8,
            interactive=False,
        )
        self.ram_meter.pack()

        metrics_grid = tb.Frame(top_body, style="PulseCardInner.TFrame")
        metrics_grid.pack(side="left", fill="both", expand=True)
        for col in range(3):
            metrics_grid.grid_columnconfigure(col, weight=1)

        self.var_used_total = tk.StringVar(value="-- / --")
        self.var_available = tk.StringVar(value="--")
        self.var_cache = tk.StringVar(value="--")
        self.var_commit = tk.StringVar(value="--")
        self.var_nonpaged = tk.StringVar(value="--")
        self.var_health = tk.StringVar(value="Evaluando...")

        metric_specs = [
            (0, 0, "Física en Uso / Total", self.var_used_total),
            (0, 1, "RAM Disponible", self.var_available),
            (0, 2, "Caché / Standby", self.var_cache),
            (1, 0, "Memoria Confirmada (Commit)", self.var_commit),
            (1, 1, "Kernel Non-Paged Pool", self.var_nonpaged),
            (1, 2, "Salud General", self.var_health),
        ]
        for r, c, title_txt, var in metric_specs:
            cell = tb.Frame(metrics_grid, style="PulseCardInner.TFrame", padding=(8, 4))
            cell.grid(row=r, column=c, sticky="nsew")
            tb.Label(cell, text=title_txt, font=("Segoe UI", 8), bootstyle="secondary", style="PulseCard.TLabel").pack(anchor="w")
            tb.Label(cell, textvariable=var, font=("Segoe UI", 10, "bold"), style="PulseCard.TLabel").pack(anchor="w")

        # ---- Pestañas Principales ----
        self.notebook = tb.Notebook(root_frame)
        self.notebook.grid(row=1, column=0, sticky="nsew")

        self.tab_opt = tb.Frame(self.notebook, padding=10)
        self.tab_procs = tb.Frame(self.notebook, padding=10)
        self.tab_hw = tb.Frame(self.notebook, padding=10)

        self.notebook.add(self.tab_opt, text="Resumen y Liberación")
        self.notebook.add(self.tab_procs, text="Procesos Consumidores")
        self.notebook.add(self.tab_hw, text="Hardware Físico y Diagnóstico")

        self._build_opt_tab()
        self._build_procs_tab()
        self._build_hw_tab()

    def _build_opt_tab(self):
        self.tab_opt.grid_columnconfigure(0, weight=1)
        self.tab_opt.grid_columnconfigure(1, weight=1)

        # Izquierda: Perfiles de Liberación
        prof_card = ui_theme.RoundedCard(self.tab_opt, title="Perfil de Liberación de RAM", padding=(10, 8))
        prof_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=(0, 10))
        pb = prof_card.body

        self.mode_var = tk.StringVar(value="safe")
        modes = [
            ("safe", "Seguro / Sin lag (Recomendado): Working Sets + Standby baja prioridad"),
            ("deep", "Profundo (Máxima liberación): Working Sets + Standby completa + Caché"),
            ("custom", "Personalizado (elegir mecanismos manualmente)"),
        ]
        for val, text in modes:
            tb.Radiobutton(
                pb,
                text=text,
                variable=self.mode_var,
                value=val,
                command=self._toggle_custom_checks,
                bootstyle="primary",
            ).pack(anchor="w", pady=3)

        self.custom_frame = tb.Frame(pb, style="PulseCardInner.TFrame", padding=(16, 4, 0, 4))
        self.opt_ws = tk.BooleanVar(value=True)
        self.opt_standby_low = tk.BooleanVar(value=True)
        self.opt_standby_full = tk.BooleanVar(value=False)
        self.opt_file_cache = tk.BooleanVar(value=False)

        for var, label in (
            (self.opt_ws, "Recortar Working Sets de procesos de usuario (excluye kernel)"),
            (self.opt_standby_low, "Purgar Standby List de baja prioridad"),
            (self.opt_standby_full, "Purgar Standby List completa + Modified List"),
            (self.opt_file_cache, "Vaciar caché de archivos del sistema"),
        ):
            tb.Checkbutton(self.custom_frame, text=label, variable=var, bootstyle="info").pack(anchor="w", pady=2)

        btn_bar = tb.Frame(pb, style="PulseCardInner.TFrame")
        btn_bar.pack(fill="x", pady=(12, 2))
        self.btn_clean = tb.Button(
            btn_bar, text="Liberar Memoria RAM", bootstyle="success", command=self._run_manual_clean
        )
        self.btn_clean.pack(side="left", padx=(0, 8))

        tb.Button(
            btn_bar, text="Exportar Reporte HTML", bootstyle="info", command=self._export_html
        ).pack(side="left")

        # Derecha: Auto-limpieza opcional (activable/desactivable por el usuario)
        auto_card = ui_theme.RoundedCard(self.tab_opt, title="Auto-Limpieza Automática (Opcional)", padding=(10, 8))
        auto_card.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=(0, 10))
        ab = auto_card.body

        self.auto_clean_var = tk.BooleanVar(value=False)
        tb.Checkbutton(
            ab,
            text="Activar auto-limpieza cuando la RAM supere el umbral",
            variable=self.auto_clean_var,
            bootstyle="primary-round-toggle",
            command=self._on_auto_clean_toggle,
        ).pack(anchor="w", pady=(2, 8))

        thr_row = tb.Frame(ab, style="PulseCardInner.TFrame")
        thr_row.pack(fill="x", pady=4)
        tb.Label(thr_row, text="Umbral de activación:", style="PulseCard.TLabel").pack(side="left", padx=(0, 8))
        self.threshold_var = tk.StringVar(value="85%")
        self.threshold_combo = tb.Combobox(
            thr_row, values=["75%", "80%", "85%", "90%"], textvariable=self.threshold_var, state="readonly", width=8
        )
        self.threshold_combo.pack(side="left")

        self.auto_status_var = tk.StringVar(
            value="Estado: Desactivada. Solo se liberará memoria cuando pulses el botón."
        )
        tb.Label(
            ab,
            textvariable=self.auto_status_var,
            font=("Segoe UI", 9),
            bootstyle="secondary",
            style="PulseCard.TLabel",
            wraplength=390,
            justify="left",
        ).pack(anchor="w", pady=(8, 0))

        # Abajo: Resultado Antes vs Después
        res_card = ui_theme.RoundedCard(self.tab_opt, title="Resultado de Última Optimización (Antes vs. Después)", padding=(10, 8))
        res_card.grid(row=1, column=0, columnspan=2, sticky="nsew")
        self.result_var = tk.StringVar(
            value="Aún no se ha ejecutado ninguna liberación en esta sesión. Selecciona un perfil y pulsa 'Liberar Memoria RAM'."
        )
        tb.Label(
            res_card.body,
            textvariable=self.result_var,
            font=("Consolas", 9),
            style="PulseCard.TLabel",
            justify="left",
            wraplength=880,
        ).pack(anchor="w", fill="x")

    def _build_procs_tab(self):
        ctrl = tb.Frame(self.tab_procs)
        ctrl.pack(fill="x", pady=(0, 8))

        self.proc_view_var = tk.StringVar(value="grouped")
        tb.Radiobutton(
            ctrl, text="Agrupado por Aplicación", variable=self.proc_view_var, value="grouped",
            command=self._render_process_tree, bootstyle="primary"
        ).pack(side="left", padx=(0, 10))
        tb.Radiobutton(
            ctrl, text="Detalle por PID", variable=self.proc_view_var, value="by_pid",
            command=self._render_process_tree, bootstyle="primary"
        ).pack(side="left", padx=(0, 14))

        tb.Label(ctrl, text="Filtrar:").pack(side="left", padx=(0, 4))
        self.proc_filter_var = tk.StringVar()
        self.proc_filter_var.trace_add("write", lambda *_: self._render_process_tree())
        tb.Entry(ctrl, textvariable=self.proc_filter_var, width=22).pack(side="left", padx=(0, 10))

        tb.Button(
            ctrl, text="Recortar RAM del Seleccionado", bootstyle="warning", command=self._trim_selected_process
        ).pack(side="right")

        tree_wrap = tb.Frame(self.tab_procs)
        tree_wrap.pack(fill="both", expand=True)

        cols = ("name", "info", "rss", "private", "pct", "cat")
        self.proc_tree = tb.Treeview(tree_wrap, columns=cols, show="headings", height=14)
        self.proc_tree.heading("name", text="Aplicación / Proceso")
        self.proc_tree.heading("info", text="Instancias / PID")
        self.proc_tree.heading("rss", text="RAM Física (MB)")
        self.proc_tree.heading("private", text="Privada (MB)")
        self.proc_tree.heading("pct", text="% RAM")
        self.proc_tree.heading("cat", text="Categoría")

        self.proc_tree.column("name", width=230, anchor="w")
        self.proc_tree.column("info", width=110, anchor="center")
        self.proc_tree.column("rss", width=120, anchor="e")
        self.proc_tree.column("private", width=120, anchor="e")
        self.proc_tree.column("pct", width=85, anchor="e")
        self.proc_tree.column("cat", width=140, anchor="center")

        vsb = tb.Scrollbar(tree_wrap, orient="vertical", command=self.proc_tree.yview)
        self.proc_tree.configure(yscrollcommand=vsb.set)
        self.proc_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self._proc_row_pids = {}

    def _build_hw_tab(self):
        self.hw_summary_var = tk.StringVar(value="Consultando módulos físicos de RAM (WMI/CIM)...")
        tb.Label(self.tab_hw, textvariable=self.hw_summary_var, font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 8))

        cols = ("slot", "mfg", "cap", "type", "speed", "part")
        self.hw_tree = tb.Treeview(self.tab_hw, columns=cols, show="headings", height=6)
        self.hw_tree.heading("slot", text="Ranura")
        self.hw_tree.heading("mfg", text="Fabricante")
        self.hw_tree.heading("cap", text="Capacidad")
        self.hw_tree.heading("type", text="Tipo")
        self.hw_tree.heading("speed", text="Velocidad")
        self.hw_tree.heading("part", text="Número de Parte")

        self.hw_tree.column("slot", width=120, anchor="w")
        self.hw_tree.column("mfg", width=150, anchor="w")
        self.hw_tree.column("cap", width=95, anchor="center")
        self.hw_tree.column("type", width=90, anchor="center")
        self.hw_tree.column("speed", width=170, anchor="center")
        self.hw_tree.column("part", width=190, anchor="w")
        self.hw_tree.pack(fill="x", pady=(0, 10))

        diag_card = ui_theme.RoundedCard(self.tab_hw, title="Diagnóstico y Recomendaciones Automáticas", padding=(10, 8))
        diag_card.pack(fill="both", expand=True)
        self.diag_container = diag_card.body

    def _toggle_custom_checks(self):
        if self.mode_var.get() == "custom":
            self.custom_frame.pack(fill="x", pady=(4, 4))
        else:
            self.custom_frame.pack_forget()

    def _on_auto_clean_toggle(self):
        if self.auto_clean_var.get():
            self.auto_status_var.set(
                f"Estado: ACTIVA. Se ejecutará limpieza segura automática al superar {self.threshold_var.get()} (espera mínima 60s)."
            )
        else:
            self.auto_status_var.set("Estado: Desactivada. Solo se liberará memoria cuando pulses el botón.")

    def _load_hardware_async(self):
        def worker():
            hw = get_physical_ram_hardware()
            try:
                self.win.after(0, lambda: self._apply_hardware_data(hw))
            except Exception:
                pass
        threading.Thread(target=worker, daemon=True).start()

    def _apply_hardware_data(self, hw):
        if not self.win.winfo_exists():
            return
        self._hardware = hw
        for item in self.hw_tree.get_children():
            self.hw_tree.delete(item)
        mods = hw.get("modules") or []
        self.hw_summary_var.set(
            f"Ranuras ocupadas: {hw.get('used_slots', 0)} de {hw.get('total_slots', 0)} | "
            f"Capacidad máxima placa base: {hw.get('max_capacity_gb', 0)} GB"
        )
        for m in mods:
            speed_txt = f"{m['configured_mhz']} MHz"
            if m["speed_mhz"] and m["speed_mhz"] != m["configured_mhz"]:
                speed_txt += f" (Nom: {m['speed_mhz']})"
            self.hw_tree.insert(
                "", "end",
                values=(m["slot"], m["manufacturer"], f"{m['capacity_gb']} GB", m["memory_type"], speed_txt, m["part_number"]),
            )
        self._update_diagnostics()

    def _update_diagnostics(self):
        self._health = evaluate_ram_health(self._snapshot, self._hardware, self._process_audit)
        self.var_health.set(f"{self._health['status']} ({self._health['score']}/100)")
        for w in self.diag_container.winfo_children():
            w.destroy()
        for f_item in self._health["findings"]:
            lvl = f_item["level"]
            style_map = {"ok": "success", "warning": "warning", "danger": "danger"}
            tb.Label(
                self.diag_container,
                text=f"[{lvl.upper()}] {f_item['title']} — {f_item['detail']}",
                bootstyle=style_map.get(lvl, "info"),
                font=("Segoe UI", 9),
                wraplength=850,
                justify="left",
                style="PulseCard.TLabel",
            ).pack(anchor="w", pady=3)

    def _render_process_tree(self):
        if not self.win.winfo_exists():
            return
        for item in self.proc_tree.get_children():
            self.proc_tree.delete(item)
        self._proc_row_pids.clear()

        flt = self.proc_filter_var.get().strip().lower()
        mode = self.proc_view_var.get()
        rows = self._process_audit.get(mode, [])
        for r in rows:
            if flt and flt not in r["name"].lower():
                continue
            info_col = f"{r['instances']} proc." if mode == "grouped" else f"PID {r['pid']}"
            iid = self.proc_tree.insert(
                "", "end",
                values=(r["name"], info_col, f"{r['rss_mb']:.1f}", f"{r['private_mb']:.1f}", f"{r['percent']:.1f}%", r["category"]),
            )
            self._proc_row_pids[iid] = {
                "name": r["name"],
                "pids": r["pids"] if mode == "grouped" else [r["pid"]],
                "protected": r["protected"],
            }

    def _refresh_live_data(self):
        if not self.win.winfo_exists():
            return
        self._snapshot = get_memory_snapshot()
        self._process_audit = get_process_memory_audit(limit=30)

        pct = self._snapshot["percent"]
        meter_style = "success" if pct < 65 else ("warning" if pct < 85 else "danger")
        self.ram_meter.configure(amountused=int(round(pct)), bootstyle=meter_style)
        self.var_used_total.set(
            f"{format_bytes(self._snapshot['used_bytes'])} / {format_bytes(self._snapshot['total_bytes'])}"
        )
        self.var_available.set(format_bytes(self._snapshot["available_bytes"]))
        self.var_cache.set(format_bytes(self._snapshot["system_cache_bytes"]))
        self.var_commit.set(
            f"{format_bytes(self._snapshot['commit_total_bytes'])} ({self._snapshot['commit_percent']}%)"
        )
        self.var_nonpaged.set(format_bytes(self._snapshot["kernel_nonpaged_bytes"]))

        self._render_process_tree()
        self._update_diagnostics()

        # Auto-limpieza opcional si el usuario la activó explícitamente
        if self.auto_clean_var.get() and not self._busy:
            try:
                thr = float(self.threshold_var.get().replace("%", "").strip())
            except ValueError:
                thr = 85.0
            now = time.time()
            if pct >= thr and (now - self._last_auto_clean_ts) >= 60.0:
                self._last_auto_clean_ts = now
                self._start_clean_worker(mode="safe", auto_triggered=True)

        self._refresh_job = self.win.after(2500, self._refresh_live_data)

    def _run_manual_clean(self):
        if self._busy:
            return
        mode = self.mode_var.get()
        custom_opts = {
            "working_sets": self.opt_ws.get(),
            "standby_low": self.opt_standby_low.get(),
            "standby_full": self.opt_standby_full.get(),
            "file_cache": self.opt_file_cache.get(),
        }
        self._start_clean_worker(mode=mode, options=custom_opts, auto_triggered=False)

    def _start_clean_worker(self, mode="safe", options=None, target_pids=None, auto_triggered=False):
        self._busy = True
        self.btn_clean.configure(state="disabled", text="Optimizando RAM...")

        def worker():
            res = optimize_ram(mode=mode, options=options, target_pids=target_pids)
            try:
                self.win.after(0, lambda: self._on_clean_finished(res, auto_triggered))
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def _on_clean_finished(self, res, auto_triggered=False):
        self._busy = False
        if not self.win.winfo_exists():
            return
        self.btn_clean.configure(state="normal", text="Liberar Memoria RAM")
        self._last_opt = res
        origin = "Auto-limpieza por umbral" if auto_triggered else f"Modo '{res['mode']}'"
        lines = [
            f"[{res['timestamp']}] {origin} completado en {res['duration_s']}s",
            f"RAM En Uso    : {res['before']['percent']}% ({format_bytes(res['before']['used_bytes'])}) -> {res['after']['percent']}% ({format_bytes(res['after']['used_bytes'])})",
            f"RAM Liberada  : {res['freed_mb']:.1f} MB | Caché liberada: {res['cache_freed_mb']:.1f} MB | Procesos recortados: {res['processes_trimmed']}",
            f"Acciones      : {' | '.join(res['steps_executed']) if res['steps_executed'] else 'Ninguna'}",
        ]
        if res["warnings"]:
            lines.append(f"Avisos        : {' ; '.join(res['warnings'])}")
        self.result_var.set("\n".join(lines))
        self._refresh_live_data()

    def _trim_selected_process(self):
        sel = self.proc_tree.selection()
        if not sel:
            messagebox.showinfo("Seleccionar proceso", "Selecciona un proceso o aplicación de la lista.", parent=self.win)
            return
        meta = self._proc_row_pids.get(sel[0])
        if not meta:
            return
        if meta["protected"]:
            messagebox.showwarning(
                "Proceso Protegido",
                f"'{meta['name']}' es un proceso crítico del sistema Windows y no debe recortarse manualmente.",
                parent=self.win,
            )
            return
        self._start_clean_worker(
            mode="custom",
            options={"working_sets": True, "standby_low": False, "standby_full": False, "file_cache": False},
            target_pids=meta["pids"],
        )

    def _export_html(self):
        default_name = f"Reporte_Auditor_RAM_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        out = filedialog.asksaveasfilename(
            parent=self.win,
            title="Guardar Reporte de Auditoría RAM",
            initialfile=default_name,
            defaultextension=".html",
            filetypes=[("Reporte HTML", "*.html")],
        )
        if not out:
            return
        try:
            saved = export_ram_audit_html(
                self._snapshot, self._hardware, self._process_audit, self._health, self._last_opt, output_path=out
            )
            messagebox.showinfo("Reporte Exportado", f"Reporte guardado en:\n{saved}", parent=self.win)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo exportar el reporte:\n{e}", parent=self.win)

    def _on_close(self):
        if self._refresh_job is not None:
            try:
                self.win.after_cancel(self._refresh_job)
            except Exception:
                pass
            self._refresh_job = None
        self.win.destroy()

    def mainloop(self):
        self.win.mainloop()


# ---------------------------------------------------------------------------
# Modo CLI (Consola integrada en GUI CMD Advance)
# ---------------------------------------------------------------------------
def _print_cli_audit():
    safe_print("=" * 72)
    safe_print("  AUDITORÍA PROFESIONAL DE MEMORIA RAM - GUI CMD ADVANCE")
    safe_print("=" * 72)
    safe_print("Progreso Total: 20%")
    snap = get_memory_snapshot()
    safe_print(f"  RAM Total Física      : {format_bytes(snap['total_bytes'])}")
    safe_print(f"  RAM En Uso            : {format_bytes(snap['used_bytes'])} ({snap['percent']}%)")
    safe_print(f"  RAM Disponible        : {format_bytes(snap['available_bytes'])}")
    safe_print(f"  Caché del Sistema     : {format_bytes(snap['system_cache_bytes'])}")
    safe_print(f"  Memoria Confirmada    : {format_bytes(snap['commit_total_bytes'])} / {format_bytes(snap['commit_limit_bytes'])} ({snap['commit_percent']}%)")
    safe_print(f"  Kernel Non-Paged Pool : {format_bytes(snap['kernel_nonpaged_bytes'])}")

    safe_print("\n[1/3] Consultando hardware físico (DIMMs)...")
    safe_print("Progreso Total: 50%")
    hw = get_physical_ram_hardware()
    safe_print(f"  Ranuras ocupadas: {hw['used_slots']} de {hw['total_slots']} | Máximo placa base: {hw['max_capacity_gb']} GB")
    for m in hw["modules"]:
        safe_print(
            f"   - {m['slot']}: {m['capacity_gb']} GB {m['memory_type']} @ {m['configured_mhz']} MHz "
            f"({m['manufacturer']} | {m['part_number']})"
        )

    safe_print("\n[2/3] Top 10 aplicaciones consumidoras de RAM...")
    safe_print("Progreso Total: 80%")
    pa = get_process_memory_audit(limit=10)
    for idx, p in enumerate(pa["grouped"], 1):
        safe_print(f"   {idx:2d}. {p['name']:<26} {p['rss_mb']:>8.1f} MB ({p['percent']:>5.1f}%) [{p['instances']} inst.]")

    safe_print("\n[3/3] Diagnóstico de salud de memoria...")
    health = evaluate_ram_health(snap, hw, pa)
    safe_print(f"  Estado general: {health['status']} ({health['score']}/100)")
    for f_item in health["findings"]:
        safe_print(f"   [{f_item['level'].upper()}] {f_item['title']}: {f_item['detail']}")
    safe_print("Progreso Total: 100%")
    safe_print("=" * 72)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Auditor y Optimizador Profesional de Memoria RAM.")
    parser.add_argument("--gui", action="store_true", help="Abre la interfaz gráfica completa del Auditor de RAM.")
    parser.add_argument(
        "--mode",
        choices=["audit", "clean-safe", "clean-deep"],
        default="audit",
        help="Modo CLI: audit (solo diagnóstico), clean-safe (sin lag), clean-deep (profundo).",
    )
    args, _ = parser.parse_known_args(argv)

    if args.gui:
        app = RamAuditorApp()
        app.mainloop()
        return 0

    if args.mode == "audit":
        _print_cli_audit()
        return 0

    clean_mode = "deep" if args.mode == "clean-deep" else "safe"
    safe_print("=" * 72)
    safe_print(f"  OPTIMIZADOR DE MEMORIA RAM (MODO: {clean_mode.upper()})")
    safe_print("=" * 72)
    safe_print("Progreso Total: 25%")
    res = optimize_ram(mode=clean_mode)
    safe_print("Progreso Total: 100%")
    safe_print(f"  RAM Antes     : {res['before']['percent']}% ({format_bytes(res['before']['used_bytes'])})")
    safe_print(f"  RAM Después   : {res['after']['percent']}% ({format_bytes(res['after']['used_bytes'])})")
    safe_print(f"  RAM Liberada  : {res['freed_mb']:.1f} MB (Caché: {res['cache_freed_mb']:.1f} MB)")
    safe_print(f"  Procesos OK   : {res['processes_trimmed']} recortados | {res['processes_skipped']} protegidos omitidos")
    for step in res["steps_executed"]:
        safe_print(f"   [OK] {step}")
    for warn in res["warnings"]:
        safe_print(f"   [AVISO] {warn}")
    safe_print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
