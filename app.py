import os
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev_secret_change_me")  # set SECRET_KEY in host for production
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.path.join(BASE_DIR, "database.db")

def get_db():
    conn = sqlite3.connect(DATABASE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE,
            candidate_id INTEGER,
            created_at TEXT
        )
    ''')
    c.execute('SELECT COUNT(*) FROM candidates')
    if c.fetchone()[0] == 0:
        # default sample candidates
        c.executemany('INSERT INTO candidates (name) VALUES (?)',
                      [("Alice",), ("Bob",), ("Charlie",)])
    conn.commit()
    conn.close()

@app.before_first_request
def before_first():
    init_db()

def get_current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (uid,)).fetchone()
    conn.close()
    return user

@app.route("/")
def index():
    if session.get("user_id"):
        return redirect(url_for("vote"))
    return redirect(url_for("login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not username or not password:
            flash("Provide username and password")
            return redirect(url_for("register"))
        conn = get_db()
        try:
            hashed = generate_password_hash(password)
            conn.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, hashed))
            conn.commit()
            flash("Registered! Please login.")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Username already exists")
            return redirect(url_for("register"))
        finally:
            conn.close()
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            flash("Logged in")
            return redirect(url_for("vote"))
        flash("Invalid credentials")
        return redirect(url_for("login"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out")
    return redirect(url_for("login"))

@app.route("/vote", methods=["GET", "POST"])
def vote():
    user = get_current_user()
    if not user:
        flash("Login required")
        return redirect(url_for("login"))
    conn = get_db()
    voted = conn.execute('SELECT * FROM votes WHERE user_id = ?', (user["id"],)).fetchone()
    candidates = conn.execute('SELECT * FROM candidates').fetchall()
    if request.method == "POST":
        if voted:
            flash("You have already voted")
            conn.close()
            return redirect(url_for("results"))
        candidate_id = request.form.get("candidate")
        if not candidate_id:
            flash("Select a candidate")
            conn.close()
            return redirect(url_for("vote"))
        conn.execute('INSERT INTO votes (user_id, candidate_id, created_at) VALUES (?,?,?)',
                     (user["id"], int(candidate_id), datetime.utcnow().isoformat()))
        conn.commit()
        conn.close()
        flash("Vote recorded! Thank you.")
        return redirect(url_for("results"))
    conn.close()
    return render_template("vote.html", user=user, candidates=candidates, voted=bool(voted))

@app.route("/results")
def results():
    conn = get_db()
    rows = conn.execute('''
        SELECT c.id, c.name, COUNT(v.id) as votes
        FROM candidates c
        LEFT JOIN votes v ON c.id = v.candidate_id
        GROUP BY c.id
        ORDER BY votes DESC
    ''').fetchall()
    conn.close()
    return render_template("results.html", rows=rows)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
