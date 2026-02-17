from flask import Flask, request, redirect, url_for, render_template_string, jsonify, abort
import sqlite3
from datetime import datetime
import base64, io, secrets
import qrcode

APP_TITLE = "Points"
DB_FILE = "points.db"

# Адмін-ключ (змініть!)
ADMIN_KEY = "CHANGE_ME_12345"

# Публічна адреса для друку на картці (ссылка буде просто на сайт)
# Якщо сайт у інтернеті: "https://ваш-домен.com"
# Якщо поки локально: лишіть "" (буде брати з браузера)
PUBLIC_BASE_URL = ""

app = Flask(__name__)

# ---------- DB ----------
def db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cards (
            token TEXT PRIMARY KEY,
            owner TEXT NOT NULL,
            points INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT NOT NULL,
            delta INTEGER NOT NULL,
            ts TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def get_card(token: str):
    conn = db()
    row = conn.execute("SELECT * FROM cards WHERE token = ?", (token,)).fetchone()
    conn.close()
    return row

def list_cards():
    conn = db()
    rows = conn.execute("SELECT * FROM cards ORDER BY created_at DESC").fetchall()
    conn.close()
    return rows

def create_card(owner: str) -> str:
    # Це і є “номер картки” (те, що кодується в QR і що вводять користувачі)
    token = secrets.token_urlsafe(8)
    conn = db()
    conn.execute(
        "INSERT INTO cards(token, owner, points, created_at) VALUES(?,?,?,?)",
        (token, owner, 0, datetime.now().isoformat(timespec="seconds"))
    )
    conn.commit()
    conn.close()
    return token

def add_points(token: str, delta: int):
    conn = db()
    conn.execute("UPDATE cards SET points = points + ? WHERE token = ?", (delta, token))
    conn.execute(
        "INSERT INTO events(token, delta, ts) VALUES(?,?,?)",
        (token, delta, datetime.now().isoformat(timespec="seconds"))
    )
    conn.commit()
    conn.close()

def delete_card(token: str):
    conn = db()
    conn.execute("DELETE FROM events WHERE token = ?", (token,))
    conn.execute("DELETE FROM cards WHERE token = ?", (token,))
    conn.commit()
    conn.close()

# ---------- helpers ----------
def base_url():
    if PUBLIC_BASE_URL.strip():
        return PUBLIC_BASE_URL.strip().rstrip("/")
    return request.host_url.rstrip("/")

def make_qr_data_uri(text: str) -> str:
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=2)
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"

def require_admin():
    k = request.args.get("k") or request.headers.get("X-Admin-Key")
    if k != ADMIN_KEY:
        abort(401)

# ---------- UI ----------
ADMIN_HTML = """
<!doctype html>
<html lang="uk"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Адмін</title>
<style>
body{font-family:system-ui,Arial;margin:18px;max-width:1000px}
.row{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
a.btn,button{padding:10px 12px;border:1px solid #ccc;background:#f7f7f7;border-radius:10px;text-decoration:none;color:#111}
.card{border:1px solid #eee;border-radius:14px;padding:12px;margin-top:12px}
table{width:100%;border-collapse:collapse;margin-top:12px}
th,td{border-bottom:1px solid #eee;padding:10px;text-align:left;vertical-align:top}
input{padding:10px;border:1px solid #ccc;border-radius:10px}
.muted{color:#666}
.small{font-size:12px}
</style>
</head><body>
<h1>Адмін</h1>

<div class="row">
  <a class="btn" href="{{url_for('scan') + '?k=' + k}}">Сканувати</a>
  <a class="btn" href="{{url_for('public_login')}}">Публічний сайт</a>
</div>

<div class="card">
  <h3 style="margin:0 0 10px">Додати картку</h3>
  <form class="row" method="post" action="{{url_for('add_card') + '?k=' + k}}">
    <input name="owner" value="Тімур" required>
    <button type="submit">Додати картку</button>
  </form>
  <div class="muted small" style="margin-top:8px">
    Після створення відкриється сторінка картки з кнопкою «Друкувати».
  </div>
</div>

<h2 style="margin-top:16px">Картки</h2>
<table>
<thead><tr><th>Ім'я</th><th>Бали</th><th>Номер</th><th>Дії</th></tr></thead>
<tbody>
{% for c in cards %}
<tr>
  <td><b>{{c['owner']}}</b></td>
  <td>{{c['points']}}</td>
  <td style="font-family:ui-monospace,monospace">{{c['token']}}</td>
  <td class="row" style="gap:8px">
    <a class="btn" href="{{url_for('print_card', token=c['token']) + '?k=' + k}}">Друкувати</a>
    <a class="btn" href="{{url_for('user_points', token=c['token'])}}">Користувач</a>

    <!-- ✅ КНОПКА ВИДАЛИТИ -->
    <form method="post"
          action="{{ url_for('admin_delete_user', token=c['token']) }}?k={{k}}"
          style="display:inline;"
          onsubmit="return confirm('Точно видалити цього користувача?')">
      <button type="submit" class="btn" style="background:#ffe5e5;border-color:#f5b5b5">
        Видалити
      </button>
    </form>
  </td>
</tr>
{% endfor %}
</tbody>
</table>
</body></html>
"""

