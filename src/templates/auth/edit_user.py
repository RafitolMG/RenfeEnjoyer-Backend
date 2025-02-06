import tkinter as tk
from tkinter import ttk

from src.core import get_resource_path
from src.data.database import edit_user

def registro():
    v= tk.Toplevel()
    v.title("Registro de datos")
    v.geometry("600x400")
    v.wm_iconbitmap(get_resource_path('assets/u327as.ico'))
    user_label = ttk.Label(v, text="Usuario:")
    user_label.pack()
    user_entry = ttk.Entry(v)
    user_entry.pack()

    mail_label = ttk.Label(v, text="Correo:")
    mail_label.pack()
    mail_entry = ttk.Entry(v)
    mail_entry.pack()

    ctr_label = ttk.Label(v, text="Contraseña:")
    ctr_label.pack()
    ctr_entry = ttk.Entry(v)
    ctr_entry.pack()

    abono_label = ttk.Label(v, text="Abono:")
    abono_label.pack()
    abono_entry = ttk.Entry(v)
    abono_entry.pack()

    submit_button = ttk.Button(v, text="Guardar", command=lambda: edit_user(str(user_entry.get()), str(mail_entry.get()), str(ctr_entry.get()), str(abono_entry.get())))
    submit_button.pack()
    v.mainloop()
