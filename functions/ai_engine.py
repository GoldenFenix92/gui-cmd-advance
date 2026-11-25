import base64
import ctypes
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
from ctypes import wintypes

from functions.utils import get_user_data_path

# Proveedores soportados y endpoints por defecto
PROVIDERS_ORDER = [
    "Google Gemini",
    "OpenAI",
    "Anthropic Claude",
    "Groq",
    "Deepseek",
    "Ollama (Local)",
    "LM Studio (Local)",
    "Personalizado",
]

LOCAL_PROVIDERS = {"Ollama (Local)", "LM Studio (Local)"}

DEFAULT_ENDPOINTS = {
    "OpenAI": "https://api.openai.com/v1/chat/completions",
    "Groq": "https://api.groq.com/openai/v1/chat/completions",
    "Deepseek": "https://api.deepseek.com/chat/completions",
    "Ollama (Local)": "http://localhost:11434/v1/chat/completions",
    "LM Studio (Local)": "http://localhost:1234/v1/chat/completions",
}

DEFAULT_MODELS_ENDPOINTS = {
    "OpenAI": "https://api.openai.com/v1/models",
    "Groq": "https://api.groq.com/openai/v1/models",
    "Deepseek": "https://api.deepseek.com/models",
    "Ollama (Local)": "http://localhost:11434/v1/models",
    "LM Studio (Local)": "http://localhost:1234/v1/models",
}

ANTHROPIC_FALLBACK_MODELS = [
    "claude-sonnet-4-20250514",
    "claude-3-7-sonnet-20250219",
    "claude-3-5-sonnet-20241022",
    "claude-3-5-haiku-20241022",
]

DPAPI_PREFIX = "dpapi:"
VAULT_FORMAT_VERSION = 1
VAULT_PBKDF2_ITERS = 200_000


# =====================================================================
# 1. Cifrado Local Windows DPAPI (transparente y retrocompatible)
# =====================================================================

class _DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_char)),
    ]


