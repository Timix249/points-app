import os
import psycopg2
from flask import Flask, request, redirect, session, url_for
import random
import string

app = Flask(__name__)
app.secret_key = "super_secret_key"

DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL not set!")

def get_connection():
    return psycopg2.connect(DATABASE_URL, sslmode='require')


# ---------- INIT DATABASE ----------
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
            card_number TEXT UNIQUE NOT NULL,
            points INTEGER DEFAULT 0
        );
    """)

    # створюємо адміна якщо нема
    cur.execute("SELECT * FROM users WHERE username='admin';")
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO users (username, password) VALUES (%s, %s);",
            ("admin", "admin123")
        )

    conn.commit()
    cur.close()
    conn.close()

init_db()


# ---------- LOGIN ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM users WHERE username=%s AND password=%s;",
            (username, password)
        )
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user:
            session["user"] = username
            return redirect("/admin")

    return """
        <h2>Login</h2>
        <form method="post">
            Username:<br>
            <input name="username"><br><br>
            Password:<br>
            <input name="password" type="password"><br><br>
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
    cur.execute("SELECT name, card_number, points FROM cards ORDER BY id DESC;")
    cards = cur.fetchall()
    cur.close()
    conn.close()

    html = """
    <h1>Адмін панель</h1>
    <a href="/logout">Вийти</a><br><br>

    <h3>Додати картку</h3>
    <form method="post" action="/add_card">
        Ім'я:<br>
        <input name="name"><br><br>
        <button type="submit">Додати</button>
    </form>

    <h3>Список карток</h3>
    <table border=1>
    <tr><th>Ім'я</th><th>Номер</th><th>Бали</th><th>Дії</th></tr>
    """

    for name, number, points in cards:
        html += f"""
        <tr>
            <td>{name}</td>
            <td>{number}</td>
            <td>{points}</td>
            <td>
                <a href="/add_point/{number}">+1</a>
                <a href="/print/{number}">Друк</a>
                <a href="/delete/{number}">Видалити</a>
            </td>
        </tr>
        """

    html += "</table>"
    return html


# ---------- ADD CARD ----------
@app.route("/add_card", methods=["POST"])
def add_card():
    if "user" not in session:
        return redirect("/login")

    name = request.form["name"]
    card_number = ''.join(random.choices(string.digits, k=8))

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO cards (name, card_number) VALUES (%s, %s);",
        (name, card_number)
    )
    conn.commit()
    cur.close()
    conn.close()

    return redirect("/admin")


# ---------- ADD POINT ----------
@app.route("/add_point/<card_number>")
def add_point(card_number):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE cards SET points = points + 1 WHERE card_number=%s;",
        (card_number,)
    )
    conn.commit()
    cur.close()
    conn.close()

    return redirect("/admin")


# ---------- DELETE ----------
@app.route("/delete/<card_number>")
def delete(card_number):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM cards WHERE card_number=%s;",
        (card_number,)
    )
    conn.commit()
    cur.close()
    conn.close()

    return redirect("/admin")


# ---------- PRINT ----------
@app.route("/print/<card_number>")
def print_card(card_number):
    return f"""
    <html>
    <body onload="window.print()">
        <h2>Бонусна картка</h2>
        <h3>№ {card_number}</h3>
        <p>Перевірити бали:</p>
        <p>https://points-app-ndyb.onrender.com/</p>
    </body>
    </html>
    """


# ---------- LOGOUT ----------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# ---------- MAIN ----------
if __name__ == "__main__":
    app.run()
