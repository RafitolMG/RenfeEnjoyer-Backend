import tkinter as tk
from tkinter import ttk

from src.core import get_resource_path
from src.data.database import get_all_users, get_user, edit_user, delete_user


def user_selection_view(set_current_user):
    def on_select():
        set_current_user.set(user.get())
        root.destroy()

    def on_edit():
        curr_user= user.get()
        curr_user= get_user(curr_user)
        v= tk.Toplevel()
        v.title("Editar datos")
        v.geometry("600x400")
        v.wm_iconbitmap(get_resource_path('assets/u327as.ico'))
        user_label = ttk.Label(v, text="Usuario:")
        user_label.pack()
        user_entry = ttk.Entry(v)
        user_entry.insert(-1, curr_user[1])
        user_entry.pack()

        mail_label = ttk.Label(v, text="Correo:")
        mail_label.pack()
        mail_entry = ttk.Entry(v)
        mail_entry.insert(-1, curr_user[2])
        mail_entry.pack()

        ctr_label = ttk.Label(v, text="Contraseña:")
        ctr_label.pack()
        ctr_entry = ttk.Entry(v)
        ctr_entry.insert(-1, curr_user[3])
        ctr_entry.pack()

        abono_label = ttk.Label(v, text="Abono:")
        abono_label.pack()
        abono_entry = ttk.Entry(v)
        abono_entry.insert(-1, curr_user[4])
        abono_entry.pack()
        def edit_on():
            edit_user(str(user_entry.get()), str(mail_entry.get()), str(ctr_entry.get()), str(abono_entry.get()))
            v.destroy()
        submit_button = ttk.Button(v, text="Guardar",
                                   command=lambda: edit_on())
        submit_button.pack()

    def on_delete():
        curr_user= user.get()
        delete_user(curr_user)
        users_data= get_all_users()
        root.destroy()
        user_selection_view(set_current_user)

    root = tk.Toplevel()
    root.title("User Selection")
    root.geometry("300x200")
    root.wm_iconbitmap(get_resource_path('assets/u327as.ico'))
    users_data = get_all_users()
    label = ttk.Label(root, text="Select a user:")
    label.pack()

    user = ttk.Combobox(root)
    user['values'] = users_data
    user.pack()
    edit_button = ttk.Button(root, text="Edit", command=on_edit)
    edit_button.pack()

    delete_button = ttk.Button(root, text="Delete", command=on_delete)
    delete_button.pack()

    button = ttk.Button(root, text="Select", command=on_select)
    button.pack()
