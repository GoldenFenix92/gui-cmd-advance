---
name: cmd-gui-design
description: >-
  Use this skill to maintain consistency in the project's UI design. Read this when adding new UI elements, modifying the layout, or implementing new visual features.
---

# CMD GUI Advance - Design System

Este documento actúa como la guía definitiva para mantener la consistencia visual y de diseño (UX/UI) en la aplicación CMD GUI Advance. Cualquier agente o desarrollador que añida componentes visuales DEBE leer y aplicar estas reglas.

## 1. Tema y Paleta de Colores (GitHub Style)

La aplicación utiliza un tema personalizado basado en la paleta de colores oficial de GitHub, soportando modos "Dark" y "Light".

### Archivo de Tema
El tema está definido en el archivo `github_theme.json` y se carga en CustomTkinter con:
```python
ctk.set_default_color_theme("github_theme.json")
```

### Colores Clave
- **Dark Mode**: Fondos profundos (`#0D1117`, `#161B22`), bordes sutiles (`#30363D`), texto claro (`#C9D1D9`).
- **Light Mode**: Fondos limpios (`#F6F8FA`, `#FFFFFF`), bordes grises (`#D0D7DE`), texto oscuro (`#24292F`).
- **Acentos (Botones y Checkboxes)**: Azul GitHub para selección (`#0969DA` / `#2F81F7`), Verde GitHub para botones de acción (`#1F883D` / `#238636`).

## 2. Layout y Estructura

La ventana principal está dividida en dos paneles usando `grid` con pesos (`weight`) para asegurar una correcta distribución al maximizar la ventana.

### Panel Izquierdo (Controles y Configuración)
- **Ubicación**: `column=0`, `weight=1`. Mantiene un tamaño relativamente estático al estirar la ventana.
- **Componentes**: 
  - Switch para modo Claro/Oscuro.
  - Menús desplegables (`CTkOptionMenu`) para Categorías y Comandos (evitar usar pestañas).
  - Un área scrolleable (`CTkScrollableFrame`) para cargar dinámicamente las opciones del comando (checkboxes).
  - Un botón de ejecución.

### Panel Derecho (Consola)
- **Ubicación**: `column=1`, `weight=3`. Se estira para tomar el espacio sobrante cuando la ventana se maximiza.
- **Componentes**: 
  - Una caja de texto (`CTkTextbox`) en modo solo lectura (`disabled`) con fuente monoespaciada (`Consolas`, `Courier`) para emular la terminal.
  - Botones en la parte inferior para "Exportar" y "Limpiar".

## 3. Generación Dinámica

La UI debe ser estrictamente dirigida por datos (Data-Driven). 
- NO se deben "hardcodear" comandos en `gui_app.py`.
- Todo comando debe leerse desde `commands_config.json`.
- Al seleccionar un comando del menú desplegable, el panel de opciones debe limpiarse y re-renderizarse dinámicamente leyendo los atributos del JSON.

## 4. Experiencia de Usuario (UX)

- **Feedback de Ejecución**: Cuando un comando se ejecuta, el botón de ejecución debe deshabilitarse y mostrar el texto "Ejecutando..." para evitar clicks múltiples accidentales.
- **Asincronía**: Toda ejecución de comando debe hacerse mediante hilos (revisar `cmd_executor.py`) para evitar que la UI se congele (no usar bloqueos síncronos).
- **Descripciones**: Mostrar descripciones breves (leídas del JSON) debajo del nombre del comando o argumento usando un color de texto gris (`text_color="gray"`) y fuente más pequeña para guiar al usuario.
