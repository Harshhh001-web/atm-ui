from flask import Flask, render_template, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = "atm-project-secret-key-change-me"
DB_NAME = "atm.db"


def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        card_number TEXT UNIQUE NOT NULL,
        pin_hash TEXT NOT NULL,
        balance REAL NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'ACTIVE',
        failed_attempts INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        type TEXT NOT NULL,
        amount REAL NOT NULL,
        balance_after REAL NOT NULL,
        description TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    """)
    user = conn.execute(
        "SELECT id FROM users WHERE card_number = ?",
        ("123456789012",)
    ).fetchone()

    if not user:
        cursor = conn.execute(
            """INSERT INTO users
               (name, card_number, pin_hash, balance)
               VALUES (?, ?, ?, ?)""",
            ("Harsh", "123456789012",
             generate_password_hash("1234"), 10000.0)
        )
        user_id = cursor.lastrowid
        conn.execute(
            """INSERT INTO transactions
               (user_id, type, amount, balance_after, description, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, "OPENING", 10000.0, 10000.0,
             "Opening balance", datetime.now().isoformat(timespec="seconds"))
        )
    conn.commit()
    conn.close()


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"success": False, "message": "Please login first."}), 401
        return fn(*args, **kwargs)
    return wrapper


def current_user():
    conn = get_db()
    user = conn.execute(
        "SELECT id, name, card_number, balance, status FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()
    conn.close()
    return user


@app.route("/")
def index():
    return render_template("login.html")


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


@app.post("/api/login")
def api_login():
    data = request.get_json(silent=True) or {}
    card = str(data.get("card_number", "")).strip()
    pin = str(data.get("pin", "")).strip()

    if not card.isdigit() or len(card) != 12:
        return jsonify({"success": False, "message": "Card number must contain 12 digits."}), 400

    if not pin.isdigit() or len(pin) != 4:
        return jsonify({"success": False, "message": "PIN must contain exactly 4 digits."}), 400

    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE card_number = ?", (card,)).fetchone()

    if not user:
        conn.close()
        return jsonify({"success": False, "message": "Invalid card number or PIN."}), 401

    if user["status"] == "BLOCKED":
        conn.close()
        return jsonify({"success": False, "message": "Card is blocked after 3 failed attempts."}), 403

    if not check_password_hash(user["pin_hash"], pin):
        attempts = user["failed_attempts"] + 1
        status = "BLOCKED" if attempts >= 3 else "ACTIVE"
        conn.execute(
            "UPDATE users SET failed_attempts = ?, status = ? WHERE id = ?",
            (attempts, status, user["id"])
        )
        conn.commit()
        conn.close()
        if status == "BLOCKED":
            return jsonify({"success": False, "message": "Card blocked after 3 failed PIN attempts."}), 403
        return jsonify({
            "success": False,
            "message": f"Invalid PIN. {3 - attempts} attempt(s) remaining."
        }), 401

    conn.execute(
        "UPDATE users SET failed_attempts = 0 WHERE id = ?",
        (user["id"],)
    )
    conn.commit()
    conn.close()

    session["user_id"] = user["id"]
    return jsonify({"success": True, "message": "Login successful.", "name": user["name"]})


@app.post("/api/logout")
def api_logout():
    session.clear()
    return jsonify({"success": True})


@app.get("/api/me")
@login_required
def api_me():
    user = current_user()
    if not user:
        session.clear()
        return jsonify({"success": False, "message": "User not found."}), 401
    return jsonify({
        "success": True,
        "name": user["name"],
        "card_number": user["card_number"],
        "balance": round(user["balance"], 2),
        "status": user["status"]
    })


def add_transaction(conn, user_id, tx_type, amount, balance_after, description):
    conn.execute(
        """INSERT INTO transactions
           (user_id, type, amount, balance_after, description, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (user_id, tx_type, amount, balance_after, description,
         datetime.now().isoformat(timespec="seconds"))
    )


@app.post("/api/withdraw")
@login_required
def api_withdraw():
    data = request.get_json(silent=True) or {}
    try:
        amount = float(data.get("amount", 0))
    except (TypeError, ValueError):
        amount = 0

    if amount <= 0:
        return jsonify({"success": False, "message": "Enter a valid withdrawal amount."}), 400
    if amount % 100 != 0:
        return jsonify({"success": False, "message": "Amount must be a multiple of ₹100."}), 400
    if amount > 20000:
        return jsonify({"success": False, "message": "Maximum withdrawal limit is ₹20,000."}), 400

    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()

    if amount > user["balance"]:
        conn.close()
        return jsonify({"success": False, "message": "Insufficient balance."}), 400

    new_balance = user["balance"] - amount
    conn.execute("UPDATE users SET balance = ? WHERE id = ?", (new_balance, user["id"]))
    add_transaction(conn, user["id"], "WITHDRAWAL", -amount, new_balance, "Cash withdrawal")
    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": f"₹{amount:,.2f} withdrawn successfully.",
        "balance": round(new_balance, 2)
    })


@app.post("/api/deposit")
@login_required
def api_deposit():
    data = request.get_json(silent=True) or {}
    try:
        amount = float(data.get("amount", 0))
    except (TypeError, ValueError):
        amount = 0

    if amount <= 0:
        return jsonify({"success": False, "message": "Enter a valid deposit amount."}), 400
    if amount > 50000:
        return jsonify({"success": False, "message": "Maximum deposit limit is ₹50,000."}), 400

    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    new_balance = user["balance"] + amount

    conn.execute("UPDATE users SET balance = ? WHERE id = ?", (new_balance, user["id"]))
    add_transaction(conn, user["id"], "DEPOSIT", amount, new_balance, "Cash deposit")
    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": f"₹{amount:,.2f} deposited successfully.",
        "balance": round(new_balance, 2)
    })


@app.post("/api/transfer")
@login_required
def api_transfer():
    data = request.get_json(silent=True) or {}
    receiver = str(data.get("receiver", "")).strip()
    try:
        amount = float(data.get("amount", 0))
    except (TypeError, ValueError):
        amount = 0

    if not receiver.isdigit() or len(receiver) not in (10, 11, 12):
        return jsonify({"success": False, "message": "Receiver account must be 10-12 digits."}), 400
    if amount <= 0:
        return jsonify({"success": False, "message": "Enter a valid transfer amount."}), 400
    if amount > 50000:
        return jsonify({"success": False, "message": "Maximum transfer limit is ₹50,000."}), 400

    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()

    if amount > user["balance"]:
        conn.close()
        return jsonify({"success": False, "message": "Insufficient balance."}), 400

    new_balance = user["balance"] - amount
    conn.execute("UPDATE users SET balance = ? WHERE id = ?", (new_balance, user["id"]))
    add_transaction(
        conn, user["id"], "TRANSFER", -amount, new_balance,
        f"Transfer to account {receiver}"
    )
    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": f"₹{amount:,.2f} transferred successfully.",
        "balance": round(new_balance, 2)
    })


@app.get("/api/transactions")
@login_required
def api_transactions():
    conn = get_db()
    rows = conn.execute(
        """SELECT type, amount, balance_after, description, created_at
           FROM transactions
           WHERE user_id = ?
           ORDER BY id DESC LIMIT 20""",
        (session["user_id"],)
    ).fetchall()
    conn.close()

    return jsonify({
        "success": True,
        "transactions": [dict(row) for row in rows]
    })


@app.post("/api/change-pin")
@login_required
def api_change_pin():
    data = request.get_json(silent=True) or {}
    old_pin = str(data.get("old_pin", "")).strip()
    new_pin = str(data.get("new_pin", "")).strip()
    confirm_pin = str(data.get("confirm_pin", "")).strip()

    if not old_pin.isdigit() or len(old_pin) != 4:
        return jsonify({"success": False, "message": "Current PIN must be 4 digits."}), 400
    if not new_pin.isdigit() or len(new_pin) != 4:
        return jsonify({"success": False, "message": "New PIN must be 4 digits."}), 400
    if new_pin != confirm_pin:
        return jsonify({"success": False, "message": "New PIN and confirmation do not match."}), 400

    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()

    if not check_password_hash(user["pin_hash"], old_pin):
        conn.close()
        return jsonify({"success": False, "message": "Current PIN is incorrect."}), 400

    if new_pin == old_pin:
        conn.close()
        return jsonify({"success": False, "message": "New PIN must be different from old PIN."}), 400

    conn.execute(
        "UPDATE users SET pin_hash = ? WHERE id = ?",
        (generate_password_hash(new_pin), user["id"])
    )
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "PIN changed successfully."})


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
