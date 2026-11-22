import subprocess
from functions.utils import safe_print


def parse_cmdkey_output(output_str):
    """Parsea la salida de 'cmdkey /list' en español e inglés."""
    credentials = []
    current_cred = {}
    for raw_line in (output_str or "").splitlines():
        line = raw_line.strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key_l = key.strip().lower()
        val = value.strip()
        if key_l in ("destino", "target"):
            if current_cred:
                credentials.append(current_cred)
            current_cred = {"destino": val}
        elif key_l in ("tipo", "type"):
            current_cred["tipo"] = val
        elif key_l in ("usuario", "nombre de usuario", "user"):
            current_cred["usuario"] = val

    if current_cred:
        credentials.append(current_cred)
    return credentials


def parse_and_explain_credentials():
    safe_print("========================================")
    safe_print("* BÓVEDA DE CREDENCIALES DE WINDOWS *")
    safe_print("========================================\n")
    safe_print("Escaneando credenciales guardadas en su sistema...\n")
    
    try:
        output = subprocess.check_output("cmdkey /list", shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
        output_str = output.decode('mbcs', errors='ignore')
        credentials = parse_cmdkey_output(output_str)
            
        if not credentials:
            safe_print("No se encontraron credenciales guardadas en Windows.")
            return

        safe_print(f"Se han encontrado {len(credentials)} credenciales:\n")
        
        for idx, cred in enumerate(credentials):
            destino = cred.get("destino", "Desconocido")
            tipo = cred.get("tipo", "Desconocido")
            usuario = cred.get("usuario", "Desconocido")
            
            # Interpretación en lenguaje natural
            if "OneDrive" in destino:
                interpretacion = f"Esta es tu cuenta de OneDrive ({usuario}). Windows usa esto para sincronizar tus archivos en la nube silenciosamente."
            elif "MicrosoftAccount" in destino or "SSO" in destino:
                interpretacion = f"Esta es una credencial de tu Cuenta Microsoft ({usuario}). Evita que tengas que escribir tu contraseña cada vez que usas apps de Microsoft (Xbox, Store, Correo)."
            elif "vscode" in destino.lower() or "github" in destino.lower():
                interpretacion = f"Credencial de desarrollo (ej. VS Code, GitHub). Permite a tus editores de código acceder a tus repositorios como el usuario {usuario}."
            elif "WindowsLive" in destino:
                interpretacion = f"Credencial legacy de Windows Live / Xbox Live para el usuario {usuario}."
            elif "LegacyGeneric" in destino:
                interpretacion = f"Una credencial genérica guardada por una aplicación local (posiblemente un navegador o red local) para el usuario {usuario}."
            elif "Domain:" in destino or "Enterprise" in destino:
                interpretacion = f"Credencial corporativa o de red local ({usuario}). Se usa para acceder a recursos de tu trabajo o computadoras en la misma red LAN."
            else:
                interpretacion = f"Esta credencial permite que una aplicación específica acceda al recurso '{destino}' automáticamente como el usuario '{usuario}' sin pedirte contraseña."
                
            safe_print(f"[{idx+1}] Destino: {destino}")
            safe_print(f"    Usuario: {usuario}")
            safe_print(f"    Tipo: {tipo}")
            safe_print(f"    -> ¿Qué significa?: {interpretacion}")
            safe_print("-" * 50)
            
        safe_print("\nNota: Por motivos de seguridad, las contraseñas en texto claro no pueden ser extraídas ni mostradas aquí.")
        safe_print("Si desea eliminar alguna, diríjase a: Panel de Control -> Administrador de credenciales.")
            
    except Exception as e:
        safe_print(f"Error al listar credenciales: {e}")

def main_cli():
    parse_and_explain_credentials()

if __name__ == "__main__":
    main_cli()
