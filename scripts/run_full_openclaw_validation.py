"""
openclaw-full-project-validation skill: backup openclaw.json, test each section
with save_config + tail log for invalid reload patterns, restore backup.

Requires gateway running. Log: %TEMP%\\openclaw\\openclaw-YYYY-MM-DD.log
"""
from __future__ import annotations

import json
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import (  # noqa: E402
    CONFIG_PATH,
    build_patch,
    deep_merge,
    load_config,
    save_config,
)

LOG_DIR = Path(tempfile.gettempdir()) / "openclaw"

FAIL_SUBSTRINGS = [
    "reload skipped (invalid config)",
    "invalid config at",
    "unrecognized key",
    "invalid input",
    "config invalid",
    "problem:",
]

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


def log_path_today() -> Path:
    return LOG_DIR / f"openclaw-{datetime.now().strftime('%Y-%m-%d')}.log"


def read_from_offset(path: Path, start: int) -> str:
    if not path.exists() or start >= path.stat().st_size:
        return ""
    with open(path, "rb") as f:
        f.seek(start)
        return f.read().decode("utf-8", errors="replace")


def scan_failures(text: str) -> str | None:
    low = text.lower()
    for s in FAIL_SUBSTRINGS:
        if s in low:
            return s
    return None


def main() -> int:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    backup = CONFIG_PATH.with_suffix(".json.skill_backup")
    if CONFIG_PATH.exists():
        shutil.copy2(CONFIG_PATH, backup)
    else:
        CONFIG_PATH.write_text("{}", encoding="utf-8")
        shutil.copy2(CONFIG_PATH, backup)

    print(f"Snapshot: {backup}")
    print(f"Config:   {CONFIG_PATH}")
    print(f"Log:      {log_path_today()} (exists={log_path_today().exists()})")

    results: list[tuple[str, str, str]] = []
    wait_s = 4

    try:
        for section in SECTIONS:
            shutil.copy2(backup, CONFIG_PATH)
            current = load_config()
            changes = MINIMAL_CHANGES.get(section, {})
            patch = build_patch(section, changes, current)
            if not patch:
                results.append((section, "SKIP", "empty patch"))
                print(f"  {section}: SKIP (empty patch)")
                continue

            lp = log_path_today()
            offset = lp.stat().st_size if lp.exists() else 0

            after = deep_merge(current, patch)
            try:
                save_config(after)
            except Exception as e:
                results.append((section, "FAIL", f"save_config: {e}"))
                print(f"  {section}: FAIL save — {e}")
                continue

            time.sleep(wait_s)
            new_log = read_from_offset(lp, offset)
            bad = scan_failures(new_log)
            if bad:
                snippet = new_log.replace("\n", " ")[:400]
                results.append((section, "FAIL", f"log:{bad} :: {snippet}"))
                print(f"  {section}: FAIL ({bad})")
            else:
                results.append((section, "PASS", ""))
                print(f"  {section}: PASS")

    finally:
        if backup.exists():
            shutil.copy2(backup, CONFIG_PATH)
            try:
                backup.unlink()
            except OSError:
                pass
        print(f"Restored: {CONFIG_PATH}")

    passed = sum(1 for _, s, _ in results if s == "PASS")
    failed = sum(1 for _, s, _ in results if s == "FAIL")
    skipped = sum(1 for _, s, _ in results if s == "SKIP")
    total = len(results)
    failed_sections = [r[0] for r in results if r[1] == "FAIL"]

    print()
    print("=== Resumo (openclaw-full-project-validation) ===")
    print(json.dumps({"total": total, "passed": passed, "failed": failed, "skipped": skipped, "failed_sections": failed_sections}, indent=2))

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
