import os
import json
import hashlib

class TaskMemory:
    def __init__(self, task_name, task_context):
        """
        task_name: Nombre de la tarea (ej. 'temp_cleaner')
        task_context: Un string único del contexto (ej. rutas de origen, comandos, etc.)
        """
        # Create a unique ID based on context
        context_hash = hashlib.md5(task_context.encode('utf-8')).hexdigest()
        self.task_id = f"{task_name}_{context_hash}"
        
        # Define memory path
        appdata = os.environ.get('APPDATA', '')
        self.memory_dir = os.path.join(appdata, "cmd_gui_advance", "memory")
        os.makedirs(self.memory_dir, exist_ok=True)
        
        self.memory_file = os.path.join(self.memory_dir, f"{self.task_id}.json")
        self.state = {"processed_items": [], "status": "pending"}
        self.load()

    def load(self):
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, "r", encoding="utf-8") as f:
                    self.state = json.load(f)
            except:
                pass

    def save(self):
        try:
            with open(self.memory_file, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=4, ensure_ascii=False)
        except:
            pass

    def mark_processed(self, item_id):
        if item_id not in self.state["processed_items"]:
            self.state["processed_items"].append(item_id)
            self.save()

    def is_processed(self, item_id):
        return item_id in self.state["processed_items"]

    def get_processed_count(self):
        return len(self.state["processed_items"])

    def clear(self):
        if os.path.exists(self.memory_file):
            try:
                os.remove(self.memory_file)
            except:
                pass
        self.state = {"processed_items": [], "status": "pending"}

    @staticmethod
    def check_pause_signal():
        """
        Verifica si la GUI ha enviado una señal de pausa.
        """
        appdata = os.environ.get('APPDATA', '')
        flag_file = os.path.join(appdata, "cmd_gui_advance", "pause.flag")
        if os.path.exists(flag_file):
            return True
        return False
