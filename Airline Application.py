import os
import uuid
import hashlib
import json
from datetime import date, datetime, timedelta
from contextlib import contextmanager
from functools import wraps

try:
    import pymysql
    pymysql.install_as_MySQLdb()
except ImportError:
    pass
import MySQLdb
import MySQLdb.cursors
from flask import (
    Flask, request, redirect, url_for, flash, render_template_string, abort, session
)
from werkzeug.exceptions import HTTPException

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "airline_secret_key_2025")


# ---------------------------------------------------------------------------
# Database connection  ·  database name matches: airline_db (lowercase)
# ---------------------------------------------------------------------------
def get_conn():
    return MySQLdb.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        user=os.environ.get("DB_USER", "root"),
        password=os.environ.get("DB_PASSWORD", "admin123"),
        database=os.environ.get("DB_NAME", "airline_db"),
        cursorclass=MySQLdb.cursors.DictCursor,
        charset="utf8mb4",
    )


@contextmanager
def db_cursor(commit: bool = False):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            yield cur
            if commit:
                conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def gen_id(prefix: str, total_len: int) -> str:
    body_len = total_len - len(prefix)
    body = uuid.uuid4().hex.upper()[:body_len]
    return f"{prefix}{body}"


def hash_password(password: str) -> str:
    salt = os.urandom(16).hex()
    hashed = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}:{hashed}"


def verify_password(stored: str, provided: str) -> bool:
    try:
        salt, hashed = stored.split(":")
        return hashlib.sha256((salt + provided).encode()).hexdigest() == hashed
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------
def is_admin():
    return session.get("role") == "admin"


def assert_owns_booking(cur, booking_id):
    """Abort 403 if a non-admin tries to access another passenger's booking."""
    if is_admin():
        return
    cur.execute(
        "SELECT passenger_id FROM booking WHERE booking_id=%s", (booking_id,)
    )
    row = cur.fetchone()
    if not row:
        abort(404)
    if row["passenger_id"] != session.get("passenger_id"):
        abort(403)


