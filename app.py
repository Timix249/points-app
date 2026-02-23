import os
import random
import string
from io import BytesIO

import psycopg2
import qrcode
from flask import Flask, request, redirect, session, send_file, jsonify

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change_this_secret")
DATABASE_URL = os.environ.get("DATABASE_URL")


# ---------------- DATABASE ----------------
def get_connection():
    return psycopg2.connect(DATABASE_URL)


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
        points INTEGER DEFAULT 0,
        blocked BOOLEAN DEFAULT FALSE
    );
    """)

    # create admin only if not exists
    cur.execute("SELECT 1 FROM users WHERE username=%s;", ("admin",))
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


def is_admin():
    return "user" in session


# ---------------- HOME ----------------
@app.route("/")
def home():
    return redirect("/user")


# ---------------- USER SITE ----------------
@app.route("/user")
def user():
    return """
<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Points</title>
<style>
body{font-family:Arial;background:#f4f6f9;margin:0;padding:20px}
.box{background:#fff;padding:20px;border-radius:16px;max-width:800px;margin:auto;box-shadow:0 8px 20px rgba(0,0,0,.06)}
.top{display:flex;justify-content:space-between;align-items:center}
input{padding:12px;border-radius:10px;border:1px solid #ddd;min-width:220px}
button{padding:12px 14px;border-radius:10px;border:0;background:#3498db;color:#fff;cursor:pointer}
#reader{width:320px;margin-top:12px;display:none}
</style>
</head>
<body>
<div class="box">
  <div class="top">
    <h2>💎 Points</h2>
    <a href="/">Home</a>
  </div>

  <div style="margin-top:15px">
    <input id="code" placeholder="Код картки">
    <button onclick="lookup()">Показати</button>
    <button onclick="startCam()">Сканувати камерою</button>
  </div>

  <div id="reader"></div>

  <div id="result" style="margin-top:20px;font-size:18px;font-weight:700"></div>
</div>

<script src="https://unpkg.com/html5-qrcode"></script>
<script>
let qr;

async function lookup(){
  const code = document.getElementById("code").value.trim();
  if(!code) return;
  const r = await fetch("/api/card/"+code);
  const data = await r.json();

  if(data.error){
    document.getElementById("result").innerText="Не знайдено";
    return;
  }

  if(data.blocked){
    document.getElementById("result").innerText="Картку заблоковано";
  }else{
    document.getElementById("result").innerText=data.name+" | Бали: "+data.points;
  }
}

function startCam(){
  document.getElementById("reader").style.display="block";
  if(qr) return;
  qr=new Html5Qrcode("reader");
  qr.start({facingMode:"environment"},{fps:10,qrbox:250},(text)=>{
    document.getElementById("code").value=text.trim();
    lookup();
  });
}
</script>
</body>
</html>
"""


@app.route("/api/card/<number>")
def api_card(number):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT name, points, blocked FROM cards WHERE number=%s;", (number,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return jsonify({"error": "not_found"}), 404

    name, points, blocked = row
    return jsonify({"name": name, "points": points, "blocked": blocked})


# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form.get("username")
        p = request.form.get("password")

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM users WHERE username=%s AND password=%s;", (u, p))
        ok = cur.fetchone()
        cur.close()
        conn.close()

        if ok:
            session["user"] = u
            return redirect("/admin")

    return """
<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Login</title>
<style>
body{font-family:Arial;background:#f4f6f9;display:flex;justify-content:center;align-items:center;height:100vh;margin:0}
.box{background:#fff;padding:30px;border-radius:16px;box-shadow:0 8px 20px rgba(0,0,0,.06);width:320px}
input{width:100%;padding:12px;margin:10px 0;border-radius:10px;border:1px solid #ddd}
button{width:100%;padding:12px;background:#2ecc71;color:#fff;border:0;border-radius:10px}
</style>
</head>
<body>
<div class="box">
<h3>Admin Login</h3>
<form method="post" autocomplete="off">
<input name="username" placeholder="Username" autocomplete="off">
<input type="password" name="password" placeholder="Password" autocomplete="new-password">
<button>Login</button>
</form>
</div>
</body>
</html>
"""


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# ---------------- ADMIN ----------------
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

    html = """
<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Admin</title>
<style>
body{font-family:Arial;background:#f4f6f9;margin:0;padding:20px}
.top{display:flex;justify-content:space-between}
.box{background:#fff;padding:15px;border-radius:14px;margin-bottom:15px}
table{width:100%;background:#fff;border-radius:14px;border-collapse:collapse}
th,td{padding:10px;text-align:center}
th{background:#2ecc71;color:#fff}
a.btn{padding:6px 10px;border-radius:8px;text-decoration:none;color:#fff;margin:2px;display:inline-block}
.g{background:#2ecc71}.r{background:#e74c3c}.b{background:#3498db}.o{background:#f39c12}
</style>
</head>
<body>

<div class="top">
<h2>💎 Points Admin</h2>
<div>
<a class="btn b" href="/scan-camera">Сканувати камерою</a>
<a class="btn b" href="/scan-scanner">Сканувати сканером</a>
<a class="btn r" href="/logout">Logout</a>
</div>
</div>

<div class="box">
<form method="post" action="/add">
<input name="name" placeholder="Ім'я клієнта" required>
<button type="submit">Додати</button>
</form>
</div>

<table>
<tr><th>Name</th><th>Code</th><th>Points</th><th>Status</th><th>Actions</th></tr>
"""

    for name, number, points, blocked in cards:
        status = "BLOCKED" if blocked else "ACTIVE"
        block_btn = (
            f'<a class="btn o" href="/toggle/{number}">Unblock</a>'
            if blocked else
            f'<a class="btn o" href="/toggle/{number}">Block</a>'
        )

        html += f"""
<tr>
<td>{name}</td>
<td>{number}</td>
<td>{points}</td>
<td>{status}</td>
<td>
<a class="btn g" href="/plus/{number}">+1</a>
<a class="btn b" href="/print/{number}">Print</a>
{block_btn}
<a class="btn r" href="/delete/{number}">Delete</a>
</td>
</tr>
"""

    html += "</table></body></html>"
    return html


@app.route("/add", methods=["POST"])
def add():
    if not is_admin():
        return redirect("/login")

    name = request.form["name"]
    number = "".join(random.choices(string.digits, k=8))

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO cards (name, number) VALUES (%s, %s);", (name, number))
    conn.commit()
    cur.close()
    conn.close()

    return redirect("/admin")


@app.route("/plus/<number>")
def plus(number):
    if not is_admin():
        return redirect("/login")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE cards SET points=points+1 WHERE number=%s AND blocked=FALSE;", (number,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect("/admin")


@app.route("/toggle/<number>")
def toggle(number):
    if not is_admin():
        return redirect("/login")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE cards SET blocked=NOT blocked WHERE number=%s;", (number,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect("/admin")


@app.route("/delete/<number>")
def delete(number):
    if not is_admin():
        return redirect("/login")

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
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


@app.route("/print/<number>")
def print_card(number):
    if not is_admin():
        return redirect("/login")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT name FROM cards WHERE number=%s;", (number,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return "Not found", 404

    name = row[0]

    return f"""
<html>
<body style="display:flex;justify-content:center;align-items:center;height:100vh;">
<div style="width:350px;height:220px;border:3px dashed black;border-radius:18px;display:flex;flex-direction:column;justify-content:center;align-items:center;">
<h3>💎 Loyalty Card</h3>
<div>{name}</div>
<img src="/qr/{number}" width="120">
<div>{number}</div>
</div>
<script>window.print()</script>
</body>
</html>
"""


if __name__ == "__main__":
    app.run()