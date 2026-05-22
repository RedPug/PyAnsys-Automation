import tkinter as tk
import numpy as np
from tkinter import filedialog, ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
from scipy.interpolate import PchipInterpolator
from src.generator import generate_smooth_noise

# --- main window ---
root = tk.Tk()
root.title("Ansys Generator")
root.geometry("1100x750")
root.minsize(960, 640)


def close_app():
    root.quit()
    root.destroy()
    raise SystemExit


root.protocol("WM_DELETE_WINDOW", close_app)

root.grid_rowconfigure(0, weight=1)
root.grid_rowconfigure(1, weight=0)
root.grid_columnconfigure(0, weight=1)

style = ttk.Style(root)
style.theme_use("clam")
style.configure("TFrame", background="#f4f6f8")
style.configure("TLabel", background="#f4f6f8", font=("Segoe UI", 10))
style.configure("TButton", font=("Segoe UI", 10), padding=(10, 6))
style.configure("RowDelete.TButton", font=("Segoe UI", 8), padding=(1, 0))
style.configure("RowAdd.TButton", font=("Segoe UI", 10), padding=(10, 0))
root.configure(background="#f4f6f8")

# --- store selected file path ---
selected_file = tk.StringVar()
entry_value_one = tk.StringVar()
entry_value_two = tk.StringVar()
entry_value_three = tk.StringVar()
noise_seed_value = tk.StringVar(value="0")
selected_table_name = tk.StringVar(value="Temperature")
noise_matrices = {
    "Temperature": np.empty((0, 0)),
    "Convection": np.empty((0, 0)),
}

