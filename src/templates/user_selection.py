import tkinter as tk
from tkinter import ttk
from src.data.database import get_all_users
def user_selection_view():
    root = tk.Tk()
    root.title("User Selection")
    root.geometry("300x200")

    label = ttk.Label(root, text="Select a user:")
    label.pack()

    user = ttk.Combobox(root)
    user['values'] = ('Alice', 'Bob', 'Charlie')
    user.pack()

    button = ttk.Button(root, text="OK", command=root.quit)
    button.pack()

    root.mainloop()
    return user.get()