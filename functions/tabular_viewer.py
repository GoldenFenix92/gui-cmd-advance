import csv
import io
import ttkbootstrap as tb
from functions import ui_theme


class TabularViewerApp(tb.Toplevel):
    def __init__(self, master, title, csv_data):
        super().__init__(master)
        self.title(f"Vista Tabular - {title}")
        self.geometry("920x620")
        ui_theme.apply_window_chrome(self)

        self.update_idletasks()
        x = int(master.winfo_x() + (master.winfo_width() / 2) - 460)
        y = int(master.winfo_y() + (master.winfo_height() / 2) - 310)
        self.geometry(f"+{x}+{y}")

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        f = io.StringIO(csv_data)
        reader = csv.reader(f)
        try:
            self.headers = next(reader)
            self.data = list(reader)
        except StopIteration:
            self.headers = ["Error"]
            self.data = [["No se pudo procesar la salida como tabla."]]

        frame = tb.Frame(self, padding=10)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        self.tree = tb.Treeview(frame, columns=self.headers, show="headings", selectmode="browse", bootstyle="info")

        vsb = tb.Scrollbar(frame, orient="vertical", command=self.tree.yview, bootstyle="round")
        hsb = tb.Scrollbar(frame, orient="horizontal", command=self.tree.xview, bootstyle="round")
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        for col in self.headers:
            self.tree.heading(col, text=col, command=lambda c=col: self.sort_column(c, False))
            self.tree.column(col, width=150, anchor="w")

        for row in self.data:
            self.tree.insert("", "end", values=row)

        ui_theme.bring_to_front(self)

    def sort_column(self, col, reverse):
        rows = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]
        try:
            rows.sort(key=lambda t: float(t[0]), reverse=reverse)
        except ValueError:
            rows.sort(reverse=reverse)

        for index, (_val, k) in enumerate(rows):
            self.tree.move(k, "", index)

        self.tree.heading(col, command=lambda: self.sort_column(col, not reverse))


def show_tabular_data(master, title, csv_data):
    app = TabularViewerApp(master, title, csv_data)
    app.grab_set()
