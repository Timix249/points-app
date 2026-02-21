import os
import psycopg2
from flask import Flask, request, redirect, session
import random
import string

app = Flask(__name__)
app.secret_key = "secret_key_123"

DATABASE_URL = os.environ.get("DATABASE_URL")

def get_connection():
    return psycopg2.connect(DATABASE_URL, sslmode="require")


# ---------- CREATE TABLES ----------
def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS cards (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        number TEXT UNIQUE NOT NULL,
        points INTEGER DEFAULT 0
    );
    """)

    # створюємо адміна якщо нема
    cur.execute("SELECT * FROM users WHERE username=%s;", ("admin",))
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO users (username, password) VALUES (%s, %s);",
            ("admin", "admin123")
        )

    conn.commit()
    cur.close()
    conn.close()


# 🔥 ВАЖЛИВО — викликаємо одразу
init_db()


# ---------- LOGIN ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form["username"]
        p = request.form["password"]

        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM users WHERE username=%s AND password=%s;",
            (u, p)
        )
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user:
            session["user"] = u
            return redirect("/admin")

    return """
    <h2>Login</h2>
    <form method="post">
    Username:<br>
    <input name="username"><br><br>
    Password:<br>
    <input type="password" name="password"><br><br>
    <button type="submit">Login</button>
    </form>
    """


# ---------- ADMIN ----------
@app.route("/admin")
def admin():
    if "user" not in session:
        return redirect("/login")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT name, number, points FROM cards ORDER BY id DESC;")
    cards = cur.fetchall()
    cur.close()
    conn.close()

    html = """
    <h1>Admin</h1>
    <a href="/logout">Logout</a><br><br>
    <h3>Add card</h3>
    <form method="post" action="/add">
    Name:<br>
    <input name="name" required><br><br>
    <button type="submit">Add</button>
    </form>
    <h3>Cards</h3>
    <table border="1">
    <tr><th>Name</th><th>Number</th><th>Points</th><th>Action</th></tr>
    """

    for name, number, points in cards:
        html += f"""
        <tr>
        <td>{name}</td>
        <td>{number}</td>
        <td>{points}</td>
        <td>
        <a href="/plus/{number}">+1</a>
        <a href="/delete/{number}">Delete</a>
        </td>
        </tr>
        """

    html += "</table>"
    return html


# ---------- ADD CARD ----------
@app.route("/add", methods=["POST"])
def add():
    if "user" not in session:
        return redirect("/login")

    name = request.form["name"]
    number = ''.join(random.choices(string.digits, k=8))

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO cards (name, number) VALUES (%s, %s);",
        (name, number)
    )
    conn.commit()
    cur.close()
    conn.close()

    return redirect("/admin")


# ---------- ADD POINT ----------
@app.route("/plus/<number>")
def plus(number):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE cards SET points = points + 1 WHERE number=%s;",
        (number,)
    )
    conn.commit()
    cur.close()
    conn.close()

    return redirect("/admin")


# ---------- DELETE ----------
@app.route("/delete/<number>")
def delete(number):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM cards WHERE number=%s;",
        (number,)
    )
    conn.commit()
    cur.close()
    conn.close()

    return redirect("/admin")


# ---------- LOGOUT ----------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


if __name__ == "__main__":
    app.run()