---
name: pyinstaller-windows-exe
description: >-
  Reglas y checklist de blindaje para compilar, depurar y mantener ejecutables Windows empaquetados con PyInstaller (--onefile --windowed) en GUI CMD Advance. Úsalo siempre que modifiques main.py, gui_app.py, scripts/build_exe.py, subprocesos o cualquier módulo en functions/.
---

# PyInstaller Windows `.EXE` Readiness (`--onefile --windowed`)

Esta skill codifica las reglas críticas que evitan fallos exclusivos del ejecutable compilado (`sys.frozen == True`) en Windows.

## 1. Subprocesos del Propio `.EXE` (`__INTERNAL__` y `subprocess.Popen`)
- **Detectar modo compilado con `getattr(sys, "frozen", False)`**, nunca asumiendo que `sys.argv[0]` termina en `.py`.
- En modo `.exe`, **NO duplicar `sys.argv[0]`**:
  - Correcto (`.exe`): `[sys.executable, "--run-flag", ...]`
  - Correcto (Python): `[sys.executable, os.path.abspath(sys.argv[0]), "--run-flag", ...]`
- **Siempre resetear el entorno del bootloader de PyInstaller 6.x** al lanzar una segunda instancia del mismo `.exe` `--onefile`:
  ```python
  env = os.environ.copy()
  env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
  env.pop("_MEIPASS2", None)
  ```
  Sin esto, el subproceso falla con `Failed to start embedded python interpreter: Failed to import encodings module`.

## 2. Consola `sys.stdout` / `sys.stderr` en `--windowed`
- En ejecutables `--windowed` lanzados sin pipe, **`sys.stdout` y `sys.stderr` pueden ser `None`**.
- **Nunca** llamar directamente a `sys.stdout.flush()`, `sys.stdout.reconfigure(...)` o leer `sys.stdout.encoding` sin validar `if sys.stdout is not None`.
- Usar `safe_print()` de `functions.utils` (que retorna en silencio si `sys.stdout is None` y hace fallback ante `UnicodeEncodeError` en `cp1252`).
- Al arranque de `main.py`, reconfigurar `stdout`/`stderr` a `utf-8` (`errors="replace"`) solo cuando no sean `None` y tengan `.reconfigure`.

## 3. Rutas de Recursos vs. Datos de Usuario
- **Lectura de recursos empaquetados** (`resources/commands_config.json`, `resources/app_icon.ico`, `resources/templates/base_report.html`, temas): usar siempre `functions.utils.get_resource_path(...)` (resuelve a `sys._MEIPASS` en `.exe`). Nunca usar `os.path.dirname(__file__)` directamente.
- **Escritura de archivos temporales o persistentes** (`favorites.json`, `process_history.json`, `config.xml`, `liberar_ram.vbs`, `tools/`): usar siempre `functions.utils.get_user_data_path(...)` (`C:\GuiCmdAdvance\...`), nunca al lado del `.exe` ni dentro de `sys._MEIPASS`.
- **Limpieza de `%TEMP%`**: cualquier limpiador temporal DEBE excluir `sys._MEIPASS` y carpetas `_MEI*` activas para no borrar `base_library.zip` del `.exe` en ejecución.

## 4. Imports Dinámicos y Dependencias
- **Prohibido ejecutar `pip install` vía `sys.executable`** cuando `getattr(sys, "frozen", False)` es `True` (en `.exe`, `sys.executable` es la propia app y provoca un bucle infinito).
- Todo módulo cargado dinámicamente en `main.py` (`--run-*`) o `gui_app.py` DEBE figurar en `HIDDEN_IMPORTS` dentro de `scripts/build_exe.py`.
- Todas las llamadas a `subprocess.run` / `subprocess.Popen` de utilidades CLI (`powershell`, `ffmpeg`, `diskpart`, `cmdkey`, `7za.exe`, `sc`, `net`) deben usar `creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)` para evitar parpadeos de ventanas negras en `--windowed`.

## 5. Verificación Obligatoria Antes de Liberar un Build
1. Ejecutar `python -m unittest discover -s tests -v` (incluye `test_project_integrity.py`, que valida `HIDDEN_IMPORTS`, `sys.stdout=None` y `sys.frozen=True`).
2. Compilar con `python scripts/build_exe.py`.
3. Ejecutar al menos un smoke-test CLI contra `dist/Gui Cmd Advance Beta.exe` (`--run-vault`, `--run-disk-attributes --disk 0 --action inspect`, `--run-7z --action analyze`) verificando salida UTF-8 limpia y ausencia de `ModuleNotFoundError`.
