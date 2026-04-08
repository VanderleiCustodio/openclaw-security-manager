from datetime import datetime, timedelta

import flask_login
from flask import Blueprint, redirect, render_template, request, session, url_for

from auth import User, get_user, verify_password, verify_totp

auth_bp = Blueprint("auth", __name__)

_MAX_LOGIN_ATTEMPTS = 5
_LOGIN_LOCKOUT_MINUTES = 15
_MAX_TOTP_ATTEMPTS = 3


def _is_locked_out():
    lockout_until = session.get("login_lockout_until")
    if lockout_until:
        if datetime.utcnow() < datetime.fromisoformat(lockout_until):
            return True
        session.pop("login_attempts", None)
        session.pop("login_lockout_until", None)
    return False


def _record_failed_login():
    attempts = session.get("login_attempts", 0) + 1
    session["login_attempts"] = attempts
    if attempts >= _MAX_LOGIN_ATTEMPTS:
        until = datetime.utcnow() + timedelta(minutes=_LOGIN_LOCKOUT_MINUTES)
        session["login_lockout_until"] = until.isoformat()


def _reset_login_attempts():
    session.pop("login_attempts", None)
    session.pop("login_lockout_until", None)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if flask_login.current_user.is_authenticated:
        return redirect(url_for("index"))

    error = None

    if request.method == "POST":
        if _is_locked_out():
            error = "Muitas tentativas. Tente novamente em 15 minutos."
        else:
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            user_row = get_user(username) if username else None

            if user_row and verify_password(user_row, password):
                _reset_login_attempts()
                session["pending_user"] = username
                session["totp_attempts"] = 0
                return redirect(url_for("auth.login_2fa"))
            else:
                _record_failed_login()
                error = "Credenciais inválidas"

    return render_template("login.html", error=error)


@auth_bp.route("/login/2fa", methods=["GET", "POST"])
def login_2fa():
    pending = session.get("pending_user")
    if not pending:
        return redirect(url_for("auth.login"))

    error = None

    if request.method == "POST":
        code = request.form.get("code", "").strip()
        user_row = get_user(pending)

        if user_row and verify_totp(user_row, code):
            user = User(user_row["id"], user_row["username"], user_row["totp_secret"])
            flask_login.login_user(user)
            session.pop("pending_user", None)
            session.pop("totp_attempts", None)
            return redirect(url_for("index"))
        else:
            totp_attempts = session.get("totp_attempts", 0) + 1
            session["totp_attempts"] = totp_attempts
            if totp_attempts >= _MAX_TOTP_ATTEMPTS:
                session.pop("pending_user", None)
                session.pop("totp_attempts", None)
                return redirect(url_for("auth.login"))
            error = "Código inválido"

    return render_template("login_2fa.html", error=error)


@auth_bp.route("/logout", methods=["POST"])
@flask_login.login_required
def logout():
    flask_login.logout_user()
    session.clear()
    return redirect(url_for("auth.login"))
