import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from functions.utils import get_user_data_path, safe_print

VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".3gp", ".mpeg", ".mpg", ".ts"}
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wma"}
VALID_OPS = (
    "probe",
    "trim",
    "audio-extract",
    "audio-normalize",
    "mute",
    "reframe",
    "gif",
    "speed",
    "hdr-to-sdr",
)


def _creation_flags():
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def get_ffmpeg_path():
    local = get_user_data_path(os.path.join("tools", "ffmpeg.exe"))
    if os.path.exists(local):
        return local
    return shutil.which("ffmpeg") or "ffmpeg"


def get_ffprobe_path():
    local = get_user_data_path(os.path.join("tools", "ffprobe.exe"))
    if os.path.exists(local):
        return local
    return shutil.which("ffprobe") or "ffprobe"


def _parse_fps(rate_str):
    if not rate_str or "/" not in str(rate_str):
        try:
            return round(float(rate_str), 2)
        except Exception:
            return 0.0
    try:
        num, den = str(rate_str).split("/", 1)
        d = float(den)
        if d <= 0:
            return 0.0
        return round(float(num) / d, 2)
    except Exception:
        return 0.0


def probe_media(input_path):
    """Inspecciona un archivo multimedia usando ffprobe y devuelve metadatos técnicos."""
    cmd = [
        get_ffprobe_path(),
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(input_path),
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=_creation_flags(),
            timeout=20,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return None
        data = json.loads(proc.stdout)
    except Exception:
        return None

    fmt = data.get("format") or {}
    streams = data.get("streams") or []
    v_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    a_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    duration_s = 0.0
    try:
        duration_s = round(float(fmt.get("duration") or 0.0), 2)
    except Exception:
        duration_s = 0.0

    size_bytes = 0
    try:
        size_bytes = int(fmt.get("size") or os.path.getsize(input_path))
    except Exception:
        size_bytes = 0

    bitrate_kbps = 0
    try:
        bitrate_kbps = int(int(fmt.get("bit_rate") or 0) / 1000)
    except Exception:
        bitrate_kbps = 0

    avg_fps = _parse_fps(v_stream.get("avg_frame_rate")) if v_stream else 0.0
    r_fps = _parse_fps(v_stream.get("r_frame_rate")) if v_stream else 0.0
    is_vfr = bool(v_stream and avg_fps > 0 and r_fps > 0 and abs(avg_fps - r_fps) > 0.5)

    color_trc = (v_stream.get("color_transfer") or "").lower() if v_stream else ""
    is_hdr = color_trc in ("smpte2084", "arib-std-b67", "smpte428")

    return {
        "path": str(input_path),
        "name": os.path.basename(str(input_path)),
        "duration_s": duration_s,
        "size_bytes": size_bytes,
        "size_mb": round(size_bytes / (1024 ** 2), 2),
        "bitrate_kbps": bitrate_kbps,
        "has_video": v_stream is not None,
        "has_audio": a_stream is not None,
        "width": int(v_stream.get("width") or 0) if v_stream else 0,
        "height": int(v_stream.get("height") or 0) if v_stream else 0,
        "fps": avg_fps or r_fps,
        "is_vfr": is_vfr,
        "video_codec": (v_stream.get("codec_name") or "") if v_stream else "",
        "pix_fmt": (v_stream.get("pix_fmt") or "") if v_stream else "",
        "color_transfer": color_trc or "bt709",
        "is_hdr": is_hdr,
        "audio_codec": (a_stream.get("codec_name") or "") if a_stream else "",
        "audio_channels": int(a_stream.get("channels") or 0) if a_stream else 0,
        "audio_sample_rate": int(a_stream.get("sample_rate") or 0) if a_stream else 0,
    }


def build_atempo_chain(speed):
    """Construye una cadena válida de filtros atempo (cada etapa en rango [0.5, 2.0])."""
    val = float(speed)
    if val <= 0:
        raise ValueError("La velocidad debe ser mayor a 0.")
    stages = []
    while val > 2.0:
        stages.append("atempo=2.0")
        val /= 2.0
    while val < 0.5:
        stages.append("atempo=0.5")
        val /= 0.5
    stages.append(f"atempo={val:.4f}".rstrip("0").rstrip("."))
    return ",".join(stages)


def _compute_target_dimensions(aspect, target_height):
    h = int(target_height) if str(target_height).isdigit() else 1080
    if h % 2 != 0:
        h -= 1
    if aspect == "9:16":
        w = int(round(h * 9 / 16))
    elif aspect == "16:9":
        w = int(round(h * 16 / 9))
    elif aspect == "1:1":
        w = h
    else:
        return None, h
    if w % 2 != 0:
        w += 1
    return w, h


def _resolve_output_path(input_path, output_dir, op, audio_format="mp3"):
    p = Path(input_path)
    out_dir = Path(output_dir) if output_dir else p.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    ext_map = {
        "audio-extract": f".{audio_format.lower().lstrip('.')}",
        "gif": ".gif",
    }
    suffix_map = {
        "trim": "_recortado",
        "audio-extract": "_audio",
        "audio-normalize": "_norm14lufs",
        "mute": "_sin_audio",
        "reframe": "_adaptado",
        "gif": "_preview",
        "speed": "_vel",
        "hdr-to-sdr": "_sdr",
    }
    target_ext = ext_map.get(op, ".mp4")
    suffix = suffix_map.get(op, f"_{op}")
    candidate = out_dir / f"{p.stem}{suffix}{target_ext}"
    if candidate.resolve() == p.resolve():
        candidate = out_dir / f"{p.stem}{suffix}_out{target_ext}"
    return str(candidate)


def build_studio_command(
    op,
    input_path,
    output_path,
    start="",
    end="",
    accurate=False,
    audio_format="mp3",
    aspect="9:16",
    fit="crop",
    height="1080",
    speed=1.5,
    has_audio=True,
):
    """Construye la lista de argumentos segura para FFmpeg según la operación elegida."""
    ffmpeg = get_ffmpeg_path()
    cmd = [ffmpeg, "-y", "-nostdin"]

    if op == "trim":
        if start:
            cmd.extend(["-ss", str(start)])
        cmd.extend(["-i", str(input_path)])
        if end:
            cmd.extend(["-to", str(end)])
        if accurate:
            cmd.extend([
                "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
                "-c:v", "libx264", "-crf", "20", "-preset", "fast",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
            ])
        else:
            cmd.extend(["-c", "copy", "-movflags", "+faststart"])
        cmd.append(str(output_path))
        return cmd

    if op == "audio-extract":
        cmd.extend(["-i", str(input_path), "-vn"])
        fmt = audio_format.lower().lstrip(".")
        if fmt == "wav":
            cmd.extend(["-c:a", "pcm_s16le"])
        elif fmt in ("m4a", "aac"):
            cmd.extend(["-c:a", "aac", "-b:a", "192k"])
        else:
            cmd.extend(["-c:a", "libmp3lame", "-q:a", "2"])
        cmd.append(str(output_path))
        return cmd

    if op == "audio-normalize":
        cmd.extend([
            "-i", str(input_path),
            "-c:v", "copy",
            "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
            str(output_path),
        ])
        return cmd

    if op == "mute":
        cmd.extend(["-i", str(input_path), "-c:v", "copy", "-an", "-movflags", "+faststart", str(output_path)])
        return cmd

    if op == "reframe":
        cmd.extend(["-i", str(input_path)])
        w, h = _compute_target_dimensions(aspect, height)
        if w is None:
            vf = f"scale=-2:{h}" if str(height).isdigit() else "scale=trunc(iw/2)*2:trunc(ih/2)*2"
            cmd.extend(["-vf", vf])
        elif fit == "pad":
            vf = (
                f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
                f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black"
            )
            cmd.extend(["-vf", vf])
        elif fit == "blur":
            fc = (
                f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},boxblur=20:5[bg];"
                f"[0:v]scale={w}:{h}:force_original_aspect_ratio=decrease[fg];"
                f"[bg][fg]overlay=(W-w)/2:(H-h)/2[v]"
            )
            cmd.extend(["-filter_complex", fc, "-map", "[v]"])
            if has_audio:
                cmd.extend(["-map", "0:a?"])
        else:
            vf = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"
            cmd.extend(["-vf", vf])
        cmd.extend([
            "-c:v", "libx264", "-crf", "21", "-preset", "fast",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
            str(output_path),
        ])
        return cmd

    if op == "gif":
        if start:
            cmd.extend(["-ss", str(start)])
        cmd.extend(["-i", str(input_path)])
        if end:
            cmd.extend(["-to", str(end)])
        cmd.extend([
            "-vf", "fps=12,scale=480:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
            str(output_path),
        ])
        return cmd

    if op == "speed":
        spd = float(speed)
        pts_factor = 1.0 / spd
        cmd.extend(["-i", str(input_path)])
        if has_audio:
            atempo_str = build_atempo_chain(spd)
            fc = f"[0:v]setpts={pts_factor:.5f}*PTS,scale=trunc(iw/2)*2:trunc(ih/2)*2[v];[0:a]{atempo_str}[a]"
            cmd.extend(["-filter_complex", fc, "-map", "[v]", "-map", "[a]"])
        else:
            cmd.extend(["-vf", f"setpts={pts_factor:.5f}*PTS,scale=trunc(iw/2)*2:trunc(ih/2)*2", "-an"])
        cmd.extend([
            "-c:v", "libx264", "-crf", "21", "-preset", "fast",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
            str(output_path),
        ])
        return cmd

    if op == "hdr-to-sdr":
        cmd.extend([
            "-i", str(input_path),
            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p",
            "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
            "-c:v", "libx264", "-crf", "20", "-preset", "fast",
            "-c:a", "copy", "-movflags", "+faststart",
            str(output_path),
        ])
        return cmd

    raise ValueError(f"Operación no soportada: {op}")


