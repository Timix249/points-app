import os
import random
import string
from io import BytesIO

import psycopg2
import qrcode
from flask import Flask, request, redirect, session, send_file, jsonify

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "super-secret-key")

DATABASE_URL = os.environ.get("DATABASE_URL")


# ---------------- DATABASE ----------------
def get_connection():
    return psycopg2.connect(DATABASE_URL, sslmode="require")


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS cards(
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        number TEXT UNIQUE NOT NULL,
        points INTEGER DEFAULT 0,
        blocked BOOLEAN DEFAULT FALSE
    );
    """)

    cur.execute("SELECT * FROM users WHERE username=%s;", ("admin",))
    if not cur.fetchone():
        cur.execute("INSERT INTO users (username,password) VALUES (%s,%s);",
                    ("admin", "admin123"))

    conn.commit()
    cur.close()
    conn.close()


init_db()


def is_admin():
    return "user" in session


# ---------------- HOME ----------------
@app.route("/")
def home():
    return redirect("/user")


# ---------------- USER (ULTRA DESIGN) ----------------
@app.route("/user")
def user():
    return """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Points</title>

<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;500;700&display=swap');

body{
  margin:0;
  font-family:'Inter',sans-serif;
  transition:0.4s;
}

body.dark{
  background: radial-gradient(circle at top,#1e293b,#0f172a);
  color:white;
}

body.light{
  background:#f1f5f9;
  color:#111827;
}

.header{
  display:flex;
  justify-content:space-between;
  padding:20px 40px;
}

.logo{
  font-weight:700;
  font-size:22px;
  background: linear-gradient(90deg,#3b82f6,#22c55e);
  -webkit-background-clip:text;
  -webkit-text-fill-color:transparent;
}

.toggle{
  cursor:pointer;
  padding:8px 14px;
  border-radius:20px;
  background:#3b82f6;
  color:white;
}

.container{
  display:flex;
  justify-content:center;
  padding:40px;
}

.card{
  width:100%;
  max-width:500px;
  padding:40px;
  border-radius:25px;
  backdrop-filter:blur(20px);
}

body.dark .card{
  background:rgba(255,255,255,0.06);
}

body.light .card{
  background:white;
  box-shadow:0 20px 50px rgba(0,0,0,0.1);
}

input{
  width:100%;
  padding:14px;
  border-radius:12px;
  border:none;
  margin-top:15px;
}

button{
  width:100%;
  padding:14px;
  margin-top:15px;
  border-radius:12px;
  border:none;
  background:linear-gradient(45deg,#3b82f6,#22c55e);
  color:white;
  font-weight:600;
  cursor:pointer;
}

.result{
  margin-top:20px;
  font-size:18px;
}
</style>
</head>

<body class="dark">

<div class="header">
  <div class="logo">💎 POINTS</div>
  <div class="toggle" onclick="toggleTheme()">🌙 / ☀️</div>
</div>

<div class="container">
  <div class="card">
    <h2>Check Your Card</h2>

    <input id="code" placeholder="Enter Code" autofocus>
    <button onclick="lookup()">Check Points</button>
    <button onclick="startCamera()">Scan with Camera</button>

    <div id="reader"></div>
    <div class="result" id="result"></div>
  </div>
</div>

<script src="https://unpkg.com/html5-qrcode"></script>

<script>
function toggleTheme(){
  document.body.classList.toggle("dark");
  document.body.classList.toggle("light");
}

async function lookup(){
  const code=document.getElementById("code").value.trim();
  if(!code) return;

  const r=await fetch("/api/card/"+code);
  const data=await r.json();

  if(data.error){
    document.getElementById("result").innerHTML="❌ Not found";
    return;
  }

  if(data.blocked){
    document.getElementById("result").innerHTML="🚫 Blocked";
  }else{
    document.getElementById("result").innerHTML="✅ "+data.name+"<br>Points: <strong>"+data.points+"</strong>";
  }
}

function startCamera(){
  const qr=new Html5Qrcode("reader");
  qr.start({facingMode:"environment"},{fps:10,qrbox:250},(text)=>{
    document.getElementById("code").value=text.trim();
    lookup();
  });
}
</script>

</body>
</html>
"""


# ---------------- API ----------------
@app.route("/api/card/<number>")
def api_card(number):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT name, points, blocked FROM cards WHERE number=%s;", (number,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return jsonify({"error": "not_found"})

    return jsonify({
        "name": row[0],
        "points": row[1],
        "blocked": row[2]
    })


# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form["username"]
        p = request.form["password"]

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username=%s AND password=%s;", (u, p))
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
      <button>Login</button>
    </form>
    """


# ---------------- ADMIN (ULTRA) ----------------
@app.route("/admin")
def admin():
    if not is_admin():
        return redirect("/login")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT name, number, points, blocked FROM cards ORDER BY id DESC;")
    cards = cur.fetchall()
    cur.close()
    conn.close()

    total_cards = len(cards)
    total_points = sum(c[2] for c in cards)

    html = f"<h1>💎 ULTRA ADMIN</h1>"
    html += f"<p>Total Cards: {total_cards} | Total Points: {total_points}</p>"
    html += '<a href="/logout">Logout</a><br><br>'
    html += """
    <form method="post" action="/add">
        <input name="name" placeholder="Customer Name">
        <button>Add Card</button>
    </form><br>
    """

    for name, number, points, blocked in cards:
        status = "BLOCKED" if blocked else "ACTIVE"
        html += f"""
        <div style="border:1px solid #ccc;padding:10px;margin:10px">
        <b>{name}</b><br>
        Code: {number}<br>
        Points: {points}<br>
        Status: {status}<br>
        <a href="/plus/{number}">+1</a> |
        <a href="/toggle/{number}">Block/Unblock</a> |
        <a href="/print/{number}">Print</a> |
        <a href="/delete/{number}">Delete</a>
        </div>
        """

    return html


@app.route("/add", methods=["POST"])
def add():
    if not is_admin():
        return redirect("/login")

    name = request.form["name"]
    number = ''.join(random.choices(string.digits, k=8))

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO cards (name,number) VALUES (%s,%s);", (name, number))
    conn.commit()
    cur.close()
    conn.close()

    return redirect("/admin")


@app.route("/plus/<number>")
def plus(number):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE cards SET points=points+1 WHERE number=%s AND blocked=false;", (number,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect("/admin")


@app.route("/toggle/<number>")
def toggle(number):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE cards SET blocked = NOT blocked WHERE number=%s;", (number,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect("/admin")


@app.route("/delete/<number>")
def delete(number):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM cards WHERE number=%s;", (number,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect("/admin")


@app.route("/qr/<number>")
def qr_code(number):
    img = qrcode.make(number)
    buf = BytesIO()
    img.save(buf)
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


@app.route("/print/<number>")
def print_card(number):
    return f"""
    <div style="width:300px;height:180px;border:2px dashed black;
    display:flex;flex-direction:column;justify-content:center;align-items:center;">
    <h3>💎 Loyalty Card</h3>
    <img src="/qr/{number}" width="100"><br>
    <b>{number}</b>
    </div>
    <script>window.print()</script>
    """


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


if __name__ == "__main__":
    app.run()