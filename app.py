import os
import random
import string
from io import BytesIO

import psycopg2
import qrcode
from flask import (
    Flask, request, redirect, session,
    send_file, jsonify
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "super_secret_key")
DATABASE_URL = os.environ.get("DATABASE_URL")


# ---------------- DATABASE ----------------
def get_connection():
    # Railway Postgres URL usually works without sslmode, keep simple
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
        points INTEGER DEFAULT 0
    );
    """)

    # create admin if not exists (safe for multi-worker)
    cur.execute("""
    INSERT INTO users (username, password)
    VALUES (%s, %s)
    ON CONFLICT (username) DO NOTHING;
    """, ("admin", "admin123"))

    conn.commit()
    cur.close()
    conn.close()


with app.app_context():
    init_db()


def require_admin():
    return "user" in session


# ---------------- HOME ----------------
@app.route("/")
def home():
    return """
    <style>
      body{font-family:Arial;background:#0b1220;color:#e8eefc;margin:0}
      .wrap{max-width:980px;margin:0 auto;padding:40px}
      .hero{background:linear-gradient(135deg,#1b2a4a,#0b1220);border:1px solid rgba(255,255,255,.08);
            border-radius:18px;padding:28px;box-shadow:0 20px 60px rgba(0,0,0,.35)}
      .btn{display:inline-block;padding:12px 16px;border-radius:12px;text-decoration:none;color:white;margin-right:10px}
      .a{background:#22c55e}.b{background:#3b82f6}.c{background:#ef4444}
      .grid{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:18px}
      .card{background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.08);border-radius:16px;padding:18px}
      small{opacity:.8}
      @media(max-width:760px){.grid{grid-template-columns:1fr}}
    </style>
    <div class="wrap">
      <div class="hero">
        <h1 style="margin:0 0 8px 0;">💎 Points / Loyalty</h1>
        <small>Admin + User site + QR + Scan</small>
        <div style="margin-top:16px;">
          <a class="btn a" href="/user">👤 User Site</a>
          <a class="btn b" href="/login">🛠 Admin Login</a>
        </div>

        <div class="grid">
          <div class="card">
            <h3 style="margin-top:0;">User Site</h3>
            <ul>
              <li>Ввести код вручну</li>
              <li>Сканувати QR камерою</li>
              <li>Бачити бали</li>
              <li>Додати +1 (для працівника/сканера)</li>
            </ul>
          </div>
          <div class="card">
            <h3 style="margin-top:0;">Admin</h3>
            <ul>
              <li>Створення карток</li>
              <li>QR на кожній картці</li>
              <li>Друк з рамкою для вирізання</li>
              <li>Відновлення по коду (якщо видалили)</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
    """


# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form.get("username", "")
        p = request.form.get("password", "")

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM users WHERE username=%s AND password=%s;", (u, p))
        ok = cur.fetchone() is not None
        cur.close()
        conn.close()

        if ok:
            session["user"] = u
            return redirect("/admin")

    return """
    <style>
      body{font-family:Arial;background:#f4f6f9;display:flex;justify-content:center;align-items:center;height:100vh;margin:0}
      .box{background:white;padding:36px;border-radius:16px;box-shadow:0 10px 30px rgba(0,0,0,0.12);width:320px}
      input{width:100%;padding:12px;margin:8px 0;border-radius:10px;border:1px solid #ddd}
      button{width:100%;padding:12px;background:#3b82f6;color:white;border:none;border-radius:10px;font-weight:700}
      a{color:#3b82f6;text-decoration:none}
    </style>
    <div class="box">
      <h2 style="margin:0 0 6px 0;">Admin Login</h2>
      <div style="opacity:.7;margin-bottom:12px;">default: admin / admin123</div>
      <form method="post">
        <input name="username" placeholder="Username" />
        <input type="password" name="password" placeholder="Password" />
        <button>Login</button>
      </form>
      <div style="margin-top:12px;"><a href="/">← Back</a></div>
    </div>
    """


# ---------------- ADMIN DASHBOARD ----------------
@app.route("/admin")
def admin():
    if not require_admin():
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
      body{{font-family:Arial;background:#0b1220;color:#e8eefc;margin:0;padding:22px}}
      .top{{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}}
      .pill{{background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.10);padding:10px 14px;border-radius:999px}}
      .btn{{display:inline-block;padding:10px 14px;border-radius:12px;text-decoration:none;color:white;font-weight:700}}
      .g{{background:#22c55e}} .r{{background:#ef4444}} .b{{background:#3b82f6}} .s{{background:#8b5cf6}}
      .grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:16px 0}}
      .card{{background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.10);border-radius:16px;padding:14px}}
      table{{width:100%;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.10);
            border-radius:16px;overflow:hidden;border-collapse:collapse}}
      th,td{{padding:12px;text-align:center}}
      th{{background:rgba(34,197,94,.25)}}
      tr:nth-child(even){{background:rgba(255,255,255,.03)}}
      input{{padding:10px;border-radius:12px;border:1px solid rgba(255,255,255,.18);background:rgba(0,0,0,.25);color:#e8eefc}}
      button{{padding:10px 14px;border-radius:12px;border:none;background:#22c55e;color:white;font-weight:800;cursor:pointer}}
      .row{{display:flex;gap:10px;flex-wrap:wrap;align-items:center}}
      small{{opacity:.8}}
      @media(max-width:900px){{.grid{{grid-template-columns:1fr}}}}
      img.qr{{background:white;padding:6px;border-radius:10px}}
    </style>

    <div class="top">
      <div>
        <h1 style="margin:0;">💎 Admin Dashboard</h1>
        <small>QR на кожній картці · Друк з рамкою · Відновлення по коду</small>
      </div>
      <div class="row">
        <a class="btn b" href="/user">User Site</a>
        <a class="btn r" href="/logout">Logout</a>
      </div>
    </div>

    <div class="grid">
      <div class="card"><div class="pill">Total Cards</div><h2 style="margin:10px 0 0 0;">{total_cards}</h2></div>
      <div class="card"><div class="pill">Total Points</div><h2 style="margin:10px 0 0 0;">{total_points}</h2></div>
      <div class="card">
        <div class="pill">Quick actions</div>
        <div class="row" style="margin-top:10px;">
          <a class="btn s" href="/admin/print_all">Print all</a>
        </div>
      </div>
    </div>

    <div class="card">
      <h3 style="margin-top:0;">➕ Create new card</h3>
      <form method="post" action="/add" class="row">
        <input name="name" placeholder="Customer name" required>
        <button>Create</button>
      </form>
      <div style="height:10px;"></div>
      <h3 style="margin:0;">♻️ Restore card (manual) by code</h3>
      <small>Якщо картку видалили, але код є на руках — введи номер і ім’я, і ми її відновимо.</small>
      <form method="post" action="/restore" class="row" style="margin-top:10px;">
        <input name="number" placeholder="Card number (8 digits)" required>
        <input name="name" placeholder="Name on card" required>
        <button style="background:#3b82f6;">Restore</button>
      </form>
    </div>

    <div style="height:14px;"></div>

    <table>
      <tr>
        <th>QR</th><th>Name</th><th>Number</th><th>Points</th><th>Actions</th>
      </tr>
    """

    for name, number, points in cards:
        html += f"""
        <tr>
          <td><img class="qr" src="/qr/{number}" width="70" height="70" /></td>
          <td>{name}</td>
          <td>{number}</td>
          <td>{points}</td>
          <td>
            <a class="btn g" href="/plus/{number}">+1</a>
            <a class="btn b" href="/print/{number}">Print</a>
            <a class="btn r" href="/delete/{number}">Delete</a>
          </td>
        </tr>
        """

    html += "</table>"
    return html


# ---------------- ADD CARD ----------------
@app.route("/add", methods=["POST"])
def add():
    if not require_admin():
        return redirect("/login")

    name = request.form.get("name", "").strip()
    number = "".join(random.choices(string.digits, k=8))

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO cards (name, number) VALUES (%s, %s);", (name, number))
    conn.commit()
    cur.close()
    conn.close()
    return redirect("/admin")


# ---------------- RESTORE (MANUAL) ----------------
@app.route("/restore", methods=["POST"])
def restore():
    if not require_admin():
        return redirect("/login")

    number = request.form.get("number", "").strip()
    name = request.form.get("name", "").strip()

    if not number.isdigit() or len(number) < 4:
        return "Bad code"

    conn = get_connection()
    cur = conn.cursor()

    # if already exists -> update name (optional) and keep points
    cur.execute("SELECT points FROM cards WHERE number=%s;", (number,))
    row = cur.fetchone()
    if row:
        cur.execute("UPDATE cards SET name=%s WHERE number=%s;", (name, number))
    else:
        cur.execute("INSERT INTO cards (name, number, points) VALUES (%s, %s, 0);", (name, number))

    conn.commit()
    cur.close()
    conn.close()
    return redirect("/admin")


# ---------------- ADD POINT (ADMIN) ----------------
@app.route("/plus/<number>")
def plus(number):
    if not require_admin():
        return redirect("/login")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE cards SET points = points + 1 WHERE number=%s;", (number,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect("/admin")


# ---------------- DELETE (ADMIN) ----------------
@app.route("/delete/<number>")
def delete(number):
    if not require_admin():
        return redirect("/login")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM cards WHERE number=%s;", (number,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect("/admin")


# ---------------- QR IMAGE ----------------
@app.route("/qr/<number>")
def qr_code(number):
    # QR contains full public URL to open user page quickly
    base = request.host_url.rstrip("/")
    payload = f"{base}/user?code={number}"

    img = qrcode.make(payload)
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


# ---------------- PRINT ONE ----------------
@app.route("/print/<number>")
def print_card(number):
    if not require_admin():
        return redirect("/login")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT name, points FROM cards WHERE number=%s;", (number,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return "Card not found"

    name, points = row
    return f"""
    <style>
      body{{font-family:Arial;display:flex;justify-content:center;align-items:center;height:100vh;background:white;margin:0}}
      .card{{
        width:88mm;height:55mm; /* bank-card size */
        border:2px dashed #111;border-radius:16px;
        display:flex;gap:12px;align-items:center;justify-content:space-between;
        padding:12px;box-sizing:border-box;
      }}
      .left{{display:flex;flex-direction:column;gap:6px}}
      .brand{{font-weight:900;font-size:16px}}
      .meta{{font-size:12px}}
      .num{{font-weight:800;letter-spacing:1px}}
      .qr{{background:white;border-radius:12px;padding:6px}}
      @media print {{
        body{{height:auto}}
      }}
    </style>

    <div class="card">
      <div class="left">
        <div class="brand">💎 LOYALTY CARD</div>
        <div class="meta"><b>{name}</b></div>
        <div class="meta">Points: <b>{points}</b></div>
        <div class="meta num">{number}</div>
        <div class="meta">Scan QR to open / add points</div>
      </div>
      <div>
        <img class="qr" src="/qr/{number}" width="110" height="110">
      </div>
    </div>

    <script>window.print()</script>
    """


# ---------------- PRINT ALL ----------------
@app.route("/admin/print_all")
def print_all():
    if not require_admin():
        return redirect("/login")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT name, number, points FROM cards ORDER BY id DESC;")
    cards = cur.fetchall()
    cur.close()
    conn.close()

    # A4 grid
    items = ""
    for name, number, points in cards:
        items += f"""
        <div class="card">
          <div class="left">
            <div class="brand">💎 LOYALTY CARD</div>
            <div class="meta"><b>{name}</b></div>
            <div class="meta">Points: <b>{points}</b></div>
            <div class="meta num">{number}</div>
          </div>
          <img class="qr" src="/qr/{number}" width="90" height="90">
        </div>
        """

    return f"""
    <style>
      body{{font-family:Arial;background:white;margin:0;padding:10mm}}
      .grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:8mm}}
      .card{{
        width:88mm;height:55mm;border:2px dashed #111;border-radius:16px;
        display:flex;justify-content:space-between;align-items:center;
        padding:10px;box-sizing:border-box;
      }}
      .brand{{font-weight:900}}
      .meta{{font-size:12px;margin-top:4px}}
      .num{{font-weight:800;letter-spacing:1px}}
      .qr{{background:white;border-radius:12px;padding:6px}}
      @media print {{ body{{padding:0}} }}
    </style>
    <div class="grid">{items}</div>
    <script>window.print()</script>
    """


# ---------------- USER SITE ----------------
@app.route("/user")
def user_site():
    # prefill from ?code=...
    prefill = request.args.get("code", "")
    return f"""
    <style>
      body{{font-family:Arial;background:#0b1220;color:#e8eefc;margin:0}}
      .wrap{{max-width:980px;margin:0 auto;padding:22px}}
      .card{{background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.10);border-radius:16px;padding:16px}}
      .row{{display:flex;gap:10px;flex-wrap:wrap;align-items:center}}
      input{{padding:12px;border-radius:12px;border:1px solid rgba(255,255,255,.18);background:rgba(0,0,0,.25);color:#e8eefc;width:260px}}
      button{{padding:12px 14px;border-radius:12px;border:none;color:white;font-weight:800;cursor:pointer}}
      .b{{background:#3b82f6}} .g{{background:#22c55e}} .r{{background:#ef4444}}
      .pill{{display:inline-block;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.10);padding:8px 12px;border-radius:999px}}
      #result{{margin-top:12px}}
      .box{{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:14px}}
      @media(max-width:900px){{.box{{grid-template-columns:1fr}}}}
      video{{width:100%;max-width:520px;border-radius:16px;border:1px solid rgba(255,255,255,.12)}}
      a{{color:#93c5fd}}
      small{{opacity:.8}}
    </style>

    <div class="wrap">
      <div class="row" style="justify-content:space-between;">
        <div>
          <h1 style="margin:0;">👤 User Site</h1>
          <small>Введи код або скануй QR камерою. (Сканер-«пістолет» теж працює — він просто “вводить текст”)</small>
        </div>
        <div class="row">
          <a class="pill" href="/">Home</a>
          <a class="pill" href="/login">Admin</a>
        </div>
      </div>

      <div class="box">
        <div class="card">
          <h3 style="margin-top:0;">🔎 Find card by code</h3>
          <div class="row">
            <input id="code" placeholder="Card code (8 digits)" value="{prefill}">
            <button class="b" onclick="lookup()">Find</button>
            <button class="g" onclick="addPoint()">+1 Point</button>
          </div>
          <div id="result" class="card" style="margin-top:12px;display:none;"></div>
          <div style="margin-top:10px;">
            <small>
              Якщо ви видалили картку в адмінці, її можна <b>відновити</b> в Admin → “Restore card”.
            </small>
          </div>
        </div>

        <div class="card">
          <h3 style="margin-top:0;">📷 Camera scan QR</h3>
          <div class="row">
            <button class="b" onclick="startCam()">Start camera</button>
            <button class="r" onclick="stopCam()">Stop</button>
          </div>
          <div style="margin-top:10px;">
            <video id="video" playsinline></video>
            <canvas id="canvas" style="display:none;"></canvas>
          </div>
          <small>Порада: дозволь доступ до камери в браузері.</small>
        </div>
      </div>
    </div>

    <!-- jsQR library (pure front-end) -->
    <script src="https://cdn.jsdelivr.net/npm/jsqr@1.4.0/dist/jsQR.js"></script>
    <script>
      const $code = document.getElementById('code');
      const $res = document.getElementById('result');
      const video = document.getElementById('video');
      const canvas = document.getElementById('canvas');
      const ctx = canvas.getContext('2d');
      let stream = null;
      let scanning = false;

      function show(obj) {{
        $res.style.display = 'block';
        $res.innerHTML = `
          <div class="row" style="justify-content:space-between;">
            <div>
              <div class="pill">Name: <b>${{obj.name}}</b></div>
              <div class="pill">Number: <b>${{obj.number}}</b></div>
              <div class="pill">Points: <b>${{obj.points}}</b></div>
            </div>
            <img src="/qr/${{obj.number}}" width="90" height="90" style="background:white;padding:6px;border-radius:12px">
          </div>
        `;
      }}

      async function lookup() {{
        const code = $code.value.trim();
        if(!code) return;
        const r = await fetch(`/api/card/${{encodeURIComponent(code)}}`);
        const data = await r.json();
        if(!data.ok) {{
          $res.style.display='block';
          $res.innerHTML = `<b>Not found</b>`;
          return;
        }}
        show(data.card);
      }}

      async function addPoint() {{
        const code = $code.value.trim();
        if(!code) return;
        const r = await fetch('/api/add_point', {{
          method:'POST',
          headers: {{'Content-Type':'application/json'}},
          body: JSON.stringify({{ number: code }})
        }});
        const data = await r.json();
        if(!data.ok) {{
          $res.style.display='block';
          $res.innerHTML = `<b>Error:</b> ${{data.error || 'unknown'}}`;
          return;
        }}
        show(data.card);
      }}

      async function startCam() {{
        if(stream) return;
        stream = await navigator.mediaDevices.getUserMedia({{ video: {{ facingMode: 'environment' }} }});
        video.srcObject = stream;
        await video.play();
        scanning = true;
        tick();
      }}

      function stopCam() {{
        scanning = false;
        if(stream) {{
          stream.getTracks().forEach(t => t.stop());
          stream = null;
        }}
        video.pause();
        video.srcObject = null;
      }}

      function tick() {{
        if(!scanning) return;
        if(video.readyState === video.HAVE_ENOUGH_DATA) {{
          canvas.width = video.videoWidth;
          canvas.height = video.videoHeight;
          ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
          const img = ctx.getImageData(0, 0, canvas.width, canvas.height);
          const code = jsQR(img.data, img.width, img.height);
          if(code && code.data) {{
            // our QR contains full URL .../user?code=XXXX or just text
            const txt = code.data;
            let extracted = txt;
            try {{
              const u = new URL(txt);
              const c = u.searchParams.get('code');
              if(c) extracted = c;
            }} catch(e) {{}}
            $code.value = extracted.replace(/\\D/g,'').slice(0, 20);
            lookup();
          }}
        }}
        requestAnimationFrame(tick);
      }}

      // auto lookup if prefilled
      if($code.value) lookup();
    </script>
    """


# ---------------- API: GET CARD ----------------
@app.route("/api/card/<number>")
def api_get_card(number):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT name, number, points FROM cards WHERE number=%s;", (number,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return jsonify(ok=False)

    name, number, points = row
    return jsonify(ok=True, card={"name": name, "number": number, "points": points})


# ---------------- API: ADD POINT (for scanner/camera) ----------------
@app.route("/api/add_point", methods=["POST"])
def api_add_point():
    data = request.get_json(silent=True) or {}
    number = str(data.get("number", "")).strip()

    if not number:
        return jsonify(ok=False, error="missing number"), 400

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("UPDATE cards SET points = points + 1 WHERE number=%s RETURNING name, number, points;", (number,))
    row = cur.fetchone()
    conn.commit()

    cur.close()
    conn.close()

    if not row:
        return jsonify(ok=False, error="card not found"), 404

    name, number, points = row
    return jsonify(ok=True, card={"name": name, "number": number, "points": points})


# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


if __name__ == "__main__":
    app.run()