class EditableTable:
    def __init__(self, parent, title, columns, initial_rows=None, on_change=None):
        self.columns = columns
        self.rows = []
        self.on_change = on_change
        self._suspend_notify = True

        self.frame = ttk.Frame(parent, padding=10)
        self.frame.grid_rowconfigure(1, weight=1)
        self.frame.grid_columnconfigure(0, weight=1)

        title_label = ttk.Label(self.frame, text=title)
        title_label.grid(row=0, column=0, sticky="w")

        table_frame = ttk.Frame(self.frame)
        table_frame.grid(row=1, column=0, sticky="nsew", pady=(8, 8))
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(table_frame, highlightthickness=0, background="#f4f6f8")
        self.canvas.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.inner_frame = ttk.Frame(self.canvas)
        self.inner_frame.bind(
            "<Configure>",
            lambda event: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas_window = self.canvas.create_window((0, 0), window=self.inner_frame, anchor="nw")
        self.canvas.bind(
            "<Configure>",
            lambda event: self.canvas.itemconfigure(self.canvas_window, width=event.width),
        )

        self.canvas.bind("<MouseWheel>", self.handle_mousewheel)
        self.inner_frame.bind("<MouseWheel>", self.handle_mousewheel)

        for row in initial_rows or []:
            self.add_row(row)
        if not self.rows:
            self.add_row()
        self.render_rows()
        self._suspend_notify = False

    def handle_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        return "break"

    def add_row(self, values=None):
        row_values = list(values) if values is not None else [""] * len(self.columns)
        if len(row_values) < len(self.columns):
            row_values.extend([""] * (len(self.columns) - len(row_values)))
        self.rows.append({"values": row_values[: len(self.columns)]})
        self.render_rows()
        self._notify_change()

    def remove_row(self, index):
        if 0 <= index < len(self.rows):
            del self.rows[index]
            if not self.rows:
                self.add_row()
            else:
                self.render_rows()
            self._notify_change()

    def _notify_change(self):
        if not self._suspend_notify and self.on_change is not None:
            self.on_change()

    def get_data(self):
        parsed_rows = []
        for row in self.rows:
            raw_values = row["values"]
            if len(raw_values) < 2:
                continue
            try:
                time_value = float(raw_values[0])
                data_value = float(raw_values[1])
            except (TypeError, ValueError):
                continue
            parsed_rows.append((time_value, data_value))
        parsed_rows.sort(key=lambda item: item[0])
        return parsed_rows

    def render_rows(self):
        for widget in self.inner_frame.winfo_children():
            widget.destroy()

        header_frame = ttk.Frame(self.inner_frame)
        header_frame.grid(row=0, column=0, sticky="ew")
        header_frame.grid_columnconfigure(0, weight=0)
        for column_index, column_name in enumerate(self.columns):
            header_frame.grid_columnconfigure(column_index + 1, weight=1)
            header = ttk.Label(header_frame, text=column_name.title(), anchor="center")
            header.grid(row=0, column=column_index + 1, sticky="ew", padx=4, pady=(0, 6))

        for row_index, row in enumerate(self.rows, start=1):
            row_frame = ttk.Frame(self.inner_frame)
            row_frame.grid(row=row_index * 2 - 1, column=0, sticky="ew", pady=(0, 0))
            row_frame.grid_columnconfigure(0, weight=0)
            for column_index in range(len(self.columns)):
                row_frame.grid_columnconfigure(column_index + 1, weight=1)

            row_frame.configure(style="TFrame")

            if len(row["values"]) < len(self.columns):
                row["values"].extend([""] * (len(self.columns) - len(row["values"])))

            remove_button = ttk.Button(
                row_frame,
                text="x",
                width=1,
                style="RowDelete.TButton",
                command=lambda index=row_index - 1: self.remove_row(index),
            )
            remove_button.grid(row=0, column=0, sticky="w", padx=(0, 3), pady=3)

            for column_index, value in enumerate(row["values"][: len(self.columns)]):
                cell_var = tk.StringVar(value=value)

                def update_value(*args, row_ref=row, index_ref=column_index, variable=cell_var):
                    row_ref["values"][index_ref] = variable.get()
                    self._notify_change()

                cell_var.trace_add("write", update_value)
                entry = ttk.Entry(row_frame, textvariable=cell_var, justify="center")
                entry.grid(row=0, column=column_index + 1, sticky="ew", padx=4, pady=4)

            separator = ttk.Separator(self.inner_frame, orient="horizontal")
            separator.grid(row=row_index * 2, column=0, sticky="ew", pady=(0, 2))

        add_button = ttk.Button(self.inner_frame, text="+", width=8, style="RowAdd.TButton", command=self.add_row)
        add_button.grid(row=len(self.rows) * 2 + 1, column=0, pady=(4, 0))

        self.inner_frame.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

# --- function: open file dialog ---
def import_file():
    file_path = filedialog.askopenfilename()
    if file_path:
        selected_file.set(file_path)
        print("Selected file:", file_path)


def build_curve_and_noise_matrix(base_table, noise_table):
    base_data = base_table.get_data()
    if len(base_data) < 2:
        return None, None, np.empty((0, 0))

    times = np.array([row[0] for row in base_data], dtype=float)
    values = np.array([row[1] for row in base_data], dtype=float)

    order = np.argsort(times)
    times = times[order]
    values = values[order]

    # PCHIP requires strictly increasing x values.
    unique_times, unique_indices = np.unique(times, return_index=True)
    times = unique_times
    values = values[unique_indices]

    if times.size < 2:
        return None, None, np.empty((0, 0))

    # Add one midpoint per segment so PCHIP tracks the original line pieces more closely.
    midpoint_times = 0.5 * (times[:-1] + times[1:])
    midpoint_values = 0.5 * (values[:-1] + values[1:])
    augmented_times = np.concatenate([times, midpoint_times])
    augmented_values = np.concatenate([values, midpoint_values])
    augmented_order = np.argsort(augmented_times)
    times = augmented_times[augmented_order]
    values = augmented_values[augmented_order]

    start_time = float(np.min(times))
    end_time = float(np.max(times))
    if end_time <= start_time:
        return None, None, np.empty((0, 0))

    sampled_times = np.arange(start_time, end_time + 10, 10)
    pchip = PchipInterpolator(times, values)
    base_sampled = pchip(sampled_times)

    seed_text = noise_seed_value.get().strip()
    seed_value = None
    if seed_text:
        try:
            seed_value = int(seed_text)
        except ValueError:
            seed_value = None

    noise_layers = noise_table.get_data()
    layer_signals = []
    for i, (period, std) in enumerate(noise_layers):
        layer_seed = None if seed_value is None else seed_value + i
        layer_signals.append(generate_smooth_noise(sampled_times, period=period, std=std, seed=layer_seed))

    if layer_signals:
        noise_matrix = np.column_stack(layer_signals)
    else:
        noise_matrix = np.empty((sampled_times.size, 0))

    return sampled_times, base_sampled, noise_matrix

# --- function: update graph ---
def plot_graph():
    ax.clear()
    if selected_table_name.get() == "Temperature":
        base_table = temperature_table
        noise_table = temperature_noise_table
        label = "Temperature"
        color = "tab:red"
    else:
        base_table = convection_table
        noise_table = convection_noise_table
        label = "Convection"
        color = "tab:blue"

    sampled_times, base_curve, noise_matrix = build_curve_and_noise_matrix(base_table, noise_table)
    noise_matrices[selected_table_name.get()] = noise_matrix
    table_data = base_table.get_data()

    if sampled_times is not None and base_curve is not None:
        if table_data:
            table_times = [row[0] for row in table_data]
            table_values = [row[1] for row in table_data]
            ax.plot(
                table_times,
                table_values,
                color="green",
                linewidth=1.8,
                label=f"{label} Table",
            )

        for layer_index in range(noise_matrix.shape[1]):
            noisy_layer_curve = base_curve + noise_matrix[:, layer_index]
            ax.plot(
                sampled_times,
                noisy_layer_curve,
                color=color,
                alpha=0.22,
                linewidth=1.2,
            )

        ax.plot(
            sampled_times,
            base_curve,
            color="black",
            linestyle=":",
            linewidth=2.0,
            label=f"{label} PCHIP",
        )

        total_noise = noise_matrix.sum(axis=1) if noise_matrix.size else np.zeros_like(base_curve)
        summed_curve = base_curve + total_noise
        ax.plot(
            sampled_times,
            summed_curve,
            color=color,
            linestyle="--",
            linewidth=2.2,
            alpha=1.0,
            label=f"{label} + Sum Noise",
        )

    ax.set_xlabel("Time")
    ax.set_ylabel("Value")
    ax.set_title(f"{selected_table_name.get()} Table Data")
    ax.grid(True, alpha=0.25)
    if sampled_times is not None and base_curve is not None:
        ax.legend()
    canvas.draw()

# --- function: clear graph ---
def clear_graph():
    ax.clear()
    ax.set_xlabel("Time")
    ax.set_ylabel("Value")
    canvas.draw()

# --- create matplotlib figure ---
fig, ax = plt.subplots(figsize=(6.5, 4.5))
# ax.set_title(selected_case.get())
ax.set_xlabel("X")
ax.set_ylabel("Y")

top_frame = ttk.Frame(root, padding=16)
top_frame.grid(row=0, column=0, sticky="nsew")
top_frame.grid_columnconfigure(0, weight=1)
top_frame.grid_columnconfigure(1, weight=3)
top_frame.grid_columnconfigure(2, weight=2)
top_frame.grid_rowconfigure(0, weight=1)

graph_frame = ttk.Frame(top_frame, padding=8)
graph_frame.grid(row=0, column=1, sticky="nsew")
graph_frame.grid_rowconfigure(0, weight=1)
graph_frame.grid_columnconfigure(0, weight=1)

canvas = FigureCanvasTkAgg(fig, master=graph_frame)
canvas_widget = canvas.get_tk_widget()
canvas_widget.grid(row=0, column=0, sticky="nsew")

bottom_frame = ttk.Frame(root, padding=(16, 0, 16, 16))
bottom_frame.grid(row=1, column=0, sticky="ew")
bottom_frame.grid_columnconfigure(0, weight=1)

tables_frame = ttk.Frame(top_frame, padding=8)
tables_frame.grid(row=0, column=2, sticky="nsew")
tables_frame.grid_columnconfigure(0, weight=1)
tables_frame.grid_rowconfigure(1, weight=1)
tables_frame.grid_rowconfigure(2, weight=1)

table_selector_frame = ttk.Frame(tables_frame)
table_selector_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
table_selector_frame.grid_columnconfigure(1, weight=1)

ttk.Label(table_selector_frame, text="Table View").grid(row=0, column=0, sticky="w", padx=(0, 8))
table_selector = ttk.Combobox(
    table_selector_frame,
    textvariable=selected_table_name,
    values=("Temperature", "Convection"),
    state="readonly",
    width=18,
)
table_selector.grid(row=0, column=1, sticky="e")

table_stack = ttk.Frame(tables_frame)
table_stack.grid(row=1, column=0, sticky="nsew")
table_stack.grid_columnconfigure(0, weight=1)
table_stack.grid_rowconfigure(0, weight=1)

noise_stack = ttk.Frame(tables_frame)
noise_stack.grid(row=2, column=0, sticky="nsew", pady=(8, 0))
noise_stack.grid_columnconfigure(0, weight=1)
noise_stack.grid_rowconfigure(0, weight=1)

temperature_table = EditableTable(
    table_stack,
    "Temperature Table",
    ("time", "temperature"),
    initial_rows=[
        ("0", "100"),
        ("7200", "300"),
        ("14400", "200"),
    ],
    on_change=lambda: plot_graph(),
)
temperature_table.frame.grid(row=0, column=0, sticky="nsew")

convection_table = EditableTable(
    table_stack,
    "Convection Table",
    ("time", "convection"),
    initial_rows=[
        ("0", "20"),
        ("7200", "20"),
        ("14400", "20"),
    ],
    on_change=lambda: plot_graph(),
)
convection_table.frame.grid(row=0, column=0, sticky="nsew")

temperature_noise_table = EditableTable(
    noise_stack,
    "Temperature Noise Layers",
    ("period", "std"),
    initial_rows=[
        ("10000", "30"),
        ("4000", "15"),
        ("1000", "8"),
        ("400", "2"),
    ],
)
temperature_noise_table.frame.grid(row=0, column=0, sticky="nsew")

convection_noise_table = EditableTable(
    noise_stack,
    "Convection Noise Layers",
    ("period", "std"),
    initial_rows=[
        ("10000", "2"),
        ("4000", "1"),
        ("1000", "0.5"),
    ],
)
convection_noise_table.frame.grid(row=0, column=0, sticky="nsew")


def update_table_visibility(event=None):
    if selected_table_name.get() == "Temperature":
        convection_table.frame.grid_remove()
        temperature_table.frame.grid()
        convection_noise_table.frame.grid_remove()
        temperature_noise_table.frame.grid()
    else:
        temperature_table.frame.grid_remove()
        convection_table.frame.grid()
        temperature_noise_table.frame.grid_remove()
        convection_noise_table.frame.grid()
    plot_graph()


table_selector.bind("<<ComboboxSelected>>", update_table_visibility)
update_table_visibility()

buttons_frame = ttk.Frame(bottom_frame)
buttons_frame.grid(row=0, column=0, sticky="ew", pady=(0, 12))

# --- buttons ---
btn_plot = ttk.Button(buttons_frame, text="Plot Graph", command=plot_graph)
btn_plot.grid(row=0, column=0, padx=(0, 10))

btn_clear = ttk.Button(buttons_frame, text="Clear Graph", command=clear_graph)
btn_clear.grid(row=0, column=1, padx=(0, 10))

btn_import = ttk.Button(buttons_frame, text="Import File", command=import_file)
btn_import.grid(row=0, column=2)

inputs_frame = ttk.Frame(bottom_frame)
inputs_frame.grid(row=1, column=0, sticky="ew")
inputs_frame.grid_columnconfigure(1, weight=1)
inputs_frame.grid_columnconfigure(3, weight=1)
inputs_frame.grid_columnconfigure(5, weight=1)
inputs_frame.grid_columnconfigure(7, weight=1)

ttk.Label(inputs_frame, text="Value 1").grid(row=0, column=0, sticky="w", padx=(0, 8))
entry_one = ttk.Entry(inputs_frame, textvariable=entry_value_one)
entry_one.grid(row=0, column=1, sticky="ew", padx=(0, 16))

ttk.Label(inputs_frame, text="Value 2").grid(row=0, column=2, sticky="w", padx=(0, 8))
entry_two = ttk.Entry(inputs_frame, textvariable=entry_value_two)
entry_two.grid(row=0, column=3, sticky="ew", padx=(0, 16))

ttk.Label(inputs_frame, text="Value 3").grid(row=0, column=4, sticky="w", padx=(0, 8))
entry_three = ttk.Entry(inputs_frame, textvariable=entry_value_three)
entry_three.grid(row=0, column=5, sticky="ew")

ttk.Label(inputs_frame, text="Noise Seed").grid(row=0, column=6, sticky="w", padx=(16, 8))
seed_entry = ttk.Entry(inputs_frame, textvariable=noise_seed_value)
seed_entry.grid(row=0, column=7, sticky="ew")
noise_seed_value.trace_add("write", lambda *_: plot_graph())

status_label = ttk.Label(bottom_frame, textvariable=selected_file)
status_label.grid(row=2, column=0, sticky="w", pady=(12, 0))

# --- run app ---
root.mainloop()