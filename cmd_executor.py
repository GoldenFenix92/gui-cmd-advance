import subprocess
import threading

def execute_command_async(command_list, output_callback, finished_callback):
    """
    Ejecuta un comando de forma asíncrona y envía la salida a un callback.
    :param command_list: Lista con el comando y sus argumentos.
    :param output_callback: Función que recibe cada línea de salida.
    :param finished_callback: Función que se llama cuando el comando termina.
    """
    def run_process():
        try:
            # shell=True permite usar comandos internos de cmd (como dir, echo)
            process = subprocess.Popen(
                command_list,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                shell=True,
                bufsize=1
            )
            
            for line in process.stdout:
                if line:
                    output_callback(line)
                    
            process.wait()
            output_callback(f"\n--- Comando finalizado con código {process.returncode} ---")
            
        except Exception as e:
            output_callback(f"\nError al ejecutar el comando: {str(e)}")
            
        finally:
            if finished_callback:
                finished_callback()
                
    # Ejecutar en un hilo separado para no bloquear la GUI
    thread = threading.Thread(target=run_process)
    thread.daemon = True
    thread.start()
