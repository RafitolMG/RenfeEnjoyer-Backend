import tkinter as tk
from tkinter import messagebox, ttk

def show_success(success_message):
    root = tk.Toplevel()
    root.withdraw()
    messagebox.showinfo("Success", success_message)
    root.destroy()

def show_error(error_message):
    root = tk.Toplevel()
    root.withdraw()
    messagebox.showerror("Error", error_message)
    root.destroy()