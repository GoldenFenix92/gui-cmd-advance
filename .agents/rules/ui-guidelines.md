---
name: ui-guidelines
description: Rules for building new UI tools and commands for gui-cmd-advance
---

# UI Guidelines for GUI-CMD-Advance

When requested to create or add a new function, tool, or command to this project, follow this primary design principle:

**Integration over Fragmentation:**
- **Primary Rule**: Every new function MUST be integrated natively into the main console/screen of the app by default.
- **Execution Flow**: Implement the logic as a CLI-friendly Python script (or PowerShell command) that can be triggered through `commands_config.json` using `__INTERNAL__` (or standard commands), parsing standard arguments and printing output to `stdout` so the main terminal captures it.
- **Exception**: Do NOT create standalone pop-up windows (`CTkToplevel`) or separate GUI screens for new tools UNLESS it is absolutely necessary (e.g., highly complex data entry, tabular viewers, or specialized dashboards) or explicitly suggested and approved as a more viable option. Even then, prefer using the main app's input fields defined in `commands_config.json`.
