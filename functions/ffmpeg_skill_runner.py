import argparse
import os
import runpy
import sys

from functions.utils import get_user_data_path, safe_print


def get_ffmpeg_skill_dir():
    """Devuelve la ruta de instalación del complemento ffmpeg-skill en tools/."""
    return get_user_data_path(os.path.join("tools", "ffmpeg-skill"))


def is_ffmpeg_skill_installed(skill_dir=None):
    base = skill_dir or get_ffmpeg_skill_dir()
    return os.path.isfile(os.path.join(base, "scripts", "_contract.py"))


def resolve_skill_script(tool_name, skill_dir=None):
    """Resuelve de forma segura un script dentro de tools/ffmpeg-skill/scripts/."""
    cleaned = str(tool_name or "").strip().replace("\\", "/")
    if not cleaned or "/" in cleaned or ".." in cleaned:
        return None
    if cleaned == "doctor":
        filename = "_contract.py"
    else:
        filename = cleaned if cleaned.endswith(".py") else f"{cleaned}.py"

    base = os.path.abspath(os.path.join(skill_dir or get_ffmpeg_skill_dir(), "scripts"))
    candidate = os.path.abspath(os.path.join(base, filename))
    if not candidate.startswith(base + os.sep):
        return None
    if not os.path.isfile(candidate):
        return None
    return candidate


def run_skill_script(tool_name, script_args=None, skill_dir=None):
    """Ejecuta un script de ffmpeg-skill usando el intérprete Python embebido (compatible con .exe)."""
    base_dir = skill_dir or get_ffmpeg_skill_dir()
    if not is_ffmpeg_skill_installed(base_dir):
        safe_print(
            "[AVISO] El complemento 'FFmpeg Skill (42 Herramientas Avanzadas)' no está instalado.\n"
            "        Instálalo en 1 clic desde el botón 'Complementos' en la barra superior de GUI CMD Advance."
        )
        return 1

    script_path = resolve_skill_script(tool_name, skill_dir=base_dir)
    if not script_path:
        safe_print(f"[ERROR] Herramienta de FFmpeg Skill no encontrada: '{tool_name}'.")
        return 1

    args_to_pass = list(script_args or [])
    if str(tool_name).strip().lower() == "doctor" and (not args_to_pass or args_to_pass[0] != "doctor"):
        args_to_pass.insert(0, "doctor")

    scripts_dir = os.path.join(base_dir, "scripts")
    tools_dir = os.path.dirname(base_dir)

    orig_argv = list(sys.argv)
    orig_path = list(sys.path)
    orig_env_path = os.environ.get("PATH", "")

    try:
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        if tools_dir and os.path.isdir(tools_dir):
            os.environ["PATH"] = f"{tools_dir}{os.pathsep}{orig_env_path}"
        sys.argv = [script_path, *args_to_pass]
        runpy.run_path(script_path, run_name="__main__")
        return 0
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        try:
            return int(code)
        except (TypeError, ValueError):
            safe_print(str(code))
            return 1
    except Exception as e:
        safe_print(f"[ERROR] Falló la ejecución de FFmpeg Skill ({tool_name}): {e}")
        return 1
    finally:
        sys.argv = orig_argv
        sys.path[:] = orig_path
        os.environ["PATH"] = orig_env_path


def main(argv=None):
    parser = argparse.ArgumentParser(description="Lanzador portable del complemento FFmpeg Skill.")
    parser.add_argument("--tool", required=True, help="Nombre de la herramienta (ej. silence, stabilize, caption, render, doctor).")
    parser.add_argument("--input", default="", help="Archivo multimedia principal (opcional).")
    args, unknown = parser.parse_known_args(argv)

    pass_args = []
    if args.input:
        pass_args.append(args.input)
    pass_args.extend(unknown)
    return run_skill_script(args.tool, pass_args)


if __name__ == "__main__":
    sys.exit(main())
