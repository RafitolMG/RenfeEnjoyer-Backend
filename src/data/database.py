import sqlite3
from src.templates.modals import modals


def create_database():
    global conn
    try:
        conn = sqlite3.connect('renfe_enjoyer_database.db')
        c = conn.cursor()
        c.execute('''DROP TABLE IF EXISTS users''')
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (id INTEGER PRIMARY KEY, 
                     username TEXT NOT NULL, 
                     password TEXT NOT NULL,
                     email TEXT NOT NULL, 
                     abono TEXT NOT NULL)''')

        conn.commit()
        conn.close()


        modals.show_success('Database created successfully')

    except Exception as e:
        conn.close()
        modals.show_error(str(e))


def add_user(username, password, email, abono):
    try:
        conn = sqlite3.connect('renfe_enjoyer_database.db')
        c = conn.cursor()
        c.execute("INSERT INTO users (username, password, email, abono) VALUES (?, ?, ?, ?)",
                  (username, password, email, abono))
        conn.commit()
        conn.close()

        modals.show_success('User added successfully')

    except Exception as e:
        conn.close()
        modals.show_error(str(e))


def edit_user(username, password, email, abono):
    try:
        conn = sqlite3.connect('renfe_enjoyer_database.db')
        c = conn.cursor()
        c.execute("UPDATE users SET username=?, password=?, email=?, abono=? WHERE username=?",
                  (username, password, email, abono, username))
        conn.commit()
        conn.close()

        modals.show_success('User edited successfully')

    except Exception as e:
        conn.close()
        modals.show_error(str(e))


def get_all_users():
    try:
        conn = sqlite3.connect('renfe_enjoyer_database.db')
        c = conn.cursor()
        c.execute("SELECT username FROM users")
        users = c.fetchall()
        conn.close()

        return users

    except Exception as e:
        conn.close()
        modals.show_error(str(e))

def get_user(username):
    try:
        conn = sqlite3.connect('renfe_enjoyer_database.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=?", (username,))
        user = c.fetchone()
        conn.close()

        return user

    except Exception as e:
        conn.close()
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
        conn.close()
        modals.show_error(str(e))
