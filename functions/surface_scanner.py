import argparse
import ctypes
import json
import os
import subprocess
import sys
import time
from ctypes import wintypes

from functions.utils import safe_print

# Win32 CreateFileW / Device I/O constants
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3
FILE_FLAG_NO_BUFFERING = 0x20000000
FILE_FLAG_WRITE_THROUGH = 0x80000000
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
FILE_BEGIN = 0

# Latency classification thresholds (milliseconds per block)
THRESH_EXCELLENT_MS = 50.0
THRESH_NORMAL_MS = 200.0
THRESH_SLOW_MS = 1000.0

SECTOR_SIZE = 512


def classify_block(elapsed_ms, io_error=False):
    """Clasifica un bloque según su latencia o error de E/S."""
    if io_error:
        return "bad"
    if elapsed_ms < THRESH_EXCELLENT_MS:
        return "excellent"
    if elapsed_ms < THRESH_NORMAL_MS:
        return "normal"
    if elapsed_ms < THRESH_SLOW_MS:
        return "slow"
    return "critical"


def check_remap_safety(disk_meta):
    """Valida si es seguro ejecutar modo remap (escritura selectiva con ceros) en el disco.

    Retorna (allowed: bool, reason: str).
    """
    if not disk_meta:
        return False, "No se pudieron obtener los metadatos del disco."
    if disk_meta.get("IsSystem") or disk_meta.get("IsBoot"):
        return (
            False,
            "BLOQUEADO POR SEGURIDAD: El disco contiene el sistema operativo o partición de arranque. "
            "No se permite reasignación con escritura sobre esta unidad.",
        )
    media = str(disk_meta.get("MediaType") or "").strip().upper()
    bus = str(disk_meta.get("BusType") or "").strip().upper()
    if media == "SSD" or bus == "NVME":
        return (
            False,
            "BLOQUEADO POR SEGURIDAD: La unidad es un SSD/NVMe. "
            "Sobrescribir bloques con ceros no repara celdas flash y solo genera desgaste innecesario. "
            "Usa el modo de solo lectura (quick o scan).",
        )
    return True, ""


def get_disk_metadata(disk_num):
    """Obtiene metadatos del disco físico mediante PowerShell (Get-Disk + Get-PhysicalDisk)."""
    ps_script = (
        f"$d = Get-Disk -Number {int(disk_num)} -ErrorAction SilentlyContinue; "
        "if ($null -eq $d) { exit 1 } "
        f"$p = Get-PhysicalDisk -ErrorAction SilentlyContinue | Where-Object {{ $_.DeviceId -eq '{int(disk_num)}' }} | Select-Object -First 1; "
        "$media = if ($p -and $p.MediaType) { [string]$p.MediaType } else { 'Unknown' }; "
        "[PSCustomObject]@{ "
        "Number = $d.Number; "
        "FriendlyName = [string]$d.FriendlyName; "
        "Size = [int64]$d.Size; "
        "BusType = [string]$d.BusType; "
        "MediaType = $media; "
        "PartitionStyle = [string]$d.PartitionStyle; "
        "OperationalStatus = [string]$d.OperationalStatus; "
        "HealthStatus = [string]$d.HealthStatus; "
        "IsSystem = [bool]$d.IsSystem; "
        "IsBoot = [bool]$d.IsBoot; "
        "IsOffline = [bool]$d.IsOffline; "
        "IsReadOnly = [bool]$d.IsReadOnly "
        "} | ConvertTo-Json -Compress"
    )
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            timeout=15,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return None
        return json.loads(proc.stdout.strip())
    except Exception:
        return None


def _is_pause_requested():
    appdata = os.environ.get("APPDATA", "")
    if not appdata:
        return False
    return os.path.exists(os.path.join(appdata, "cmd_gui_advance", "pause.flag"))


