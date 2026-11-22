import atexit
import os
import json
import hashlib


class TaskMemory:
    def __init__(self, task_name, task_context, batch_size=50):
        """
        task_name: Nombre de la tarea (ej. 'temp_cleaner')
        task_context: Un string único del contexto (ej. rutas de origen, comandos, etc.)
        batch_size: Cantidad de ítems antes de volcar el JSON a disco.
        """
        context_hash = hashlib.md5(task_context.encode("utf-8")).hexdigest()
        self.task_id = f"{task_name}_{context_hash}"
        self.batch_size = max(1, int(batch_size))
        self._dirty_count = 0

        appdata = os.environ.get("APPDATA", "")
        self.memory_dir = os.path.join(appdata, "cmd_gui_advance", "memory")
        os.makedirs(self.memory_dir, exist_ok=True)

        self.memory_file = os.path.join(self.memory_dir, f"{self.task_id}.json")
        self.state = {"processed_items": [], "status": "pending"}
        self._processed_set = set()
        self.load()
        atexit.register(self.flush)

    def load(self):
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    self.state = loaded
            except Exception:
                pass
        items = self.state.get("processed_items", [])
        self._processed_set = set(items) if isinstance(items, list) else set()

    def save(self):
        try:
            self.state["processed_items"] = list(self._processed_set)
            with open(self.memory_file, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2, ensure_ascii=False)
            self._dirty_count = 0
        except Exception:
            pass

    def flush(self):
        if self._dirty_count > 0:
            self.save()

    def mark_processed(self, item_id):
        if item_id not in self._processed_set:
            self._processed_set.add(item_id)
            self._dirty_count += 1
            if self._dirty_count >= self.batch_size:
                self.save()

    def is_processed(self, item_id):
        return item_id in self._processed_set

    def get_processed_count(self):
        return len(self._processed_set)

    def clear(self):
        self._dirty_count = 0
        self._processed_set.clear()
        self.state = {"processed_items": [], "status": "pending"}
        if os.path.exists(self.memory_file):
            try:
                os.remove(self.memory_file)
            except Exception:
                pass

    @staticmethod
    def check_pause_signal():
        """Verifica si la GUI ha enviado una señal de pausa."""
        appdata = os.environ.get("APPDATA", "")
        flag_file = os.path.join(appdata, "cmd_gui_advance", "pause.flag")
        return os.path.exists(flag_file)