def _print_probe_report(info):
    safe_print("=" * 68)
    safe_print(f"  INSPECTOR TÉCNICO (FFPROBE): {info['name']}")
    safe_print("=" * 68)
    safe_print(f"  Ruta       : {info['path']}")
    safe_print(f"  Tamaño     : {info['size_mb']:.2f} MB | Duración: {info['duration_s']} s | Bitrate: {info['bitrate_kbps']} kbps")
    if info["has_video"]:
        vfr_tag = " (VFR - Frecuencia variable)" if info["is_vfr"] else " (CFR)"
        hdr_tag = f"HDR ({info['color_transfer']})" if info["is_hdr"] else f"SDR ({info['color_transfer']})"
        safe_print(f"  Video      : {info['width']}x{info['height']} @ {info['fps']} fps{vfr_tag}")
        safe_print(f"  Códec/Color: {info['video_codec']} | {info['pix_fmt']} | {hdr_tag}")
    else:
        safe_print("  Video      : Sin pista de video")
    if info["has_audio"]:
        safe_print(
            f"  Audio      : {info['audio_codec']} | {info['audio_channels']} ch | {info['audio_sample_rate']} Hz"
        )
    else:
        safe_print("  Audio      : Sin pista de audio")
    safe_print("=" * 68)


def _collect_inputs(raw_inputs, input_list):
    collected = []
    for item in (raw_inputs or []):
        if item and str(item).strip():
            collected.append(str(item).strip().strip('"'))
    if input_list:
        from functions.drag_drop import load_input_list_file
        collected.extend(load_input_list_file(input_list))

    files = []
    for entry in collected:
        p = Path(entry)
        if p.is_file():
            files.append(str(p))
        elif p.is_dir():
            for child in sorted(p.iterdir()):
                if child.is_file() and (child.suffix.lower() in VIDEO_EXTS or child.suffix.lower() in AUDIO_EXTS):
                    files.append(str(child))
    return files


