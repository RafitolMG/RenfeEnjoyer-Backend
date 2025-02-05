import tkinter as tk
from tkinter import ttk

from sympy.physics.units import current

from src.core import renfe_enjoyer
from src.data.database import create_database, get_user
from src.templates.auth.register_user import registro
from src.templates.views.user_selection import user_selection_view

def main():
    # Ventana principal
    root = tk.Tk()
    root.title("Renfe Enjoyer")
    root.geometry("600x400")
    root.wm_iconbitmap('./assets/u327as.ico')
    # Menu principal
    menu=tk.Menu(root)

    # Sub menu de datos
    data_menu = tk.Menu(menu, tearoff=0)
    menu.add_cascade(label="Datos", menu=data_menu)

    # Opciones del sub menu de datos
    data_menu.add_command(label="Create Database", command=lambda: create_database())
    data_menu.add_command(label="Add User", command=lambda: registro() )

    current_user = tk.StringVar()

    def current_user_data():
        return get_user(current_user.get())

    data_menu.add_command(label="Select User", command=lambda: user_selection_view(current_user))

    # Configura el menu principal
    root.config(menu=menu)

    # user_label = ttk.Label(root, text="Usuario:")
    # user_label.pack()
    # user_spinbox = ttk.Spinbox(root, values=("Dani"))
    # user_spinbox.pack()

    # hora de salida del tren ui
    hora_label = ttk.Label(root, text="Hora de salida:")
    hora_label.pack()
    hora_entry = ttk.Entry(root)
    hora_entry.pack()

    # seleccion ida y vuelta ui
    ida_vuelta_label = ttk.Label(root, text="Tipo de billete:")
    ida_vuelta_label.pack()
    ida_vuelta_entry = ttk.Combobox(root, values=("ida", "vuelta"))
    ida_vuelta_entry.pack()

    # seleccio de fecha ui
    fecha_label = ttk.Label(root, text="Fecha:")
    fecha_label.pack()
    fecha_entry = ttk.Entry(root, text="dd/mm/yyyy")
    fecha_entry.pack()

    # boton de busqueda de billetes
    submit_button = ttk.Button(root, text="Buscar billetes", command=lambda: renfe_enjoyer(str(hora_entry.get()), str(ida_vuelta_entry.get()), str(fecha_entry.get()), current_user_data()[2], current_user_data()[3], current_user_data()[4]))
    submit_button.pack()
    test_but = ttk.Button(root, text="test", command=lambda: current_user_data())
    test_but.pack()
    root.mainloop()