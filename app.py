import os
import psycopg2
import qrcode
from io import BytesIO
from flask import Flask, request, redirect, session, send_file, render_template_string
import random, string

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret")

DATABASE_URL = os.environ.get("DATABASE_URL")

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
        points INTEGER DEFAULT 0,
        blocked BOOLEAN DEFAULT FALSE
    );
    """)
    cur.execute("SELECT * FROM users WHERE username=%s;", ("admin",))
    if not cur.fetchone():
        cur.execute("INSERT INTO users (username, password) VALUES (%s,%s);", ("admin", "admin123"))
    conn.commit()
    cur.close()
    conn.close()

init_db()

# ---------- HOME ----------
@app.route("/")
def home():
    return """
    <h1>Points System</h1>
    <a href="/login">Admin Login</a><br>
    <a href="/user">User Site</a>
    """

# ---------- LOGIN ----------
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        u = request.form["username"]
        p = request.form["password"]
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username=%s AND password=%s;", (u,p))
        user = cur.fetchone()
        cur.close(); conn.close()
        if user:
            session["user"] = u
            return redirect("/admin")
    return """
    <h2>Admin Login</h2>
    <form method="post">
      <input name="username" placeholder="Username"><br>
      <input type="password" name="password" placeholder="Password"><br>
      <button>Login</button>
    </form>
    """

# ---------- ADMIN ----------
@app.route("/admin")
def admin():
    if "user" not in session:
        return redirect("/login")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT name, number, points, blocked FROM cards ORDER BY id DESC;")
    cards = cur.fetchall()
    cur.close(); conn.close()

    html = "<h1>Admin Dashboard</h1>"
    html += '<a href="/logout">Logout</a><br><br>'
    html += """
    <form method="post" action="/add">
      <input name="name" placeholder="Name">
      <button>Add Card</button>
    </form>
    <br>
    <table border=1 cellpadding=6>
    <tr><th>Name</th><th>Code</th><th>QR</th><th>Points</th><th>Status</th><th>Actions</th></tr>
    """
    for name, number, points, blocked in cards:
        html += f"""
        <tr>
          <td>{name}</td>
          <td>{number}</td>
          <td><img src="/qr/{number}" width="80"></td>
          <td>{points}</td>
          <td>{"❌ Blocked" if blocked else "✅ Active"}</td>
          <td>
            <a href="/plus/{number}">+1</a> |
            <a href="/block/{number}">Block</a> |
            <a href="/unblock/{number}">Unblock</a> |
            <a href="/print/{number}">Print</a> |
            <a href="/delete/{number}">Delete</a>
          </td>
        </tr>
        """
    html += "</table>"
    html += '<br><a href="/print_all">Print all cards</a>'
    return html

# ---------- USER SITE ----------
@app.route("/user", methods=["GET","POST"])
def user():
    card = None
    if request.method == "POST":
        code = request.form["code"]
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT name, points, blocked FROM cards WHERE number=%s;", (code,))
        card = cur.fetchone()
        cur.close(); conn.close()
    return render_template_string("""
    <h1>User Site</h1>

    <form method="post">
      <input name="code" placeholder="Enter card code">
      <button>Check</button>
    </form>

    <button onclick="startScan()">Scan with Camera</button>
    <video id="video" width="300" hidden></video>

    {% if card %}
      <h2>{{card[0]}}</h2>
      <p>Points: {{card[1]}}</p>
      <p>Status: {{ "Blocked" if card[2] else "Active" }}</p>
    {% endif %}

<script>
function startScan(){
  navigator.mediaDevices.getUserMedia({video:{facingMode:"environment"}}).then(stream=>{
    const v=document.getElementById("video");
    v.hidden=false;
    v.srcObject=stream;
    v.play();
  });
}
</script>
    """, card=card)

# ---------- ADD CARD ----------
@app.route("/add", methods=["POST"])
def add():
    if "user" not in session: return redirect("/login")
    name = request.form["name"]
    number = ''.join(random.choices(string.digits, k=8))
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO cards (name, number) VALUES (%s,%s);", (name,number))
    conn.commit()
    cur.close(); conn.close()
    return redirect("/admin")

@app.route("/plus/<number>")
def plus(number):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE cards SET points = points + 1 WHERE number=%s AND blocked=false;", (number,))
    conn.commit()
    cur.close(); conn.close()
    return redirect("/admin")

@app.route("/block/<number>")
def block(number):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE cards SET blocked=true WHERE number=%s;", (number,))
    conn.commit()
    cur.close(); conn.close()
    return redirect("/admin")

@app.route("/unblock/<number>")
def unblock(number):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE cards SET blocked=false WHERE number=%s;", (number,))
    conn.commit()
    cur.close(); conn.close()
    return redirect("/admin")

@app.route("/delete/<number>")
def delete(number):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM cards WHERE number=%s;", (number,))
    conn.commit()
    cur.close(); conn.close()
    return redirect("/admin")

# ---------- QR ----------
@app.route("/qr/<number>")
def qr(number):
    img = qrcode.make(number)
    buf = BytesIO()
    img.save(buf)
    buf.seek(0)
    return send_file(buf, mimetype="image/png")

# ---------- PRINT ----------
@app.route("/print/<number>")
def print_card(number):
    return f"""
    <style>
    .card {{
      width:300px;height:180px;border:2px dashed black;
      display:flex;flex-direction:column;justify-content:center;align-items:center;
    }}
    </style>
    <div class="card">
      <h3>Card</h3>
      <img src="/qr/{number}" width="100"><br>
      <b>{number}</b>
    </div>
    <script>window.print()</script>
    """

@app.route("/print_all")
def print_all():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT number FROM cards;")
    cards = cur.fetchall()
    cur.close(); conn.close()

    html = "<style>.card{width:300px;height:180px;border:2px dashed black;display:inline-flex;flex-direction:column;justify-content:center;align-items:center;margin:10px;}</style>"
    for (number,) in cards:
        html += f'<div class="card"><img src="/qr/{number}" width="100"><br>{number}</div>'
    html += "<script>window.print()</script>"
    return html

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

if __name__ == "__main__":
    app.run()