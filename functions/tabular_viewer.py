import customtkinter as ctk
from tkinter import ttk
import csv
import io

class TabularViewerApp(ctk.CTkToplevel):
    def __init__(self, master, title, csv_data):
        super().__init__(master)
        self.title(f"Vista Tabular - {title}")
        self.geometry("900x600")
        
        # Center Window
        self.update_idletasks()
        x = int(master.winfo_x() + (master.winfo_width() / 2) - (900 / 2))
        y = int(master.winfo_y() + (master.winfo_height() / 2) - (600 / 2))
        self.geometry(f"+{x}+{y}")
        
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # Parse CSV
        f = io.StringIO(csv_data)
        reader = csv.reader(f)
        try:
            self.headers = next(reader)
            self.data = list(reader)
        except StopIteration:
            self.headers = ["Error"]
            self.data = [["No se pudo procesar la salida como tabla."]]
            
        # Configure Treeview Style
        style = ttk.Style(self)
        style.theme_use("default")
        style.configure("Treeview", background="#2b2b2b", foreground="white", fieldbackground="#2b2b2b", borderwidth=0)
        style.configure("Treeview.Heading", background="#1f1f1f", foreground="white", relief="flat")
        style.map("Treeview", background=[("selected", "#1f6aa5")])
        
        # Frame for Treeview and Scrollbars
        frame = ctk.CTkFrame(self)
        frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        
        # Treeview
        self.tree = ttk.Treeview(frame, columns=self.headers, show="headings", selectmode="browse")
        
        # Scrollbars
        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        
        # Insert Data
        for col in self.headers:
            self.tree.heading(col, text=col, command=lambda c=col: self.sort_column(c, False))
            self.tree.column(col, width=150, anchor="w")
            
        for row in self.data:
            self.tree.insert("", "end", values=row)
            
    def sort_column(self, col, reverse):
        l = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]
        try:
            l.sort(key=lambda t: float(t[0]), reverse=reverse)
        except ValueError:
            l.sort(reverse=reverse)
            
        for index, (val, k) in enumerate(l):
            self.tree.move(k, "", index)
            
        self.tree.heading(col, command=lambda: self.sort_column(col, not reverse))

def show_tabular_data(master, title, csv_data):
    app = TabularViewerApp(master, title, csv_data)
    app.grab_set()