def assert_owns_passenger(passenger_id):
    if is_admin():
        return
    if passenger_id != session.get("passenger_id"):
        abort(403)


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Bootstrap: create app_user table and default admin if needed
# ---------------------------------------------------------------------------
def ensure_admin_user():
    """
    The schema SQL has no app_user table, so we create it on first run.
    The admin account uses the PASSENGER table for real users; admin is stand-alone.
    """
    try:
        with db_cursor(commit=True) as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS app_user (
                    user_id      INT PRIMARY KEY AUTO_INCREMENT,
                    username     VARCHAR(80) UNIQUE NOT NULL,
                    password_hash VARCHAR(200) NOT NULL,
                    role         ENUM('admin','user') NOT NULL DEFAULT 'user',
                    passenger_id CHAR(8) DEFAULT NULL,
                    FOREIGN KEY (passenger_id) REFERENCES PASSENGER(passenger_id)
                )
            """)
            cur.execute("SELECT COUNT(*) AS c FROM app_user WHERE role='admin'")
            if cur.fetchone()["c"] == 0:
                cur.execute(
                    "INSERT INTO app_user (username, password_hash, role) VALUES (%s,%s,'admin')",
                    ("admin", hash_password("admin123")),
                )
    except Exception as exc:
        print(f"[warn] ensure_admin_user: {exc}")


# ---------------------------------------------------------------------------
# Layout (template)
# ---------------------------------------------------------------------------
BASE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ title }} · SkyWay</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #f5f1ea; --bg-2: #faf6ee; --surface: #ffffff;
      --ink: #0f172a; --ink-2: #334155; --muted: #6b7c93;
      --border: #ebe4d6; --primary: #ea580c; --primary-2: #c2410c;
      --primary-soft: #fff7ed; --teal: #0f766e; --teal-soft: #ccfbf1;
      --ok: #15803d; --ok-soft: #dcfce7;
      --warn: #b45309; --warn-soft: #fef3c7;
      --danger: #b91c1c; --danger-soft: #fee2e2;
      --info: #0369a1; --info-soft: #e0f2fe;
      --shadow: 0 2px 12px rgba(15,23,42,.06);
    }
    * { box-sizing: border-box; }
    body { margin:0; background:var(--bg); color:var(--ink);
           font-family:'Inter',-apple-system,system-ui,"Segoe UI",Roboto,sans-serif;
           -webkit-font-smoothing:antialiased; }
    header.app {
      background:linear-gradient(120deg,#0f172a 0%,#1e3a5f 55%,#0f766e 100%);
      color:#fff; padding:16px 36px;
      display:flex; align-items:center; justify-content:space-between; gap:16px;
      box-shadow:0 2px 18px rgba(15,23,42,.15); flex-wrap:wrap;
    }
    header.app .brand { display:flex; align-items:center; gap:10px;
                        font-weight:700; font-size:20px; letter-spacing:-.02em; }
    header.app .brand .logo { width:34px; height:34px; border-radius:9px;
      background:linear-gradient(135deg,#ea580c,#f59e0b);
      display:flex; align-items:center; justify-content:center; font-size:17px;
      box-shadow:0 4px 12px rgba(234,88,12,.4); }
    header.app nav { display:flex; gap:4px; flex-wrap:wrap; }
    header.app nav a { color:rgba(255,255,255,.78); text-decoration:none;
      padding:8px 14px; border-radius:8px; font-size:14px; font-weight:500;
      transition:all .15s; }
    header.app nav a:hover { color:#fff; background:rgba(255,255,255,.08); }
    header.app nav a.active { color:#fff; background:rgba(255,255,255,.18); }
    .user-chip { display:inline-flex; align-items:center; gap:10px;
                 margin-left:14px; padding:6px 12px; border-radius:999px;
                 background:rgba(255,255,255,.12); font-size:13px; }
    .user-chip .who { color:#fff; font-weight:600; }
    .user-chip .who em { color:#fdba74; font-style:normal; font-weight:500; }
    .user-chip .logout { color:rgba(255,255,255,.85); text-decoration:none;
                         font-size:12px; }
    .user-chip .logout:hover { color:#fff; }
    .auth-card { max-width:420px; margin:60px auto; }
    .auth-card h1 { text-align:center; margin-bottom:6px; }
    .auth-card .sub { text-align:center; color:var(--muted); margin-bottom:24px; font-size:14px; }
    .auth-card .btn { width:100%; padding:12px 18px; }
    .auth-card .alt { text-align:center; margin-top:18px; font-size:14px; color:var(--muted); }
    .auth-card .alt a { color:var(--primary); font-weight:600; text-decoration:none; }
    .subnav { background:#fff; border-bottom:1px solid var(--border);
              padding:10px 36px; display:flex; align-items:center; gap:4px;
              font-size:13px; flex-wrap:wrap; }
    .subnav .lbl { color:var(--muted); margin-right:6px; font-weight:600;
                   text-transform:uppercase; letter-spacing:.06em; font-size:11px; }
    .subnav a { color:var(--ink-2); text-decoration:none; padding:5px 12px;
                border-radius:6px; font-weight:500; }
    .subnav a:hover { background:var(--bg); color:var(--ink); }
    .subnav a.active { background:var(--primary-soft); color:var(--primary-2); }
    main { max-width:1180px; margin:28px auto; padding:0 24px 60px; }
    h1 { font-size:26px; font-weight:700; letter-spacing:-.02em; margin:0 0 16px; }
    h2 { font-size:18px; font-weight:600; margin:28px 0 14px; letter-spacing:-.01em; }
    .muted { color:var(--muted); }
    .topbar { display:flex; justify-content:space-between; align-items:center;
              margin-bottom:18px; gap:16px; flex-wrap:wrap; }
    .topbar h1 { margin:0; }
    .card { background:var(--surface); border-radius:16px; padding:24px;
            box-shadow:var(--shadow); border:1px solid var(--border); }
    .stats { display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr));
             gap:16px; margin-bottom:28px; }
    .stat { background:var(--surface); border:1px solid var(--border);
            border-radius:16px; padding:20px; box-shadow:var(--shadow);
            position:relative; overflow:hidden; }
    .stat .label { font-size:11px; color:var(--muted); text-transform:uppercase;
                   letter-spacing:.08em; font-weight:600; }
    .stat .value { font-size:30px; font-weight:700; margin-top:8px;
                   color:var(--ink); letter-spacing:-.02em; }
    .stat .icon { position:absolute; top:18px; right:18px; width:38px; height:38px;
                  border-radius:10px; background:var(--primary-soft); color:var(--primary-2);
                  display:flex; align-items:center; justify-content:center;
                  font-size:18px; font-weight:700; }
    .stat.teal .icon { background:var(--teal-soft); color:var(--teal); }
    .stat.ok   .icon { background:var(--ok-soft);   color:var(--ok); }
    .stat.warn .icon { background:var(--warn-soft); color:var(--warn); }
    table { width:100%; border-collapse:separate; border-spacing:0;
            background:var(--surface); border-radius:14px; overflow:hidden;
            box-shadow:var(--shadow); border:1px solid var(--border); font-size:14px; }
    th, td { padding:14px 18px; text-align:left; }
    th { background:var(--bg-2); font-size:11px; font-weight:600;
         text-transform:uppercase; letter-spacing:.06em; color:var(--muted);
         border-bottom:1px solid var(--border); }
    tbody tr:not(:last-child) td { border-bottom:1px solid var(--border); }
    tbody tr:hover { background:#fcfaf5; }
    .badge { display:inline-block; padding:4px 11px; border-radius:999px;
             font-size:11px; font-weight:600; letter-spacing:.02em; }
    .b-Scheduled, .b-Confirmed, .b-Issued, .b-Completed, .b-Loaded, .b-Arrived
        { background:var(--ok-soft); color:var(--ok); }
    .b-Pending, .b-Boarding, .b-Checked-In, .b-Not-Issued, .b-In-Transit, .b-Delayed
        { background:var(--warn-soft); color:var(--warn); }
    .b-Cancelled, .b-Failed, .b-Expired, .b-Lost
        { background:var(--danger-soft); color:var(--danger); }
    .b-Refunded, .b-Used, .b-Departed
        { background:var(--info-soft); color:var(--info); }
    .btn { display:inline-block; padding:10px 18px; border-radius:10px;
           background:var(--primary); color:#fff; text-decoration:none;
           font-size:14px; border:0; cursor:pointer; font-weight:600;
           font-family:inherit; transition:all .15s;
           box-shadow:0 1px 2px rgba(0,0,0,.05); }
    .btn:hover { background:var(--primary-2); transform:translateY(-1px);
                 box-shadow:0 4px 12px rgba(234,88,12,.28); }
    .btn.secondary { background:#fff; color:var(--teal); border:1.5px solid var(--teal); }
    .btn.secondary:hover { background:var(--teal-soft); transform:none; box-shadow:none; }
    .btn.danger { background:var(--danger); }
    .btn.danger:hover { background:#991b1b; box-shadow:0 4px 12px rgba(185,28,28,.28); }
    .btn.small { padding:6px 12px; font-size:12px; border-radius:8px; }
    .btn.ghost { background:transparent; color:var(--ink-2); border:1px solid var(--border); }
    .btn.ghost:hover { background:var(--bg-2); transform:none; box-shadow:none; }
    form.inline { display:inline-block; margin:0; }
    .form-grid { display:grid; gap:16px;
                 grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); }
    label { display:block; font-size:11px; font-weight:600; color:var(--ink-2);
            margin-bottom:6px; text-transform:uppercase; letter-spacing:.06em; }
    input, select, textarea { width:100%; padding:11px 13px;
      border:1.5px solid var(--border); border-radius:10px; background:#fff;
      font-size:14px; font-family:inherit; color:var(--ink);
      transition:border-color .15s; }
    input:focus, select:focus, textarea:focus { outline:none;
      border-color:var(--primary); box-shadow:0 0 0 3px rgba(234,88,12,.12); }
    .flash { padding:14px 18px; border-radius:12px; margin-bottom:14px;
             font-size:14px; border-left:4px solid; font-weight:500; }
    .flash.success { background:var(--ok-soft);     border-color:var(--ok);     color:var(--ok); }
    .flash.danger  { background:var(--danger-soft); border-color:var(--danger); color:var(--danger); }
    .flash.warning { background:var(--warn-soft);   border-color:var(--warn);   color:var(--warn); }
    .flash.info    { background:var(--info-soft);   border-color:var(--info);   color:var(--info); }
    .pill { background:var(--primary-soft); color:var(--primary-2);
            padding:3px 10px; border-radius:999px; font-size:12px; font-weight:600; }
    code { background:var(--bg-2); padding:2px 7px; border-radius:5px;
           font-size:12px; font-family:'SF Mono',Menlo,monospace; color:var(--ink-2); }
    a.link { color:var(--primary); text-decoration:none; font-weight:500; }
    a.link:hover { text-decoration:underline; }
    .label.muted { color:var(--muted); font-size:11px; text-transform:uppercase;
                   letter-spacing:.06em; font-weight:600; margin-bottom:4px; }
    .hero { background:linear-gradient(120deg,#0f172a 0%,#1e3a5f 50%,#0f766e 100%);
            border-radius:20px; padding:44px 40px; color:#fff;
            margin-bottom:28px; position:relative; overflow:hidden;
            box-shadow:0 10px 32px rgba(15,23,42,.18); }
    .hero::before { content:""; position:absolute; right:-60px; top:-40px;
      width:280px; height:280px; border-radius:50%;
      background:radial-gradient(circle,rgba(234,88,12,.4),transparent 70%);
      pointer-events:none; }
    .hero h1 { font-size:34px; font-weight:700; margin:0 0 8px;
               letter-spacing:-.02em; color:#fff; }
    .hero .sub { color:rgba(255,255,255,.78); font-size:16px;
                 margin-bottom:24px; max-width:580px; }
    .hero .search-card { background:#fff; border-radius:14px; padding:20px;
      box-shadow:0 12px 30px rgba(0,0,0,.18); position:relative; z-index:1; }
    .hero .search-card .form-grid { gap:12px; }
    .hero .search-card .btn { width:100%; padding:12px 18px; }
    .quick-actions { display:grid; gap:14px; margin-bottom:28px;
                     grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); }
    .quick { background:#fff; border:1px solid var(--border); border-radius:14px;
             padding:18px; text-decoration:none; color:var(--ink);
             transition:all .15s; box-shadow:var(--shadow); display:block; }
    .quick:hover { transform:translateY(-2px); border-color:var(--primary);
                   box-shadow:0 6px 18px rgba(234,88,12,.15); }
    .quick .qicon { width:42px; height:42px; border-radius:10px;
      background:var(--primary-soft); color:var(--primary-2);
      display:flex; align-items:center; justify-content:center;
      font-size:20px; margin-bottom:12px; font-weight:700; }
    .quick .qtitle { font-weight:600; font-size:15px; }
    .quick .qsub { color:var(--muted); font-size:12px; margin-top:2px; }
    @media (max-width:720px) {
      header.app { padding:14px 20px; }
      .subnav { padding:10px 20px; overflow-x:auto; }
      main { padding:0 16px 40px; }
      .hero { padding:32px 24px; }
      .hero h1 { font-size:26px; }
    }
  </style>
</head>
<body>
  <header class="app">
    <div class="brand">
      <div class="logo">✈</div>
      <span>SkyWay</span>
    </div>
    {% set p = active or '' %}
    {% if user %}
    <nav>
      <a class="{% if p=='dashboard' %}active{% endif %}" href="{{ url_for('dashboard') }}">Home</a>
      <a class="{% if p=='flights'   %}active{% endif %}" href="{{ url_for('flights') }}">Search Flights</a>
      <a class="{% if p=='bookings'  %}active{% endif %}" href="{{ url_for('bookings') }}">My Bookings</a>
      {% if user.role == 'admin' %}
        <a class="{% if p=='passengers'%}active{% endif %}" href="{{ url_for('passengers') }}">Travelers</a>
      {% else %}
        <a class="{% if p=='passengers'%}active{% endif %}"
           href="{{ url_for('passenger_detail', passenger_id=user.passenger_id) }}">My Profile</a>
      {% endif %}
      <a class="{% if p=='checkin'      %}active{% endif %}" href="{{ url_for('checkin_list') }}">Check-In</a>
      <a class="{% if p=='notifications'%}active{% endif %}" href="{{ url_for('notifications') }}">Notifications</a>
      <span class="user-chip">
        <span class="who">{{ user.username }}{% if user.role=='admin' %} <em>· admin</em>{% endif %}</span>
        <a class="logout" href="{{ url_for('logout') }}">Sign out</a>
      </span>
    </nav>
    {% else %}
    <nav>
      <a href="{{ url_for('login') }}">Sign in</a>
      <a href="{{ url_for('register') }}">Create account</a>
    </nav>
    {% endif %}
  </header>
  {% if user and user.role == 'admin' %}
  <div class="subnav">
    <span class="lbl">Operations</span>
    <a class="{% if p=='payments' %}active{% endif %}" href="{{ url_for('payments') }}">Payments</a>
    <a class="{% if p=='baggage'  %}active{% endif %}" href="{{ url_for('baggage') }}">Baggage</a>
    <a class="{% if p=='crew'     %}active{% endif %}" href="{{ url_for('crew') }}">Crew</a>
    <a class="{% if p=='airports' %}active{% endif %}" href="{{ url_for('airports') }}">Airports & Routes</a>
  </div>
  {% endif %}
  <main>
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% for category, message in messages %}
        <div class="flash {{ category }}">{{ message }}</div>
      {% endfor %}
    {% endwith %}
    {{ body|safe }}
  </main>
</body>
</html>
"""


def render(title, body, active=""):
    user = None
    if session.get("user_id"):
        user = {
            "username":     session.get("username"),
            "role":         session.get("role"),
            "passenger_id": session.get("passenger_id"),
        }
    return render_template_string(BASE, title=title, body=body, active=active, user=user)


def badge(value):
    cls = (value or "").replace(" ", "-")
    return f'<span class="badge b-{cls}">{value}</span>'


