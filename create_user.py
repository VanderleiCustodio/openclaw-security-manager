import getpass
import sqlite3
import sys
from pathlib import Path

import pyotp

sys.path.insert(0, str(Path(__file__).parent.resolve()))

from auth import DB_PATH, OPENCLAW_DIR, create_user  # noqa: E402


def _try_print_qr(uri: str) -> None:
    try:
        import qrcode
        qr = qrcode.QRCode()
        qr.add_data(uri)
        qr.make(fit=True)
        qr.print_ascii(invert=True)
    except ImportError:
        print("(Instale 'qrcode' para exibir o QR code ASCII: pip install qrcode)")


def main():
    print("=== OpenClaw — Criar Usuário ===\n")

    username = input("Username: ").strip()
    if not username:
        print("Erro: username não pode ser vazio.")
        sys.exit(1)

    OPENCLAW_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
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
    existing = conn.execute(
        "SELECT id FROM users WHERE username = ?", (username,)
    ).fetchone()
    conn.close()

    if existing:
        print(f"Erro: usuário '{username}' já existe.")
        sys.exit(1)

    password = getpass.getpass("Senha: ")
    if len(password) < 8:
        print("Erro: a senha deve ter no mínimo 8 caracteres.")
        sys.exit(1)

    password_confirm = getpass.getpass("Confirme a senha: ")
    if password != password_confirm:
        print("Erro: as senhas não coincidem.")
        sys.exit(1)

    secret = create_user(username, password)
    uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name=username, issuer_name="OpenClaw"
    )

    print(f"\nUsuário '{username}' criado com sucesso!\n")
    print("--- Configuração do Autenticador ---")
    print(f"URI de provisionamento:\n{uri}\n")
    _try_print_qr(uri)
    print("\nEscaneie o QR code com Google Authenticator ou Authy.")
    print("Guarde a URI acima como backup caso precise reconfigurar o app.")


if __name__ == "__main__":
    main()