SCAN_HTML = """
<!doctype html>
<html lang="uk"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Сканування</title>
<style>
body{font-family:system-ui,Arial;margin:18px;max-width:900px}
a.btn,button{padding:10px 12px;border:1px solid #ccc;background:#f7f7f7;border-radius:10px;text-decoration:none;color:#111}
.box{border:2px dashed #bbb;border-radius:16px;padding:16px;margin-top:12px}
input{width:100%;font-size:18px;padding:14px;border-radius:14px;border:1px solid #ccc}
.muted{color:#666}
</style></head><body>
<a class="btn" href="{{url_for('admin') + '?k=' + k}}">← Адмін</a>

<h1>Сканувати</h1>
<div class="muted">Скануйте QR на картці. QR містить “номер картки” → +1 бал.</div>

<div class="box">
  <input id="code" placeholder="Скануйте QR..." autofocus>
  <div id="st" class="muted" style="margin-top:10px"></div>
</div>

<script>
const inp = document.getElementById('code');
const st = document.getElementById('st');

inp.addEventListener('keydown', async (e) => {
  if (e.key === 'Enter') {
    e.preventDefault();
    const token = inp.value.trim();
    inp.value = "";
    if (!token) return;

    const resp = await fetch("/api/admin/scan?k={{k}}", {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body: JSON.stringify({ token })
    });
    const data = await resp.json();
    st.textContent = resp.ok
      ? `✅ +1. Тепер у ${data.owner}: ${data.points}`
      : `❌ ${data.error || "помилка"}`;
    inp.focus();
  }
});
document.addEventListener('click', () => inp.focus());
</script>
</body></html>
"""

PRINT_HTML = """
<!doctype html>
<html lang="uk"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Друк</title>
<style>
.no-print{margin:18px}
a.btn,button{padding:10px 12px;border:1px solid #ccc;background:#f7f7f7;border-radius:10px;text-decoration:none;color:#111;font-family:system-ui,Arial}
.sheet{width:90mm;height:55mm;border:1px solid #ddd;border-radius:14px;padding:10mm;box-sizing:border-box}
.name{font-family:system-ui,Arial;font-size:22px;font-weight:900;letter-spacing:1px;text-transform:uppercase}
.small{font-family:system-ui,Arial;font-size:10px;color:#444;margin-top:6px;word-break:break-all}
.row{display:flex;gap:10mm;align-items:center;margin-top:8mm}
img{width:32mm;height:32mm}
.token{font-family:ui-monospace,monospace;font-size:12px;margin-top:6px}
@media print{ .no-print{display:none} body{margin:0} .sheet{border:none} }
</style></head><body>
<div class="no-print">
  <button onclick="window.print()">Друкувати</button>
  <a class="btn" href="{{url_for('admin') + '?k=' + k}}">Назад</a>
</div>

<div class="sheet">
  <div class="name">{{owner}}</div>

  <div class="row">
    <div>
      <!-- QR = номер картки (token), щоб сканер додавав бали -->
      <img src="{{qr}}" alt="QR">
      <div class="token">{{token}}</div>
    </div>
    <div style="flex:1">
      <div style="font-family:system-ui,Arial;font-size:12px;font-weight:800">Сайт:</div>
      <div class="small">{{site_url}}</div>
      <div class="small" style="margin-top:6px;"><b>Номер картки:</b> {{token}}</div>
    </div>
  </div>
</div>

<script>window.onload = () => window.print();</script>
</body></html>
"""