# ---------------------------------------------------------------------------
# Authentication: login / register / logout
# ---------------------------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        with db_cursor() as cur:
            cur.execute("SELECT * FROM app_user WHERE username=%s", (username,))
            u = cur.fetchone()
        if u and verify_password(u["password_hash"], password):
            session.clear()
            session["user_id"]      = u["user_id"]
            session["username"]     = u["username"]
            session["role"]         = u["role"]
            session["passenger_id"] = u["passenger_id"]
            flash(f"Welcome back, {u['username']}.", "success")
            nxt = request.args.get("next") or ""
            if nxt and nxt.startswith("/") and not nxt.startswith("//") and not nxt.startswith("/\\"):
                return redirect(nxt)
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "danger")

    body = f"""
    <div class="card auth-card">
      <h1>Sign in to SkyWay</h1>
      <div class="sub">Manage your bookings, check in online, and track every flight.</div>
      <form method="post">
        <div style="margin-bottom:14px">
          <label>Username</label>
          <input name="username" autofocus required></div>
        <div style="margin-bottom:18px">
          <label>Password</label>
          <input name="password" type="password" required></div>
        <button class="btn" type="submit">Sign in</button>
      </form>
      <div class="alt">
        New here? <a href="{url_for('register')}">Create an account</a><br>
        <span class="muted" style="font-size:12px">
          Admin demo: <code>admin</code> / <code>admin123</code></span>
      </div>
    </div>
    """
    return render("Sign in", body)


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm  = request.form.get("confirm", "")
        name     = request.form.get("name", "").strip()
        passport = request.form.get("passport_no", "").strip()
        dob      = request.form.get("dob", "").strip()

        errors = []
        if not (username and password and name and passport and dob):
            errors.append("All fields are required.")
        if password and len(password) < 6:
            errors.append("Password must be at least 6 characters.")
        if password != confirm:
            errors.append("Passwords do not match.")

        if not errors:
            try:
                with db_cursor(commit=True) as cur:
                    cur.execute("SELECT 1 FROM app_user WHERE username=%s", (username,))
                    if cur.fetchone():
                        raise ValueError("That username is already taken.")
                    pid = gen_id("PSG", 8)
                    # PASSENGER schema: passenger_id CHAR(8), name VARCHAR(100), passport_no VARCHAR(20), dob DATE
                    cur.execute(
                        "INSERT INTO passenger (passenger_id, name, passport_no, dob) VALUES (%s,%s,%s,%s)",
                        (pid, name, passport, dob),
                    )
                    cur.execute(
                        "INSERT INTO app_user (username, password_hash, role, passenger_id) VALUES (%s,%s,'user',%s)",
                        (username, hash_password(password), pid),
                    )
                    cur.execute("SELECT LAST_INSERT_ID() AS uid")
                    new_id = cur.fetchone()["uid"]
                session.clear()
                session["user_id"]      = new_id
                session["username"]     = username
                session["role"]         = "user"
                session["passenger_id"] = pid
                flash(f"Welcome aboard, {name}!", "success")
                return redirect(url_for("dashboard"))
            except Exception as e:
                errors.append(str(e))

        for err in errors:
            flash(err, "danger")

    today = date.today().isoformat()
    f = request.form
    body = f"""
    <div class="card auth-card" style="max-width:560px">
      <h1>Create your account</h1>
      <div class="sub">Just a few details and you're ready to fly.</div>
      <form method="post">
        <h2 style="font-size:14px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:0 0 12px">Account</h2>
        <div class="form-grid" style="margin-bottom:14px">
          <div><label>Username *</label>
            <input name="username" value="{f.get('username','')}" required></div>
          <div><label>Password *</label>
            <input name="password" type="password" minlength="6" required></div>
          <div><label>Confirm password *</label>
            <input name="confirm" type="password" minlength="6" required></div>
        </div>
        <h2 style="font-size:14px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:18px 0 12px">Traveler details</h2>
        <div class="form-grid" style="margin-bottom:18px">
          <div><label>Full name *</label>
            <input name="name" value="{f.get('name','')}" required></div>
          <div><label>Passport no. *</label>
            <input name="passport_no" value="{f.get('passport_no','')}" required></div>
          <div><label>Date of birth *</label>
            <input name="dob" type="date" max="{today}"
                   value="{f.get('dob','')}" required></div>
        </div>
        <button class="btn" type="submit">Create account</button>
      </form>
      <div class="alt">
        Already a member? <a href="{url_for('login')}">Sign in</a>
      </div>
    </div>
    """
    return render("Create account", body)


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
@app.route("/")
@login_required
def dashboard():
    admin = is_admin()
    pid   = session.get("passenger_id")
    with db_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS c FROM flight WHERE status='Scheduled'")
        scheduled = cur.fetchone()["c"]
        if admin:
            cur.execute("SELECT COUNT(*) AS c FROM booking")
            confirmed = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(*) AS c FROM passenger")
            passengers_n = cur.fetchone()["c"]
            cur.execute("SELECT COALESCE(SUM(amount),0) AS t FROM payment WHERE status='Completed'")
            revenue = cur.fetchone()["t"]
        else:
            cur.execute("SELECT COUNT(*) AS c FROM booking WHERE passenger_id=%s", (pid,))
            confirmed = cur.fetchone()["c"]
            passengers_n = confirmed
            cur.execute(
                """SELECT COALESCE(SUM(pay.amount),0) AS t
                   FROM payment pay
                   JOIN booking b ON b.booking_id = pay.booking_id
                   WHERE b.passenger_id=%s AND pay.status='Completed'""",
                (pid,),
            )
            revenue = cur.fetchone()["t"]

        # Airport list: JOIN city for city name
        cur.execute("""
            SELECT a.iata_code, ci.city_name AS city
            FROM airport a
            JOIN city ci ON ci.city_id = a.city_id
            ORDER BY a.iata_code
        """)
        airports_list = cur.fetchall()

        # Upcoming flights: JOIN city table for city names
        cur.execute("""
            SELECT f.flight_id, al.name AS airline,
                   ap1.iata_code AS from_code, ci1.city_name AS from_city,
                   ap2.iata_code AS to_code,   ci2.city_name AS to_city,
                   f.departure_time, f.status
            FROM flight f
            JOIN airline al   ON al.airline_id  = f.airline_id
            JOIN route   r    ON r.route_id     = f.route_id
            JOIN airport ap1  ON ap1.airport_id = r.departure_airport
            JOIN city    ci1  ON ci1.city_id    = ap1.city_id
            JOIN airport ap2  ON ap2.airport_id = r.arrival_airport
            JOIN city    ci2  ON ci2.city_id    = ap2.city_id
            ORDER BY f.departure_time
            LIMIT 6
        """)
        upcoming = cur.fetchall()

        rb_where, rb_params = "", ()
        if not admin:
            rb_where   = "WHERE b.passenger_id = %s"
            rb_params  = (pid,)
        cur.execute(f"""
            SELECT b.booking_id, p.name,
                   ap1.iata_code AS from_code, ap2.iata_code AS to_code
            FROM booking b
            JOIN passenger p  ON p.passenger_id  = b.passenger_id
            JOIN flight    f  ON f.flight_id      = b.flight_id
            JOIN route     r  ON r.route_id       = f.route_id
            JOIN airport  ap1 ON ap1.airport_id   = r.departure_airport
            JOIN airport  ap2 ON ap2.airport_id   = r.arrival_airport
            {rb_where}
            ORDER BY b.booking_id DESC
            LIMIT 5
        """, rb_params)
        recent_bookings = cur.fetchall()

    air_opts = "".join(
        f'<option value="{a["iata_code"]}">{a["iata_code"]} — {a["city"]}</option>'
        for a in airports_list
    )

    body = f"""
    <div class="hero">
      <h1>Where would you like to fly?</h1>
      <div class="sub">Search across {len(airports_list)} airports and book your seat in seconds.</div>
      <form method="get" action="{url_for('flights')}" class="search-card">
        <div class="form-grid">
          <div><label>From</label>
            <select name="from"><option value="">Any airport</option>{air_opts}</select></div>
          <div><label>To</label>
            <select name="to"><option value="">Any airport</option>{air_opts}</select></div>
          <div><label>Departure date</label>
            <input type="date" name="date"></div>
          <div style="display:flex;align-items:flex-end">
            <button class="btn" type="submit">Search flights</button></div>
        </div>
      </form>
    </div>

    <div class="quick-actions">
      <a class="quick" href="{url_for('bookings')}">
        <div class="qicon">📋</div>
        <div class="qtitle">My Bookings</div>
        <div class="qsub">View, modify, or cancel</div></a>
      <a class="quick" href="{url_for('checkin_list')}">
        <div class="qicon">✓</div>
        <div class="qtitle">Online Check-In</div>
        <div class="qsub">Get your boarding pass</div></a>
      {(
          f'<a class="quick" href="{url_for("passengers")}">'
          f'<div class="qicon">👤</div><div class="qtitle">Travelers</div>'
          f'<div class="qsub">Manage profiles</div></a>'
        ) if admin else (
          f'<a class="quick" href="{url_for("passenger_detail", passenger_id=pid)}">'
          f'<div class="qicon">👤</div><div class="qtitle">My Profile</div>'
          f'<div class="qsub">Personal details</div></a>'
        ) if pid else ""}
      <a class="quick" href="{url_for('notifications')}">
        <div class="qicon">🔔</div>
        <div class="qtitle">Notifications</div>
        <div class="qsub">Updates & alerts</div></a>
    </div>

    <div class="stats">
      <div class="stat">
        <div class="icon">✈</div>
        <div class="label">Scheduled flights</div>
        <div class="value">{scheduled}</div></div>
      <div class="stat ok">
        <div class="icon">✓</div>
        <div class="label">{'Total bookings' if admin else 'My bookings'}</div>
        <div class="value">{confirmed}</div></div>
      <div class="stat teal">
        <div class="icon">👥</div>
        <div class="label">{'Travelers' if admin else 'My total bookings'}</div>
        <div class="value">{passengers_n}</div></div>
      <div class="stat warn">
        <div class="icon">$</div>
        <div class="label">{'Revenue (PKR)' if admin else 'Spent (PKR)'}</div>
        <div class="value">{revenue:,.0f}</div></div>
    </div>

    <h2>Upcoming flights</h2>
    <table>
      <thead><tr><th>Flight</th><th>Airline</th><th>From</th><th>To</th>
                 <th>Departure</th><th>Status</th><th></th></tr></thead>
      <tbody>
    """
    for fl in upcoming:
        body += (
            f"<tr><td><code>{fl['flight_id']}</code></td>"
            f"<td>{fl['airline']}</td>"
            f"<td><strong>{fl['from_code']}</strong> {fl['from_city']}</td>"
            f"<td><strong>{fl['to_code']}</strong> {fl['to_city']}</td>"
            f"<td>{fl['departure_time'].strftime('%a %d %b · %H:%M')}</td>"
            f"<td>{badge(fl['status'])}</td>"
            f"<td><a class='link' href='{url_for('flight_detail', flight_id=fl['flight_id'])}'>View →</a></td></tr>"
        )
    body += "</tbody></table>"

    body += (
        f"<h2>{'Recent bookings' if admin else 'My recent bookings'}</h2>"
        "<table><thead><tr><th>Booking</th><th>Traveler</th>"
        "<th>Route</th></tr></thead><tbody>"
    )
    if not recent_bookings:
        body += (
            f"<tr><td colspan='3' style='text-align:center;color:var(--muted);padding:24px'>"
            f"No bookings yet — <a class='link' href='{url_for('flights')}'>search flights</a> to get started.</td></tr>"
        )
    for b in recent_bookings:
        body += (
            f"<tr><td><a class='link' href='"
            f"{url_for('booking_detail', booking_id=b['booking_id'])}'>"
            f"<code>{b['booking_id']}</code></a></td>"
            f"<td>{b['name']}</td>"
            f"<td>{b['from_code']} → {b['to_code']}</td></tr>"
        )
    body += "</tbody></table>"
    return render("Home", body, active="dashboard")


