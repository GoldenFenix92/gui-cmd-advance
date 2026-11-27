# Auditoría Obligatoria y Exclusiva de Versionado (SemVer)

Después de **cualquier cambio** funcional, arquitectónico, corrección de errores o antes de compilar/publicar un ejecutable, es **obligatorio** ejecutar esta auditoría de versionado para garantizar que la versión del proyecto sea siempre coherente y nunca vuelvan a ocurrir desfases, bucles de actualización o numeraciones arbitrarias.

## 1. Fuente Única de Verdad (`VERSION`)

- El archivo `VERSION` en la raíz del repositorio es la **única fuente de verdad** para la versión de la aplicación.
- Debe cumplir estrictamente con SemVer canónico:
  - Estable: `MAJOR.MINOR.PATCH` (ejemplo: `2.0.0`, `2.1.3`)
  - Pre-release: `MAJOR.MINOR.PATCH-(alpha|beta|rc)[.N]` (ejemplo: `2.0.0-beta`, `2.0.0-beta.2`, `2.1.0-rc.1`)
- **Prohibido** hardcodear versiones en `gui_app.py`, `functions/telemetry.py` o `scripts/build_exe.py`. Todos deben leer la versión exclusivamente a través de `functions/versioning.py`.
- **Prohibido** derivar `MAJOR.MINOR.PATCH` a partir del conteo de commits (`1.0.<commits>`). El conteo de commits de Git solo se usa en el **4.º octeto** de `FileVersion` de Windows (`MAJOR.MINOR.PATCH.BUILD`).

## 2. Reglas de Incremento de Versión por Tipo de Cambio

Antes de cerrar un cambio o preparar un release, evalúa el alcance de los cambios desde el último tag/release:

| Tipo de cambio | Qué incrementar | Ejemplo (Beta) | Ejemplo (Estable) |
|---|---|---|---|
| **Arquitectónico / Breaking** (`BREAKING CHANGE` / `!:`) | `MAJOR` (reinicia `MINOR` y `PATCH` a `0`) | `2.0.0-beta` -> `3.0.0-beta` | `2.0.0` -> `3.0.0` |
| **Nueva funcionalidad** (`feat:`) | `MINOR` (reinicia `PATCH` a `0`) | `2.0.0-beta` -> `2.1.0-beta` | `2.0.0` -> `2.1.0` |
| **Corrección / ajuste menor** (`fix:`, `perf:`, `style:`) | `PATCH` | `2.1.0-beta` -> `2.1.1-beta` | `2.1.0` -> `2.1.1` |
| **Paso de Beta a Estable** | Quitar sufijo `-beta` (confirmado al compilar) | `2.1.0-beta` -> `2.1.0` | — |
| **Solo docs / tests / chore interno** | Sin incremento obligatorio | Mantiene `VERSION` | Mantiene `VERSION` |

> Nota: Las versiones Beta usan siempre el sufijo limpio `-beta` (sin `.1` / `.2`). Antes de compilar, `scripts/build_exe.py` pregunta si la compilación continúa siendo Beta (`s`) o pasa a Estable (`n`).

## 3. Reglas del Compilador y Auto-Actualizador

1. `scripts/build_exe.py` debe leer `VERSION` vía `resolve_build_metadata()`:
   - Detecta automáticamente el canal (**Beta** si tiene sufijo `alpha`/`beta`/`rc`, **Estable** si no).
   - Nombra automáticamente el binario `Gui Cmd Advance Beta.exe` o `Gui Cmd Advance.exe` sin intervención manual propensa a error.
   - Genera `version.py` (`__version__` y `__build__`) y `version_info.txt` con `FileVersion = MAJOR.MINOR.PATCH.BUILD` y `ProductVersion = VERSION`.
2. `functions/telemetry.py` debe comparar versiones **únicamente** con `is_newer_version(remote_tag, current_version)` de `functions/versioning.py`:
   - Nunca usar `!=` o comparación de cadenas.
   - Debe retornar `False` ante versiones iguales (`v2.0.0-beta` vs `2.0.0-beta`) y ante versiones remotas menores (sin downgrades).

## 4. Checklist Obligatoria de Auditoría de Versión

Antes de declarar completado un cambio o crear un tag/release:

1. Confirmar que `VERSION` contiene una cadena SemVer válida y coherente con el alcance de los cambios.
2. Ejecutar `.\.venv\Scripts\python.exe -m unittest tests/test_versioning.py -v` y confirmar **0 errores y 0 fallos**.
3. Si se prepara un release o compilación `.exe`:
   - Verificar que el tag de Git coincida exactamente con `v<VERSION>` (ejemplo: `v2.0.0-beta`).
   - Compilar con `scripts/build_exe.py` y confirmar que `FileVersion` y el nombre del `.exe` coinciden con `VERSION`.
4. Si cualquier punto falla o hay desfase entre `VERSION`, `build_exe.py`, `telemetry.py` o `version.py`, corregir inmediatamente antes de continuar.
