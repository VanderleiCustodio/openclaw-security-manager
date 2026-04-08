import sqlite3
from datetime import datetime
from pathlib import Path

import pyotp
from flask_login import LoginManager
from werkzeug.security import check_password_hash, generate_password_hash

OPENCLAW_DIR = Path.home() / ".openclaw"
DB_PATH = OPENCLAW_DIR / "users.db"


class User:
    def __init__(self, id_, username, totp_secret):
        self.id = id_
        self.username = username
        self.totp_secret = totp_secret

    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)


def _get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_auth(app):
    OPENCLAW_DIR.mkdir(parents=True, exist_ok=True)

    conn = _get_conn()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                username    TEXT UNIQUE NOT NULL,
                password    TEXT NOT NULL,
                totp_secret TEXT NOT NULL,
                created_at  TEXT NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()

    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        conn = _get_conn()
        try:
            row = conn.execute(
                "SELECT id, username, totp_secret FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return User(row["id"], row["username"], row["totp_secret"])


def get_user(username):
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT id, username, password, totp_secret FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    finally:
        conn.close()
    return row


def create_user(username, password):
    hashed = generate_password_hash(password, method="pbkdf2:sha256")
    secret = pyotp.random_base32()
    created_at = datetime.utcnow().isoformat()
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO users (username, password, totp_secret, created_at) VALUES (?, ?, ?, ?)",
            (username, hashed, secret, created_at),
        )
        conn.commit()
    finally:
        conn.close()
    return secret


def verify_password(user_row, password):
    return check_password_hash(user_row["password"], password)


def verify_totp(user_row, code):
    totp = pyotp.TOTP(user_row["totp_secret"])
    return totp.verify(code)