# ---------------------------------------------------------------------------
# Flights
# ---------------------------------------------------------------------------
@app.route("/flights")
@login_required
def flights():
    src    = (request.args.get("from") or "").strip().upper()
    dst    = (request.args.get("to")   or "").strip().upper()
    date_q = (request.args.get("date") or "").strip()

    conds, params = [], []
    if src:
        conds.append("ap1.iata_code = %s"); params.append(src)
    if dst:
        conds.append("ap2.iata_code = %s"); params.append(dst)
    if date_q:
        conds.append("DATE(f.departure_time) = %s"); params.append(date_q)
    where_sql = ("WHERE " + " AND ".join(conds)) if conds else ""

    with db_cursor() as cur:
        cur.execute("""
            SELECT a.iata_code, ci.city_name AS city
            FROM airport a
            JOIN city ci ON ci.city_id = a.city_id
            ORDER BY a.iata_code
        """)
        airports_list = cur.fetchall()
        cur.execute(f"""
            SELECT f.flight_id, al.name AS airline,
                   ap1.iata_code AS from_code, ci1.city_name AS from_city,
                   ap2.iata_code AS to_code,   ci2.city_name AS to_city,
                   f.departure_time, f.arrival_time, f.status,
                   am.model_name AS aircraft, am.total_seats,
                   (SELECT COUNT(*) FROM booking b WHERE b.flight_id = f.flight_id) AS booked
            FROM flight f
            JOIN airline        al  ON al.airline_id  = f.airline_id
            JOIN route          r   ON r.route_id     = f.route_id
            JOIN airport        ap1 ON ap1.airport_id = r.departure_airport
            JOIN city           ci1 ON ci1.city_id    = ap1.city_id
            JOIN airport        ap2 ON ap2.airport_id = r.arrival_airport
            JOIN city           ci2 ON ci2.city_id    = ap2.city_id
            JOIN aircraft       ac  ON ac.aircraft_id = f.aircraft_id
            JOIN aircraft_model am  ON am.model_id    = ac.model_id
            {where_sql}
            ORDER BY f.departure_time
        """, params)
        rows = cur.fetchall()

    from_opts = "".join(
        f'<option value="{a["iata_code"]}" {"selected" if a["iata_code"]==src else ""}>'
        f'{a["iata_code"]} — {a["city"]}</option>'
        for a in airports_list
    )
    to_opts = "".join(
        f'<option value="{a["iata_code"]}" {"selected" if a["iata_code"]==dst else ""}>'
        f'{a["iata_code"]} — {a["city"]}</option>'
        for a in airports_list
    )

    body = f"""
    <div class="topbar"><h1>Search flights</h1></div>
    <form method="get" class="card" style="margin-bottom:18px">
      <div class="form-grid">
        <div><label>From</label>
          <select name="from"><option value="">Any airport</option>{from_opts}</select></div>
        <div><label>To</label>
          <select name="to"><option value="">Any airport</option>{to_opts}</select></div>
        <div><label>Date</label>
          <input type="date" name="date" value="{date_q}"></div>
      </div>
      <div style="margin-top:14px">
        <button class="btn" type="submit">Search flights</button>
        <a class="btn secondary" href="{url_for('flights')}">Reset</a>
      </div>
    </form>

    <h2 style="margin-top:24px">Available flights ({len(rows)})</h2>
    <table>
      <thead><tr><th>Flight</th><th>Airline</th><th>Aircraft</th><th>From</th><th>To</th>
                 <th>Departure</th><th>Arrival</th><th>Seats</th><th>Status</th><th></th></tr></thead>
      <tbody>
    """
    if not rows:
        body += "<tr><td colspan='10' class='muted'>No flights match your search.</td></tr>"
    for fl in rows:
        avail = max(0, fl["total_seats"] - fl["booked"])
        book_link = ""
        if fl["status"] in ("Scheduled", "Delayed") and avail > 0:
            book_link = (
                f" · <a class='link' href='"
                f"{url_for('new_booking')}?flight_id={fl['flight_id']}'>book</a>"
            )
        body += (
            f"<tr><td><code>{fl['flight_id']}</code></td>"
            f"<td>{fl['airline']}</td>"
            f"<td>{fl['aircraft']}</td>"
            f"<td>{fl['from_code']} ({fl['from_city']})</td>"
            f"<td>{fl['to_code']} ({fl['to_city']})</td>"
            f"<td>{fl['departure_time'].strftime('%Y-%m-%d %H:%M')}</td>"
            f"<td>{fl['arrival_time'].strftime('%Y-%m-%d %H:%M')}</td>"
            f"<td>{avail} / {fl['total_seats']}</td>"
            f"<td>{badge(fl['status'])}</td>"
            f"<td><a class='link' href='{url_for('flight_detail', flight_id=fl['flight_id'])}'>view</a>"
            f"{book_link}</td></tr>"
        )
    body += "</tbody></table>"
    return render("Flights", body, active="flights")


@app.route("/flights/<flight_id>")
@login_required
def flight_detail(flight_id):
    with db_cursor() as cur:
        cur.execute("""
            SELECT f.*, al.name AS airline,
                   ap1.name AS from_airport, ci1.city_name AS from_city, ap1.iata_code AS from_code,
                   ap2.name AS to_airport,   ci2.city_name AS to_city,   ap2.iata_code AS to_code,
                   am.model_name AS aircraft, am.total_seats, r.distance AS distance_km
            FROM flight f
            JOIN airline        al  ON al.airline_id  = f.airline_id
            JOIN route          r   ON r.route_id     = f.route_id
            JOIN airport        ap1 ON ap1.airport_id = r.departure_airport
            JOIN city           ci1 ON ci1.city_id    = ap1.city_id
            JOIN airport        ap2 ON ap2.airport_id = r.arrival_airport
            JOIN city           ci2 ON ci2.city_id    = ap2.city_id
            JOIN aircraft       ac  ON ac.aircraft_id = f.aircraft_id
            JOIN aircraft_model am  ON am.model_id    = ac.model_id
            WHERE f.flight_id = %s
        """, (flight_id,))
        flight = cur.fetchone()
        if not flight:
            abort(404)

        cur.execute("""
            SELECT c.crew_id, c.name, fc.role
            FROM flight_crew fc
            JOIN crew c ON c.crew_id = fc.crew_id
            WHERE fc.flight_id = %s
            ORDER BY fc.role
        """, (flight_id,))
        crew_rows = cur.fetchall()

        cur.execute("""
            SELECT b.booking_id, p.name,
                   s.seat_number, sc.class_name AS seat_class
            FROM booking b
            JOIN passenger  p  ON p.passenger_id = b.passenger_id
            JOIN seat       s  ON s.seat_id      = b.seat_id
            JOIN seat_class sc ON sc.class_id    = s.class_id
            WHERE b.flight_id = %s
            ORDER BY s.seat_number
        """, (flight_id,))
        booking_rows = cur.fetchall()

    body = f"""
    <p><a class="link" href="{url_for('flights')}">&larr; All flights</a></p>
    <h1>Flight {flight['flight_id']} {badge(flight['status'])}</h1>
    <div class="card">
      <div class="form-grid">
        <div><div class="label muted">Airline</div><strong>{flight['airline']}</strong></div>
        <div><div class="label muted">Aircraft</div><strong>{flight['aircraft']}</strong> ({flight['total_seats']} seats)</div>
        <div><div class="label muted">From</div><strong>{flight['from_code']}</strong> — {flight['from_airport']}, {flight['from_city']}</div>
        <div><div class="label muted">To</div><strong>{flight['to_code']}</strong> — {flight['to_airport']}, {flight['to_city']}</div>
        <div><div class="label muted">Departure</div>{flight['departure_time'].strftime('%Y-%m-%d %H:%M')}</div>
        <div><div class="label muted">Arrival</div>{flight['arrival_time'].strftime('%Y-%m-%d %H:%M')}</div>
        <div><div class="label muted">Distance</div>{flight['distance_km']} km</div>
      </div>
    </div>

    <h2>Crew ({len(crew_rows)})</h2>
    <table><thead><tr><th>ID</th><th>Name</th><th>Role</th></tr></thead><tbody>
    """
    for c in crew_rows:
        body += f"<tr><td><code>{c['crew_id']}</code></td><td>{c['name']}</td><td>{c['role']}</td></tr>"
    if not crew_rows:
        body += "<tr><td colspan='3' class='muted'>No crew assigned.</td></tr>"
    body += "</tbody></table>"

    body += f"<h2>Bookings ({len(booking_rows)})</h2><table><thead><tr><th>Booking</th><th>Passenger</th><th>Seat</th><th>Class</th></tr></thead><tbody>"
    for b in booking_rows:
        body += (
            f"<tr><td><code>{b['booking_id']}</code></td>"
            f"<td>{b['name']}</td>"
            f"<td>{b['seat_number']}</td><td>{b['seat_class']}</td></tr>"
        )
    if not booking_rows:
        body += "<tr><td colspan='4' class='muted'>No bookings yet.</td></tr>"
    body += "</tbody></table>"
    return render(f"Flight {flight_id}", body, active="flights")