class Win32RawDiskHandle:
    """Acceso directo de bajo nivel a \\\\.\\PhysicalDriveN con FILE_FLAG_NO_BUFFERING."""

    def __init__(self, device_path, writable=False):
        self.device_path = device_path
        self.writable = writable
        self.handle = None

    def __enter__(self):
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateFileW.restype = wintypes.HANDLE
        access = GENERIC_READ | (GENERIC_WRITE if self.writable else 0)
        flags = FILE_FLAG_NO_BUFFERING | (FILE_FLAG_WRITE_THROUGH if self.writable else 0)
        h = kernel32.CreateFileW(
            self.device_path,
            access,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None,
            OPEN_EXISTING,
            flags,
            None,
        )
        if h == INVALID_HANDLE_VALUE or h == 0:
            err = ctypes.GetLastError()
            raise OSError(f"No se pudo abrir {self.device_path} (WinError {err}). Ejecuta como Administrador.")
        self.handle = h
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.handle is not None:
            try:
                ctypes.windll.kernel32.CloseHandle(self.handle)
            except Exception:
                pass
            self.handle = None

    def _seek(self, offset):
        kernel32 = ctypes.windll.kernel32
        new_pos = ctypes.c_int64(0)
        ok = kernel32.SetFilePointerEx(
            wintypes.HANDLE(self.handle),
            ctypes.c_int64(offset),
            ctypes.byref(new_pos),
            FILE_BEGIN,
        )
        if not ok:
            raise OSError(f"SetFilePointerEx fallo en offset {offset} (WinError {ctypes.GetLastError()})")

    def read_block(self, offset, size):
        self._seek(offset)
        buf = ctypes.create_string_buffer(size)
        bytes_read = wintypes.DWORD(0)
        ok = ctypes.windll.kernel32.ReadFile(
            wintypes.HANDLE(self.handle),
            buf,
            wintypes.DWORD(size),
            ctypes.byref(bytes_read),
            None,
        )
        if not ok:
            raise OSError(f"ReadFile fallo en offset {offset} (WinError {ctypes.GetLastError()})")
        return bytes_read.value

    def write_zeros(self, offset, size):
        self._seek(offset)
        buf = ctypes.create_string_buffer(size)  # inicializado en ceros
        bytes_written = wintypes.DWORD(0)
        ok = ctypes.windll.kernel32.WriteFile(
            wintypes.HANDLE(self.handle),
            buf,
            wintypes.DWORD(size),
            ctypes.byref(bytes_written),
            None,
        )
        if not ok:
            raise OSError(f"WriteFile fallo en offset {offset} (WinError {ctypes.GetLastError()})")
        return bytes_written.value


def build_surface_map(block_results, total_size, cells=100):
    """Construye un mapa ASCII de `cells` celdas (0%..100%) con severidad máxima por celda.

    Leyenda: '.' excelente/normal, ':' lento, '!' critico, 'X' danado/error I/O, '-' sin muestrear.
    """
    if total_size <= 0 or cells <= 0:
        return "-" * max(0, cells)

    rank = {"excellent": 1, "normal": 1, "slow": 2, "critical": 3, "bad": 4}
    sym = {0: "-", 1: ".", 2: ":", 3: "!", 4: "X"}
    bucket = [0] * cells

    for item in block_results:
        idx = int((item["offset"] / total_size) * cells)
        if idx >= cells:
            idx = cells - 1
        r = rank.get(item["status"], 1)
        if r > bucket[idx]:
            bucket[idx] = r

    return "".join(sym[b] for b in bucket)


def find_largest_healthy_range(block_results, total_size):
    """Calcula el mayor rango contiguo sano (sin bloques critical/bad) en bytes."""
    if total_size <= 0:
        return (0, 0)
    bad_intervals = sorted(
        (b["offset"], b["offset"] + b["size"])
        for b in block_results
        if b["status"] in ("critical", "bad")
    )
    if not bad_intervals:
        return (0, total_size)

    best_start, best_end = 0, 0
    cursor = 0
    for start, end in bad_intervals:
        if start > cursor:
            if (start - cursor) > (best_end - best_start):
                best_start, best_end = cursor, start
        cursor = max(cursor, end)
    if total_size > cursor and (total_size - cursor) > (best_end - best_start):
        best_start, best_end = cursor, total_size
    return (best_start, best_end)