PUBLIC_LOGIN_HTML = """
<!doctype html>
<html lang="uk"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{title}}</title>
<style>
body{font-family:system-ui,Arial;margin:18px;max-width:700px}
.box{border:1px solid #eee;border-radius:16px;padding:14px;margin-top:12px}
h1{margin:0 0 8px}
input{width:100%;font-size:18px;padding:14px;border-radius:14px;border:1px solid #ccc;box-sizing:border-box}
button{padding:10px 12px;border:1px solid #ccc;background:#f7f7f7;border-radius:10px}
.muted{color:#666}
.row{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-top:10px}
#reader{margin-top:12px}
</style>
</head><body>
<h1>{{title}}</h1>
<div class="muted">Введіть номер картки або натисніть «Сканувати QR».</div>

<div class="box">
  <input id="token" placeholder="Номер картки (наприклад: AbC123...)" autocomplete="off">
  <div class="row">
    <button id="go">Показати бали</button>
    <button id="start">Сканувати QR</button>
    <button id="stop" style="display:none;">Зупинити</button>
  </div>
  <div id="msg" class="muted" style="margin-top:10px;"></div>
  <div id="reader"></div>
</div>

<script src="https://unpkg.com/html5-qrcode"></script>
<script>
const tokenEl = document.getElementById('token');
const msg = document.getElementById('msg');
const goBtn = document.getElementById('go');
const startBtn = document.getElementById('start');
const stopBtn = document.getElementById('stop');

function openPoints() {
  const t = tokenEl.value.trim();
  if (!t) { msg.textContent = "Введіть номер картки."; return; }
  window.location.href = "/u/" + encodeURIComponent(t);
}

goBtn.onclick = openPoints;
tokenEl.addEventListener('keydown', (e) => { if (e.key === 'Enter') openPoints(); });

let qr = null;

startBtn.onclick = async () => {
  msg.textContent = "Відкриваємо камеру…";
  startBtn.style.display = "none";
  stopBtn.style.display = "inline-block";

  qr = new Html5Qrcode("reader");
  try {
    await qr.start(
      { facingMode: "environment" },
      { fps: 10, qrbox: 220 },
      (decodedText) => {
        tokenEl.value = decodedText.trim();
        msg.textContent = "Зчитано. Відкриваємо бали…";
        stopScanner();
        openPoints();
      }
    );
    msg.textContent = "Наведіть камеру на QR на картці.";
  } catch (e) {
    msg.textContent = "Не вдалося відкрити камеру. Введіть номер вручну.";
    startBtn.style.display = "inline-block";
    stopBtn.style.display = "none";
  }
};

async function stopScanner() {
  if (qr) {
    try { await qr.stop(); } catch(e) {}
    try { await qr.clear(); } catch(e) {}
    qr = null;
  }
  stopBtn.style.display = "none";
  startBtn.style.display = "inline-block";
}

stopBtn.onclick = stopScanner;
</script>
</body></html>
"""

USER_POINTS_HTML = """
<!doctype html>
<html lang="uk"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Мої бали</title>
<style>
body{font-family:system-ui,Arial;margin:18px;max-width:700px}
.box{border:1px solid #eee;border-radius:16px;padding:14px;margin-top:12px}
.name{font-size:22px;font-weight:900}
.points{font-size:44px;font-weight:900;margin-top:8px}
.muted{color:#666}
a.btn{display:inline-block;padding:10px 12px;border:1px solid #ccc;background:#f7f7f7;border-radius:10px;text-decoration:none;color:#111;margin-top:12px}
</style></head><body>
<div class="box">
  <div class="name">{{owner}}</div>
  <div class="muted">Бали:</div>
  <div class="points">{{points}}</div>
  <div class="muted" style="margin-top:10px;font-family:ui-monospace,monospace">Номер картки: {{token}}</div>
</div>
<a class="btn" href="{{url_for('public_login')}}">← Назад</a>
</body></html>
"""

# ---------- Routes ----------
@app.route("/")
def public_login():
    return render_template_string(PUBLIC_LOGIN_HTML, title=APP_TITLE)

@app.route("/u/<token>")
def user_points(token):
    card = get_card(token)
    if not card:
        return "Картку не знайдено", 404
    return render_template_string(USER_POINTS_HTML, owner=card["owner"], points=card["points"], token=token)

@app.route("/admin")
def admin():
    require_admin()
    cards = list_cards()
    k = request.args.get("k") or ADMIN_KEY
    return render_template_string(ADMIN_HTML, cards=cards, k=k)

@app.route("/admin/add", methods=["POST"])
def add_card():
    require_admin()
    owner = (request.form.get("owner") or "Тімур").strip()
    token = create_card(owner)
    k = request.args.get("k") or ADMIN_KEY
    return redirect(url_for("print_card", token=token, k=k))

@app.route("/admin/scan")
def scan():
    require_admin()
    k = request.args.get("k") or ADMIN_KEY
    return render_template_string(SCAN_HTML, k=k)

@app.route("/admin/print/<token>")
def print_card(token):
    require_admin()
    card = get_card(token)
    if not card:
        return "Не знайдено", 404

    site_url = f"{base_url()}/"
    qr = make_qr_data_uri(token)

    k = request.args.get("k") or ADMIN_KEY
    return render_template_string(
        PRINT_HTML,
        owner=card["owner"],
        token=token,
        site_url=site_url,
        qr=qr,
        k=k
    )

# ✅ НОВЕ: видалити одного користувача
@app.route("/admin/delete/<token>", methods=["POST"])
def admin_delete_user(token):
    require_admin()
    delete_card(token)
    k = request.args.get("k") or ADMIN_KEY
    return redirect(url_for("admin", k=k))

@app.route("/api/admin/scan", methods=["POST"])
def api_admin_scan():
    require_admin()
    data = request.get_json(force=True, silent=True) or {}
    token = (data.get("token") or "").strip()
    if not token:
        return jsonify({"error": "token required"}), 400

    card = get_card(token)
    if not card:
        return jsonify({"error": "card not found"}), 404

    add_points(token, 1)
    card2 = get_card(token)
    return jsonify({"owner": card2["owner"], "points": card2["points"]})

if __name__ == "__main__":
    init_db()
    print("Public:", "http://127.0.0.1:5000/")
    print("Admin :", "http://127.0.0.1:5000/admin?k=" + ADMIN_KEY)
    app.run(host="127.0.0.1", port=5000, debug=False)
