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


# ---------- INIT DB ----------
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


# =====================================================
# ================= USER SIDE =========================
# =====================================================

@app.route("/")
def home():
    return """
<!DOCTYPE html>
<html>
<head>
<title>Points Card</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<script src="https://unpkg.com/html5-qrcode"></script>
<style>
body {
    font-family: Arial;
    text-align: center;
    background: linear-gradient(135deg, #1e3c72, #2a5298);
    color: white;
    padding: 20px;
}
button {
    padding: 12px 20px;
    border: none;
    background: #ffffff;
    color: #2a5298;
    border-radius: 10px;
    font-weight: bold;
}
</style>
</head>
<body>

<h1>Scan Your Card</h1>
<p>Use camera to check your points</p>

<div id="reader" style="width:300px;margin:auto;"></div>

<script>
function onScanSuccess(decodedText) {
    window.location.href = "/check/" + decodedText;
}
new Html5QrcodeScanner("reader", { fps: 10, qrbox: 250 })
.render(onScanSuccess);
</script>

<br><br>
<a href="/login" style="color:white;">Admin Login</a>

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
        return "<h2>Card not found</h2><a href='/'>Back</a>"

    name, points = card

    return f"""
<!DOCTYPE html>
<html>
<head>
<title>Your Card</title>
<style>
body {{
    font-family: Arial;
    text-align: center;
    background: #f4f4f4;
    padding: 30px;
}}
.card {{
    background: white;
    padding: 25px;
    border-radius: 20px;
    max-width: 350px;
    margin: auto;
    box-shadow: 0 8px 20px rgba(0,0,0,0.2);
}}
h2 {{
    margin: 0;
}}
.points {{
    font-size: 28px;
    margin: 15px 0;
    color: #2a5298;
}}
@media print {{
    button {{ display:none; }}
}}
button {{
    padding: 10px 20px;
    border: none;
    background: #2a5298;
    color: white;
    border-radius: 10px;
}}
</style>
</head>
<body>

<div class="card">
<h2>{name}</h2>
<div class="points">Points: {points}</div>
<p>Card: {number}</p>
</div>

<br>
<button onclick="window.print()">Print</button>
<br><br>
<a href="/">Back</a>

</body>
</html>
"""


# =====================================================
# ================= ADMIN SIDE ========================
# =====================================================

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
    <h2>Admin Login</h2>
    <form method="post">
    <input name="username" placeholder="Username"><br><br>
    <input type="password" name="password" placeholder="Password"><br><br>
    <button type="submit">Login</button>
    </form>
    """


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
    <h1>Admin Panel</h1>
    <a href="/logout">Logout</a><br><br>

    <h3>Create Card</h3>
    <form method="post" action="/add">
    <input name="name" placeholder="Name" required>
    <button type="submit">Create</button>
    </form>

    <h3>Scan to Add Point</h3>
    <div id="reader" style="width:300px;"></div>

    <script src="https://unpkg.com/html5-qrcode"></script>
    <script>
    function onScanSuccess(decodedText) {
        window.location.href = "/plus/" + decodedText;
    }
    new Html5QrcodeScanner("reader", { fps: 10, qrbox: 250 })
    .render(onScanSuccess);
    </script>

    <h3>All Cards</h3>
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

    return f"""
    <h2>Card Created</h2>
    <p>Name: {name}</p>
    <p>Number: {number}</p>
    <img src="https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={number}">
    <br><br>
    <button onclick="window.print()">Print Card</button>
    <br><br>
    <a href="/admin">Back</a>
    """


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


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


if __name__ == "__main__":
    app.run()