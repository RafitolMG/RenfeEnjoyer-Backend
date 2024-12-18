import sqlite3
from src.templates import modals

def create_database():
    try:
        conn = sqlite3.connect('renfe_enjoyer_database.db')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (id INTEGER PRIMARY KEY, 
                     username TEXT NOT NULL, 
                     password TEXT NOT NULL,
                     email TEXT NOT NULL CHECK (email LIKE '%@%.%'), 
                     abono TEXT NOT NULL)''')

        conn.commit()
        conn.close()

        modals.show_success('Database created successfully')

    except Exception as e:
        modals.show_error(str(e))

def add_user(username, password, email, abono):
    try:
        conn = sqlite3.connect('renfe_enjoyer_database.db')
        c = conn.cursor()
        c.execute("INSERT INTO users (username, password, email, abono) VALUES (?, ?, ?, ?)", (username, password, email, abono))
        conn.commit()
        conn.close()

        modals.show_success('User added successfully')

    except Exception as e:
        show_error(str(e))

def edit_user(username, password, email, abono):
    try:
        conn = sqlite3.connect('renfe_enjoyer_database.db')
        c = conn.cursor()
        c.execute("UPDATE users SET username=?, password=?, email=?, abono=? WHERE username=?", (username, password, email, abono, username))
        conn.commit()
        conn.close()

        modals.show_success('User edited successfully')

    except Exception as e:
        modals.show_error(str(e))

def delete_user(username):
    try:
        conn = sqlite3.connect('renfe_enjoyer_database.db')
        c = conn.cursor()
        c.execute("DELETE FROM users WHERE username=?", (username,))
        conn.commit()
        conn.close()

        modals.show_success('User deleted successfully')

    except Exception as e:
        modals.show_error(str(e))