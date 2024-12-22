import tkinter as tk
from tkinter import ttk

from src.core import renfe_enjoyer
from src.data.database import create_database, add_user, edit_user

def main():
    # Ventana principal
    root = tk.Tk()
    root.title("Renfe Enjoyer")
    root.geometry("600x400")
    root.wm_iconbitmap('.\\assets\\u327as.ico')

    # Menu principal
    menu=tk.Menu(root)

    # Sub menu de datos
    data_menu = tk.Menu(menu, tearoff=0)
    menu.add_cascade(label="Datos", menu=data_menu)

    # Opciones del sub menu de datos
    data_menu.add_command(label="Create Database", command=lambda: create_database())
    data_menu.add_command(label="Register User", command=lambda: add_user())
    data_menu.add_command(label="Edit User", command=lambda: edit_user())
    data_menu.add_command(label="Select user", command=lambda: delete_user())

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

    def get_credentials():
        user = 'Rafa'
        if user == "Rafa":
            pass

    # boton de busqueda de billetes
    submit_button = ttk.Button(root, text="Buscar billetes", command=lambda: renfe_enjoyer(str(hora_entry.get()), str(ida_vuelta_entry.get()), str(fecha_entry.get()), *get_credentials()))
    submit_button.pack()
    root.mainloop()