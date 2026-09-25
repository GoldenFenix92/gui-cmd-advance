import subprocess
import threading
import os

class CommandRunner:
    def __init__(self):
        self.process = None

    def execute_command_async(self, command_string, output_callback, finished_callback):
        def run_process():
            try:
                self.process = subprocess.Popen(
                    command_string,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    shell=True,
                    bufsize=0
                )
                
                buffer = bytearray()
                while True:
                    b = self.process.stdout.read(1)
                    if not b:
                        if buffer:
                            try:
                                decoded = buffer.decode('utf-8')
                            except UnicodeDecodeError:
                                decoded = buffer.decode('mbcs', 'ignore')
                            output_callback(decoded)
                        break
                    
                    if b == b'\x00':
                        continue
                        
                    buffer.extend(b)
                    if b in [b'\n', b'\r']:
                        try:
                            decoded = buffer.decode('utf-8')
                        except UnicodeDecodeError:
                            decoded = buffer.decode('mbcs', 'ignore')
                        output_callback(decoded)
                        buffer.clear()
                        
                self.process.wait()
                if self.process.returncode != 0 and self.process.returncode is not None:
                    output_callback(f"\n--- Comando finalizado o detenido (código {self.process.returncode}) ---")
                else:
                    output_callback(f"\n--- Comando finalizado con éxito ---")
                
            except Exception as e:
                output_callback(f"\nError al ejecutar el comando: {str(e)}")
                
            finally:
                self.process = None
                if finished_callback:
                    finished_callback()
                    
        thread = threading.Thread(target=run_process)
        thread.daemon = True
        thread.start()

    def stop_command(self):
        if self.process:
            try:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(self.process.pid)], capture_output=True)
            except Exception as e:
                pass

_runner = CommandRunner()

def execute_command_async(command_string, output_callback, finished_callback):
    _runner.execute_command_async(command_string, output_callback, finished_callback)

def stop_command():
    _runner.stop_command()