# ---------------------------------------------------------------------------
# Passengers
# ---------------------------------------------------------------------------
@app.route("/passengers")
@login_required
def passengers():
    if not is_admin():
        abort(403)
    with db_cursor() as cur:
        cur.execute("""
            SELECT p.passenger_id, p.name, p.passport_no, p.dob,
                   COUNT(b.booking_id) AS booking_count
            FROM passenger p
            LEFT JOIN booking b ON b.passenger_id = p.passenger_id
            GROUP BY p.passenger_id, p.name, p.passport_no, p.dob
            ORDER BY p.name
        """)
        rows = cur.fetchall()

    body = f"""
    <div class="topbar"><h1>Passengers</h1>
      <a class="btn" href="{url_for('new_passenger')}">+ New passenger</a></div>
    <table><thead><tr><th>ID</th><th>Name</th><th>Passport</th><th>DOB</th><th>Bookings</th><th></th></tr></thead><tbody>
    """
    for p in rows:
        body += (
            f"<tr><td><code>{p['passenger_id']}</code></td>"
            f"<td>{p['name']}</td><td>{p['passport_no']}</td>"
            f"<td>{p['dob']}</td>"
            f"<td><span class='pill'>{p['booking_count']}</span></td>"
            f"<td><a class='link' href='{url_for('passenger_detail', passenger_id=p['passenger_id'])}'>View</a></td></tr>"
        )
    body += "</tbody></table>"
    return render("Passengers", body, active="passengers")


@app.route("/passengers/new", methods=["GET", "POST"])
@login_required
def new_passenger():
    if not is_admin():
        abort(403)
    if request.method == "POST":
        name     = request.form.get("name", "").strip()
        passport = request.form.get("passport_no", "").strip()
        dob      = request.form.get("dob", "").strip()

        if not (name and passport and dob):
            flash("Name, passport, and date of birth are required.", "danger")
        else:
            try:
                pid = gen_id("PSG", 8)
                with db_cursor(commit=True) as cur:
                    cur.execute(
                        "INSERT INTO passenger (passenger_id, name, passport_no, dob) VALUES (%s,%s,%s,%s)",
                        (pid, name, passport, dob),
                    )
                flash(f"Passenger {pid} added.", "success")
                return redirect(url_for("passengers"))
            except Exception as e:
                flash(f"Error: {e}", "danger")

    body = f"""
    <p><a class="link" href="{url_for('passengers')}">&larr; Passengers</a></p>
    <h1>New passenger</h1>
    <form method="post" class="card">
      <div class="form-grid">
        <div><label>Full name *</label><input name="name" required></div>
        <div><label>Passport no. *</label><input name="passport_no" required></div>
        <div><label>Date of birth *</label><input type="date" name="dob" required max="{date.today().isoformat()}"></div>
      </div>
      <div style="margin-top:16px"><button class="btn" type="submit">Save passenger</button>
        <a class="btn secondary" href="{url_for('passengers')}">Cancel</a></div>
    </form>
    """
    return render("New passenger", body, active="passengers")


@app.route("/passengers/<passenger_id>")
@login_required
def passenger_detail(passenger_id):
    assert_owns_passenger(passenger_id)
    with db_cursor() as cur:
        cur.execute("SELECT * FROM passenger WHERE passenger_id=%s", (passenger_id,))
        p = cur.fetchone()
        if not p:
            abort(404)
        cur.execute("""
            SELECT b.booking_id,
                   f.departure_time, f.flight_id,
                   ap1.iata_code AS from_code, ap2.iata_code AS to_code,
                   s.seat_number, sc.class_name AS seat_class
            FROM booking b
            JOIN flight      f   ON f.flight_id    = b.flight_id
            JOIN route       r   ON r.route_id     = f.route_id
            JOIN airport     ap1 ON ap1.airport_id = r.departure_airport
            JOIN airport     ap2 ON ap2.airport_id = r.arrival_airport
            JOIN seat        s   ON s.seat_id      = b.seat_id
            JOIN seat_class  sc  ON sc.class_id    = s.class_id
            WHERE b.passenger_id = %s
            ORDER BY b.booking_id DESC
        """, (passenger_id,))
        history = cur.fetchall()

    body = f"""
    {"<p><a class='link' href='" + url_for('passengers') + "'>&larr; Passengers</a></p>" if is_admin() else ""}
    <div class="topbar">
      <h1>{p['name']}</h1>
      <a class="btn" href="{url_for('edit_passenger', passenger_id=passenger_id)}">Edit profile</a>
    </div>
    <div class="card" style="margin-bottom:18px">
      <div class="form-grid">
        <div><div class="label muted">Passenger ID</div><code>{p['passenger_id']}</code></div>
        <div><div class="label muted">Passport</div>{p['passport_no']}</div>
        <div><div class="label muted">Date of birth</div>{p['dob']}</div>
      </div>
    </div>
    <h2>Booking history ({len(history)})</h2>
    <table><thead><tr><th>Booking</th><th>Flight</th><th>Route</th>
                       <th>Departure</th><th>Seat</th><th>Class</th></tr></thead><tbody>
    """
    for h in history:
        body += (
            f"<tr><td><a class='link' href='"
            f"{url_for('booking_detail', booking_id=h['booking_id'])}'>"
            f"<code>{h['booking_id']}</code></a></td>"
            f"<td><code>{h['flight_id']}</code></td>"
            f"<td>{h['from_code']} → {h['to_code']}</td>"
            f"<td>{h['departure_time'].strftime('%Y-%m-%d %H:%M')}</td>"
            f"<td>{h['seat_number']}</td>"
            f"<td>{h['seat_class']}</td></tr>"
        )
    if not history:
        body += "<tr><td colspan='6' class='muted'>No bookings yet.</td></tr>"
    body += "</tbody></table>"
    return render(p['name'], body, active="passengers")


@app.route("/passengers/<passenger_id>/edit", methods=["GET", "POST"])
@login_required
def edit_passenger(passenger_id):
    assert_owns_passenger(passenger_id)
    with db_cursor() as cur:
        cur.execute("SELECT * FROM passenger WHERE passenger_id=%s", (passenger_id,))
        p = cur.fetchone()
        if not p:
            abort(404)

    if request.method == "POST":
        name     = request.form.get("name", "").strip()
        passport = request.form.get("passport_no", "").strip()
        dob      = request.form.get("dob", "").strip()
        if not (name and passport and dob):
            flash("Name, passport, and date of birth are required.", "danger")
        else:
            try:
                with db_cursor(commit=True) as cur:
                    cur.execute(
                        "UPDATE passenger SET name=%s, passport_no=%s, dob=%s WHERE passenger_id=%s",
                        (name, passport, dob, passenger_id),
                    )
                flash("Profile updated.", "success")
                return redirect(url_for("passenger_detail", passenger_id=passenger_id))
            except Exception as e:
                flash(f"Error: {e}", "danger")

    body = f"""
    <p><a class="link" href="{url_for('passenger_detail', passenger_id=passenger_id)}">&larr; Profile</a></p>
    <h1>Edit profile</h1>
    <form method="post" class="card">
      <div class="form-grid">
        <div><label>Full name *</label>
          <input name="name" value="{p['name']}" required></div>
        <div><label>Passport no. *</label>
          <input name="passport_no" value="{p['passport_no']}" required></div>
        <div><label>Date of birth *</label>
          <input type="date" name="dob" value="{p['dob']}"
                 max="{date.today().isoformat()}" required></div>
      </div>
      <div style="margin-top:14px">
        <button class="btn" type="submit">Save profile</button>
        <a class="btn secondary" href="{url_for('passenger_detail', passenger_id=passenger_id)}">Cancel</a>
      </div>
    </form>
    """
    return render("Edit passenger", body, active="passengers")