def compute_offsets(total_size, block_size, mode, quick_samples=250):
    """Genera los offsets alineados a 512 bytes a evaluar según el modo."""
    if total_size < SECTOR_SIZE:
        return []
    aligned_block = max(SECTOR_SIZE, (block_size // SECTOR_SIZE) * SECTOR_SIZE)
    max_start = max(0, ((total_size - aligned_block) // SECTOR_SIZE) * SECTOR_SIZE)

    if mode == "quick":
        count = max(1, min(quick_samples, max(1, total_size // aligned_block)))
        if count == 1:
            return [0]
        step = max_start / (count - 1)
        offsets = []
        seen = set()
        for i in range(count):
            off = (int(i * step) // SECTOR_SIZE) * SECTOR_SIZE
            if off not in seen and off + aligned_block <= total_size:
                seen.add(off)
                offsets.append(off)
        return offsets

    offsets = []
    off = 0
    while off + aligned_block <= total_size:
        offsets.append(off)
        off += aligned_block
    return offsets


def run_surface_scan(disk_handle, total_size, mode="quick", block_size=4 * 1024 * 1024, quick_samples=250, log_cb=safe_print):
    """Ejecuta el escaneo (y remap selectivo si mode=='remap') sobre un handle compatible."""
    offsets = compute_offsets(total_size, block_size, mode, quick_samples=quick_samples)
    total_blocks = len(offsets)
    if total_blocks == 0:
        return {
            "total_blocks": 0,
            "counts": {"excellent": 0, "normal": 0, "slow": 0, "critical": 0, "bad": 0},
            "remapped_ok": 0,
            "remapped_fail": 0,
            "issues": [],
            "results": [],
            "paused": False,
        }

    counts = {"excellent": 0, "normal": 0, "slow": 0, "critical": 0, "bad": 0}
    results = []
    issues = []
    remapped_ok = 0
    remapped_fail = 0
    paused = False
    last_pct_reported = -1

    for idx, off in enumerate(offsets, 1):
        if _is_pause_requested():
            paused = True
            log_cb("\n[AVISO] Escaneo pausado por el usuario.")
            break

        t0 = time.perf_counter()
        io_err = None
        try:
            disk_handle.read_block(off, block_size)
        except Exception as exc:
            io_err = str(exc)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        status = classify_block(elapsed_ms, io_error=(io_err is not None))

        remap_note = ""
        if mode == "remap" and status in ("critical", "bad"):
            try:
                disk_handle.write_zeros(off, block_size)
                t_ver = time.perf_counter()
                disk_handle.read_block(off, block_size)
                ver_ms = (time.perf_counter() - t_ver) * 1000.0
                if ver_ms < THRESH_SLOW_MS:
                    status = "normal"
                    remapped_ok += 1
                    remap_note = f"REASIGNADO OK ({ver_ms:.1f} ms)"
                    log_cb(
                        f"  [OK] Bloque en {off / (1024**3):.2f} GB (LBA {off // SECTOR_SIZE}): {remap_note}"
                    )
                else:
                    remapped_fail += 1
                    remap_note = f"SIGUE CRITICO ({ver_ms:.1f} ms)"
                    log_cb(
                        f"  [ERROR] Bloque en {off / (1024**3):.2f} GB (LBA {off // SECTOR_SIZE}): {remap_note}"
                    )
            except Exception as exc:
                remapped_fail += 1
                remap_note = f"IRRECUPERABLE ({exc})"
                log_cb(
                    f"  [ERROR] Bloque en {off / (1024**3):.2f} GB (LBA {off // SECTOR_SIZE}): {remap_note}"
                )

        counts[status] += 1
        rec = {
            "offset": off,
            "size": block_size,
            "lba": off // SECTOR_SIZE,
            "gb": off / (1024 ** 3),
            "ms": elapsed_ms,
            "status": status,
            "error": io_err or "",
            "remap": remap_note,
        }
        results.append(rec)

        if status in ("slow", "critical", "bad") or remap_note:
            issues.append(rec)
            if not remap_note and status in ("critical", "bad"):
                log_cb(
                    f"  [{'ERROR' if status == 'bad' else 'AVISO'}] Zona {rec['gb']:.2f} GB "
                    f"(LBA {rec['lba']}) — {status.upper()} ({elapsed_ms:.0f} ms)"
                    + (f" | {io_err}" if io_err else "")
                )

        pct = int((idx / total_blocks) * 100)
        if pct != last_pct_reported and (pct % 2 == 0 or idx == total_blocks):
            last_pct_reported = pct
            log_cb(f"Progreso Total: {pct}%")

    return {
        "total_blocks": len(results),
        "counts": counts,
        "remapped_ok": remapped_ok,
        "remapped_fail": remapped_fail,
        "issues": issues,
        "results": results,
        "paused": paused,
    }


def print_summary_report(disk_meta, mode, block_mb, summary):
    total_size = int(disk_meta.get("Size") or 0)
    size_gb = total_size / (1024 ** 3) if total_size else 0.0
    counts = summary["counts"]
    surface_map = build_surface_map(summary["results"], total_size, cells=100)
    healthy_start, healthy_end = find_largest_healthy_range(summary["results"], total_size)
    healthy_span_gb = (healthy_end - healthy_start) / (1024 ** 3)

    safe_print("\n" + "=" * 76)
    safe_print("  RESUMEN DEL ESCANEO DE SUPERFICIE")
    safe_print("=" * 76)
    safe_print(f"  Disco         : #{disk_meta.get('Number')} — {disk_meta.get('FriendlyName')}")
    safe_print(f"  Capacidad     : {size_gb:.2f} GB | Bus: {disk_meta.get('BusType')} | Tipo: {disk_meta.get('MediaType')}")
    safe_print(f"  Modo / Bloque : {mode.upper()} | {block_mb} MB | Bloques evaluados: {summary['total_blocks']}")
    safe_print("-" * 76)
    safe_print(f"  Excelentes (<50 ms)     : {counts['excellent']}")
    safe_print(f"  Normales   (50-200 ms)  : {counts['normal']}")
    safe_print(f"  Lentos     (200-1000ms) : {counts['slow']}")
    safe_print(f"  Criticos   (>1000 ms)   : {counts['critical']}")
    safe_print(f"  Danados    (Error I/O)  : {counts['bad']}")
    if mode == "remap":
        safe_print(f"  Reasignados con exito   : {summary['remapped_ok']}")
        safe_print(f"  Irrecuperables          : {summary['remapped_fail']}")

    safe_print("\n  [ MAPA VISUAL DE SUPERFICIE (0% -> 100%, cada simbolo = 1% del disco) ]")
    safe_print("  Leyenda: [.] Sano  [:] Lento  [!] Critico  [X] Danado  [-] Sin muestrear")
    safe_print(f"    0%- 49%: [{surface_map[:50]}]")
    safe_print(f"   50%-100%: [{surface_map[50:]}]")

    if summary["issues"]:
        safe_print(f"\n  [ ZONAS LENTAS O DEFECTUOSAS DETECTADAS ({len(summary['issues'])} bloques) ]")
        for it in summary["issues"][:30]:
            pct = (it["offset"] / total_size * 100.0) if total_size else 0.0
            extra = f" | {it['remap']}" if it["remap"] else (f" | {it['error']}" if it["error"] else "")
            safe_print(
                f"   - {pct:5.1f}% | {it['gb']:6.2f} GB | LBA {it['lba']:<12} | {it['status'].upper():<8} ({it['ms']:.0f} ms){extra}"
            )
        if len(summary["issues"]) > 30:
            safe_print(f"   ... (+{len(summary['issues']) - 30} bloques adicionales)")

    safe_print("\n  [ DIAGNOSTICO Y RECOMENDACION ]")
    bad_total = counts["bad"] + counts["critical"]
    if bad_total == 0 and counts["slow"] == 0:
        safe_print("  [OK] Superficie saludable: no se detectaron sectores lentos ni defectuosos.")
    elif bad_total == 0:
        safe_print(
            f"  [AVISO] Se detectaron {counts['slow']} zonas lentas. Respalda datos importantes y monitorea SMART."
        )
    else:
        safe_print(
            f"  [ERROR] Se detectaron {bad_total} bloques criticos/danados. NO almacenes datos criticos en esta unidad."
        )
        if healthy_span_gb >= 1.0:
            safe_print(
                f"  [INFO] Mayor zona sana contigua: {healthy_start / (1024**3):.1f} GB a {healthy_end / (1024**3):.1f} GB "
                f"(~{healthy_span_gb:.1f} GB utilizables evitando la zona afectada)."
            )
    safe_print("=" * 76)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Escáner de Superficie y Reparación de Sectores")
    parser.add_argument("--disk", required=True, help="Número de disco físico (ej. 3)")
    parser.add_argument("--mode", choices=["quick", "scan", "remap"], default="quick")
    parser.add_argument("--block-mb", type=int, default=4, help="Tamaño de bloque en MB (1, 4 u 8)")
    args = parser.parse_args(argv)

    try:
        disk_num = int(str(args.disk).split()[0])
    except Exception:
        safe_print(f"[ERROR] Número de disco inválido: {args.disk}")
        sys.exit(1)

    meta = get_disk_metadata(disk_num)
    if not meta:
        safe_print(f"[ERROR] No se encontró el Disco {disk_num}.")
        sys.exit(1)

    if args.mode == "remap":
        allowed, reason = check_remap_safety(meta)
        if not allowed:
            safe_print(f"[ERROR] {reason}")
            sys.exit(1)

    total_size = int(meta.get("Size") or 0)
    if total_size <= 0:
        safe_print(f"[ERROR] El Disco {disk_num} reporta tamaño 0 bytes (puede estar desconectado o sin medio).")
        sys.exit(1)

    block_mb = max(1, min(16, args.block_mb))
    block_size = block_mb * 1024 * 1024
    dev_path = f"\\\\.\\PhysicalDrive{disk_num}"

    safe_print("=" * 76)
    safe_print(f"  ESCANER DE SUPERFICIE — DISCO {disk_num}: {meta.get('FriendlyName')}")
    safe_print(f"  Modo: {args.mode.upper()} | Tamaño: {total_size / (1024**3):.2f} GB | Bloque: {block_mb} MB")
    safe_print("=" * 76)

    writable = args.mode == "remap"
    try:
        with Win32RawDiskHandle(dev_path, writable=writable) as handle:
            summary = run_surface_scan(
                handle,
                total_size=total_size,
                mode=args.mode,
                block_size=block_size,
            )
    except OSError as exc:
        safe_print(f"[ERROR] {exc}")
        sys.exit(1)

    print_summary_report(meta, args.mode, block_mb, summary)
    if summary["counts"]["bad"] > 0 or summary["remapped_fail"] > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
