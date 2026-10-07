import subprocess
import os

def parse_and_explain_credentials():
    print("========================================")
    print("* BÓVEDA DE CREDENCIALES DE WINDOWS *")
    print("========================================\n")
    print("Escaneando credenciales guardadas en su sistema...\n")
    
    try:
        output = subprocess.check_output("cmdkey /list", shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
        output_str = output.decode('mbcs', errors='ignore')
        lines = output_str.strip().split('\n')
        
        credentials = []
        current_cred = {}
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith("Destino:"):
                if current_cred:
                    credentials.append(current_cred)
                current_cred = {"destino": line.split(":", 1)[1].strip()}
            elif line.startswith("Tipo:"):
                current_cred["tipo"] = line.split(":", 1)[1].strip()
            elif line.startswith("Usuario:") or line.startswith("Nombre de usuario:"):
                current_cred["usuario"] = line.split(":", 1)[1].strip()
                
        if current_cred:
            credentials.append(current_cred)
            
        if not credentials:
            print("No se encontraron credenciales guardadas en Windows.")
            return

        print(f"Se han encontrado {len(credentials)} credenciales:\n")
        
        for idx, cred in enumerate(credentials):
            destino = cred.get("destino", "Desconocido")
            tipo = cred.get("tipo", "Desconocido")
            usuario = cred.get("usuario", "Desconocido")
            
            # Interpretación en lenguaje natural
            interpretacion = ""
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
                
            print(f"[{idx+1}] Destino: {destino}")
            print(f"    Usuario: {usuario}")
            print(f"    Tipo: {tipo}")
            print(f"    -> ¿Qué significa?: {interpretacion}")
            print("-" * 50)
            
        print("\nNota: Por motivos de seguridad, las contraseñas en texto claro no pueden ser extraídas ni mostradas aquí.")
        print("Si desea eliminar alguna, diríjase a: Panel de Control -> Administrador de credenciales.")
            
    except Exception as e:
        print(f"Error al listar credenciales: {e}")

def main_cli():
    parse_and_explain_credentials()

if __name__ == "__main__":
    main_cli()