# ---------------------------------------------------------------------------
# Bookings
# ---------------------------------------------------------------------------
@app.route("/bookings")
@login_required
def bookings():
    where, params = "", ()
    if not is_admin():
        where  = "WHERE b.passenger_id = %s"
        params = (session.get("passenger_id"),)
    with db_cursor() as cur:
        cur.execute(f"""
            SELECT b.booking_id,
                   p.name,
                   ap1.iata_code AS from_code, ap2.iata_code AS to_code,
                   f.departure_time,
                   s.seat_number, sc.class_name AS seat_class
            FROM booking b
            JOIN passenger  p   ON p.passenger_id  = b.passenger_id
            JOIN flight     f   ON f.flight_id      = b.flight_id
            JOIN seat       s   ON s.seat_id        = b.seat_id
            JOIN seat_class sc  ON sc.class_id      = s.class_id
            JOIN route      r   ON r.route_id       = f.route_id
            JOIN airport    ap1 ON ap1.airport_id   = r.departure_airport
            JOIN airport    ap2 ON ap2.airport_id   = r.arrival_airport
            {where}
            ORDER BY b.booking_id DESC
        """, params)
        rows = cur.fetchall()

    title = "All bookings" if is_admin() else "My bookings"
    body = f"""
    <div class="topbar"><h1>{title}</h1>
      <a class="btn" href="{url_for('new_booking')}">+ New booking</a></div>
    <table><thead><tr><th>Booking</th><th>Traveler</th><th>Route</th>
                       <th>Departure</th><th>Seat</th><th>Class</th><th></th></tr></thead><tbody>
    """
    for b in rows:
        view_btn = (
            f"<a class='btn small' href='"
            f"{url_for('booking_detail', booking_id=b['booking_id'])}'>View</a>"
        )
        body += (
            f"<tr><td><a class='link' href='"
            f"{url_for('booking_detail', booking_id=b['booking_id'])}'>"
            f"<code>{b['booking_id']}</code></a></td>"
            f"<td>{b['name']}</td>"
            f"<td>{b['from_code']} → {b['to_code']}</td>"
            f"<td>{b['departure_time'].strftime('%Y-%m-%d %H:%M')}</td>"
            f"<td>{b['seat_number']}</td>"
            f"<td>{b['seat_class']}</td>"
            f"<td>{view_btn}</td></tr>"
        )
    body += "</tbody></table>"
    return render("Bookings", body, active="bookings")


@app.route("/bookings/new", methods=["GET", "POST"])
@login_required
def new_booking():
    if request.method == "POST":
        flight_id    = request.form.get("flight_id")
        passenger_id = (
            request.form.get("passenger_id")
            if is_admin() else session.get("passenger_id")
        )
        seat_id = request.form.get("seat_id")
        if not (flight_id and passenger_id and seat_id):
            flash("Flight, passenger, and seat are all required.", "danger")
        else:
            try:
                bid = gen_id("BKG", 10)
                with db_cursor(commit=True) as cur:
                    cur.execute(
                        "INSERT INTO booking (booking_id, passenger_id, flight_id, seat_id) VALUES (%s,%s,%s,%s)",
                        (bid, passenger_id, flight_id, seat_id),
                    )
                flash(f"Booking {bid} created.", "success")
                return redirect(url_for("booking_detail", booking_id=bid))
            except Exception as e:
                flash(f"Error: {e}", "danger")

    with db_cursor() as cur:
        # Flights dropdown: MySQL CONCAT instead of ||
        cur.execute("""
            SELECT f.flight_id,
                   CONCAT(ap1.iata_code, ' → ', ap2.iata_code, ' | ',
                          DATE_FORMAT(f.departure_time, '%%Y-%%m-%%d %%H:%%i')) AS label
            FROM flight f
            JOIN route   r   ON r.route_id     = f.route_id
            JOIN airport ap1 ON ap1.airport_id = r.departure_airport
            JOIN airport ap2 ON ap2.airport_id = r.arrival_airport
            WHERE f.status IN ('Scheduled','Delayed')
            ORDER BY f.departure_time
        """)
        flights_list = cur.fetchall()

        cur.execute("""
            SELECT passenger_id, name FROM passenger ORDER BY name
        """)
        passengers_list = cur.fetchall()

        flight_seats = {}
        for fl in flights_list:
            cur.execute("""
                SELECT s.seat_id, s.seat_number, sc.class_name AS seat_class
                FROM seat s
                JOIN seat_class sc ON sc.class_id = s.class_id
                JOIN aircraft   ac ON ac.aircraft_id = s.aircraft_id
                JOIN flight      f ON f.aircraft_id  = ac.aircraft_id
                WHERE f.flight_id = %s
                  AND s.seat_id NOT IN (
                      SELECT seat_id FROM booking WHERE flight_id = %s
                  )
                ORDER BY sc.class_name, s.seat_number
            """, (fl["flight_id"], fl["flight_id"]))
            flight_seats[fl["flight_id"]] = cur.fetchall()

    preset_flight = request.args.get("flight_id", "")
    flight_options = "".join(
        f'<option value="{fl["flight_id"]}" '
        f'{"selected" if fl["flight_id"]==preset_flight else ""}>'
        f'{fl["flight_id"]} — {fl["label"]}</option>'
        for fl in flights_list
    )

    if is_admin():
        passenger_options = "".join(
            f'<option value="{p["passenger_id"]}">{p["passenger_id"]} — {p["name"]}</option>'
            for p in passengers_list
        )
        passenger_field = (
            f'<div><label>Traveler *</label>'
            f'<select name="passenger_id" required>'
            f'<option value="">— select traveler —</option>{passenger_options}'
            f'</select></div>'
        )
    else:
        my = next(
            (p for p in passengers_list if p["passenger_id"] == session.get("passenger_id")),
            None,
        )
        my_name = my["name"] if my else session.get("username", "")
        passenger_field = (
            f'<div><label>Traveler</label>'
            f'<input value="{my_name}" disabled>'
            f'<input type="hidden" name="passenger_id" value="{session.get("passenger_id")}">'
            f'</div>'
        )

    seat_data_js = "{" + ",".join(
        f'"{fid}":[' + ",".join(
            f'{{"id":"{s["seat_id"]}","label":"{s["seat_number"]} ({s["seat_class"]})"}}'
            for s in seats
        ) + "]"
        for fid, seats in flight_seats.items()
    ) + "}"

    body = f"""
    <p><a class="link" href="{url_for('bookings')}">&larr; Bookings</a></p>
    <h1>New booking</h1>
    <form method="post" class="card">
      <div class="form-grid">
        <div><label>Flight *</label>
          <select name="flight_id" id="flight_id" required onchange="updateSeats()">
            <option value="">— select flight —</option>{flight_options}
          </select></div>
        {passenger_field}
        <div><label>Seat *</label>
          <select name="seat_id" id="seat_id" required>
            <option value="">— select flight first —</option>
          </select></div>
      </div>
      <div style="margin-top:16px">
        <button class="btn" type="submit">Create booking</button>
        <a class="btn secondary" href="{url_for('bookings')}">Cancel</a>
      </div>
    </form>
    <script>
      const SEATS = {seat_data_js};
      function updateSeats() {{
        const f = document.getElementById('flight_id').value;
        const sel = document.getElementById('seat_id');
        sel.innerHTML = '';
        const list = SEATS[f] || [];
        if (!list.length) {{
          sel.innerHTML = '<option value="">No seats available</option>';
          return;
        }}
        sel.innerHTML = '<option value="">— select seat —</option>' +
          list.map(s => `<option value="${{s.id}}">${{s.label}}</option>`).join('');
      }}
      if (document.getElementById('flight_id').value) updateSeats();
    </script>
    """
    return render("New booking", body, active="bookings")


@app.route("/bookings/<booking_id>")
@login_required
def booking_detail(booking_id):
    with db_cursor() as cur:
        assert_owns_booking(cur, booking_id)
        cur.execute("""
            SELECT b.*,
                   p.name, p.passport_no, p.dob,
                   f.departure_time, f.arrival_time, f.status AS flight_status,
                   al.name AS airline, am.model_name AS aircraft,
                   ap1.iata_code AS from_code, ap1.name AS from_airport, ci1.city_name AS from_city,
                   ap2.iata_code AS to_code,   ap2.name AS to_airport,   ci2.city_name AS to_city,
                   r.distance AS distance_km,
                   s.seat_number, sc.class_name AS seat_class
            FROM booking b
            JOIN passenger      p   ON p.passenger_id  = b.passenger_id
            JOIN flight         f   ON f.flight_id      = b.flight_id
            JOIN airline        al  ON al.airline_id    = f.airline_id
            JOIN aircraft       ac  ON ac.aircraft_id   = f.aircraft_id
            JOIN aircraft_model am  ON am.model_id      = ac.model_id
            JOIN route          r   ON r.route_id       = f.route_id
            JOIN airport        ap1 ON ap1.airport_id   = r.departure_airport
            JOIN city           ci1 ON ci1.city_id      = ap1.city_id
            JOIN airport        ap2 ON ap2.airport_id   = r.arrival_airport
            JOIN city           ci2 ON ci2.city_id      = ap2.city_id
            JOIN seat           s   ON s.seat_id        = b.seat_id
            JOIN seat_class     sc  ON sc.class_id      = s.class_id
            WHERE b.booking_id = %s
        """, (booking_id,))
        bk = cur.fetchone()
        if not bk:
            abort(404)

        cur.execute(
            "SELECT * FROM payment WHERE booking_id=%s ORDER BY payment_id DESC",
            (booking_id,),
        )
        pays = cur.fetchall()

        cur.execute("SELECT * FROM baggage WHERE booking_id=%s", (booking_id,))
        bags = cur.fetchall()

    actions = []
    actions.append(
        f"<a class='btn secondary' href='{url_for('pay_booking', booking_id=booking_id)}'>Make payment</a>"
    )

    pay_rows = ""
    for pay in pays:
        pay_rows += (
            f"<tr><td><code>{pay['payment_id']}</code></td>"
            f"<td>{pay['amount']:,.2f}</td>"
            f"<td>{badge(pay['status'])}</td></tr>"
        )
    if not pays:
        pay_rows = "<tr><td colspan='3' class='muted'>No payments yet.</td></tr>"

    bag_rows = ""
    for bg in bags:
        bag_rows += (
            f"<tr><td><code>{bg['baggage_id']}</code></td>"
            f"<td>{bg['weight']} kg</td></tr>"
        )
    if not bags:
        bag_rows = "<tr><td colspan='2' class='muted'>No baggage registered.</td></tr>"

    body = f"""
    <p><a class="link" href="{url_for('bookings')}">&larr; All bookings</a></p>
    <div class="topbar">
      <h1>Booking {bk['booking_id']}</h1>
    </div>

    <div class="card" style="margin-bottom:18px">
      <div class="form-grid">
        <div><div class="label muted">Booking ID</div><strong>{bk['booking_id']}</strong></div>
        <div><div class="label muted">Passenger</div>{bk['name']}</div>
        <div><div class="label muted">Passport</div>{bk['passport_no']}</div>
        <div><div class="label muted">DOB</div>{bk['dob']}</div>
      </div>
    </div>

    <div class="card" style="margin-bottom:18px">
      <h2 style="margin-top:0">Flight {bk['flight_id']} {badge(bk['flight_status'])}</h2>
      <div class="form-grid">
        <div><div class="label muted">Airline</div><strong>{bk['airline']}</strong></div>
        <div><div class="label muted">Aircraft</div>{bk['aircraft']}</div>
        <div><div class="label muted">From</div>
             <strong>{bk['from_code']}</strong> {bk['from_city']}<br>
             <span class="muted" style="font-size:12px">{bk['from_airport']}</span></div>
        <div><div class="label muted">To</div>
             <strong>{bk['to_code']}</strong> {bk['to_city']}<br>
             <span class="muted" style="font-size:12px">{bk['to_airport']}</span></div>
        <div><div class="label muted">Departure</div>{bk['departure_time'].strftime('%Y-%m-%d %H:%M')}</div>
        <div><div class="label muted">Arrival</div>{bk['arrival_time'].strftime('%Y-%m-%d %H:%M')}</div>
        <div><div class="label muted">Seat</div><strong>{bk['seat_number']}</strong> ({bk['seat_class']})</div>
        <div><div class="label muted">Distance</div>{bk['distance_km']} km</div>
      </div>
    </div>

    <div style="margin:18px 0;display:flex;gap:8px;flex-wrap:wrap">
      {" ".join(actions)}
    </div>

    <h2>Payments</h2>
    <table><thead><tr><th>Payment</th><th>Amount</th><th>Status</th></tr></thead>
    <tbody>{pay_rows}</tbody></table>

    <h2>Baggage</h2>
    <table><thead><tr><th>Baggage</th><th>Weight</th></tr></thead>
    <tbody>{bag_rows}</tbody></table>
    """
    return render(f"Booking {booking_id}", body, active="bookings")