def dpapi_protect(plaintext: str) -> str:
    """Cifra una cadena usando Windows DPAPI (ligada al usuario actual).

    Si no está en Windows o falla, devuelve el texto sin modificar.
    """
    if not plaintext:
        return ""
    if plaintext.startswith(DPAPI_PREFIX):
        return plaintext
    if sys.platform != "win32":
        return plaintext
    try:
        raw = plaintext.encode("utf-8")
        buf = ctypes.create_string_buffer(raw, len(raw))
        blob_in = _DATA_BLOB(len(raw), buf)
        blob_out = _DATA_BLOB()
        ok = ctypes.windll.crypt32.CryptProtectData(
            ctypes.byref(blob_in),
            "GuiCmdAdvanceAIVault",
            None,
            None,
            None,
            0,
            ctypes.byref(blob_out),
        )
        if not ok:
            return plaintext
        try:
            encrypted = ctypes.string_at(blob_out.pbData, blob_out.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(blob_out.pbData)
        return DPAPI_PREFIX + base64.b64encode(encrypted).decode("ascii")
    except Exception:
        return plaintext


def dpapi_unprotect(stored: str) -> str:
    """Descifra una cadena protegida con DPAPI; retrocompatible con texto plano."""
    if not stored:
        return ""
    if not stored.startswith(DPAPI_PREFIX):
        return stored
    if sys.platform != "win32":
        return ""
    try:
        encrypted = base64.b64decode(stored[len(DPAPI_PREFIX):].encode("ascii"))
        buf = ctypes.create_string_buffer(encrypted, len(encrypted))
        blob_in = _DATA_BLOB(len(encrypted), buf)
        blob_out = _DATA_BLOB()
        ok = ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(blob_in),
            None,
            None,
            None,
            None,
            0,
            ctypes.byref(blob_out),
        )
        if not ok:
            return ""
        try:
            decrypted = ctypes.string_at(blob_out.pbData, blob_out.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(blob_out.pbData)
        return decrypted.decode("utf-8")
    except Exception:
        return ""


# =====================================================================
# 2. Respaldo Portátil Cifrado (.aivault) con Contraseña Maestra
# =====================================================================

def _xor_keystream(data: bytes, enc_key: bytes, nonce: bytes) -> bytes:
    """Cifrado de flujo CTR basado en SHA-256 (librería estándar, sin dependencias)."""
    out = bytearray(len(data))
    counter = 0
    pos = 0
    while pos < len(data):
        block = hashlib.sha256(enc_key + nonce + counter.to_bytes(8, "big")).digest()
        chunk_len = min(len(block), len(data) - pos)
        for i in range(chunk_len):
            out[pos + i] = data[pos + i] ^ block[i]
        pos += chunk_len
        counter += 1
    return bytes(out)


def export_encrypted_vault(settings: dict, password: str) -> str:
    """Serializa y cifra settings (con llaves en claro en memoria) a un paquete JSON .aivault."""
    if not password or len(password) < 4:
        raise ValueError("La contraseña maestra debe tener al menos 4 caracteres.")
    # Asegurar llaves descifradas dentro del payload cifrado portátil
    plain_settings = json.loads(json.dumps(settings))
    for prov_data in plain_settings.get("providers", {}).values():
        if isinstance(prov_data, dict) and prov_data.get("api_key"):
            prov_data["api_key"] = dpapi_unprotect(prov_data["api_key"])

    payload_bytes = json.dumps(plain_settings, ensure_ascii=False).encode("utf-8")
    salt = secrets.token_bytes(16)
    nonce = secrets.token_bytes(16)
    master = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, VAULT_PBKDF2_ITERS, dklen=64)
    enc_key, mac_key = master[:32], master[32:]
    ciphertext = _xor_keystream(payload_bytes, enc_key, nonce)
    tag = hmac.new(mac_key, salt + nonce + ciphertext, hashlib.sha256).digest()

    envelope = {
        "format": "gui_cmd_advance_aivault",
        "version": VAULT_FORMAT_VERSION,
        "iterations": VAULT_PBKDF2_ITERS,
        "salt": base64.b64encode(salt).decode("ascii"),
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
        "hmac": base64.b64encode(tag).decode("ascii"),
    }
    return json.dumps(envelope, indent=2)


