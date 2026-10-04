# GUI CMD ADVANCE 🚀

**GUI CMD ADVANCE** es una herramienta gráfica moderna y profesional construida en Python (CustomTkinter) que actúa como una interfaz amigable e inteligente para ejecutar comandos complejos de CMD y PowerShell en Windows, así como herramientas multimedia avanzadas, sin necesidad de tocar la terminal.

¡Un panel de control "todo en uno" para administradores de sistemas, técnicos y power users!

## ✨ Características Principales

*   **⚡ Motor Híbrido CMD/PowerShell:** Ejecuta código directamente en el sistema operativo mediante un motor asíncrono y seguro (no congela la interfaz).
*   **🛠️ Herramientas Propias Integradas:**
    *   **Buscador de Duplicados:** Escanea y limpia archivos duplicados mediante hashes MD5.
    *   **Compresor de Multimedia:** Optimiza imágenes y videos en lote (Integrado con Pillow y FFmpeg).
    *   **Reparador de Multimedia:** Rescata imágenes truncadas y reconstruye videos corruptos.
    *   **Bóveda de Credenciales:** Gestiona, lee y manipula las contraseñas de red de Windows (cmdkey) con una interfaz propia.
    *   **Limpiador Temp Avanzado:** Escanea de forma asíncrona y vacía cachés de Windows Update, Prefetch y Temp.
    *   **Búsqueda Avanzada de Texto:** Un wrapper ultra-rápido de Findstr que agrupa múltiples coincidencias por archivo, soporta Regex y abre archivos nativamente.
    *   **Visor SMART Avanzado:** Extrae y decodifica a bajo nivel los bloques WMI/CIM de discos SATA y NVMe para diagnosticar la salud de tus discos (temperatura, horas de encendido, sectores reasignados) con una interfaz similar a CrystalDiskInfo.
    *   **Bóveda IA y Tren de Modelos:** Integración profunda con Google Gemini, OpenAI, Claude, Deepseek y Groq. Permite configurar múltiples llaves simultáneas (Multi-Agente) e implementar un "Tren de Modelos" que salta automáticamente a otros modelos si el primero falla por cuotas excedidas (Error 429), garantizando una interpretación infalible. Además cuenta con un simulador de conexión para testear las cuotas de tu Tren.
    *   **Despliegue de Office (ODT):** Herramienta gráfica interna para descargar, configurar el XML e instalar Microsoft Office LTSC 2019/2021/2024.
*   **🎨 Interfaz Moderna (CustomTkinter):**
    *   Soporte dinámico para **Modo Claro** y **Modo Oscuro** con un estilo **Flat Design** sin bordes molestos.
    *   Resaltado de sintaxis inteligente en la consola (IPs, errores, rutas y éxitos tienen sus propios colores).
    *   Gestor de Complementos Universal para instalar dependencias de terceros (como FFmpeg o la ODT de Microsoft) bajo demanda.
*   **💾 Sistema de Favoritos:** Guarda tus comandos más usados con un clic (⭐) para acceder rápidamente a ellos.
*   **📊 Monitoreo en Tiempo Real:** Barra de estado inferior con uso actual de CPU y RAM.
*   **📂 Exportación de Reportes:** Guarda los resultados de la consola en formato `.html` interactivo, con visualización de tablas avanzadas, o `.txt` con un solo clic.
*   **🧹 Limpieza Inteligente:** Casilla de *Auto-Limpiar* para mantener los resultados siempre claros.
*   **📦 100% Portable (Zero-Install):** Desarrollado para compilarse en un único archivo `.exe` ultraligero (sin dependencias). Puedes llevar la herramienta en una USB, y el programa creará automáticamente su entorno aislado de persistencia en `C:\GuiCmdAdvance`, protegiendo tus datos contra eliminaciones accidentales y permitiendo un uso offline total.

## 🚀 Instalación y Uso (Modo Portable)

Si solo quieres usar la aplicación, no necesitas instalar Python.
1. Ve a la sección de **Releases** (o a la carpeta `dist/` si has clonado el repositorio).
2. Descarga `Gui Cmd Advance.exe` o `Gui Cmd Advance Beta.exe`.
3. Haz doble clic para ejecutarlo en cualquier PC con Windows (se pedirán permisos de Administrador para que los comandos de red y disco funcionen correctamente).
4. El programa detectará si necesitas complementos extra y te ofrecerá descargarlos en su propia carpeta para un ecosistema aislado.

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
El proyecto incluye un script de automatización (`build_exe.py`) que detecta automáticamente la versión de los commits de Git, inyecta los metadatos de autoría y construye el `.exe` como `--onefile` (ya no adjunta binarios grandes como FFmpeg, manteniendo la build ligera).

```bash
python build_exe.py
```
Te preguntará si es una versión Beta. Tras unos segundos, tendrás tu ejecutable pulido en la carpeta `dist/`.

## ⚙️ ¿Cómo agregar nuevos comandos?
El programa lee los comandos dinámicamente desde `resources/commands_config.json`.
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
