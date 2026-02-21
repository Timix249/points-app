import os
import psycopg2
from flask import Flask, request, redirect, session
import random
import string

app = Flask(__name__)
app.secret_key = "super_secret_key"

DATABASE_URL = os.environ.get("DATABASE_URL")

def get_connection():
    return psycopg2.connect(DATABASE_URL, sslmode="require")


# ================= INIT DATABASE =================

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

init_db()


# ================= USER SIDE =================

@app.route("/")
def home():
    return """
<!DOCTYPE html>
<html>
<head>
<title>Punkte System</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<script src="https://unpkg.com/html5-qrcode"></script>
<style>
body {
    margin:0;
    font-family:Arial;
    background:linear-gradient(135deg,#0f2027,#203a43,#2c5364);
    color:white;
    text-align:center;
}
.container {
    padding:50px 20px;
}
.logo {
    font-size:28px;
    font-weight:bold;
    margin-bottom:10px;
}
#reader {
    margin:auto;
    width:300px;
}
.admin-link {
    margin-top:40px;
    display:inline-block;
    color:white;
    opacity:0.6;
}
</style>
</head>
<body>

<div class="container">
    <div class="logo">⭐ POINTS CLUB</div>
    <h2>Karte scannen</h2>
    <p>QR Code vor Kamera halten</p>
    <div id="reader"></div>
    <a class="admin-link" href="/login">Admin Login</a>
</div>

<script>
function onScanSuccess(decodedText) {
    window.location.href = "/check/" + decodedText;
}
new Html5QrcodeScanner("reader", { fps: 10, qrbox: 250 })
.render(onScanSuccess);
</script>

</body>
</html>
"""


@app.route("/check/<number>")
def check(number):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT name, points FROM cards WHERE number=%s;", (number,))
    card = cur.fetchone()
    cur.close()
    conn.close()

    if not card:
        return "<h2>Karte nicht gefunden</h2><a href='/'>Zurück</a>"

    name, points = card

    return f"""
<!DOCTYPE html>
<html>
<head>
<style>
body {{
    display:flex;
    justify-content:center;
    align-items:center;
    height:100vh;
    background:#f2f2f2;
    font-family:Arial;
}}
.print-area {{
    width:350px;
}}
.card {{
    border:3px dashed black;
    border-radius:15px;
    padding:20px;
    text-align:center;
    background:white;
}}
.name {{ font-size:22px; font-weight:bold; }}
.points {{ font-size:28px; margin:20px 0; color:#2c5364; }}

button {{
    margin-top:15px;
    padding:10px 20px;
    background:#2c5364;
    color:white;
    border:none;
    border-radius:8px;
}}

@media print {{
    body * {{ visibility:hidden; }}
    .print-area, .print-area * {{ visibility:visible; }}
    .print-area {{ position:absolute; top:0; left:0; }}
    button {{ display:none; }}
}}
</style>
</head>
<body>

<div class="print-area">
    <div class="card">
        <div class="name">{name}</div>
        <div class="points">{points} Punkte</div>
        <div>Nr: {number}</div>
    </div>
    <button onclick="window.print()">Karte drucken</button>
</div>

</body>
</html>
"""


# ================= ADMIN LOGIN =================

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        u = request.form["username"]
        p = request.form["password"]

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username=%s AND password=%s;", (u,p))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user:
            session["user"] = u
            return redirect("/admin")

    return """
    <h2>Admin Login</h2>
    <form method="post">
    <input name="username" placeholder="Username"><br><br>
    <input type="password" name="password" placeholder="Password"><br><br>
    <button type="submit">Login</button>
    </form>
    """


# ================= ADMIN DASHBOARD =================

@app.route("/admin")
def admin():
    if "user" not in session:
        return redirect("/login")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM cards;")
    total_cards = cur.fetchone()[0]

    cur.execute("SELECT COALESCE(SUM(points),0) FROM cards;")
    total_points = cur.fetchone()[0]

    cur.execute("SELECT name, number, points FROM cards ORDER BY id DESC;")
    cards = cur.fetchall()

    cur.close()
    conn.close()

    html = f"""
<!DOCTYPE html>
<html>
<head>
<title>Admin Dashboard</title>
<style>
body {{
    margin:0;
    font-family:Arial;
    background:#f4f6f9;
}}
.header {{
    background:#2c5364;
    color:white;
    padding:15px;
    font-size:20px;
}}
.container {{
    padding:30px;
}}
.stats {{
    display:flex;
    gap:20px;
    margin-bottom:30px;
}}
.box {{
    background:white;
    padding:20px;
    border-radius:10px;
    flex:1;
    box-shadow:0 4px 10px rgba(0,0,0,0.1);
}}
button {{
    padding:8px 15px;
    border:none;
    border-radius:6px;
    background:#2c5364;
    color:white;
}}
table {{
    width:100%;
    border-collapse:collapse;
    background:white;
    box-shadow:0 4px 10px rgba(0,0,0,0.1);
}}
th, td {{
    padding:10px;
    text-align:center;
}}
th {{
    background:#2c5364;
    color:white;
}}
tr:nth-child(even) {{
    background:#f2f2f2;
}}
a {{
    text-decoration:none;
    color:#2c5364;
    font-weight:bold;
}}
</style>
</head>
<body>

<div class="header">
⭐ POINTS CLUB – Admin Dashboard
</div>

<div class="container">

<div class="stats">
    <div class="box">
        <h3>Gesamt Karten</h3>
        <h2>{total_cards}</h2>
    </div>
    <div class="box">
        <h3>Gesamt Punkte</h3>
        <h2>{total_points}</h2>
    </div>
</div>

<h3>Neue Karte erstellen</h3>
<form method="post" action="/add">
<input name="name" placeholder="Name" required>
<button type="submit">Erstellen</button>
</form>

<br><br>

<h3>Karten Übersicht</h3>
<table>
<tr><th>Name</th><th>Nummer</th><th>Punkte</th><th>Aktion</th></tr>
"""

    for name, number, points in cards:
        html += f"""
<tr>
<td>{name}</td>
<td>{number}</td>
<td>{points}</td>
<td>
<a href="/plus/{number}">+1</a> |
<a href="/delete/{number}">Löschen</a>
</td>
</tr>
"""

    html += """
</table>
<br><br>
<a href="/logout">Logout</a>
</div>
</body>
</html>
"""
    return html


# ================= ACTIONS =================

@app.route("/add", methods=["POST"])
def add():
    if "user" not in session:
        return redirect("/login")

    name = request.form["name"]
    number = ''.join(random.choices(string.digits, k=8))

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO cards (name, number) VALUES (%s, %s);",(name,number))
    conn.commit()
    cur.close()
    conn.close()

    return redirect("/admin")


@app.route("/plus/<number>")
def plus(number):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE cards SET points = points + 1 WHERE number=%s;",(number,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect("/admin")


@app.route("/delete/<number>")
def delete(number):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM cards WHERE number=%s;",(number,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect("/admin")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


if __name__ == "__main__":
    app.run()