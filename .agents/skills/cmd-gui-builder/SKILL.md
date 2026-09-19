---
name: cmd-gui-builder
description: >-
  Use this skill when the user asks to add a new command to the CMD GUI application, or to check the progress of the implemented commands.
  This skill provides the checklist of all planned commands and instructions on how to add them.
---

# CMD GUI Builder Skill

This skill tracks the progress of the CMD GUI project and provides instructions on how to add new commands.

## Progress Checklist (COMMANDS.md)

The list of all commands to be implemented and their status is maintained in:
[COMMANDS.md](./COMMANDS.md)

When a new command is completed, update `COMMANDS.md` by marking it with `[x]`.

## How to Add a New Command

1. **Update Configuration**: Open `commands_config.json` and add the new command under the appropriate category.
2. **Handle Special Logic (if needed)**: If the command requires special formatting or parsing, update `cmd_executor.py`.
3. **Update GUI (if needed)**: The GUI should ideally parse `commands_config.json` dynamically. If dynamic parsing is not enough, update `gui_app.py` to add specific UI elements.
4. **Mark as Done**: Check off the command in `COMMANDS.md`.