def import_encrypted_vault(vault_text: str, password: str) -> dict:
    """Valida integridad HMAC y descifra un archivo .aivault con la contraseña maestra."""
    if not password:
        raise ValueError("Debes ingresar la contraseña maestra.")
    try:
        envelope = json.loads(vault_text)
    except Exception as exc:
        raise ValueError(f"Archivo .aivault inválido: {exc}")

    if envelope.get("format") != "gui_cmd_advance_aivault":
        raise ValueError("El archivo seleccionado no es un respaldo .aivault válido.")

    salt = base64.b64decode(envelope["salt"].encode("ascii"))
    nonce = base64.b64decode(envelope["nonce"].encode("ascii"))
    ciphertext = base64.b64decode(envelope["ciphertext"].encode("ascii"))
    expected_tag = base64.b64decode(envelope["hmac"].encode("ascii"))
    iters = int(envelope.get("iterations", VAULT_PBKDF2_ITERS))

    master = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iters, dklen=64)
    enc_key, mac_key = master[:32], master[32:]
    actual_tag = hmac.new(mac_key, salt + nonce + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(actual_tag, expected_tag):
        raise ValueError("Contraseña incorrecta o archivo .aivault alterado.")

    plain_bytes = _xor_keystream(ciphertext, enc_key, nonce)
    return json.loads(plain_bytes.decode("utf-8"))


# =====================================================================
# 3. Persistencia de Configuración (ai_settings.json)
# =====================================================================

def _default_settings() -> dict:
    return {
        "providers": {
            "Google Gemini": {"api_key": "", "model": "", "cached_models": []},
            "OpenAI": {"api_key": "", "model": "", "cached_models": []},
            "Anthropic Claude": {"api_key": "", "model": "", "cached_models": []},
            "Groq": {"api_key": "", "model": "", "cached_models": []},
            "Deepseek": {"api_key": "", "model": "", "cached_models": []},
            "Ollama (Local)": {
                "api_key": "",
                "model": "",
                "base_url": DEFAULT_ENDPOINTS["Ollama (Local)"],
                "cached_models": [],
            },
            "LM Studio (Local)": {
                "api_key": "",
                "model": "",
                "base_url": DEFAULT_ENDPOINTS["LM Studio (Local)"],
                "cached_models": [],
            },
            "Personalizado": {"api_key": "", "model": "", "base_url": "", "cached_models": []},
        },
        "current_provider": "Google Gemini",
        "free_only": True,
        "model_train": [],
    }


def get_settings_path() -> str:
    tools_dir = get_user_data_path("tools")
    os.makedirs(tools_dir, exist_ok=True)
    return os.path.join(tools_dir, "ai_settings.json")


def load_ai_settings() -> dict:
    """Carga la configuración de IA descifrando transparentemente las llaves DPAPI."""
    old_path = get_user_data_path("ai_settings.json")
    settings_path = get_settings_path()
    if os.path.exists(old_path) and not os.path.exists(settings_path):
        try:
            shutil.move(old_path, settings_path)
        except Exception:
            pass

    settings = _default_settings()
    try:
        if os.path.exists(settings_path):
            with open(settings_path, "r", encoding="utf-8") as f:
                saved = json.load(f)
            if "providers" not in saved:
                prov = saved.get("provider", "Google Gemini")
                settings["current_provider"] = prov
                if prov in settings["providers"]:
                    settings["providers"][prov]["api_key"] = dpapi_unprotect(saved.get("api_key", ""))
                    settings["providers"][prov]["model"] = saved.get("model", "")
                    settings["providers"][prov]["cached_models"] = saved.get("cached_models", [])
                    if "base_url" in saved:
                        settings["providers"][prov]["base_url"] = saved["base_url"]
                if "free_only" in saved:
                    settings["free_only"] = saved["free_only"]
            else:
                for k, v in saved.items():
                    if k == "providers" and isinstance(v, dict):
                        for pk, pv in v.items():
                            if pk in settings["providers"] and isinstance(pv, dict):
                                merged = dict(pv)
                                if merged.get("api_key"):
                                    merged["api_key"] = dpapi_unprotect(merged["api_key"])
                                settings["providers"][pk].update(merged)
                    else:
                        settings[k] = v
    except Exception:
        pass
    return settings


def save_ai_settings(settings: dict) -> str:
    """Guarda ai_settings.json cifrando las llaves API con Windows DPAPI."""
    settings_path = get_settings_path()
    to_save = json.loads(json.dumps(settings))
    for prov_data in to_save.get("providers", {}).values():
        if isinstance(prov_data, dict) and prov_data.get("api_key"):
            prov_data["api_key"] = dpapi_protect(prov_data["api_key"])
    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(to_save, f, indent=4, ensure_ascii=False)
    return settings_path


# =====================================================================
# 4. Recorte Inteligente de Logs y Prompts por Dominio (sin emojis)
# =====================================================================

def is_localhost_url(url: str) -> bool:
    if not url:
        return False
    try:
        host = (urllib.parse.urlparse(url).hostname or "").lower()
        return host in ("localhost", "127.0.0.1", "::1")
    except Exception:
        return False


def provider_requires_api_key(provider: str, base_url: str = "") -> bool:
    if provider in LOCAL_PROVIDERS:
        return False
    if provider == "Personalizado" and is_localhost_url(base_url):
        return False
    return True


def smart_truncate_log(text: str, max_chars: int = 18000) -> str:
    """Recorta logs extensos conservando cabecera, líneas de error/aviso y resumen final."""
    if not text or len(text) <= max_chars:
        return text or ""

    lines = text.splitlines()
    head_lines = lines[:35]
    tail_lines = lines[-60:]
    middle = lines[35:-60] if len(lines) > 95 else []

    important_mid = [
        ln for ln in middle
        if any(tok in ln.lower() for tok in ("[error]", "error:", "[warning]", "[aviso]", "failed", "fallo", "denegado", "corrupt", "bad", "critico", "resumen"))
    ][:80]

    assembled = (
        "\n".join(head_lines)
        + f"\n\n[... {max(0, len(middle) - len(important_mid))} líneas intermedias omitidas para optimizar tokens ...]\n\n"
        + ("\n".join(important_mid) + "\n\n" if important_mid else "")
        + "\n".join(tail_lines)
    )
    if len(assembled) > max_chars:
        half = max_chars // 2 - 40
        return assembled[:half] + "\n\n[... contenido recortado por límite de tokens ...]\n\n" + assembled[-half:]
    return assembled


def build_analysis_prompt(content: str, style: str = "tecnico", domain: str = None) -> str:
    """Construye un prompt especializado por dominio y estilo, en español limpio sin emojis."""
    if not domain:
        try:
            from functions.report_generator import detect_report_profile
            domain = detect_report_profile(command=content[:400])
        except Exception:
            domain = "system"

    domain_hint = {
        "storage": "Contexto: Almacenamiento/Discos (SMART, particiones, sectores, formateo, USB). Prioriza salud física, riesgo de pérdida de datos y recomendaciones prácticas.",
        "network": "Contexto: Redes y Conectividad (IP, DNS, latencia, rutas, puertos). Prioriza causa de conectividad y pasos de verificación.",
        "security": "Contexto: Seguridad y Permisos (Firewall, ACL/icacls, credenciales, SDelete). Prioriza impacto de seguridad y permisos.",
        "multimedia": "Contexto: Procesamiento Multimedia (FFmpeg, compresión, reparación, duplicados). Prioriza ahorro de espacio, archivos dañados y calidad.",
        "processes": "Contexto: Procesos y RAM de Windows. Identifica procesos prescindibles (bloatware) y advierte cuáles son críticos de Windows.",
        "system": "Contexto: Administración y Mantenimiento de Windows (SFC, DISM, eventos, sistema).",
    }.get(domain, "Contexto: Consola de administración Windows.")

    style_hint = {
        "simple": "Explica en lenguaje muy sencillo y directo para un usuario no técnico.",
        "errores": "Enfócate ÚNICAMENTE en los errores/advertencias detectados, su causa raíz y los pasos exactos para solucionarlos.",
    }.get(style, "Ofrece un diagnóstico técnico claro estructurado en: 1) Qué ocurrió, 2) Hallazgos o errores, 3) Acción recomendada.")

    safe_content = smart_truncate_log(content)
    return (
        "Eres un especialista senior en soporte técnico de Windows integrado en GUI CMD Advance.\n"
        f"{domain_hint}\n"
        f"{style_hint}\n"
        "Reglas estrictas de formato: Responde en español, en texto plano limpio (SIN emojis y SIN sintaxis Markdown como ** o ##).\n\n"
        "Salida a analizar:\n"
        f"{safe_content}"
    )


# =====================================================================
# 5. Cliente HTTP Unificado y Ejecutor del Tren de Modelos
# =====================================================================

def _resolve_chat_url(provider: str, base_url: str = "") -> str:
    if provider == "Personalizado":
        return (base_url or "").strip()
    if provider in LOCAL_PROVIDERS and (base_url or "").strip():
        return base_url.strip()
    return DEFAULT_ENDPOINTS.get(provider, "")


def _resolve_models_url(provider: str, base_url: str = "") -> str:
    if provider in DEFAULT_MODELS_ENDPOINTS and not (provider in LOCAL_PROVIDERS and base_url.strip()):
        return DEFAULT_MODELS_ENDPOINTS[provider]
    if base_url.strip():
        u = base_url.strip().rstrip("/")
        if u.endswith("/chat/completions"):
            return u[:-len("/chat/completions")] + "/models"
        if u.endswith("/v1"):
            return u + "/models"
        return u + "/v1/models"
    return DEFAULT_MODELS_ENDPOINTS.get(provider, "")


def call_provider(
    provider: str,
    model: str,
    api_key: str,
    prompt: str,
    base_url: str = "",
    timeout: int = 25,
    max_tokens: int = 2048,
) -> str:
    """Ejecuta una llamada de inferencia contra cualquiera de los 8 proveedores soportados."""
    if provider_requires_api_key(provider, base_url) and not api_key:
        raise ValueError(f"Falta API Key para {provider}.")
    if not model:
        raise ValueError(f"Falta seleccionar un modelo para {provider}.")

    if provider == "Google Gemini":
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        return data["candidates"][0]["content"]["parts"][0]["text"]

    if provider == "Anthropic Claude":
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        return data["content"][0]["text"]

    # OpenAI-compatible (OpenAI, Groq, Deepseek, Ollama, LM Studio, Personalizado)
    url = _resolve_chat_url(provider, base_url)
    if not url:
        raise ValueError(f"Falta URL Base para {provider}.")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="replace"))
    return data["choices"][0]["message"]["content"]


