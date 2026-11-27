import os
import re
import subprocess
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


def classify_commit_impact(commit_messages):
    """Clasifica el impacto SemVer ('major', 'minor', 'patch', 'none') desde mensajes Conventional Commits."""
    impact_rank = {"none": 0, "patch": 1, "minor": 2, "major": 3}
    best = "none"

    breaking_re = re.compile(r"^[a-zA-Z]+(?:\([^)]+\))?!:", re.MULTILINE)
    feat_re = re.compile(r"^feat(?:\([^)]+\))?:", re.IGNORECASE)
    patch_re = re.compile(r"^(?:fix|perf|security|refactor|style)(?:\([^)]+\))?:", re.IGNORECASE)

    for raw_msg in commit_messages or []:
        msg = str(raw_msg or "").strip()
        if not msg:
            continue
        first_line = msg.splitlines()[0].strip()
        if "BREAKING CHANGE:" in msg or "BREAKING-CHANGE:" in msg or breaking_re.search(first_line):
            candidate = "major"
        elif feat_re.match(first_line):
            candidate = "minor"
        elif patch_re.match(first_line):
            candidate = "patch"
        else:
            candidate = "none"
        if impact_rank[candidate] > impact_rank[best]:
            best = candidate
            if best == "major":
                break
    return best


def apply_release_channel(version_str, is_beta):
    """Devuelve la versión SemVer en canal Beta ('X.Y.Z-beta') o Estable ('X.Y.Z'), sin sufijos .1/.2."""
    parsed = parse_version(version_str)
    if parsed is None:
        raise ValueError(f"Versión SemVer inválida: {version_str!r}")
    major, minor, patch = parsed[0], parsed[1], parsed[2]
    if is_beta:
        return f"{major}.{minor}.{patch}-beta"
    return f"{major}.{minor}.{patch}"


def bump_semver(base_version, impact):
    """Calcula la siguiente versión SemVer canónica según el impacto ('major', 'minor', 'patch', 'none').

    - Siempre mantiene el formato limpio sin sufijos numéricos (.1/.2):
      - Estable: '2.0.0' -> major: '3.0.0', minor: '2.1.0', patch: '2.0.1'
      - Beta:    '2.0.0-beta' -> major: '3.0.0-beta', minor: '2.1.0-beta', patch: '2.0.1-beta'
    """
    cleaned = str(base_version or "").strip()
    if not is_valid_canonical_semver(cleaned):
        raise ValueError(f"Versión SemVer base inválida: {base_version!r}")
    if impact not in ("major", "minor", "patch", "none"):
        raise ValueError(f"Impacto SemVer inválido: {impact!r}")

    m = CANONICAL_SEMVER_RE.match(cleaned)
    major = int(m.group(1))
    minor = int(m.group(2))
    patch = int(m.group(3))
    pre_label = m.group(4)

    if impact == "none":
        return f"{major}.{minor}.{patch}-beta" if pre_label else f"{major}.{minor}.{patch}"

    if impact == "major":
        major += 1
        minor = 0
        patch = 0
    elif impact == "minor":
        minor += 1
        patch = 0
    else:
        patch += 1

    if pre_label:
        return f"{major}.{minor}.{patch}-beta"
    return f"{major}.{minor}.{patch}"


def _run_git(args, repo_root=None):
    cwd = repo_root or PROJECT_ROOT
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            timeout=5,
        )
        if proc.returncode != 0:
            return None
        return proc.stdout
    except Exception:
        return None


def is_version_file_dirty(repo_root=None):
    """Retorna True si el archivo VERSION tiene cambios sin commitear en el working tree."""
    out = _run_git(["status", "--porcelain", "--", "VERSION"], repo_root=repo_root)
    return bool(out and out.strip())


def get_commits_since_last_version_update(repo_root=None):
    """Obtiene los mensajes de commits posteriores al último commit que modificó VERSION."""
    last_ver_hash = _run_git(["log", "-n", "1", "--format=%H", "--", "VERSION"], repo_root=repo_root)
    if not last_ver_hash or not last_ver_hash.strip():
        return []
    commit_hash = last_ver_hash.strip()
    raw = _run_git(["log", f"{commit_hash}..HEAD", "--format=%s%n%b%x1e"], repo_root=repo_root)
    if not raw:
        return []
    return [entry.strip() for entry in raw.split("\x1e") if entry.strip()]


def detect_version_from_git(version_file=None, repo_root=None):
    """Detecta la versión activa combinando VERSION y el impacto de commits posteriores en Git."""
    root = repo_root or PROJECT_ROOT
    vpath = version_file or os.path.join(root, "VERSION")
    base_version = read_canonical_version(vpath)

    if not os.path.isdir(os.path.join(root, ".git")):
        return {
            "base_version": base_version,
            "detected_version": base_version,
            "impact": "none",
            "commits_since": 0,
            "auto_bumped": False,
        }

    # Si VERSION ya fue ajustado manualmente en el working tree, respetar ese valor sin doble incremento
    if is_version_file_dirty(repo_root=root):
        return {
            "base_version": base_version,
            "detected_version": base_version,
            "impact": "none",
            "commits_since": 0,
            "auto_bumped": False,
        }

    commits = get_commits_since_last_version_update(repo_root=root)
    impact = classify_commit_impact(commits)
    detected = bump_semver(base_version, impact)
    return {
        "base_version": base_version,
        "detected_version": detected,
        "impact": impact,
        "commits_since": len(commits),
        "auto_bumped": detected != base_version,
    }


def sync_version_files(version_str, build_number=None, repo_root=None):
    """Sincroniza VERSION y version.py con la versión SemVer canónica indicada."""
    cleaned = str(version_str or "").strip()
    if not is_valid_canonical_semver(cleaned):
        raise ValueError(f"Versión SemVer inválida: {version_str!r}")
    root = repo_root or PROJECT_ROOT
    with open(os.path.join(root, "VERSION"), "w", encoding="utf-8") as f:
        f.write(f"{cleaned}\n")
    if build_number is not None:
        with open(os.path.join(root, "version.py"), "w", encoding="utf-8") as vf:
            vf.write(f'__version__ = "{cleaned}"\n')
            vf.write(f"__build__ = {int(build_number)}\n")


def get_app_version():
    """Obtiene la versión activa de la aplicación de forma unificada.

    - En entorno compilado (PyInstaller): prioriza version.py empaquetado.
    - En desarrollo desde código fuente: detecta automáticamente desde VERSION + commits Git.
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
            return detect_version_from_git(VERSION_FILE_PATH, PROJECT_ROOT)["detected_version"]
        except Exception:
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
