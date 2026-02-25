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
    return psycopg2.connect(DATABASE_URL)


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
        points INTEGER DEFAULT 0
    );
    """)

    cur.execute("""
    ALTER TABLE cards
    ADD COLUMN IF NOT EXISTS blocked BOOLEAN DEFAULT FALSE;
    """)

    cur.execute("SELECT * FROM users WHERE username=%s;", ("admin",))
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO users (username,password) VALUES (%s,%s);",
            ("admin", "admin123")
        )

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


# ---------------- USER ----------------
@app.route("/user")
def user():
    return """
    <html>
    <head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
    body{
        font-family: Arial;
        background:#111827;
        color:white;
        text-align:center;
        padding:40px;
    }
    input{
        padding:12px;
        width:250px;
        border-radius:6px;
        border:none;
    }
    button{
        padding:12px 16px;
        border:none;
        border-radius:6px;
        background:#2563eb;
        color:white;
        margin-top:10px;
        cursor:pointer;
    }
    .box{
        background:#1f2937;
        padding:30px;
        border-radius:12px;
        display:inline-block;
    }
    </style>
    </head>
    <body>
        <div class="box">
            <h2>💎 Check Points</h2>
            <input id="code" placeholder="Enter Code">
            <br>
            <button onclick="lookup()">Check</button>
            <div id="result" style="margin-top:15px;"></div>
        </div>

        <script>
        async function lookup(){
            const code=document.getElementById("code").value;
            const r=await fetch("/api/card/"+code);
            const data=await r.json();

            if(data.error){
                document.getElementById("result").innerHTML="❌ Not found";
            }else if(data.blocked){
                document.getElementById("result").innerHTML="🚫 Blocked";
            }else{
                document.getElementById("result").innerHTML=
                "✅ "+data.name+"<br>Points: "+data.points;
            }
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
    <h2 style="text-align:center;">Admin Login</h2>
    <form method="post" style="text-align:center;">
      <input name="username" placeholder="Username"><br><br>
      <input type="password" name="password" placeholder="Password"><br><br>
      <button>Login</button>
    </form>
    """


# ---------------- ADMIN (MODERN) ----------------
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
    <html>
    <head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
    body{
        margin:0;
        font-family: Arial;
        background:#0f172a;
        color:white;
    }
    .container{
        max-width:1100px;
        margin:40px auto;
        padding:20px;
    }
    .top{
        display:flex;
        justify-content:space-between;
        align-items:center;
    }
    .btn{
        padding:6px 12px;
        border-radius:6px;
        text-decoration:none;
        font-size:13px;
        color:white;
    }
    .green{background:#16a34a;}
    .red{background:#dc2626;}
    .blue{background:#2563eb;}
    .orange{background:#f59e0b;}
    .grid{
        display:grid;
        grid-template-columns:repeat(auto-fill,minmax(260px,1fr));
        gap:20px;
        margin-top:30px;
    }
    .card{
        background:#1e293b;
        padding:20px;
        border-radius:12px;
    }
    input{
        padding:10px;
        border:none;
        border-radius:6px;
    }
    button{
        padding:10px;
        border:none;
        border-radius:6px;
        background:#2563eb;
        color:white;
        cursor:pointer;
    }
    </style>
    </head>
    <body>
    <div class="container">
        <div class="top">
            <h1>💎 Admin</h1>
            <a class="btn red" href="/logout">Logout</a>
        </div>

        <form method="post" action="/add">
            <input name="name" placeholder="Customer Name" required>
            <button>Add Card</button>
        </form>

        <div class="grid">
    """

    for name, number, points, blocked in cards:
        status = "Blocked" if blocked else "Active"
        toggle_text = "Unblock" if blocked else "Block"

        html += f"""
        <div class="card">
            <h3>{name}</h3>
            Code: {number}<br>
            Points: {points}<br>
            Status: {status}<br><br>

            <a class="btn green" href="/plus/{number}">+1</a>
            <a class="btn orange" href="/toggle/{number}">{toggle_text}</a>
            <a class="btn red" href="/delete/{number}">Delete</a>
            <a class="btn blue" href="/print/{number}">QR</a>
        </div>
        """

    html += """
        </div>
    </div>
    </body>
    </html>
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


@app.route("/print/<number>")
def print_card(number):
    img = qrcode.make(number)
    buf = BytesIO()
    img.save(buf)
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


if __name__ == "__main__":
    app.run()