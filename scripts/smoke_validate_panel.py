"""
Smoke validation: get_ui_state -> index.html + build_patch por secao (sem gravar JSON).
Alinhado a .omc/skills/openclaw-full-project-validation (evidencia local sem mutar ~/.openclaw).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from flask import render_template  # noqa: E402

from app import (  # noqa: E402
    app,
    build_patch,
    deep_merge,
    get_ui_state,
    load_config,
    build_status,
)

REQUIRED_STATE_KEYS = frozenset(
    [
        "dm_pairing_whatsapp",
        "dm_pairing_telegram",
        "dm_pairing_discord",
        "dm_pairing_teams",
        "gateway_bind",
        "gateway_auth_mode",
        "sandbox_mode",
        "tools_allow",
        "tools_deny",
        "plugins_allow",
        "plugins_deny",
        "log_level",
        "model_primary",
        "config_path",
        "config_exists",
        "session_reset_mode",
        "session_idle_minutes",
        "memory_flush_enabled",
        "permissions",
    ]
)

SECTIONS = [
    "dm_pairing",
    "gateway",
    "sandbox",
    "tools",
    "plugins",
    "logging",
    "model",
    "session",
    "hardened_preset",
    "personal_preset",
    "team_preset",
    "enterprise_preset",
    "devops_preset",
]

MINIMAL_CHANGES = {
    "dm_pairing": {
        "whatsapp": "pairing",
        "telegram": "pairing",
        "discord": "pairing",
        "msteams": "pairing",
    },
    "gateway": {"bind": "loopback", "auth_mode": "token", "mdns": "minimal"},
    "sandbox": {
        "mode": "non-main",
        "scope": "session",
        "workspace_access": "ro",
    },
    "tools": {
        "allow": "exec",
        "deny": "browser",
        "elevated_enabled": False,
    },
    "plugins": {"allow": [], "deny": []},
    "logging": {
        "level": "info",
        "redact": "tools",
        "console_level": "warn",
    },
    "model": {"primary": "anthropic/claude-opus-4-5"},
    "session": {
        "reset_mode": "idle",
        "idle_minutes": "9999999",
        "memory_flush_enabled": True,
    },
}


def main() -> int:
    cfg = load_config()
    state = get_ui_state(cfg)
    missing = REQUIRED_STATE_KEYS - set(state)
    if missing:
        print("FAIL: get_ui_state missing keys:", sorted(missing))
        return 1

    with app.app_context():
        html = render_template("index.html", state=state)

    path = str(state["config_path"])
    if path not in html:
        print("FAIL: config_path not found in rendered HTML")
        return 1
    if "dm_whatsapp" not in html:
        print("FAIL: expected control id dm_whatsapp in HTML")
        return 1
    if "session_reset_mode" not in html:
        print("FAIL: expected id session_reset_mode in HTML")
        return 1

    rows = build_status(cfg)
    if not isinstance(rows, list) or not rows:
        print("FAIL: build_status should return non-empty list")
        return 1

    # build_patch: presets must return non-empty; outros com MINIMAL_CHANGES
    for section in SECTIONS:
        changes = MINIMAL_CHANGES.get(section, {})
        patch = build_patch(section, changes, cfg)
        if not patch:
            print(f"FAIL: build_patch({section!r}) returned empty dict")
            return 1
        merged = deep_merge(cfg, patch)
        try:
            json.dumps(merged)
        except (TypeError, ValueError) as e:
            print(f"FAIL: merged config not JSON-serializable for {section}: {e}")
            return 1

    print("OK smoke_validate_panel")
    print("  state keys:", len(state))
    print("  HTML length:", len(html))
    print("  build_status rows:", len(rows))
    print("  config_path in HTML: yes")
    print("  build_patch sections tested:", len(SECTIONS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
