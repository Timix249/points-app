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

    # USERS TABLE
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    );
    """)

    # CARDS TABLE (basic)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS cards(
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        number TEXT UNIQUE NOT NULL,
        points INTEGER DEFAULT 0
    );
    """)

    # ✅ AUTO ADD BLOCKED COLUMN IF MISSING
    cur.execute("""
    ALTER TABLE cards
    ADD COLUMN IF NOT EXISTS blocked BOOLEAN DEFAULT FALSE;
    """)

    # DEFAULT ADMIN
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


# ---------------- USER PAGE ----------------
@app.route("/user")
def user():
    return """
    <h1>💎 Points</h1>
    <input id='code' placeholder='Enter Code'>
    <button onclick='lookup()'>Check</button>
    <div id='result'></div>

    <script>
    async function lookup(){
        const code=document.getElementById("code").value;
        const r=await fetch("/api/card/"+code);
        const data=await r.json();

        if(data.error){
            document.getElementById("result").innerHTML="Not found";
        }else if(data.blocked){
            document.getElementById("result").innerHTML="Blocked";
        }else{
            document.getElementById("result").innerHTML=
            data.name+" - Points: "+data.points;
        }
    }
    </script>
    """


# ---------------- API ----------------
@app.route("/api/card/<number>")
def api_card(number):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT name, points, blocked FROM cards WHERE number=%s;",
        (number,)
    )
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
      <button>Login</button>
    </form>
    """


# ---------------- ADMIN ----------------
@app.route("/admin")
def admin():
    if not is_admin():
        return redirect("/login")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT name, number, points, blocked FROM cards ORDER BY id DESC;"
    )
    cards = cur.fetchall()
    cur.close()
    conn.close()

    html = "<h1>💎 ADMIN</h1>"
    html += "<a href='/logout'>Logout</a><br><br>"
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
    cur.execute(
        "INSERT INTO cards (name,number) VALUES (%s,%s);",
        (name, number)
    )
    conn.commit()
    cur.close()
    conn.close()

    return redirect("/admin")


@app.route("/plus/<number>")
def plus(number):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE cards SET points=points+1 WHERE number=%s AND blocked=false;",
        (number,)
    )
    conn.commit()
    cur.close()
    conn.close()
    return redirect("/admin")


@app.route("/toggle/<number>")
def toggle(number):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE cards SET blocked = NOT blocked WHERE number=%s;",
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
    cur.execute("DELETE FROM cards WHERE number=%s;", (number,))
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