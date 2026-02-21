import os
import psycopg2
from flask import Flask, request, redirect, session
import random
import string

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "super_secret_key")

DATABASE_URL = os.environ.get("DATABASE_URL")


# ---------- DATABASE ----------
def get_connection():
    return psycopg2.connect(DATABASE_URL, sslmode="require")


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

    cur.execute("SELECT * FROM users WHERE username=%s;", ("admin",))
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO users (username, password) VALUES (%s, %s);",
            ("admin", "admin123")
        )

    conn.commit()
    cur.close()
    conn.close()


with app.app_context():
    init_db()


# ---------- HOME ----------
@app.route("/")
def home():
    return redirect("/login")


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
    <style>
    body{font-family:Arial;background:#f4f6f9;display:flex;justify-content:center;align-items:center;height:100vh}
    .box{background:white;padding:40px;border-radius:15px;box-shadow:0 10px 30px rgba(0,0,0,0.1);width:300px}
    input{width:100%;padding:10px;margin:8px 0;border-radius:8px;border:1px solid #ddd}
    button{width:100%;padding:10px;background:#4CAF50;color:white;border:none;border-radius:8px}
    h2{text-align:center}
    </style>
    <div class="box">
    <h2>Admin Login</h2>
    <form method="post">
    <input name="username" placeholder="Username">
    <input type="password" name="password" placeholder="Password">
    <button>Login</button>
    </form>
    </div>
    """


# ---------- ADMIN DASHBOARD ----------
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

    total_cards = len(cards)
    total_points = sum(c[2] for c in cards)

    html = f"""
    <style>
    body{{font-family:Arial;background:#f4f6f9;margin:0;padding:20px}}
    .top{{display:flex;justify-content:space-between;align-items:center}}
    .stats{{display:flex;gap:20px;margin:20px 0}}
    .card-stat{{background:white;padding:20px;border-radius:15px;box-shadow:0 5px 15px rgba(0,0,0,0.05)}}
    table{{width:100%;background:white;border-radius:15px;overflow:hidden;border-collapse:collapse}}
    th,td{{padding:12px;text-align:center}}
    th{{background:#4CAF50;color:white}}
    tr:nth-child(even){{background:#f2f2f2}}
    a.button{{padding:6px 12px;border-radius:6px;text-decoration:none;color:white;margin:2px;display:inline-block}}
    .green{{background:#4CAF50}}
    .red{{background:#e74c3c}}
    .blue{{background:#3498db}}
    input{{padding:8px;border-radius:6px;border:1px solid #ccc}}
    button{{padding:8px 12px;background:#4CAF50;color:white;border:none;border-radius:6px}}
    </style>

    <div class="top">
        <h1>💎 Points Admin Dashboard</h1>
        <a href="/logout" class="button red">Logout</a>
    </div>

    <div class="stats">
        <div class="card-stat">Total Cards<br><h2>{total_cards}</h2></div>
        <div class="card-stat">Total Points<br><h2>{total_points}</h2></div>
    </div>

    <h3>Add New Card</h3>
    <form method="post" action="/add">
        <input name="name" placeholder="Customer Name" required>
        <button>Add</button>
    </form>

    <h3 style="margin-top:30px;">All Cards</h3>

    <table>
    <tr><th>Name</th><th>Number</th><th>Points</th><th>Actions</th></tr>
    """

    for name, number, points in cards:
        html += f"""
        <tr>
        <td>{name}</td>
        <td>{number}</td>
        <td>{points}</td>
        <td>
            <a href="/plus/{number}" class="button green">+1</a>
            <a href="/print/{number}" class="button blue">Print</a>
            <a href="/delete/{number}" class="button red">Delete</a>
        </td>
        </tr>
        """

    html += "</table>"
    return html


# ---------- ADD ----------
@app.route("/add", methods=["POST"])
def add():
    if "user" not in session:
        return redirect("/login")

    name = request.form["name"]
    number = ''.join(random.choices(string.digits, k=8))

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO cards (name, number) VALUES (%s, %s);", (name, number))
    conn.commit()
    cur.close()
    conn.close()

    return redirect("/admin")


# ---------- ADD POINT ----------
@app.route("/plus/<number>")
def plus(number):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE cards SET points = points + 1 WHERE number=%s;", (number,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect("/admin")


# ---------- PRINT CARD ----------
@app.route("/print/<number>")
def print_card(number):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT name FROM cards WHERE number=%s;", (number,))
    card = cur.fetchone()
    cur.close()
    conn.close()

    if not card:
        return "Card not found"

    name = card[0]

    return f"""
    <style>
    body{{font-family:Arial;display:flex;justify-content:center;align-items:center;height:100vh;background:white}}
    .card{{
        width:350px;
        height:200px;
        border:3px dashed black;
        border-radius:20px;
        display:flex;
        flex-direction:column;
        justify-content:center;
        align-items:center;
    }}
    h2{{margin:10px}}
    p{{margin:5px}}
    @media print {{
        body{{background:white}}
    }}
    </style>

    <div class="card">
        <h2>💎 Loyalty Card</h2>
        <p><strong>{name}</strong></p>
        <p>Card Number: {number}</p>
        <p>Scan to collect points</p>
    </div>

    <script>
    window.print();
    </script>
    """


# ---------- DELETE ----------
@app.route("/delete/<number>")
def delete(number):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM cards WHERE number=%s;", (number,))
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