def main(argv=None):
    parser = argparse.ArgumentParser(description="Estudio Rápido de Video y Audio basado en FFmpeg.")
    parser.add_argument("--input", action="append", help="Archivo o carpeta de entrada.")
    parser.add_argument("--input-list", default="", help="Archivo JSON con lista de archivos multimedia.")
    parser.add_argument("--op", choices=VALID_OPS, default="probe", help="Operación a realizar.")
    parser.add_argument("--output", default="", help="Carpeta de salida (opcional).")
    parser.add_argument("--start", default="", help="Tiempo inicio para recortar/GIF (ej. 00:00:05).")
    parser.add_argument("--end", default="", help="Tiempo fin para recortar/GIF (ej. 00:00:20).")
    parser.add_argument("--accurate", action="store_true", help="Recorte preciso por cuadro (re-codifica).")
    parser.add_argument("--audio-format", choices=["mp3", "wav", "m4a"], default="mp3", help="Formato al extraer audio.")
    parser.add_argument("--aspect", choices=["9:16", "16:9", "1:1", "original"], default="9:16", help="Relación de aspecto.")
    parser.add_argument("--fit", choices=["crop", "pad", "blur"], default="crop", help="Modo de encuadre.")
    parser.add_argument("--height", default="1080", help="Altura objetivo (1080, 720, original).")
    parser.add_argument("--speed", type=float, default=1.5, help="Factor de velocidad (ej. 0.5, 1.5, 2.0).")

    args, _ = parser.parse_known_args(argv)
    files = _collect_inputs(args.input, args.input_list)
    if not files:
        safe_print("[ERROR] Debes seleccionar al menos un archivo o carpeta multimedia (--input o --input-list).")
        return 1

    total = len(files)
    ok_count = 0
    fail_count = 0

    for idx, fp in enumerate(files, 1):
        info = probe_media(fp)
        if args.op == "probe":
            if info:
                _print_probe_report(info)
                ok_count += 1
            else:
                safe_print(f"[ERROR] No se pudo inspeccionar el archivo con ffprobe: {fp}")
                fail_count += 1
            safe_print(f"Progreso Total: {int(idx / total * 100)}%")
            continue

        out_path = _resolve_output_path(fp, args.output, args.op, audio_format=args.audio_format)
        has_audio = info["has_audio"] if info else True
        safe_print(f"\n[{idx}/{total}] Operación '{args.op}' -> {os.path.basename(fp)}")
        cmd = build_studio_command(
            op=args.op,
            input_path=fp,
            output_path=out_path,
            start=args.start,
            end=args.end,
            accurate=args.accurate,
            audio_format=args.audio_format,
            aspect=args.aspect,
            fit=args.fit,
            height=args.height,
            speed=args.speed,
            has_audio=has_audio,
        )
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=_creation_flags(),
        )
        if proc.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            after_info = probe_media(out_path)
            detail = (
                f"{after_info['size_mb']:.2f} MB, {after_info['duration_s']}s"
                if after_info
                else f"{os.path.getsize(out_path)} bytes"
            )
            safe_print(f"  [OK] Guardado: {out_path} ({detail})")
            ok_count += 1
        else:
            err_tail = (proc.stderr or "").strip().splitlines()[-3:]
            safe_print(f"  [ERROR] Falló FFmpeg en {fp}: {' | '.join(err_tail)}")
            fail_count += 1
        safe_print(f"Progreso Total: {int(idx / total * 100)}%")

    safe_print(f"\n[RESUMEN ESTUDIO] Exitosos: {ok_count} | Fallidos: {fail_count}")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