def classify_http_error(exc: Exception) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        if exc.code == 429:
            return "HTTP 429 (Límite de cuota excedido)"
        if exc.code in (401, 403):
            return f"HTTP {exc.code} (API Key inválida o sin permisos)"
        if exc.code == 404:
            return "HTTP 404 (Modelo o endpoint no encontrado)"
        if exc.code in (400, 413):
            return f"HTTP {exc.code} (Solicitud rechazada / exceso de tokens)"
        return f"HTTP {exc.code}"
    if isinstance(exc, TimeoutError) or "timed out" in str(exc).lower():
        return "Timeout (El proveedor no respondió a tiempo)"
    return str(exc)[:80]


def fetch_provider_models(
    provider: str,
    api_key: str = "",
    base_url: str = "",
    free_only: bool = True,
    timeout: int = 15,
) -> list:
    """Obtiene la lista de modelos disponibles para cualquier proveedor (incluyendo Ollama/LM Studio)."""
    models = []
    if provider == "Google Gemini":
        url = "https://generativelanguage.googleapis.com/v1beta/models"
        req = urllib.request.Request(url, headers={"x-goog-api-key": api_key})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            res = json.loads(resp.read().decode("utf-8", errors="replace"))
        for m in res.get("models", []):
            name = m.get("name", "").replace("models/", "")
            if name and "vision" not in name and "embedding" not in name:
                models.append(name)

    elif provider == "Anthropic Claude":
        url = "https://api.anthropic.com/v1/models"
        req = urllib.request.Request(
            url,
            headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                res = json.loads(resp.read().decode("utf-8", errors="replace"))
            models = [m.get("id", "") for m in res.get("data", []) if m.get("id")]
        except Exception:
            models = list(ANTHROPIC_FALLBACK_MODELS)

    else:
        url = _resolve_models_url(provider, base_url)
        if not url:
            return []
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                res = json.loads(resp.read().decode("utf-8", errors="replace"))
            for m in res.get("data", []):
                if m.get("id"):
                    models.append(m["id"])
        except Exception:
            # Fallback nativo de Ollama (/api/tags)
            if provider == "Ollama (Local)":
                parsed = urllib.parse.urlparse(url)
                tags_url = f"{parsed.scheme}://{parsed.netloc}/api/tags"
                req = urllib.request.Request(tags_url)
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    res = json.loads(resp.read().decode("utf-8", errors="replace"))
                for m in res.get("models", []):
                    if m.get("name"):
                        models.append(m["name"])
            else:
                raise

    models = sorted(list(set(models)), reverse=True)
    if free_only and provider not in LOCAL_PROVIDERS and provider != "Personalizado":
        excluded = (
            "pro", "opus", "gpt-4", "advanced", "sonnet", "image",
            "video", "veo", "sora", "audio", "whisper", "embedding", "realtime", "tts",
        )
        filtered = [m for m in models if not any(x in m.lower() for x in excluded)]
        if filtered:
            models = filtered
    return models


def run_model_train(
    settings: dict,
    prompt: str,
    use_train: bool = True,
    status_cb=None,
    timeout: int = 25,
):
    """Ejecuta el Tren de Modelos con fallback automático (o proveedor principal si el tren está vacío).

    Retorna dict: {ok, text, provider, model, errors}.
    """
    train = list(settings.get("model_train", [])) if use_train else []
    if not train:
        prov = settings.get("current_provider", "Google Gemini")
        pdata = settings.get("providers", {}).get(prov, {})
        if pdata.get("model"):
            train = [{"provider": prov, "model": pdata.get("model")}]

    if not train:
        return {
            "ok": False,
            "text": "",
            "provider": "",
            "model": "",
            "errors": ["No hay modelos configurados. Abre 'Configurar API (IA)' para definir un proveedor o Tren."],
        }

    errors = []
    for item in train:
        provider = item.get("provider", "")
        model = item.get("model", "")
        pdata = settings.get("providers", {}).get(provider, {})
        api_key = pdata.get("api_key", "")
        base_url = pdata.get("base_url", "")

        if provider_requires_api_key(provider, base_url) and not api_key:
            errors.append(f"{provider} ({model}): Sin API Key.")
            continue

        if status_cb:
            status_cb(f"Consultando {provider} ({model})...")

        try:
            text_out = call_provider(
                provider=provider,
                model=model,
                api_key=api_key,
                prompt=prompt,
                base_url=base_url,
                timeout=timeout,
            )
            return {
                "ok": True,
                "text": text_out,
                "provider": provider,
                "model": model,
                "errors": errors,
            }
        except Exception as exc:
            reason = classify_http_error(exc)
            errors.append(f"{provider} ({model}): {reason}")
            if status_cb:
                status_cb(f"[AVISO] {provider} ({model}) falló ({reason}). Probando siguiente...")

    return {
        "ok": False,
        "text": "",
        "provider": "",
        "model": "",
        "errors": errors,
    }


# =====================================================================
# 6. Analizador Offline Enriquecido (8 dominios, sin internet ni API)
# =====================================================================

def analyze_offline(content: str) -> str:
    """Genera un diagnóstico local instantáneo cubriendo los principales módulos de la app."""
    if not content or not content.strip():
        return "[INFO] No hay texto en consola para analizar."

    low = content.lower()
    out = []

    # 1. Ping
    if "ping" in low and ("ttl=" in low or "perdidos" in low or "lost" in low):
        out.append("[RED - PING]")
        m_lost = re.search(r"(?:perdidos|lost)\s*=\s*(\d+)", low)
        if m_lost:
            lost = int(m_lost.group(1))
            if lost == 0:
                out.append("  [OK] Conectividad estable: 0 paquetes perdidos.")
            else:
                out.append(f"  [AVISO] Se perdieron {lost} paquetes. Revisa cable, WiFi o ejecuta tracert/pathping.")
        m_avg = re.search(r"(?:media|average)\s*=\s*(\d+)\s*ms", low)
        if m_avg:
            ms = int(m_avg.group(1))
            nivel = "excelente" if ms < 50 else ("normal" if ms < 150 else "alta")
            out.append(f"  Latencia promedio: {ms} ms ({nivel}).")

    # 2. IPConfig
    if "ipconfig" in low or "ipv4" in low or "puerta de enlace" in low:
        ip = re.search(r"(?:direcci.n ipv4|ipv4 address)[^:]*:\s*([\d\.]+)", low)
        gw = re.search(r"(?:puerta de enlace predeterminada|default gateway)[^:]*:\s*([\d\.]+)", low)
        if ip or gw:
            out.append("[RED - IPCONFIG]")
            if ip:
                out.append(f"  [OK] Dirección IPv4 local detectada: {ip.group(1)}")
            if gw:
                out.append(f"  [OK] Puerta de enlace (router): {gw.group(1)}")

    # 3. SFC / DISM
    if "sfc" in low or "dism" in low or "protección de recursos" in low or "resource protection" in low:
        out.append("[SISTEMA - SFC / DISM]")
        if any(k in low for k in ("no encontró ninguna infracción", "did not find any integrity violations", "la operación de restauración se completó")):
            out.append("  [OK] La integridad del sistema Windows es saludable o fue restaurada.")
        elif any(k in low for k in ("no pudo reparar", "unable to fix", "corrupt")):
            out.append("  [ERROR] Se detectaron archivos dañados sin reparar. Ejecuta DISM /RestoreHealth y luego repite SFC /scannow.")

    # 4. Escáner de Superficie / Sectores / SMART
    if "escaner de superficie" in low or "mapa visual de superficie" in low or "reallocated" in low or "smart" in low:
        out.append("[ALMACENAMIENTO - SUPERFICIE / SMART]")
        m_bad = re.search(r"danados\s*\(error i/o\)\s*:\s*(\d+)", low)
        m_crit = re.search(r"criticos\s*\(>1000 ms\)\s*:\s*(\d+)", low)
        if m_bad and int(m_bad.group(1)) > 0:
            out.append(f"  [ERROR] Se detectaron {m_bad.group(1)} bloques dañados con error de E/S. Respalda tus datos de inmediato.")
        elif m_crit and int(m_crit.group(1)) > 0:
            out.append(f"  [AVISO] Se detectaron {m_crit.group(1)} bloques críticos (>1000 ms). Monitorea el disco con SMART.")
        elif "superficie saludable" in low:
            out.append("  [OK] Superficie física saludable sin sectores lentos ni defectuosos.")

    # 5. Auditor USB
    if "auditor de autenticidad" in low or "vid / pid" in low:
        out.append("[ALMACENAMIENTO - AUDITOR DE AUTENTICIDAD]")
        if "falsificada" in low or "alterada" in low or "corrupt" in low:
            out.append("  [ERROR] Indicios de unidad falsificada o capacidad alterada. No almacenes datos importantes en ella.")
        elif "original" in low or "autentica" in low:
            out.append("  [OK] La unidad pasó las verificaciones de autenticidad.")

    # 6. Compresor Multimedia
    if "espacio ahorrado:" in low or "compresor" in low:
        out.append("[MULTIMEDIA - COMPRESIÓN]")
        m_save = re.search(r"espacio ahorrado:\s*([^\r\n]+)", content, flags=re.IGNORECASE)
        if m_save:
            out.append(f"  [OK] Ahorro reportado: {m_save.group(1).strip()}")

    # 7. SDelete
    if "sdelete" in low or "borrado seguro irreversible" in low:
        out.append("[SEGURIDAD - SDELETE]")
        if "completada exitosamente" in low:
            out.append("  [OK] El borrado seguro irreversible concluyó sin errores.")

    # 8. Conteo general de errores y advertencias
    err_lines = [ln.strip() for ln in content.splitlines() if any(k in ln.lower() for k in ("[error]", "error:", "acceso denegado", "access is denied", "fallo definitivo"))]
    warn_lines = [ln.strip() for ln in content.splitlines() if any(k in ln.lower() for k in ("[aviso]", "[warning]", "advertencia"))]

    if err_lines or warn_lines:
        out.append("[RESUMEN DE INCIDENCIAS]")
        out.append(f"  Errores detectados: {len(err_lines)} | Advertencias: {len(warn_lines)}")
        for e in err_lines[:5]:
            out.append(f"  - {e[:140]}")

    if not out:
        out.append("[INFO] Análisis local finalizado. No se detectaron errores ni patrones conocidos; usa 'Analizar con IA (Online)' para una explicación detallada.")

    return "\n".join(out)