@app.route("/bookings/<booking_id>/cancel", methods=["POST"])
@login_required
def cancel_booking(booking_id):
    try:
        with db_cursor(commit=True) as cur:
            assert_owns_booking(cur, booking_id)
            cur.execute("DELETE FROM booking WHERE booking_id=%s", (booking_id,))
        flash(f"Booking {booking_id} removed.", "warning")
    except HTTPException:
        raise
    except Exception as e:
        flash(f"Error: {e}", "danger")
    return redirect(url_for("bookings"))


@app.route("/bookings/<booking_id>/pay", methods=["GET", "POST"])
@login_required
def pay_booking(booking_id):
    with db_cursor() as cur:
        assert_owns_booking(cur, booking_id)
        cur.execute(
            "SELECT b.*, p.name FROM booking b JOIN passenger p ON p.passenger_id=b.passenger_id WHERE booking_id=%s",
            (booking_id,),
        )
        bk = cur.fetchone()
        if not bk:
            abort(404)

    if request.method == "POST":
        amount = request.form.get("amount", "").strip()
        try:
            amount_f = float(amount)
            if amount_f <= 0:
                raise ValueError("Amount must be greater than zero")
            pid = gen_id("PAY", 10)
            with db_cursor(commit=True) as cur:
                cur.execute(
                    "INSERT INTO payment (payment_id, amount, status, booking_id) VALUES (%s,%s,'Completed',%s)",
                    (pid, amount_f, booking_id),
                )
            flash(f"Payment {pid} completed.", "success")
            return redirect(url_for("booking_detail", booking_id=booking_id))
        except Exception as e:
            flash(f"Error: {e}", "danger")

    body = f"""
    <p><a class="link" href="{url_for('booking_detail', booking_id=booking_id)}">&larr; Booking {booking_id}</a></p>
    <h1>Make payment</h1>
    <p class="muted">Passenger: {bk['name']}</p>
    <form method="post" class="card">
      <div class="form-grid">
        <div><label>Amount (PKR) *</label>
          <input name="amount" type="number" step="0.01" min="0.01" required></div>
      </div>
      <div style="margin-top:14px">
        <button class="btn" type="submit">Pay now</button>
        <a class="btn secondary" href="{url_for('booking_detail', booking_id=booking_id)}">Cancel</a>
      </div>
    </form>
    """
    return render("Make payment", body, active="bookings")


@app.route("/bookings/<booking_id>/edit", methods=["GET", "POST"])
@login_required
def edit_booking(booking_id):
    with db_cursor() as cur:
        assert_owns_booking(cur, booking_id)
        cur.execute(
            "SELECT b.*, f.aircraft_id FROM booking b JOIN flight f ON f.flight_id=b.flight_id WHERE booking_id=%s",
            (booking_id,),
        )
        bk = cur.fetchone()
        if not bk:
            abort(404)

    if request.method == "POST":
        new_seat = request.form.get("seat_id")
        if not new_seat:
            flash("Please select a seat.", "danger")
        else:
            try:
                with db_cursor(commit=True) as cur:
                    cur.execute(
                        "UPDATE booking SET seat_id=%s WHERE booking_id=%s",
                        (new_seat, booking_id),
                    )
                flash("Seat updated.", "success")
                return redirect(url_for("booking_detail", booking_id=booking_id))
            except Exception as e:
                flash(f"Error: {e}", "danger")

    with db_cursor() as cur:
        cur.execute("""
            SELECT s.seat_id, s.seat_number, sc.class_name AS seat_class
            FROM seat s
            JOIN seat_class sc ON sc.class_id = s.class_id
            WHERE s.aircraft_id = %s
              AND (s.seat_id = %s OR s.seat_id NOT IN (
                    SELECT seat_id FROM booking WHERE flight_id=%s
              ))
            ORDER BY sc.class_name, s.seat_number
        """, (bk["aircraft_id"], bk["seat_id"], bk["flight_id"]))
        seats = cur.fetchall()

    seat_opts = "".join(
        f'<option value="{s["seat_id"]}" '
        f'{"selected" if s["seat_id"]==bk["seat_id"] else ""}>'
        f'{s["seat_number"]} ({s["seat_class"]})</option>'
        for s in seats
    )
    body = f"""
    <p><a class="link" href="{url_for('booking_detail', booking_id=booking_id)}">&larr; Booking {booking_id}</a></p>
    <h1>Modify booking</h1>
    <form method="post" class="card">
      <div class="form-grid">
        <div><label>Seat</label>
          <select name="seat_id" required>{seat_opts}</select></div>
      </div>
      <div style="margin-top:14px">
        <button class="btn" type="submit">Save changes</button>
        <a class="btn secondary" href="{url_for('booking_detail', booking_id=booking_id)}">Cancel</a>
      </div>
    </form>
    """
    return render("Modify booking", body, active="bookings")


@app.route("/bookings/<booking_id>/checkin", methods=["POST"])
@login_required
def checkin(booking_id):
    flash("Check-in noted (no check-in status column in schema).", "info")
    return redirect(url_for("booking_detail", booking_id=booking_id))


# ---------------------------------------------------------------------------
# Payments / Baggage / Crew / Airports  (admin only)
# ---------------------------------------------------------------------------
@app.route("/payments")
@login_required
def payments():
    if not is_admin():
        abort(403)
    with db_cursor() as cur:
        cur.execute("""
            SELECT pay.payment_id, pay.amount, pay.status,
                   b.booking_id, p.name
            FROM payment pay
            JOIN booking   b ON b.booking_id   = pay.booking_id
            JOIN passenger p ON p.passenger_id = b.passenger_id
            ORDER BY pay.payment_id DESC
        """)
        rows = cur.fetchall()
    body = "<h1>Payments</h1><table><thead><tr><th>Payment</th><th>Booking</th><th>Passenger</th><th>Amount</th><th>Status</th></tr></thead><tbody>"
    for r in rows:
        body += (
            f"<tr><td><code>{r['payment_id']}</code></td>"
            f"<td><code>{r['booking_id']}</code></td>"
            f"<td>{r['name']}</td>"
            f"<td>{r['amount']:,.2f}</td>"
            f"<td>{badge(r['status'])}</td></tr>"
        )
    body += "</tbody></table>"
    return render("Payments", body, active="payments")


@app.route("/baggage")
@login_required
def baggage():
    if not is_admin():
        abort(403)
    with db_cursor() as cur:
        cur.execute("""
            SELECT bg.baggage_id, bg.weight,
                   b.booking_id, p.name,
                   ap1.iata_code AS from_code, ap2.iata_code AS to_code
            FROM baggage bg
            JOIN booking   b  ON b.booking_id   = bg.booking_id
            JOIN passenger p  ON p.passenger_id = b.passenger_id
            JOIN flight    f  ON f.flight_id    = b.flight_id
            JOIN route     r  ON r.route_id     = f.route_id
            JOIN airport  ap1 ON ap1.airport_id = r.departure_airport
            JOIN airport  ap2 ON ap2.airport_id = r.arrival_airport
            ORDER BY bg.baggage_id
        """)
        rows = cur.fetchall()
    body = "<h1>Baggage</h1><table><thead><tr><th>Baggage</th><th>Booking</th><th>Passenger</th><th>Route</th><th>Weight (kg)</th></tr></thead><tbody>"
    for r in rows:
        body += (
            f"<tr><td><code>{r['baggage_id']}</code></td>"
            f"<td><code>{r['booking_id']}</code></td>"
            f"<td>{r['name']}</td>"
            f"<td>{r['from_code']} → {r['to_code']}</td>"
            f"<td>{r['weight']} kg</td></tr>"
        )
    body += "</tbody></table>"
    return render("Baggage", body, active="baggage")


