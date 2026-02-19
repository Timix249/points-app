import os
import psycopg2
from flask import Flask, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = "super_secret_key_123"

DATABASE_URL = os.environ.get("DATABASE_URL")

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "123456"   # можеш змінити


def get_connection():
    return psycopg2.connect(DATABASE_URL)


def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cards (
            id SERIAL PRIMARY KEY,
            number TEXT UNIQUE NOT NULL,
            points INTEGER DEFAULT 0
        );
    """)
    conn.commit()
    cur.close()
    conn.close()


init_db()


# ---------------- ПЕРЕВІРКА АВТОРИЗАЦІЇ ----------------
def is_logged_in():
    return session.get("logged_in")


# ---------------- ГОЛОВНА ----------------
@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        number = request.form["number"]

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT points FROM cards WHERE number=%s;", (number,))
        card = cur.fetchone()
        cur.close()
        conn.close()

        if card:
            return f"<h2>Картка №{number}</h2><h3>Бали: {card[0]}</h3>"
        else:
            return "<h3>Картку не знайдено</h3>"

    return """
        <h2>Перевірити бали</h2>
        <form method="POST">
            <input name="number" placeholder="Номер картки" required>
            <button type="submit">Перевірити</button>
        </form>
        <br>
        <a href="/login">Адмін логін</a>
    """


# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("admin"))
        else:
            return "<h3>Неправильний логін або пароль</h3>"

    return """
        <h2>Адмін логін</h2>
        <form method="POST">
            <input name="username" placeholder="Логін" required><br><br>
            <input name="password" type="password" placeholder="Пароль" required><br><br>
            <button type="submit">Увійти</button>
        </form>
    """


# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


# ---------------- АДМІН ----------------
@app.route("/admin")
def admin():
    if not is_logged_in():
        return redirect(url_for("login"))

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT number, points FROM cards ORDER BY id DESC;")
    cards = cur.fetchall()
    cur.close()
    conn.close()

    html = "<h2>Адмін панель</h2>"
    html += '<a href="/logout">Вийти</a><br><br>'
    html += '<a href="/add">Додати картку</a><br><br>'

    for number, points in cards:
        html += f"""
        <div style="margin-bottom:10px;">
            №{number} | Бали: {points}
            <a href="/add_points/{number}">➕</a>
            <a href="/delete/{number}">❌ Видалити</a>
            <a href="/print/{number}">🖨 Друк</a>
        </div>
        """

    return html


# ---------------- ДОДАТИ КАРТКУ ----------------
@app.route("/add")
def add_card():
    if not is_logged_in():
        return redirect(url_for("login"))

    number = str(int.from_bytes(os.urandom(3), "big"))

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO cards (number, points) VALUES (%s, 0) ON CONFLICT DO NOTHING;",
        (number,),
    )
    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("admin"))


# ---------------- ДОДАТИ БАЛ ----------------
@app.route("/add_points/<number>")
def add_points(number):
    if not is_logged_in():
        return redirect(url_for("login"))

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE cards SET points = points + 1 WHERE number=%s;", (number,))
    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("admin"))


# ---------------- ВИДАЛИТИ ----------------
@app.route("/delete/<number>")
def delete(number):
    if not is_logged_in():
        return redirect(url_for("login"))

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM cards WHERE number=%s;", (number,))
    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("admin"))


# ---------------- ДРУК ----------------
@app.route("/print/<number>")
def print_card(number):
    if not is_logged_in():
        return redirect(url_for("login"))

    return f"""
    <html>
    <body onload="window.print()">
        <h2>Бонусна картка</h2>
        <h3>№ {number}</h3>
        <p>Перевірити бали:</p>
        <p>https://points-app-ndyb.onrender.com/</p>
    </body>
    </html>
    """


if __name__ == "__main__":
    app.run()
