import customtkinter as ctk
import subprocess
import os

from gui_app import center_window

class CredentialsVaultApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Bóveda de Credenciales de Windows")
        center_window(self, 800, 500)
        
        try:
            from gui_app import get_resource_path
            self.iconbitmap(get_resource_path("app_icon.ico"))
        except:
            pass

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Top Bar
        self.top_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.top_frame.grid(row=0, column=0, padx=20, pady=15, sticky="ew")
        
        self.lbl_title = ctk.CTkLabel(self.top_frame, text="🛡️ Gestor de Credenciales de Windows", font=("Arial", 18, "bold"))
        self.lbl_title.pack(side="left")

        self.btn_refresh = ctk.CTkButton(self.top_frame, text="🔄 Recargar", width=100, command=self.load_credentials)
        self.btn_refresh.pack(side="right", padx=(10, 0))

        self.btn_native = ctk.CTkButton(self.top_frame, text="🔐 Abrir Bóveda Nativa (Ver Claves)", width=200, fg_color="#F39C12", hover_color="#D68910", text_color="white", command=self.open_native_vault)
        self.btn_native.pack(side="right")

        # List Frame
        self.scroll_frame = ctk.CTkScrollableFrame(self)
        self.scroll_frame.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="nsew")

        self.load_credentials()

    def load_credentials(self):
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        try:
            output = subprocess.check_output("cmdkey /list", shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
            output_str = output.decode('mbcs', errors='ignore')
            lines = output_str.strip().split('\n')
            
            current_target = ""
            current_type = ""
            current_user = ""
            
            creds = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                # Soporte para español e inglés
                if "Destino:" in line or "Target:" in line:
                    current_target = line.split(":", 1)[1].strip()
                elif "Tipo:" in line or "Type:" in line:
                    current_type = line.split(":", 1)[1].strip()
                elif "Usuario:" in line or "User:" in line:
                    current_user = line.split(":", 1)[1].strip()
                    if current_target:
                        creds.append({
                            "target": current_target,
                            "type": current_type,
                            "user": current_user
                        })
                        current_target, current_type, current_user = "", "", ""

            if not creds:
                lbl_empty = ctk.CTkLabel(self.scroll_frame, text="No se encontraron credenciales guardadas.", font=("Arial", 14))
                lbl_empty.pack(pady=20)
            else:
                for cred in creds:
                    self.create_cred_row(cred)
                    
        except subprocess.CalledProcessError:
            lbl_err = ctk.CTkLabel(self.scroll_frame, text="Error al leer las credenciales. Usa la bóveda nativa.", font=("Arial", 14), text_color="red")
            lbl_err.pack(pady=20)

    def create_cred_row(self, cred):
        row = ctk.CTkFrame(self.scroll_frame)
        row.pack(fill="x", pady=5, padx=5)

        info_frame = ctk.CTkFrame(row, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True, padx=10, pady=5)

        lbl_target = ctk.CTkLabel(info_frame, text=f"🌐 Destino: {cred['target']}", font=("Arial", 13, "bold"), anchor="w", wraplength=550)
        lbl_target.pack(fill="x")
        
        lbl_user = ctk.CTkLabel(info_frame, text=f"👤 Usuario: {cred['user']}  |  🏷️ Tipo: {cred['type']}", font=("Arial", 12), text_color="gray", anchor="w", wraplength=550)
        lbl_user.pack(fill="x")

        delete_btn = ctk.CTkButton(row, text="🗑️ Eliminar", width=80, fg_color="#E74C3C", hover_color="#C0392B", 
                                   command=lambda t=cred['target']: self.delete_credential(t))
        delete_btn.pack(side="right", padx=10, pady=10)

    def delete_credential(self, target):
        try:
            cmd = f'cmdkey /delete:"{target}"'
            subprocess.check_call(cmd, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
            self.load_credentials()
        except subprocess.CalledProcessError:
            from tkinter import messagebox
            messagebox.showerror("Error", f"No se pudo eliminar la credencial: {target}")

    def open_native_vault(self):
        try:
            subprocess.Popen("control keymgr.dll", shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
        except:
            pass

if __name__ == "__main__":
    ctk.set_appearance_mode("Dark")
    app = CredentialsVaultApp()
    app.mainloop()
