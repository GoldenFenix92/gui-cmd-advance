# GUI CMD ADVANCE 🚀

**GUI CMD ADVANCE** es una herramienta gráfica moderna y profesional construida en Python (CustomTkinter) que actúa como una interfaz amigable e inteligente para ejecutar comandos complejos de CMD y PowerShell en Windows, así como herramientas multimedia avanzadas, sin necesidad de tocar la terminal.

¡Un panel de control "todo en uno" para administradores de sistemas, técnicos y power users!

## ✨ Características Principales

*   **⚡ Motor Híbrido CMD/PowerShell:** Ejecuta código directamente en el sistema operativo mediante un motor asíncrono y seguro (no congela la interfaz).
*   **🛠️ Herramientas Propias Integradadas:**
    *   **Buscador de Duplicados:** Escanea y limpia archivos duplicados mediante hashes MD5.
    *   **Compresor de Multimedia:** Optimiza imágenes y videos en lote (Integrado con Pillow y FFmpeg).
    *   **Reparador de Multimedia:** Rescata imágenes truncadas y reconstruye videos corruptos.
*   **🎨 Interfaz Moderna (CustomTkinter):**
    *   Soporte dinámico para **Modo Claro** y **Modo Oscuro**.
    *   Resaltado de sintaxis inteligente en la consola (IPs, errores, rutas y éxitos tienen sus propios colores).
*   **💾 Sistema de Favoritos:** Guarda tus comandos más usados con un clic (⭐) para acceder rápidamente a ellos.
*   **📊 Monitoreo en Tiempo Real:** Barra de estado inferior con uso actual de CPU y RAM.
*   **📂 Exportación de Reportes:** Guarda los resultados de la consola en formato `.html` interactivo o `.txt` con un solo clic.
*   **🧹 Limpieza Inteligente:** Casilla de *Auto-Limpiar* para mantener los resultados siempre claros.
*   **📦 100% Portable (OneFile):** Desarrollado para compilarse en un único archivo `.exe`. Puedes llevar la herramienta en una USB y ejecutarla en cualquier PC sin instalar dependencias, Python ni configurar entornos.

## 🚀 Instalación y Uso (Modo Portable)

Si solo quieres usar la aplicación, no necesitas instalar Python.
1. Ve a la sección de **Releases** (o a la carpeta `dist/` si has clonado el repositorio).
2. Descarga `Gui Cmd Advance.exe` o `Gui Cmd Advance Beta.exe`.
3. Haz doble clic para ejecutarlo en cualquier PC con Windows (se pedirán permisos de Administrador para que los comandos de red y disco funcionen correctamente).

## 🛠️ Entorno de Desarrollo (Para Programadores)

Si deseas clonar el proyecto, agregar tus propios comandos o modificar el código fuente:

### Requisitos:
*   Python 3.12+
*   Windows 10 / 11

### Instalación:
```bash
# 1. Clonar el repositorio
git clone https://github.com/GoldenFenix92/gui-cmd-advance.git
cd gui-cmd-advance

# 2. Crear un entorno virtual e instalar dependencias
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```
*(Nota: Si `requirements.txt` no existe, asegúrate de instalar `customtkinter`, `pillow`, `psutil`, `pymupdf`)*

### Compilación (Crear tu propio .EXE Portable)
El proyecto incluye un script de automatización (`build_exe.py`) que detecta automáticamente la versión de los commits de Git, inyecta los metadatos de autoría, enlaza `ffmpeg.exe` y construye el `.exe` como `--onefile`.

```bash
python build_exe.py
```
Te preguntará si es una versión Beta. Tras unos segundos, tendrás tu ejecutable pulido en la carpeta `dist/`.

## ⚙️ ¿Cómo agregar nuevos comandos?
El programa lee los comandos dinámicamente desde `commands_config.json`.
Puedes abrir ese archivo y agregar tus propios comandos fácilmente. Ejemplo de estructura:

```json
{
    "name": "ipconfig",
    "description": "Muestra la configuración de red actual.",
    "command": "ipconfig",
    "args": [
        {
            "name": "Todo (All)",
            "flag": "/all",
            "type": "checkbox",
            "description": "Muestra la configuración completa."
        }
    ]
}
```
**Scripts Internos:** Si agregas herramientas de Python personalizadas, usa la bandera `__INTERNAL__ --run-tu-script` en lugar de `python tu-script.py` para asegurar que sigan funcionando cuando la app se compile.

## 📜 Créditos y Autoría
*   **Desarrollador Principal:** Golden Fenix
*   **Copyright:** © 2026 GoldenFenix. Todos los derechos reservados.

---
*Este proyecto fue diseñado con un alto enfoque en calidad de vida (UX), tolerancia a fallos y portabilidad extrema.*
