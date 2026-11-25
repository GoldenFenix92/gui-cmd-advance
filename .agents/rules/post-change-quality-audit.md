---
name: post-change-quality-audit
description: Mandatory post-change quality audit and repair loop after every modification in GUI CMD Advance.
trigger: always_on
---

# Auditoría Obligatoria de Calidad Post-Cambio

Después de realizar **cualquier cambio** de código, interfaz gráfica, configuración (`resources/commands_config.json`, temas, plantillas) o scripts de compilación, es **obligatorio** ejecutar una auditoría de calidad antes de reportar la tarea como terminada o realizar un commit.

## Checklist de Auditoría Post-Cambio

1. **Suite Completa de Pruebas Automatizadas**:
   - Ejecutar `.\.venv\Scripts\python.exe -m unittest discover -s tests -v` y confirmar **0 errores y 0 fallos**.
   - Si el cambio introduce lógica nueva o corrige un bug, agregar o actualizar pruebas unitarias que cubran el comportamiento nuevo y los casos borde.
2. **Higiene y Seguridad del Código**:
   - Cero emojis decorativos en código/UI (solo se permiten los botones compactos aprobados: `ℹ`, `❔`, `⭐`, `🗑️`, `👁️`/`🙈` y `⭐ Favoritos`).
   - Cero bloques `except:` desnudos (usar `except Exception:` o excepciones específicas).
   - Todas las llamadas `subprocess` deben incluir `creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)` o `startupinfo`.
   - Usar `safe_print()` de `functions.utils` en módulos de `functions/`.
3. **Integridad de Catálogo y PyInstaller (`--onefile --windowed`)**:
   - Verificar JSON válido y sintaxis PowerShell AST sin errores en `resources/commands_config.json`.
   - Confirmar que todo módulo nuevo en `functions/` figure en `HIDDEN_IMPORTS` dentro de `scripts/build_exe.py` y que todo flag `--run-*` exista en `main.py`.
   - Si se compila un `.exe`, ejecutar un smoke-test CLI contra el binario generado en `dist/`.
4. **Verificación Funcional / Visual**:
   - Confirmar que los cambios de UI, advertencias, flujos encadenados o reportes se comporten correctamente y no generen regresiones en funciones existentes.

## Regla de Reparación Inmediata (Ciclo Cerrado)

- Si **cualquier** verificación de la auditoría falla, muestra advertencias inesperadas o presenta un comportamiento incorrecto:
  1. **NO** declarar la tarea completada ni avanzar al commit.
  2. Diagnosticar la causa raíz del problema.
  3. Volver al código para repararlo completamente.
  4. Repetir la auditoría de calidad desde el paso 1 hasta confirmar que **todo** funcione correctamente.