@app.route("/crew")
@login_required
def crew():
    if not is_admin():
        abort(403)
    with db_cursor() as cur:
        # CREW table only has crew_id and name; flight_crew has role
        cur.execute("""
            SELECT c.crew_id, c.name,
                   COUNT(fc.flight_id) AS assigned
            FROM crew c
            LEFT JOIN flight_crew fc ON fc.crew_id = c.crew_id
            GROUP BY c.crew_id, c.name
            ORDER BY c.name
        """)
        rows = cur.fetchall()
    body = "<h1>Crew</h1><table><thead><tr><th>ID</th><th>Name</th><th>Assigned flights</th></tr></thead><tbody>"
    for r in rows:
        body += (
            f"<tr><td><code>{r['crew_id']}</code></td>"
            f"<td>{r['name']}</td>"
            f"<td><span class='pill'>{r['assigned']}</span></td></tr>"
        )
    body += "</tbody></table>"
    return render("Crew", body, active="crew")


@app.route("/airports")
@login_required
def airports():
    if not is_admin():
        abort(403)
    with db_cursor() as cur:
        cur.execute("""
            SELECT a.airport_id, a.iata_code, a.name,
                   ci.city_name AS city, co.country_name AS country
            FROM airport a
            JOIN city    ci ON ci.city_id    = a.city_id
            JOIN country co ON co.country_id = ci.country_id
            ORDER BY co.country_name, ci.city_name
        """)
        ap = cur.fetchall()
        cur.execute("""
            SELECT r.route_id, r.distance,
                   ap1.iata_code AS from_code, ci1.city_name AS from_city,
                   ap2.iata_code AS to_code,   ci2.city_name AS to_city
            FROM route r
            JOIN airport ap1 ON ap1.airport_id = r.departure_airport
            JOIN city    ci1 ON ci1.city_id    = ap1.city_id
            JOIN airport ap2 ON ap2.airport_id = r.arrival_airport
            JOIN city    ci2 ON ci2.city_id    = ap2.city_id
            ORDER BY r.route_id
        """)
        routes_list = cur.fetchall()
        cur.execute("""
            SELECT al.airline_id, al.iata_code, al.name, co.country_name AS country
            FROM airline al
            JOIN country co ON co.country_id = al.country_id
            ORDER BY al.name
        """)
        airlines_list = cur.fetchall()

    body = "<h1>Airports & routes</h1><h2>Airports</h2><table><thead><tr><th>ID</th><th>IATA</th><th>Name</th><th>City</th><th>Country</th></tr></thead><tbody>"
    for a in ap:
        body += f"<tr><td><code>{a['airport_id']}</code></td><td><strong>{a['iata_code']}</strong></td><td>{a['name']}</td><td>{a['city']}</td><td>{a['country']}</td></tr>"
    body += "</tbody></table>"

    body += "<h2>Routes</h2><table><thead><tr><th>ID</th><th>From</th><th>To</th><th>Distance (km)</th></tr></thead><tbody>"
    for r in routes_list:
        body += (
            f"<tr><td><code>{r['route_id']}</code></td>"
            f"<td>{r['from_code']} ({r['from_city']})</td>"
            f"<td>{r['to_code']} ({r['to_city']})</td>"
            f"<td>{r['distance']} km</td></tr>"
        )
    body += "</tbody></table>"

    body += "<h2>Airlines</h2><table><thead><tr><th>ID</th><th>IATA</th><th>Name</th><th>Country</th></tr></thead><tbody>"
    for a in airlines_list:
        body += f"<tr><td><code>{a['airline_id']}</code></td><td><strong>{a['iata_code']}</strong></td><td>{a['name']}</td><td>{a['country']}</td></tr>"
    body += "</tbody></table>"
    return render("Airports", body, active="airports")


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------
@app.route("/notifications")
@login_required
def notifications():
    items = []
    admin = is_admin()
    pid   = session.get("passenger_id")
    with db_cursor() as cur:
        if admin:
            cur.execute("""
                SELECT f.flight_id, f.departure_time, f.status,
                       ap1.iata_code AS from_code, ap2.iata_code AS to_code
                FROM flight f
                JOIN route   r   ON r.route_id     = f.route_id
                JOIN airport ap1 ON ap1.airport_id = r.departure_airport
                JOIN airport ap2 ON ap2.airport_id = r.arrival_airport
                WHERE f.status IN ('Delayed','Cancelled')
                ORDER BY f.departure_time DESC
            """)
        else:
            cur.execute("""
                SELECT DISTINCT f.flight_id, f.departure_time, f.status,
                       ap1.iata_code AS from_code, ap2.iata_code AS to_code
                FROM flight f
                JOIN route   r   ON r.route_id     = f.route_id
                JOIN airport ap1 ON ap1.airport_id = r.departure_airport
                JOIN airport ap2 ON ap2.airport_id = r.arrival_airport
                JOIN booking b   ON b.flight_id    = f.flight_id
                WHERE f.status IN ('Delayed','Cancelled')
                  AND b.passenger_id = %s
                ORDER BY f.departure_time DESC
            """, (pid,))
        for fl in cur.fetchall():
            kind = "warning" if fl["status"] == "Delayed" else "danger"
            items.append((
                fl["departure_time"], kind,
                f"Flight {fl['flight_id']} ({fl['from_code']} → {fl['to_code']}) is {fl['status']}.",
                url_for("flight_detail", flight_id=fl["flight_id"]),
            ))

    items.sort(key=lambda r: r[0], reverse=True)
    body = "<h1>Notifications</h1>"
    if not items:
        body += "<p class='muted'>You have no notifications.</p>"
    else:
        body += "<div style='display:flex;flex-direction:column;gap:10px'>"
        for ts, kind, text, link in items:
            body += (
                f"<a class='flash {kind}' href='{link}' "
                f"style='text-decoration:none;color:inherit;display:block'>"
                f"<div style='font-weight:600'>{text}</div>"
                f"<div class='muted' style='font-size:12px'>{ts.strftime('%Y-%m-%d %H:%M')}</div></a>"
            )
        body += "</div>"
    return render("Notifications", body, active="notifications")


# ---------------------------------------------------------------------------
# Check-in list (simplified — schema has no check-in status column)
# ---------------------------------------------------------------------------
@app.route("/checkin")
@login_required
def checkin_list():
    own_filter, params = "", ()
    if not is_admin():
        own_filter = "AND b.passenger_id = %s"
        params     = (session.get("passenger_id"),)
    with db_cursor() as cur:
        cur.execute(f"""
            SELECT b.booking_id,
                   p.name,
                   f.flight_id, f.departure_time,
                   ap1.iata_code AS from_code, ap2.iata_code AS to_code,
                   s.seat_number, sc.class_name AS seat_class
            FROM booking b
            JOIN passenger  p   ON p.passenger_id  = b.passenger_id
            JOIN flight     f   ON f.flight_id      = b.flight_id
            JOIN route      r   ON r.route_id       = f.route_id
            JOIN airport    ap1 ON ap1.airport_id   = r.departure_airport
            JOIN airport    ap2 ON ap2.airport_id   = r.arrival_airport
            JOIN seat       s   ON s.seat_id        = b.seat_id
            JOIN seat_class sc  ON sc.class_id      = s.class_id
            WHERE f.status IN ('Scheduled','Delayed')
              {own_filter}
            ORDER BY f.departure_time
        """, params)
        rows = cur.fetchall()

    body = """
    <div class="topbar">
      <div>
        <h1>Online check-in</h1>
        <p class="muted" style="margin:4px 0 0">Check in early to grab your boarding pass.</p>
      </div>
    </div>
    <table>
      <thead><tr><th>Booking</th><th>Traveler</th><th>Flight</th><th>Route</th>
                 <th>Departure</th><th>Seat</th><th>Class</th><th></th></tr></thead>
      <tbody>
    """
    if not rows:
        body += "<tr><td colspan='8' class='muted'>No upcoming bookings found.</td></tr>"
    for b in rows:
        action = (
            f"<form method='post' class='inline' action='"
            f"{url_for('checkin', booking_id=b['booking_id'])}'>"
            f"<button class='btn small' type='submit'>Check in</button></form>"
        )
        body += (
            f"<tr><td><a class='link' href='"
            f"{url_for('booking_detail', booking_id=b['booking_id'])}'>"
            f"<code>{b['booking_id']}</code></a></td>"
            f"<td>{b['name']}</td>"
            f"<td><code>{b['flight_id']}</code></td>"
            f"<td>{b['from_code']} → {b['to_code']}</td>"
            f"<td>{b['departure_time'].strftime('%a %d %b · %H:%M')}</td>"
            f"<td>{b['seat_number']}</td>"
            f"<td>{b['seat_class']}</td>"
            f"<td>{action}</td></tr>"
        )
    body += "</tbody></table>"
    return render("Check-in", body, active="checkin")


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------
@app.errorhandler(403)
def forbidden(e):
    return render("Forbidden", "<h1>403</h1><p>You do not have permission to view this page.</p>"), 403


@app.errorhandler(404)
def not_found(e):
    return render("Not found", "<h1>404</h1><p>That page does not exist.</p>"), 404


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    with app.app_context():
        ensure_admin_user()
    app.run(host="0.0.0.0", port=5000, debug=True)