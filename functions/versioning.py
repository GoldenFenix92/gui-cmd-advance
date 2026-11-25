import os
import re
import sys

# Patrón SemVer estricto para el archivo canónico VERSION:
# Ejemplos válidos: 2.0.0, 2.0.0-beta, 2.0.0-beta.1, 2.1.0-rc.2, 2.0.0-alpha.1
CANONICAL_SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-(alpha|beta|rc)(?:\.([1-9]\d*))?)?$"
)

# Patrón flexible para comparar tags remotos, cadenas heredadas ("1.0.126 Beta", "v1.0.39-beta", "2.0.0.136")
FLEXIBLE_VERSION_RE = re.compile(
    r"^\s*v?(\d+)\.(\d+)\.(\d+)(?:\.(\d+))?(?:[\s\-_]*(alpha|beta|rc)(?:[\.\-_]?(\d+))?)?\s*$",
    re.IGNORECASE,
)

PRERELEASE_ORDER = {
    "alpha": 0,
    "beta": 1,
    "rc": 2,
    None: 3,  # Release estable siempre tiene mayor precedencia que cualquier pre-release
}

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION_FILE_PATH = os.path.join(PROJECT_ROOT, "VERSION")


def is_valid_canonical_semver(version_str):
    """Retorna True si la cadena cumple el formato canónico SemVer del proyecto."""
    if not version_str or not isinstance(version_str, str):
        return False
    return bool(CANONICAL_SEMVER_RE.match(version_str.strip()))


def parse_version(version_str):
    """Parsea una cadena de versión a una tupla ordenable para comparación SemVer.

    Soporta formatos canónicos ('2.0.0-beta', '2.0.0-beta.1', '2.0.0'),
    tags de GitHub ('v2.0.0-beta') y formatos heredados ('1.0.126 Beta').

    Retorna None si la cadena no es reconocible.
    """
    if not version_str or not isinstance(version_str, str):
        return None
    m = FLEXIBLE_VERSION_RE.match(version_str.strip())
    if not m:
        return None
    major = int(m.group(1))
    minor = int(m.group(2))
    patch = int(m.group(3))
    pre_label = m.group(5).lower() if m.group(5) else None
    pre_num = int(m.group(6)) if m.group(6) else 0
    pre_rank = PRERELEASE_ORDER[pre_label]
    return (major, minor, patch, pre_rank, pre_num)


def is_newer_version(remote_version, current_version):
    """Retorna True únicamente si remote_version es estrictamente mayor que current_version.

    Evita bucles de actualización en Betas ('2.0.0-beta' vs 'v2.0.0-beta' -> False)
    y evita downgrades cuando el usuario ejecuta una versión más reciente que el último release.
    """
    remote_parsed = parse_version(remote_version)
    current_parsed = parse_version(current_version)
    if remote_parsed is None or current_parsed is None:
        return False
    return remote_parsed > current_parsed


def is_prerelease(version_str):
    """Retorna True si la versión incluye etiqueta pre-release (alpha, beta, rc)."""
    parsed = parse_version(version_str)
    if parsed is None:
        return False
    return parsed[3] < PRERELEASE_ORDER[None]


def to_windows_version_tuple(version_str, build_number=0):
    """Convierte una versión SemVer + número de build Git a tupla Windows (v1, v2, v3, v4)."""
    parsed = parse_version(version_str)
    if parsed is None:
        raise ValueError(f"Versión SemVer inválida: {version_str!r}")
    build = max(0, min(int(build_number), 65535))
    return (parsed[0], parsed[1], parsed[2], build)


def format_git_tag(version_str):
    """Devuelve el tag Git estándar correspondiente (ej. '2.0.0-beta' -> 'v2.0.0-beta')."""
    cleaned = str(version_str or "").strip()
    if not cleaned:
        return ""
    return cleaned if cleaned.startswith("v") else f"v{cleaned}"


def read_canonical_version(version_file=None):
    """Lee y valida la versión canónica desde el archivo VERSION del repositorio."""
    path = version_file or VERSION_FILE_PATH
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read().strip()
    if not is_valid_canonical_semver(raw):
        raise ValueError(
            f"El archivo VERSION contiene un valor inválido: {raw!r}. "
            "Usa formato SemVer válido (ej. '2.0.0', '2.0.0-beta', '2.0.0-beta.1')."
        )
    return raw


def get_app_version():
    """Obtiene la versión activa de la aplicación de forma unificada.

    - En entorno compilado (PyInstaller): prioriza version.py empaquetado.
    - En desarrollo desde código fuente: prioriza el archivo canónico VERSION.
    """
    if getattr(sys, "frozen", False):
        try:
            from version import __version__ as frozen_ver
            if frozen_ver:
                return str(frozen_ver).strip()
        except Exception:
            pass

    if os.path.isfile(VERSION_FILE_PATH):
        try:
            return read_canonical_version(VERSION_FILE_PATH)
        except Exception:
            pass

    try:
        from version import __version__ as fallback_ver
        if fallback_ver:
            return str(fallback_ver).strip()
    except Exception:
        pass

    return "0.0.0"
