import copy
import json
import os
import shutil
import stat
import subprocess
import time
from datetime import datetime
from pathlib import Path

try:
    import psutil as _psutil
except ImportError:
    _psutil = None

import re

from flask import Flask, jsonify, render_template, request, redirect, session, url_for
from flask_login import login_required
from auth import init_auth
from auth_routes import auth_bp

# Resolve paths relative to this file — works regardless of where Python is run from
BASE_DIR = Path(__file__).parent.resolve()

app = Flask(__name__, template_folder=str(BASE_DIR / "templates"))
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(32)
init_auth(app)
app.register_blueprint(auth_bp)


@app.after_request
def set_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    if not response.headers.get("Content-Security-Policy"):
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src https://fonts.gstatic.com; "
            "script-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:;"
        )
    return response


# ---------------------------------------------------------------------------
# Config path detection
# ---------------------------------------------------------------------------

def detect_config_path() -> Path:
    """
    Try candidate paths in order. Returns the first that exists,
    or falls back to a sensible default for the current platform.

    Windows : %USERPROFILE%\\.openclaw  or  %APPDATA%\\openclaw
    Linux   : /root/.openclaw  →  ~/.openclaw  →  /etc/openclaw
    macOS   : ~/.openclaw
    """
    import platform
    _sys = platform.system()

    if _sys == "Windows":
        candidates = [
            Path.home() / ".openclaw" / "openclaw.json",
            Path(os.environ.get("APPDATA", Path.home())) / "openclaw" / "openclaw.json",
        ]
    else:  # Linux, macOS, BSD, etc.
        candidates = [
            Path("/root/.openclaw/openclaw.json"),
            Path.home() / ".openclaw" / "openclaw.json",
            Path("/etc/openclaw/openclaw.json"),
        ]

    for p in candidates:
        if p.exists():
            return p
    return candidates[0]  # default: first candidate for this platform


CONFIG_PATH = detect_config_path()
OPENCLAW_DIR = CONFIG_PATH.parent
BACKUP_DIR = OPENCLAW_DIR / "backups"
PAIRINGS_PATH = OPENCLAW_DIR / "pairings.json"


# ---------------------------------------------------------------------------
# Multi-user config discovery
# ---------------------------------------------------------------------------

def discover_user_configs() -> list:
    """Return list of dicts for every Linux user, including those without read access."""
    found = []
    if os.name != "nt":  # Linux / macOS
        candidates = []
        # Primary: read real users from /etc/passwd (uid >= 1000 + root)
        try:
            import pwd as _pwd
            entries = sorted(_pwd.getpwall(), key=lambda e: e.pw_name)
            for entry in entries:
                try:
                    uid  = entry.pw_uid
                    home = Path(entry.pw_dir) if entry.pw_dir else None
                    name = entry.pw_name
                    if home and (uid == 0 or uid >= 1000):
                        candidates.append((name, home / ".openclaw" / "openclaw.json"))
                except Exception:
                    pass
        except Exception:
            # Fallback: scan /home/*
            home_base = Path("/home")
            if home_base.exists():
                try:
                    for user_home in sorted(home_base.iterdir()):
                        if user_home.is_dir():
                            candidates.append((user_home.name, user_home / ".openclaw" / "openclaw.json"))
                except PermissionError:
                    pass
            candidates.append(("root", Path("/root/.openclaw/openclaw.json")))
        for username, cfg in candidates:
            try:
                home_dir = cfg.parent.parent  # /home/username or /root
                home_accessible = os.access(str(home_dir), os.X_OK)
                exists = bool(cfg.exists()) if home_accessible else False
                locked = not home_accessible
                found.append({
                    "user": username,
                    "path": str(cfg),
                    "readable": bool(os.access(str(cfg), os.R_OK)) if exists else None,
                    "writable": bool(os.access(str(cfg), os.W_OK)) if exists else None,
                    "exists": exists if home_accessible else None,
                    "locked": locked,
                })
            except Exception:
                found.append({
                    "user": username,
                    "path": str(cfg),
                    "readable": None,
                    "writable": None,
                    "exists": None,
                    "locked": True,
                })
    # Windows fallback (development) — always include the detected default
    default_str = str(CONFIG_PATH)
    if not any(u["path"] == default_str for u in found):
        found.insert(0, {
            "user": os.environ.get("USERNAME", "default"),
            "path": default_str,
            "readable": True,
            "writable": True,
            "exists": True,
            "locked": False,
        })
    return found


def get_active_paths():
    """Return (config_path, openclaw_dir, backup_dir) for the selected user."""
    from flask import has_request_context, session as _session
    if has_request_context():
        active = _session.get("active_config_path")
        if active:
            p = Path(active)
            return p, p.parent, p.parent / "backups"
    return CONFIG_PATH, OPENCLAW_DIR, BACKUP_DIR


# ---------------------------------------------------------------------------
# Safe JSON load / save with backup
# ---------------------------------------------------------------------------

def load_config() -> dict:
    config_path, _, _ = get_active_paths()
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}
    return {}


def backup_config():
    config_path, openclaw_dir, backup_dir = get_active_paths()
    if not config_path.exists():
        return None
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = backup_dir / f"openclaw_{ts}.json"
    shutil.copy2(config_path, dest)
    # Keep only last 10 backups
    backups = sorted(backup_dir.glob("openclaw_*.json"))
    for old in backups[:-10]:
        old.unlink()
    return str(dest)


def save_config(config: dict) -> str:
    """Validate JSON, backup, then write atomically. Returns backup path."""
    config_path, openclaw_dir, _ = get_active_paths()
    serialised = json.dumps(config, indent=2, ensure_ascii=False)
    json.loads(serialised)  # Re-parse to catch edge cases

    backup_path = backup_config()
    openclaw_dir.mkdir(parents=True, exist_ok=True)

    # Write to temp file first, then rename (atomic on POSIX)
    tmp = config_path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(serialised)
    tmp.replace(config_path)

    return backup_path


# ---------------------------------------------------------------------------
# Schema-aware deep merge
#
# Rules:
#   dict  → merge recursively
#   list  → replace entirely (caller passes the full intended list)
#   scalar→ replace
#   None value in patch → delete the key
# ---------------------------------------------------------------------------

def deep_merge(base: dict, patch: dict) -> dict:
    result = copy.deepcopy(base)
    for key, value in patch.items():
        if value is None:
            result.pop(key, None)
        elif key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


# ---------------------------------------------------------------------------
# Patch builders — one per section, schema-aware
# ---------------------------------------------------------------------------

def _patch_dm_pairing(changes: dict, current: dict) -> dict:
    patch = {"channels": {}}

    if "whatsapp" in changes:
        wa = copy.deepcopy(current.get("channels", {}).get("whatsapp", {}))
        wa["dmPolicy"] = changes["whatsapp"]
        if "group_mention" in changes:
            wa.setdefault("groups", {})["*"] = {"requireMention": changes["group_mention"]}
        patch["channels"]["whatsapp"] = wa

    if "telegram" in changes:
        tg = copy.deepcopy(current.get("channels", {}).get("telegram", {}))
        tg["dmPolicy"] = changes["telegram"]
        patch["channels"]["telegram"] = tg

    if "discord" in changes:
        dc = copy.deepcopy(current.get("channels", {}).get("discord", {}))
        dc.setdefault("dm", {})["policy"] = changes["discord"]
        patch["channels"]["discord"] = dc

    if "teams" in changes:
        ms = copy.deepcopy(current.get("channels", {}).get("teams", {}))
        ms["dmPolicy"] = changes["teams"]
        patch["channels"]["teams"] = ms

    return patch if patch["channels"] else {}


def _patch_gateway(changes: dict, current: dict) -> dict:
    gw = copy.deepcopy(current.get("gateway", {}))

    if "bind" in changes:
        gw["bind"] = changes["bind"]
    if "port" in changes and str(changes["port"]).strip():
        gw["port"] = int(changes["port"])
    if "auth_mode" in changes:
        gw.setdefault("auth", {})["mode"] = changes["auth_mode"]
    if "auth_token" in changes and str(changes["auth_token"]).strip():
        gw.setdefault("auth", {})["token"] = changes["auth_token"].strip()

    patch = {"gateway": gw}

    if "mdns" in changes:
        disc = copy.deepcopy(current.get("discovery", {}))
        disc.setdefault("mdns", {})["mode"] = changes["mdns"]
        patch["discovery"] = disc

    return patch


def _patch_sandbox(changes: dict, current: dict) -> dict:
    agents = copy.deepcopy(current.get("agents", {}))
    sb = agents.setdefault("defaults", {}).setdefault("sandbox", {})

    if "mode" in changes:
        sb["mode"] = changes["mode"]
    if "scope" in changes:
        sb["scope"] = changes["scope"]
    if "workspace_access" in changes:
        sb["workspaceAccess"] = changes["workspace_access"]

    return {"agents": agents}


def _patch_tools(changes: dict, current: dict) -> dict:
    tools = copy.deepcopy(current.get("tools", {}))
    agents = copy.deepcopy(current.get("agents", {}))

    if "profile" in changes:
        tools["profile"] = changes["profile"]
        # If a profile is set, remove explicit allow/deny to avoid conflicts
        tools.pop("allow", None)
        tools.pop("deny", None)
    else:
        # Explicit allow/deny — remove profile to avoid ambiguity
        tools.pop("profile", None)
        if "allow" in changes and changes["allow"].strip():
            tools["allow"] = [t.strip() for t in changes["allow"].split(",") if t.strip()]
        if "deny" in changes and changes["deny"].strip():
            tools["deny"] = [t.strip() for t in changes["deny"].split(",") if t.strip()]

    # Elevated tool settings live under agents.defaults.tools.elevated
    if "elevated_enabled" in changes:
        elev = agents.setdefault("defaults", {}).setdefault("tools", {}).setdefault("elevated", {})
        elev["enabled"] = changes["elevated_enabled"]
    if "elevated_allow_from" in changes:
        elev = agents.setdefault("defaults", {}).setdefault("tools", {}).setdefault("elevated", {})
        raw = changes["elevated_allow_from"]
        elev["allowFrom"] = [s.strip() for s in (raw if isinstance(raw, list) else raw.split(",")) if s.strip()]

    patch = {"tools": tools}
    if agents:
        patch["agents"] = agents
    return patch


def _patch_plugins(changes: dict, current: dict) -> dict:
    plugins = copy.deepcopy(current.get("plugins", {}))
    if "allow" in changes:
        raw = changes["allow"]
        plugins["allow"] = [p.strip() for p in (raw if isinstance(raw, list) else raw.split(",")) if p.strip()]
    if "deny" in changes:
        raw = changes["deny"]
        plugins["deny"] = [p.strip() for p in (raw if isinstance(raw, list) else raw.split(",")) if p.strip()]
    return {"plugins": plugins}


def _patch_logging(changes: dict, current: dict) -> dict:
    log = copy.deepcopy(current.get("logging", {}))

    if "level" in changes:
        log["level"] = changes["level"]
    if "redact" in changes:
        log["redactSensitive"] = changes["redact"]
    if "file" in changes and changes["file"].strip():
        log["file"] = changes["file"].strip()
    if "console_level" in changes:
        log["consoleLevel"] = changes["console_level"]
    if "console_style" in changes:
        log["consoleStyle"] = changes["console_style"]

    return {"logging": log}


def _patch_model(changes: dict, current: dict) -> dict:
    agents = copy.deepcopy(current.get("agents", {}))
    model = agents.setdefault("defaults", {}).setdefault("model", {})

    if "primary" in changes and changes["primary"].strip():
        model["primary"] = changes["primary"].strip()
    if "fallback" in changes and changes["fallback"].strip():
        model["fallback"] = changes["fallback"].strip()

    return {"agents": agents}


def _patch_hardened_preset(current: dict) -> dict:
    """Full recommended config. Merges into existing so no existing fields are lost."""
    return {
        "gateway": {
            "bind": "loopback",
            "auth": {"mode": "token"},
            # token left untouched — user must set their own
        },
        "discovery": {"mdns": {"mode": "minimal"}},
        "channels": {
            "whatsapp": {
                "dmPolicy": "pairing",
                "groups": {"*": {"requireMention": True}},
            },
            "telegram": {"dmPolicy": "pairing"},
            "discord":  {"dm": {"policy": "pairing"}},
            "teams":    {"dmPolicy": "pairing"},
        },
        "agents": {
            "defaults": {
                "sandbox": {
                    "mode": "non-main",
                    "scope": "session",
                    "workspaceAccess": "none",
                },
                "model": {"primary": "anthropic/claude-opus-4-5"},
            }
        },
        "logging": {
            "level": "info",
            "redactSensitive": "tools",
        },
    }


def _patch_personal_preset(current: dict) -> dict:
    """Personal/developer profile — balances security with dev usability."""
    return {
        "gateway": {
            "bind": "loopback",
            "auth": {"mode": "token"},
        },
        "discovery": {"mdns": {"mode": "minimal"}},
        "channels": {
            "whatsapp": {
                "dmPolicy": "pairing",
                "groups": {"*": {"requireMention": True}},
            },
            "telegram": {"dmPolicy": "pairing"},
            "discord":  {"dm": {"policy": "pairing"}},
            "teams":    {"dmPolicy": "pairing"},
        },
        "agents": {
            "defaults": {
                "sandbox": {
                    "mode": "non-main",
                    "scope": "session",
                    "workspaceAccess": "ro",
                },
                "model": {"primary": "anthropic/claude-opus-4-5"},
                "tools": {
                    "elevated": {"enabled": False},
                },
            }
        },
        "tools": {
            "profile": "standard",
            "allow": [
                "Read(**)",
                "Edit(~/projetos/**)",
                "Bash(git status)",
                "Bash(git diff *)",
                "Bash(git add *)",
                "Bash(git commit *)",
                "Bash(git log *)",
                "Bash(npm test)",
                "Bash(npm run *)",
                "Bash(npx *)",
            ],
            "deny": [
                "Bash(sudo *)",
                "Bash(rm -rf *)",
                "Bash(curl *)",
                "Bash(wget *)",
                "Bash(ssh *)",
                "Bash(env)",
                "Bash(printenv)",
                "Bash(npm install *)",
                "Bash(pip install *)",
                "Read(**/.env)",
                "Read(**/.env.*)",
                "Read(~/.aws/**)",
                "Read(~/.ssh/**)",
                "WebFetch(*)",
            ],
        },
        "plugins": {"deny": []},
        "session": {"dmScope": "contacts"},
        "logging": {
            "level": "info",
            "redactSensitive": "tools",
        },
    }


def _patch_team_preset(current: dict) -> dict:
    """Team/CI-CD profile — restrictive, suitable for shared repositories."""
    return {
        "gateway": {
            "bind": "loopback",
            "auth": {"mode": "token"},
        },
        "discovery": {"mdns": {"mode": "off"}},
        "channels": {
            "whatsapp": {
                "dmPolicy": "allowlist",
                "groups": {"*": {"requireMention": True}},
            },
            "telegram": {"dmPolicy": "allowlist"},
            "discord":  {"dm": {"policy": "allowlist"}},
            "teams":    {"dmPolicy": "allowlist"},
        },
        "agents": {
            "defaults": {
                "sandbox": {
                    "mode": "all",
                    "scope": "agent",
                    "workspaceAccess": "none",
                },
                "model": {"primary": "anthropic/claude-opus-4-5"},
                "tools": {
                    "elevated": {"enabled": False},
                },
            }
        },
        "tools": {
            "profile": "restricted",
            "allow": [
                "Read(**)",
                "Edit(src/**)",
                "Edit(tests/**)",
                "Edit(docs/**)",
                "Bash(npm test)",
                "Bash(npm run build)",
                "Bash(npm run lint)",
                "Bash(git status)",
                "Bash(git diff *)",
                "Bash(git add src/** tests/**)",
                "Bash(git commit *)",
            ],
            "deny": [
                "Bash(sudo *)",
                "Bash(rm *)",
                "Bash(curl *)",
                "Bash(wget *)",
                "Bash(ssh *)",
                "Bash(scp *)",
                "Bash(nc *)",
                "Bash(env)",
                "Bash(printenv)",
                "Bash(npm install *)",
                "Bash(git push *)",
                "Bash(git reset --hard *)",
                "Read(**/.env*)",
                "Read(**/credentials*)",
                "WebFetch(*)",
                "Agent(*)",
            ],
        },
        "plugins": {
            "allow": [],
            "deny": ["*"],
        },
        "session": {"dmScope": "contacts"},
        "logging": {
            "level": "info",
            "redactSensitive": "all",
        },
    }


def _patch_enterprise_preset(current: dict) -> dict:
    """Enterprise profile — maximum security, managed-settings.json style."""
    return {
        "gateway": {
            "bind": "loopback",
            "auth": {"mode": "token"},
        },
        "discovery": {"mdns": {"mode": "off"}},
        "channels": {
            "whatsapp": {
                "dmPolicy": "allowlist",
                "groups": {"*": {"requireMention": True}},
            },
            "telegram": {"dmPolicy": "allowlist"},
            "discord":  {"dm": {"policy": "allowlist"}},
            "teams":    {"dmPolicy": "allowlist"},
        },
        "agents": {
            "defaults": {
                "sandbox": {
                    "mode": "all",
                    "scope": "agent",
                    "workspaceAccess": "none",
                },
                "model": {"primary": "anthropic/claude-opus-4-5"},
                "tools": {
                    "elevated": {
                        "enabled": False,
                        "allowFrom": [],
                    },
                },
            }
        },
        "tools": {
            "profile": "minimal",
            "deny": [
                "Bash(sudo *)",
                "Bash(chmod *)",
                "Bash(chown *)",
                "Bash(curl *)",
                "Bash(wget *)",
                "Bash(ssh *)",
                "Bash(scp *)",
                "Bash(nc *)",
                "Bash(nmap *)",
                "Bash(env)",
                "Bash(printenv)",
                "Bash(npm install *)",
                "Bash(pip install *)",
                "Write(/etc/**)",
                "Write(/usr/**)",
                "Write(/bin/**)",
                "Write(~/.ssh/**)",
                "Write(~/.aws/**)",
                "Write(~/.gnupg/**)",
                "Read(**/.env)",
                "Read(**/.env.*)",
                "Read(**/credentials*)",
                "Read(**/secrets*)",
                "Read(~/.aws/**)",
                "Read(~/.ssh/**)",
                "Read(~/.gnupg/**)",
                "WebFetch(*)",
                "Agent(*)",
            ],
        },
        "plugins": {
            "allow": [],
            "deny": ["*"],
        },
        "session": {"dmScope": "none"},
        "logging": {
            "level": "warn",
            "redactSensitive": "all",
            "consoleLevel": "error",
        },
    }


def _patch_devops_preset(current: dict) -> dict:
    """DevOps profile — GitHub, GitLab, MongoDB, Azure DevOps, Docker, Kubernetes."""
    return {
        "gateway": {
            "bind": "loopback",
            "auth": {"mode": "token"},
        },
        "discovery": {"mdns": {"mode": "minimal"}},
        "channels": {
            "whatsapp": {"dmPolicy": "pairing", "groups": {"*": {"requireMention": True}}},
            "telegram": {"dmPolicy": "pairing"},
            "discord":  {"dm": {"policy": "pairing"}},
            "teams":    {"dmPolicy": "pairing"},
        },
        "agents": {
            "defaults": {
                "sandbox": {
                    "mode": "non-main",
                    "scope": "session",
                    "workspaceAccess": "ro",
                },
                "model": {"primary": "anthropic/claude-opus-4-5"},
                "tools": {"elevated": {"enabled": False}},
            }
        },
        "tools": {
            "profile": "restricted",
            "allow": [
                "Read(**)",
                "Edit(src/**)", "Edit(tests/**)", "Edit(.github/**)",
                "Edit(.gitlab-ci.yml)", "Edit(Dockerfile)", "Edit(docker-compose*.yml)",
                "Edit(*.tf)", "Edit(*.yaml)", "Edit(*.yml)",
                # Git
                "Bash(git status)", "Bash(git diff *)", "Bash(git add *)",
                "Bash(git commit *)", "Bash(git log *)", "Bash(git checkout *)",
                "Bash(git branch *)", "Bash(git fetch *)", "Bash(git pull *)",
                # GitHub CLI
                "Bash(gh pr *)", "Bash(gh issue *)", "Bash(gh repo *)",
                "Bash(gh run *)", "Bash(gh workflow *)",
                # GitLab CLI
                "Bash(glab mr *)", "Bash(glab issue *)", "Bash(glab ci *)",
                # CI/CD
                "Bash(npm test)", "Bash(npm run *)", "Bash(npx *)",
                "Bash(pytest *)", "Bash(python -m pytest *)",
                # Docker (read-only)
                "Bash(docker ps *)", "Bash(docker logs *)", "Bash(docker-compose ps)",
                "Bash(docker-compose logs *)",
                # Kubernetes (read-only)
                "Bash(kubectl get *)", "Bash(kubectl describe *)", "Bash(kubectl logs *)",
                # MongoDB
                "Bash(mongosh --eval *)",
                # Terraform (plan/validate only)
                "Bash(terraform plan)", "Bash(terraform validate)", "Bash(terraform fmt *)",
                # Azure DevOps
                "Bash(az devops *)", "Bash(az pipelines *)",
            ],
            "deny": [
                "Bash(sudo *)", "Bash(rm -rf *)",
                "Bash(git push --force *)", "Bash(git reset --hard *)",
                "Bash(git push origin main)", "Bash(git push origin master)",
                "Bash(docker run *)", "Bash(docker exec *)",
                "Bash(kubectl delete *)", "Bash(kubectl exec *)",
                "Bash(terraform apply *)", "Bash(terraform destroy *)",
                "Bash(az login *)",
                "Bash(env)", "Bash(printenv)",
                "Bash(curl *)", "Bash(wget *)", "Bash(ssh *)",
                "Bash(npm install *)", "Bash(pip install *)",
                "Read(**/.env)", "Read(**/.env.*)",
                "Read(~/.aws/**)", "Read(~/.ssh/**)",
                "Read(**/credentials*)", "Read(**/secrets*)",
                "Read(**/*.pem)", "Read(**/*.key)",
            ],
        },
        "plugins": {"deny": []},
        "session": {"dmScope": "contacts"},
        "logging": {
            "level": "info",
            "redactSensitive": "tools",
        },
    }


PATCH_BUILDERS = {
    "dm_pairing":        _patch_dm_pairing,
    "gateway":           _patch_gateway,
    "sandbox":           _patch_sandbox,
    "tools":             _patch_tools,
    "plugins":           _patch_plugins,
    "logging":           _patch_logging,
    "model":             _patch_model,
    "personal_preset":   lambda changes, current: _patch_personal_preset(current),
    "team_preset":       lambda changes, current: _patch_team_preset(current),
    "enterprise_preset": lambda changes, current: _patch_enterprise_preset(current),
    "devops_preset":     lambda changes, current: _patch_devops_preset(current),
}


def build_patch(section: str, changes: dict, current: dict) -> dict:
    if section == "hardened_preset":
        return _patch_hardened_preset(current)
    if section == "personal_preset":
        return _patch_personal_preset(current)
    if section == "team_preset":
        return _patch_team_preset(current)
    if section == "enterprise_preset":
        return _patch_enterprise_preset(current)
    if section == "devops_preset":
        return _patch_devops_preset(current)
    builder = PATCH_BUILDERS.get(section)
    if builder:
        return builder(changes, current)
    return {}


# ---------------------------------------------------------------------------
# Diff
# ---------------------------------------------------------------------------

def compute_diff(before: dict, after: dict, path: str = "") -> list:
    diffs = []
    all_keys = set(before) | set(after)
    for k in sorted(all_keys):
        full_path = f"{path}.{k}" if path else k
        bv, av = before.get(k), after.get(k)
        if bv == av:
            continue
        if isinstance(bv, dict) and isinstance(av, dict):
            diffs.extend(compute_diff(bv, av, full_path))
        else:
            diffs.append({"path": full_path, "before": bv, "after": av})
    return diffs


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------

def check_permissions() -> dict:
    import platform
    if platform.system() == "Windows":
        # Unix-style chmod bits do not apply on Windows — mark as N/A
        return {
            "dir":    {"path": str(OPENCLAW_DIR), "current": None, "expected": None, "ok": None, "na": True},
            "config": {"path": str(CONFIG_PATH),  "current": None, "expected": None, "ok": None, "na": True},
        }
    results = {}
    for label, path, expected in [("dir", OPENCLAW_DIR, 0o700), ("config", CONFIG_PATH, 0o600)]:
        if path.exists():
            mode = stat.S_IMODE(os.stat(path).st_mode)
            results[label] = {"path": str(path), "current": oct(mode), "expected": oct(expected), "ok": mode == expected}
        else:
            results[label] = {"path": str(path), "current": None, "expected": oct(expected), "ok": None}
    return results


def fix_permissions() -> list:
    import platform
    if platform.system() == "Windows":
        return ["Permissões Unix (chmod) não são aplicáveis no Windows."]
    applied = []
    if OPENCLAW_DIR.exists():
        os.chmod(OPENCLAW_DIR, 0o700)
        applied.append(f"{OPENCLAW_DIR} → 700")
    if CONFIG_PATH.exists():
        os.chmod(CONFIG_PATH, 0o600)
        applied.append(f"{CONFIG_PATH} → 600")
    return applied


# ---------------------------------------------------------------------------
# UI state builder
# ---------------------------------------------------------------------------

def _get(d, *keys, default=None):
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k)
        if d is None:
            return default
    return d if d is not None else default


def get_ui_state(cfg: dict) -> dict:
    elev = _get(cfg, "agents", "defaults", "tools", "elevated", "enabled", default="")
    return {
        "dm_pairing_whatsapp":      _get(cfg, "channels", "whatsapp", "dmPolicy",              default=""),
        "dm_pairing_telegram":      _get(cfg, "channels", "telegram", "dmPolicy",              default=""),
        "dm_pairing_discord":       _get(cfg, "channels", "discord",  "dm", "policy",          default=""),
        "dm_pairing_teams":         _get(cfg, "channels", "teams",    "dmPolicy",              default=""),
        "group_require_mention":    _get(cfg, "channels", "whatsapp", "groups", "*", "requireMention", default=False),
        "dm_scope":                 _get(cfg, "session",  "dmScope",  default=""),

        "gateway_bind":             _get(cfg, "gateway",   "bind",          default=""),
        "gateway_auth_mode":        _get(cfg, "gateway",   "auth", "mode",  default=""),
        "gateway_auth_token":       _get(cfg, "gateway",   "auth", "token", default=""),
        "gateway_port":             _get(cfg, "gateway",   "port",          default=""),
        "mdns_mode":                _get(cfg, "discovery", "mdns", "mode",  default=""),

        "sandbox_mode":             _get(cfg, "agents", "defaults", "sandbox", "mode",            default=""),
        "sandbox_scope":            _get(cfg, "agents", "defaults", "sandbox", "scope",           default=""),
        "sandbox_workspace_access": _get(cfg, "agents", "defaults", "sandbox", "workspaceAccess", default=""),

        "tools_profile":    _get(cfg, "tools", "profile", default=""),
        "tools_allow":      ", ".join(_get(cfg, "tools", "allow", default=[]) or []),
        "tools_deny":       ", ".join(_get(cfg, "tools", "deny",  default=[]) or []),

        "elevated_enabled":    elev,
        "elevated_allow_from": ", ".join(_get(cfg, "agents", "defaults", "tools", "elevated", "allowFrom", default=[]) or []),

        "plugins_allow": ", ".join(_get(cfg, "plugins", "allow", default=[]) or []),
        "plugins_deny":  ", ".join(_get(cfg, "plugins", "deny",  default=[]) or []),

        "log_level":         _get(cfg, "logging", "level",           default=""),
        "log_redact":        _get(cfg, "logging", "redactSensitive", default=""),
        "log_file":          _get(cfg, "logging", "file",            default=""),
        "log_console_level": _get(cfg, "logging", "consoleLevel",    default=""),
        "log_console_style": _get(cfg, "logging", "consoleStyle",    default=""),

        "model_primary":  _get(cfg, "agents", "defaults", "model", "primary",  default=""),
        "model_fallback": _get(cfg, "agents", "defaults", "model", "fallback", default=""),

        "permissions":   check_permissions(),
        "config_path":   str(CONFIG_PATH),
        "config_exists": CONFIG_PATH.exists(),
    }


# ---------------------------------------------------------------------------
# Security status comparison — atual vs recomendado
# ---------------------------------------------------------------------------

RECOMMENDED = {
    # (label, json_path_display, recommended_value, safe_values, risk_if_missing)
    "dm_whatsapp":      ("DM Pairing — WhatsApp",      "channels.whatsapp.dmPolicy",              "pairing",             ["pairing", "allowlist"], "high"),
    "dm_telegram":      ("DM Pairing — Telegram",      "channels.telegram.dmPolicy",              "pairing",             ["pairing", "allowlist"], "high"),
    "dm_discord":       ("DM Pairing — Discord",       "channels.discord.dm.policy",              "pairing",             ["pairing", "allowlist"], "high"),
    "dm_teams":         ("DM Pairing — Teams",         "channels.teams.dmPolicy",                 "pairing",             ["pairing", "allowlist"], "high"),
    "group_mention":    ("Grupos exigem @mention",     "channels.whatsapp.groups.*.requireMention","true",               ["true"], "medium"),
    "gateway_bind":     ("Gateway bind",               "gateway.bind",                            "loopback",            ["loopback", "tailnet"], "critical"),
    "gateway_auth":     ("Gateway auth mode",          "gateway.auth.mode",                       "token",               ["token", "password"], "critical"),
    "gateway_token":    ("Gateway auth token",         "gateway.auth.token",                      "<set>",               [], "critical"),
    "mdns":             ("mDNS mode",                  "discovery.mdns.mode",                     "minimal",             ["minimal", "off"], "low"),
    "sandbox_mode":     ("Sandbox mode",               "agents.defaults.sandbox.mode",            "non-main",            ["non-main", "all"], "critical"),
    "sandbox_scope":    ("Sandbox scope",              "agents.defaults.sandbox.scope",           "session",             ["session", "agent"], "medium"),
    "sandbox_ws":       ("Sandbox workspaceAccess",    "agents.defaults.sandbox.workspaceAccess", "none",                ["none", "ro"], "high"),
    "log_level":        ("Log level",                  "logging.level",                           "info",                ["info", "debug"], "low"),
    "log_redact":       ("Log redactSensitive",        "logging.redactSensitive",                 "tools",               ["tools", "all"], "high"),
    "model":            ("Modelo principal",           "agents.defaults.model.primary",           "anthropic/claude-opus-4-5", [], "medium"),
    "perm_dir":         ("Permissão ~/.openclaw",      "filesystem",                              "0o700",               [], "high"),
    "perm_cfg":         ("Permissão openclaw.json",    "filesystem",                              "0o600",               [], "high"),
    # New items from security guide
    "tools_deny_sudo":  ("Deny Bash(sudo *)",          "tools.deny",                              "<set>",               [], "critical"),
    "tools_deny_curl":  ("Deny Bash(curl/wget *)",     "tools.deny",                              "<set>",               [], "high"),
    "tools_deny_env":   ("Deny Bash(env/printenv)",    "tools.deny",                              "<set>",               [], "high"),
    "tools_deny_env_files": ("Deny Read(.env files)", "tools.deny",                              "<set>",               [], "high"),
    "tools_deny_secrets":   ("Deny Read(.aws/.ssh)",   "tools.deny",                              "<set>",               [], "critical"),
    "elevated_disabled": ("Elevated tools desabilitado", "agents.defaults.tools.elevated.enabled", "false",             ["false", "False"], "high"),
    # Missing checks from security guide
    "tools_profile":    ("Tools profile",               "tools.profile",          "restricted",  ["restricted", "minimal"], "high"),
    "plugins_deny":     ("Plugins bloqueados",           "plugins.deny",           "<non-empty>", [],                       "high"),
    "log_console_level":("Log consoleLevel",             "logging.consoleLevel",   "warn",        ["warn", "error"],        "low"),
    "dm_scope":         ("DM scope (session)",           "session.dmScope",        "contacts",    ["contacts", "none"],     "medium"),
}

RISK_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _tools_deny_contains(cfg: dict, *keywords) -> bool:
    """Return True if tools.deny list contains at least one entry matching any keyword."""
    deny_list = _get(cfg, "tools", "deny", default=[]) or []
    deny_str = " ".join(deny_list).lower()
    return any(kw.lower() in deny_str for kw in keywords)


def build_status(cfg: dict) -> list:
    perms = check_permissions()
    token = _get(cfg, "gateway", "auth", "token", default="")
    elevated_enabled = _get(cfg, "agents", "defaults", "tools", "elevated", "enabled", default=None)

    raw = {
        "dm_whatsapp":   str(_get(cfg, "channels", "whatsapp", "dmPolicy",              default="")),
        "dm_telegram":   str(_get(cfg, "channels", "telegram", "dmPolicy",              default="")),
        "dm_discord":    str(_get(cfg, "channels", "discord",  "dm", "policy",          default="")),
        "dm_teams":      str(_get(cfg, "channels", "teams",    "dmPolicy",              default="")),
        "group_mention": str(_get(cfg, "channels", "whatsapp", "groups", "*", "requireMention", default="")).lower(),
        "gateway_bind":  str(_get(cfg, "gateway", "bind",       default="")),
        "gateway_auth":  str(_get(cfg, "gateway", "auth", "mode", default="")),
        "gateway_token": "<set>" if token and str(token).strip() else "",
        "mdns":          str(_get(cfg, "discovery", "mdns", "mode", default="")),
        "sandbox_mode":  str(_get(cfg, "agents", "defaults", "sandbox", "mode",            default="")),
        "sandbox_scope": str(_get(cfg, "agents", "defaults", "sandbox", "scope",           default="")),
        "sandbox_ws":    str(_get(cfg, "agents", "defaults", "sandbox", "workspaceAccess", default="")),
        "log_level":     str(_get(cfg, "logging", "level",           default="")),
        "log_redact":    str(_get(cfg, "logging", "redactSensitive", default="")),
        "model":         str(_get(cfg, "agents", "defaults", "model", "primary", default="")),
        # On Windows permissions are N/A — treat as "ok" to avoid false alerts
        "perm_dir":      "N/A" if perms.get("dir", {}).get("na") else (perms.get("dir", {}).get("current") or ""),
        "perm_cfg":      "N/A" if perms.get("config", {}).get("na") else (perms.get("config", {}).get("current") or ""),
        # New security items
        "tools_deny_sudo":      "<set>" if _tools_deny_contains(cfg, "sudo") else "",
        "tools_deny_curl":      "<set>" if _tools_deny_contains(cfg, "curl", "wget") else "",
        "tools_deny_env":       "<set>" if _tools_deny_contains(cfg, "printenv", "bash(env)") else "",
        "tools_deny_env_files": "<set>" if _tools_deny_contains(cfg, ".env") else "",
        "tools_deny_secrets":   "<set>" if _tools_deny_contains(cfg, ".aws", ".ssh") else "",
        "elevated_disabled":    "false" if elevated_enabled is False else (str(elevated_enabled).lower() if elevated_enabled is not None else ""),
        # New missing checks
        "tools_profile":     str(_get(cfg, "tools", "profile", default="")),
        "plugins_deny":      "<non-empty>" if (_get(cfg, "plugins", "deny", default=[]) or []) else "",
        "log_console_level": str(_get(cfg, "logging", "consoleLevel", default="")),
        "dm_scope":          str(_get(cfg, "session", "dmScope", default="")),
    }

    rows = []
    for key, (label, path, rec, safe_vals, risk) in RECOMMENDED.items():
        current = raw.get(key, "")

        if key in ("gateway_token", "tools_deny_sudo", "tools_deny_curl",
                   "tools_deny_env", "tools_deny_env_files", "tools_deny_secrets"):
            ok = current == "<set>"
        elif key == "plugins_deny":
            ok = current == "<non-empty>"
        elif key in ("perm_dir", "perm_cfg") and current == "N/A":
            ok = True  # Windows: chmod not applicable, not a security gap
        elif safe_vals:
            ok = current in safe_vals
        else:
            # For model: any non-empty value is OK; opus is best
            ok = bool(current)

        # Determine status
        if not current:
            status = "missing"    # not configured at all
        elif ok:
            status = "ok"
        else:
            status = "warn"

        rows.append({
            "key":       key,
            "label":     label,
            "path":      path,
            "current":   current or "— não definido —",
            "recommended": rec,
            "status":    status,
            "risk":      risk,
        })

    # Sort: missing/warn first, then by risk severity
    rows.sort(key=lambda r: (0 if r["status"] != "ok" else 1, RISK_ORDER.get(r["risk"], 9)))
    return rows


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/api/users")
@login_required
def api_users():
    users = discover_user_configs()
    active = session.get("active_config_path", str(CONFIG_PATH))
    return jsonify({"users": users, "active": active})


@app.route("/api/select-user", methods=["POST"])
@login_required
def api_select_user():
    data = request.json or {}
    path_str = data.get("path", "")
    known = {u["path"] for u in discover_user_configs()}
    if path_str not in known:
        return jsonify({"success": False, "error": "Config path inválido."}), 400
    p = Path(path_str)
    if not os.access(p, os.R_OK):
        return jsonify({"success": False, "error": "Sem permissão de leitura."}), 403
    session["active_config_path"] = path_str
    return jsonify({"success": True, "path": path_str})


@app.route("/security-status")
@login_required
def security_status():
    cfg = load_config()
    rows = build_status(cfg)
    total = len(rows)
    ok_count = sum(1 for r in rows if r["status"] == "ok")
    return jsonify({"rows": rows, "ok": ok_count, "total": total})


@app.route("/")
@login_required
def index():
    cfg = load_config()
    state = get_ui_state(cfg)
    return render_template("index.html", state=state)


@app.route("/preview-change", methods=["POST"])
@login_required
def preview_change():
    data = request.json
    current = load_config()
    patch = build_patch(data.get("section"), data.get("changes", {}), current)
    after = deep_merge(current, patch)
    diff = compute_diff(current, after)
    return jsonify({
        "diff": diff,
        "patch_json": json.dumps(patch, indent=2, ensure_ascii=False),
    })


@app.route("/apply", methods=["POST"])
@login_required
def apply_route():
    data = request.json
    section = data.get("section")
    changes = data.get("changes", {})

    if section == "permissions":
        applied = fix_permissions()
        return jsonify({"success": True, "applied": applied, "backup": None})

    current = load_config()
    patch = build_patch(section, changes, current)

    if not patch:
        return jsonify({"success": False, "error": "Nenhuma alteração gerada para a seção: " + section})

    after = deep_merge(current, patch)
    diff = compute_diff(current, after)

    if not diff:
        return jsonify({"success": True, "applied": [], "message": "Configuração já estava correta.", "backup": None})

    try:
        backup_path = save_config(after)
    except Exception as e:
        return jsonify({"success": False, "error": f"Erro ao salvar: {e}"})

    applied = [f"{d['path']}: {json.dumps(d['before'])} → {json.dumps(d['after'])}" for d in diff]
    return jsonify({"success": True, "applied": applied, "backup": backup_path, "diff": diff})


@app.route("/run-cmd", methods=["POST"])
@login_required
def run_cmd():
    data = request.json or {}
    cmd_type = data.get("type", "audit")
    deep     = data.get("deep", False)

    CMD_MAP = {
        "audit":          ["openclaw", "security", "audit"] + (["--deep"] if deep else []),
        "doctor":         ["openclaw", "doctor"],
        "sandbox_explain":["openclaw", "sandbox", "explain"],
        "nono_check":     ["nono", "setup", "--check-only"],
        "nono_ps":        ["nono", "ps"],
    }
    cmd = CMD_MAP.get(cmd_type)
    if not cmd:
        return jsonify({"output": f"Tipo desconhecido: {cmd_type}"})

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        output = result.stdout or result.stderr or "(sem saída)"
    except FileNotFoundError:
        output = f"⚠️ '{cmd[0]}' não encontrado no PATH."
    except subprocess.TimeoutExpired:
        output = "⚠️ Timeout após 30s."
    except Exception as e:
        output = f"Erro: {e}"
    return jsonify({"output": output})


# Keep old route for compatibility
@app.route("/run-audit", methods=["POST"])
@login_required
def run_audit():
    deep = (request.json or {}).get("deep", False)
    return run_cmd.__wrapped__() if hasattr(run_cmd,'__wrapped__') else jsonify({"output":"use /run-cmd"})




_ERROR_PATTERNS = [
    (
        "docker",
        [
            # Windows Docker Desktop
            "dockerDesktopLinuxEngine", "docker API", "npipe", "dockerd",
            # Linux Docker daemon
            "dial unix", "/var/run/docker.sock", "/run/docker.sock",
            "docker.sock", "unix://", "Is the docker daemon running",
            "Cannot connect to the Docker daemon",
            # Generic container runtime
            "podman.sock", "containerd",
        ],
        "Docker / container runtime não está acessível",
        "O sandbox tenta conectar ao daemon Docker (ou Podman). "
        "Linux: verifique se o serviço está ativo com 'systemctl status docker' e se o usuário está no grupo 'docker'. "
        "Windows: inicie o Docker Desktop e aguarde o engine Linux ficar ativo. "
        "Ou desative o sandbox no config.",
    ),
    (
        "permission",
        ["EACCES", "permission denied", "acesso negado", "Access is denied",
         "Operation not permitted", "EPERM"],
        "Permissão negada",
        "O processo não tem permissão para acessar o recurso. "
        "Linux: verifique as permissões do arquivo/socket (ex: 'ls -la /var/run/docker.sock') "
        "ou adicione o usuário ao grupo correto ('usermod -aG docker $USER'). "
        "Windows: execute como administrador.",
    ),
    (
        "network",
        ["ECONNREFUSED", "connection refused", "ETIMEDOUT", "ENOTFOUND",
         "connection reset by peer", "broken pipe", "no route to host"],
        "Falha de rede",
        "A conexão foi recusada ou expirou. Verifique se o serviço alvo está rodando e acessível.",
    ),
    (
        "notfound",
        ["ENOENT", "no such file", "não pode encontrar o arquivo",
         "cannot find the file", "no such file or directory"],
        "Arquivo ou socket não encontrado",
        "Um arquivo ou socket necessário não existe. "
        "Linux: verifique se o serviço dependente está em execução ('systemctl status docker'). "
        "Verifique também se o socket existe em /var/run/docker.sock ou /run/docker.sock.",
    ),
]

def _diagnose(message: str) -> dict | None:
    msg_lower = message.lower()
    for key, keywords, title, explanation in _ERROR_PATTERNS:
        if any(kw.lower() in msg_lower for kw in keywords):
            return {"key": key, "title": title, "explanation": explanation}
    return None


@app.route("/docker/status")
@login_required
def docker_status():
    """Check if Docker (or Podman) daemon is reachable on this machine."""
    import platform
    running = False
    engine  = None
    detail  = None
    _sys    = platform.system()

    # ── 1. Try docker CLI first ──────────────────────────────────────────────
    try:
        result = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            capture_output=True, text=True, timeout=6,
        )
        if result.returncode == 0 and result.stdout.strip():
            running = True
            engine  = "docker"
            detail  = f"v{result.stdout.strip()}"
        else:
            detail = (result.stderr or "docker info falhou").strip().splitlines()[0]
    except FileNotFoundError:
        detail = "Executável 'docker' não encontrado no PATH."
    except subprocess.TimeoutExpired:
        detail = "Timeout ao conectar ao daemon Docker (>6s)."
    except Exception as e:
        detail = str(e)

    # ── 2. If docker not running, try Podman as fallback (Linux / macOS) ─────
    podman_running = False
    if not running and _sys in ("Linux", "Darwin"):
        try:
            pr = subprocess.run(
                ["podman", "info", "--format", "{{.Version.Version}}"],
                capture_output=True, text=True, timeout=6,
            )
            if pr.returncode == 0 and pr.stdout.strip():
                podman_running = True
                engine = "podman"
                detail = f"Podman v{pr.stdout.strip()} (Docker-compatible)"
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            pass

    # ── 3. Platform-specific socket / pipe probes ─────────────────────────────
    pipe_status   = None   # Windows named pipes
    socket_status = None   # Linux/macOS unix sockets

    if _sys == "Windows":
        pipes = {
            "dockerDesktopLinuxEngine": r"\\.\pipe\dockerDesktopLinuxEngine",
            "docker_engine":            r"\\.\pipe\docker_engine",
            "podman":                   r"\\.\pipe\podman-desktop-companion-podman-socket",
        }
        found = [name for name, path in pipes.items() if Path(path).exists()]
        pipe_status = found if found else None

    elif _sys == "Linux":
        uid = os.getuid() if hasattr(os, "getuid") else 0
        sockets = {
            "docker (system)":    "/var/run/docker.sock",
            "docker (run)":       "/run/docker.sock",
            "docker (desktop)":   str(Path.home() / ".docker" / "desktop" / "docker.sock"),
            "podman (system)":    "/run/podman/podman.sock",
            f"podman (user {uid})": f"/run/user/{uid}/podman/podman.sock",
        }
        found = [name for name, path in sockets.items() if Path(path).exists()]
        socket_status = found if found else None

    elif _sys == "Darwin":
        uid = os.getuid() if hasattr(os, "getuid") else 0
        sockets = {
            "docker (desktop)": str(Path.home() / ".docker" / "run" / "docker.sock"),
            "colima":           str(Path.home() / ".colima" / "docker.sock"),
            f"podman (user {uid})": f"/run/user/{uid}/podman/podman.sock",
        }
        found = [name for name, path in sockets.items() if Path(path).exists()]
        socket_status = found if found else None

    return jsonify({
        "running":        running or podman_running,
        "engine":         engine,
        "detail":         detail,
        "platform":       _sys,
        "pipes":          pipe_status,
        "sockets":        socket_status,
    })


@app.route("/gateway/errors")
@login_required
def gateway_errors():
    """Return today's error-level lines from the gateway log file, with diagnosis."""
    import tempfile
    log_dir = Path(tempfile.gettempdir()) / "openclaw"
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = log_dir / f"openclaw-{today}.log"
    if not log_file.exists():
        return jsonify({"errors": [], "log_file": str(log_file), "found": False})
    errors = []
    try:
        with open(log_file, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("level") == "error":
                        msg = entry.get("message", line)
                        errors.append({
                            "time":      entry.get("time", ""),
                            "subsystem": entry.get("subsystem", ""),
                            "message":   msg,
                            "diagnosis": _diagnose(msg),
                        })
                except json.JSONDecodeError:
                    if '"level":"error"' in line or '"level": "error"' in line:
                        errors.append({"time": "", "subsystem": "", "message": line, "diagnosis": _diagnose(line)})
    except Exception as e:
        return jsonify({"errors": [], "log_file": str(log_file), "found": True, "read_error": str(e)})
    return jsonify({"errors": errors[-100:], "log_file": str(log_file), "found": True})


@app.route("/config")
@login_required
def config_view():
    return jsonify(load_config())


@app.route("/compare")
@login_required
def compare_configs():
    """Return a field-level diff between two configs (backup names or 'current')."""
    a_name = request.args.get("a", "current")
    b_name = request.args.get("b", "current")

    def _load_named(name: str):
        if name == "current":
            return load_config()
        src = BACKUP_DIR / name
        if not src.exists():
            return None
        with open(src, encoding="utf-8") as f:
            return json.load(f)

    cfg_a = _load_named(a_name)
    cfg_b = _load_named(b_name)
    if cfg_a is None:
        return jsonify({"error": f"Backup não encontrado: {a_name}"}), 404
    if cfg_b is None:
        return jsonify({"error": f"Backup não encontrado: {b_name}"}), 404

    diff = compute_diff(cfg_a, cfg_b)
    return jsonify({"diff": diff, "a": a_name, "b": b_name, "total": len(diff)})


@app.route("/backups")
@login_required
def list_backups():
    if not BACKUP_DIR.exists():
        return jsonify([])
    files = sorted(BACKUP_DIR.glob("openclaw_*.json"), reverse=True)
    return jsonify([{"name": f.name, "mtime": f.stat().st_mtime} for f in files[:10]])


SAFE_BACKUP_RE = re.compile(r"^openclaw_\d{8}_\d{6}\.json$")


@app.route("/restore/<backup_name>", methods=["POST"])
@login_required
def restore_backup(backup_name):
    if not SAFE_BACKUP_RE.match(backup_name):
        return jsonify({"success": False, "error": "Nome de backup inválido."}), 400
    src = (BACKUP_DIR / backup_name).resolve()
    try:
        src.relative_to(BACKUP_DIR.resolve())
    except ValueError:
        return jsonify({"success": False, "error": "Acesso negado."}), 403
    if not src.exists():
        return jsonify({"success": False, "error": "Backup não encontrado."})
    try:
        with open(src, encoding="utf-8") as f:
            cfg = json.load(f)
        save_config(cfg)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ---------------------------------------------------------------------------
# nono — kernel-level sandbox (Landlock on Linux, Seatbelt on macOS)
# ---------------------------------------------------------------------------

NONO_SYSTEMD_TEMPLATE = """\
[Unit]
Description=OpenClaw Gateway (sandboxed via nono)
After=network.target

[Service]
Type=simple
User={user}
WorkingDirectory={workdir}
ExecStart={nono_bin} run {nono_flags} -- openclaw gateway
Restart=on-failure
RestartSec=5s
Environment=HOME={home}

[Install]
WantedBy=multi-user.target
"""


def check_nono() -> dict:
    """Check nono installation and kernel support."""
    result = {"installed": False, "version": None, "kernel_support": None, "platform": None}
    import platform
    result["platform"] = platform.system()

    try:
        out = subprocess.run(["nono", "--version"], capture_output=True, text=True, timeout=5)
        if out.returncode == 0:
            result["installed"] = True
            result["version"] = out.stdout.strip() or out.stderr.strip()
    except FileNotFoundError:
        pass
    except Exception:
        pass

    # Check Landlock support on Linux (requires kernel >= 5.13)
    if result["platform"] == "Linux":
        try:
            kver = platform.release().split("-")[0]
            major, minor = int(kver.split(".")[0]), int(kver.split(".")[1])
            result["kernel_support"] = (major, minor) >= (5, 13)
            result["kernel_version"] = kver
        except Exception:
            result["kernel_support"] = None
    elif result["platform"] == "Darwin":
        result["kernel_support"] = True  # Seatbelt always available on macOS

    return result


def build_nono_command(opts: dict) -> str:
    """Build the nono run command from UI options."""
    parts = ["nono", "run"]

    profile = opts.get("profile", "")
    if profile == "openclaw":
        parts += ["--profile", "openclaw"]
    elif profile == "custom":
        # Read paths
        for rp in opts.get("read_paths", []):
            rp = rp.strip()
            if rp:
                parts += ["--read", rp]
        # Write paths
        for wp in opts.get("write_paths", []):
            wp = wp.strip()
            if wp:
                parts += ["--write", wp]
        # Network
        net = opts.get("network", "block")
        if net == "block":
            parts.append("--net-block")
        elif net == "allow":
            for domain in opts.get("allowed_domains", []):
                domain = domain.strip()
                if domain:
                    parts += ["--allow-host", domain]

    # Rollback / snapshots
    if opts.get("rollback"):
        parts.append("--rollback")

    # Detached mode
    if opts.get("detached"):
        parts.append("--detached")

    parts += ["--", "openclaw", "gateway"]
    return " ".join(parts)


def build_nono_systemd(opts: dict) -> str:
    import getpass
    import platform
    if platform.system() != "Linux":
        return "# systemd está disponível apenas no Linux.\n# No Windows use o Task Scheduler; no macOS use launchd."
    nono_bin = subprocess.run(["which", "nono"], capture_output=True, text=True).stdout.strip() or "/usr/local/bin/nono"
    flags_parts = []

    profile = opts.get("profile", "")
    if profile == "openclaw":
        flags_parts += ["--profile", "openclaw"]
    else:
        for rp in opts.get("read_paths", []):
            rp = rp.strip()
            if rp:
                flags_parts += ["--read", rp]
        for wp in opts.get("write_paths", []):
            wp = wp.strip()
            if wp:
                flags_parts += ["--write", wp]
        if opts.get("network", "block") == "block":
            flags_parts.append("--net-block")

    if opts.get("rollback"):
        flags_parts.append("--rollback")

    return NONO_SYSTEMD_TEMPLATE.format(
        user=getpass.getuser(),
        workdir=str(Path.home()),
        nono_bin=nono_bin,
        nono_flags=" ".join(flags_parts),
        home=str(Path.home()),
    )


@app.route("/platform/info")
@login_required
def platform_info():
    """Return basic platform metadata so the UI can adapt per OS."""
    import platform
    _sys = platform.system()
    return jsonify({
        "os":      _sys,                          # "Linux" | "Windows" | "Darwin"
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "is_linux":   _sys == "Linux",
        "is_windows": _sys == "Windows",
        "is_mac":     _sys == "Darwin",
        "config_path": str(CONFIG_PATH),
        "openclaw_dir": str(OPENCLAW_DIR),
    })


@app.route("/nono/status")
@login_required
def nono_status():
    return jsonify(check_nono())


@app.route("/nono/preview", methods=["POST"])
@login_required
def nono_preview():
    opts = request.json or {}
    cmd = build_nono_command(opts)
    systemd = build_nono_systemd(opts) if opts.get("include_systemd") else None
    return jsonify({"command": cmd, "systemd": systemd})


@app.route("/nono/install-check", methods=["POST"])
@login_required
def nono_install_check():
    """Run nono setup --check-only to verify sandbox feature coverage."""
    try:
        out = subprocess.run(
            ["nono", "setup", "--check-only"],
            capture_output=True, text=True, timeout=15
        )
        output = out.stdout or out.stderr or "(sem saída)"
    except FileNotFoundError:
        import platform
        _sys = platform.system()
        if _sys == "Linux":
            output = (
                "⚠️ nono não encontrado no PATH.\n\n"
                "Ubuntu / Debian:\n"
                "  sudo apt update && sudo apt install nono\n\n"
                "Via Cargo (Rust):\n"
                "  cargo install nono\n\n"
                "Verifique suporte a Landlock (kernel ≥ 5.13):\n"
                "  uname -r"
            )
        elif _sys == "Darwin":
            output = "⚠️ nono não encontrado.\n\nInstale com:\n  brew install nono\n  cargo install nono"
        else:
            output = "⚠️ nono não encontrado no PATH."
    except Exception as e:
        output = f"Erro: {e}"
    return jsonify({"output": output})


@app.route("/nono/run-check", methods=["POST"])
@login_required
def nono_run_check():
    """Run nono inspect on the openclaw process if running."""
    try:
        out = subprocess.run(
            ["nono", "ps"],
            capture_output=True, text=True, timeout=10
        )
        output = out.stdout or out.stderr or "(nenhuma sessão ativa)"
    except FileNotFoundError:
        output = "⚠️ nono não encontrado."
    except Exception as e:
        output = f"Erro: {e}"
    return jsonify({"output": output})


PROFILE_META = {
    "personal": {
        "tagline": "Desenvolvedor individual — usabilidade com segurança básica",
        "use_case": "Projetos pessoais, home office, desenvolvimento local",
        "tools_enabled": ["Git (status/diff/add/commit/log)", "npm test / npm run / npx", "Leitura de todos os arquivos", "Edição em ~/projetos/**"],
        "tools_restricted": ["sudo", "rm -rf", "curl / wget", "SSH", "npm install / pip install", "Arquivos .env / .aws / .ssh"],
        "highlights": ["DM por pairing em todos os canais", "Sandbox non-main / session", "Ferramentas elevadas desabilitadas", "tools.profile: standard"],
        "channels": "pairing",
        "sandbox": "non-main / session",
    },
    "team": {
        "tagline": "Servidor compartilhado — restrições para ambientes multi-usuário",
        "use_case": "Repositórios compartilhados, CI/CD interno, squads de desenvolvimento",
        "tools_enabled": ["Git (sem push/force)", "npm test / build / lint", "Leitura restrita de código"],
        "tools_restricted": ["sudo / rm", "curl / wget / SSH / SCP / NC", "npm install", "git push / git reset --hard", "Agent(*)", "WebFetch(*)"],
        "highlights": ["DM por allowlist", "Todos os plugins bloqueados", "Sandbox all / agent", "tools.profile: restricted", "Logs totalmente redatados"],
        "channels": "allowlist",
        "sandbox": "all / agent",
    },
    "enterprise": {
        "tagline": "Produção — conformidade máxima e controle total",
        "use_case": "Ambientes regulados, compliance, IT corporativo, produção",
        "tools_enabled": ["Apenas operações essenciais de leitura"],
        "tools_restricted": ["sudo / chmod / chown", "curl / wget / SSH / SCP / NC / nmap", "npm install / pip install", "Write em /etc /usr /bin /.ssh /.aws /.gnupg", ".env / credentials / secrets / *.pem / *.key", "WebFetch(*) / Agent(*)"],
        "highlights": ["DM scope: none", "tools.profile: minimal", "Plugins bloqueados", "Sandbox all / agent", "Log level: warn — consoleLevel: error"],
        "channels": "allowlist",
        "sandbox": "all / agent",
    },
    "devops": {
        "tagline": "CI/CD e infraestrutura — acesso controlado a ferramentas DevOps",
        "use_case": "GitHub, GitLab, MongoDB, Azure DevOps, Docker, Kubernetes, Terraform",
        "tools_enabled": ["Git completo (fetch/pull/checkout/branch)", "GitHub CLI — gh pr / issue / run / workflow", "GitLab CLI — glab mr / issue / ci", "Docker ps / logs (somente leitura)", "kubectl get / describe / logs (somente leitura)", "mongosh --eval", "terraform plan / validate / fmt", "az devops / az pipelines", "npm / pytest"],
        "tools_restricted": ["docker run / docker exec", "kubectl delete / kubectl exec", "terraform apply / destroy", "git push --force / push para main", "az login", "curl / wget / SSH", "npm install / pip install", "Credenciais / secrets / .pem / .key"],
        "highlights": ["tools.profile: restricted", "CI/CD read-only", "Infra somente leitura", "DM por pairing", "Sandbox non-main / session"],
        "channels": "pairing",
        "sandbox": "non-main / session",
    },
}


@app.route("/profiles")
@login_required
def profiles():
    cfg = load_config()
    result = {}
    for name, builder_key in [
        ("personal",   "personal_preset"),
        ("team",       "team_preset"),
        ("enterprise", "enterprise_preset"),
        ("devops",     "devops_preset"),
    ]:
        patch = build_patch(builder_key, {}, cfg)
        after = deep_merge(cfg, patch)
        diff = compute_diff(cfg, after)
        result[name] = {
            "diff": diff,
            "change_count": len(diff),
            "config": after,
            "meta": PROFILE_META.get(name, {}),
        }
    return jsonify(result)


# ---------------------------------------------------------------------------
# Checklist — security guide recommendations vs current config
# ---------------------------------------------------------------------------

CHECKLIST_ITEMS = [
    # (key, label, criticality, description, checker_fn)
    # checker_fn(cfg) -> bool: True = done/ok
    {
        "key": "deny_sudo",
        "label": "Deny Bash(sudo *)",
        "criticality": "critical",
        "description": "Previne escalonamento de privilégios via sudo.",
        "guide_ref": "C3",
    },
    {
        "key": "deny_curl_wget",
        "label": "Deny Bash(curl/wget *)",
        "criticality": "critical",
        "description": "Bloqueia exfiltração de dados e download de payloads maliciosos.",
        "guide_ref": "C3",
    },
    {
        "key": "deny_rm_rf",
        "label": "Deny Bash(rm -rf *)",
        "criticality": "critical",
        "description": "Previne destruição acidental ou maliciosa de arquivos.",
        "guide_ref": "C3",
    },
    {
        "key": "deny_env",
        "label": "Deny Bash(env) / Bash(printenv)",
        "criticality": "high",
        "description": "Impede leitura de variáveis de ambiente (API keys, tokens).",
        "guide_ref": "C3",
    },
    {
        "key": "deny_ssh",
        "label": "Deny Bash(ssh/scp *)",
        "criticality": "high",
        "description": "Bloqueia acesso a sistemas remotos via SSH.",
        "guide_ref": "C3",
    },
    {
        "key": "deny_env_files",
        "label": "Deny Read(**/.env*)",
        "criticality": "high",
        "description": "Protege arquivos .env com segredos e credenciais.",
        "guide_ref": "A3",
    },
    {
        "key": "deny_aws_ssh_read",
        "label": "Deny Read(~/.aws/**) / Read(~/.ssh/**)",
        "criticality": "critical",
        "description": "Protege credenciais AWS e chaves SSH de leitura pelo agente.",
        "guide_ref": "A3",
    },
    {
        "key": "deny_pkg_install",
        "label": "Deny npm install / pip install",
        "criticality": "high",
        "description": "Previne slopsquatting e ataques de supply chain via pacotes.",
        "guide_ref": "A4",
    },
    {
        "key": "gateway_bind_loopback",
        "label": "Gateway bind = loopback",
        "criticality": "critical",
        "description": "Garante que o gateway só aceita conexões locais.",
        "guide_ref": "gateway",
    },
    {
        "key": "gateway_auth_token",
        "label": "Gateway auth mode = token",
        "criticality": "critical",
        "description": "Requer autenticação por token para acessar o gateway.",
        "guide_ref": "gateway",
    },
    {
        "key": "gateway_token_set",
        "label": "Gateway auth token configurado",
        "criticality": "critical",
        "description": "Token de autenticação definido (não vazio).",
        "guide_ref": "gateway",
    },
    {
        "key": "sandbox_enabled",
        "label": "Sandbox mode ativo (non-main ou all)",
        "criticality": "critical",
        "description": "Isola agentes em sandbox para limitar impacto de comprometimento.",
        "guide_ref": "A1",
    },
    {
        "key": "sandbox_workspace_none",
        "label": "Sandbox workspaceAccess = none ou ro",
        "criticality": "high",
        "description": "Limita acesso do agente ao workspace.",
        "guide_ref": "A1",
    },
    {
        "key": "log_redact",
        "label": "Log redactSensitive configurado",
        "criticality": "high",
        "description": "Redacta informações sensíveis nos logs.",
        "guide_ref": "logging",
    },
    {
        "key": "mdns_safe",
        "label": "mDNS mode = minimal ou off",
        "criticality": "low",
        "description": "Reduz exposição via descoberta de rede local.",
        "guide_ref": "discovery",
    },
    {
        "key": "dm_pairing",
        "label": "DM Policy = pairing ou allowlist (todos os canais)",
        "criticality": "high",
        "description": "Evita que qualquer pessoa envie mensagens diretas ao agente.",
        "guide_ref": "channels",
    },
    {
        "key": "elevated_disabled",
        "label": "Elevated tools desabilitado",
        "criticality": "high",
        "description": "Desativa ferramentas com privilégios elevados por padrão.",
        "guide_ref": "agents",
    },
]


def _check_checklist_item(key: str, cfg: dict) -> bool:
    """Return True if the checklist item is satisfied by the current config."""
    deny = _get(cfg, "tools", "deny", default=[]) or []
    deny_str = " ".join(deny).lower()

    checks = {
        "deny_sudo":           lambda: any("sudo" in d.lower() for d in deny),
        "deny_curl_wget":      lambda: _tools_deny_contains(cfg, "curl", "wget"),
        "deny_rm_rf":          lambda: any("rm" in d.lower() for d in deny),
        "deny_env":            lambda: _tools_deny_contains(cfg, "printenv", "bash(env)"),
        "deny_ssh":            lambda: _tools_deny_contains(cfg, "bash(ssh", "bash(scp"),
        "deny_env_files":      lambda: _tools_deny_contains(cfg, ".env"),
        "deny_aws_ssh_read":   lambda: _tools_deny_contains(cfg, ".aws", ".ssh"),
        "deny_pkg_install":    lambda: _tools_deny_contains(cfg, "npm install", "pip install"),
        "gateway_bind_loopback": lambda: _get(cfg, "gateway", "bind", default="") in ("loopback", "tailnet"),
        "gateway_auth_token":  lambda: _get(cfg, "gateway", "auth", "mode", default="") in ("token", "password"),
        "gateway_token_set":   lambda: bool(_get(cfg, "gateway", "auth", "token", default="")),
        "sandbox_enabled":     lambda: _get(cfg, "agents", "defaults", "sandbox", "mode", default="") in ("non-main", "all"),
        "sandbox_workspace_none": lambda: _get(cfg, "agents", "defaults", "sandbox", "workspaceAccess", default="") in ("none", "ro"),
        "log_redact":          lambda: _get(cfg, "logging", "redactSensitive", default="") in ("tools", "all"),
        "mdns_safe":           lambda: _get(cfg, "discovery", "mdns", "mode", default="") in ("minimal", "off"),
        "dm_pairing":          lambda: all(
            _get(cfg, "channels", ch[0], *ch[1:], default="") in ("pairing", "allowlist")
            for ch in [
                ("whatsapp", "dmPolicy"),
                ("telegram", "dmPolicy"),
                ("discord", "dm", "policy"),
            ]
        ),
        "elevated_disabled":   lambda: _get(cfg, "agents", "defaults", "tools", "elevated", "enabled", default=None) is False,
    }

    checker = checks.get(key)
    if checker is None:
        return False
    try:
        return bool(checker())
    except Exception:
        return False


@app.route("/checklist")
@login_required
def checklist():
    cfg = load_config()
    by_criticality = {"critical": [], "high": [], "medium": [], "low": []}

    for item in CHECKLIST_ITEMS:
        done = _check_checklist_item(item["key"], cfg)
        entry = {
            "key":          item["key"],
            "label":        item["label"],
            "description":  item["description"],
            "guide_ref":    item["guide_ref"],
            "status":       "ok" if done else "pending",
            "done":         done,
        }
        bucket = item.get("criticality", "low")
        by_criticality.setdefault(bucket, []).append(entry)

    total = sum(len(v) for v in by_criticality.values())
    done_count = sum(1 for v in by_criticality.values() for e in v if e["done"])

    return jsonify({
        "by_criticality": by_criticality,
        "total": total,
        "done": done_count,
        "pending": total - done_count,
        "score_pct": round(done_count / total * 100) if total else 0,
    })


# ---------------------------------------------------------------------------
# System metrics
# ---------------------------------------------------------------------------

def _get_metrics_linux() -> dict:
    """Read metrics from /proc on Linux without psutil."""
    metrics = {}
    try:
        with open("/proc/meminfo") as f:
            mem = {line.split(":")[0].strip(): int(line.split(":")[1].strip().split()[0])
                   for line in f if ":" in line}
        total = mem.get("MemTotal", 0)
        avail = mem.get("MemAvailable", 0)
        used  = total - avail
        metrics["ram_total_mb"] = round(total / 1024)
        metrics["ram_used_mb"]  = round(used  / 1024)
        metrics["ram_pct"]      = round(used / total * 100) if total else 0
    except Exception:
        pass
    try:
        with open("/proc/loadavg") as f:
            parts = f.read().split()
        metrics["load_1m"]  = float(parts[0])
        metrics["load_5m"]  = float(parts[1])
        metrics["load_15m"] = float(parts[2])
        metrics["procs"]    = parts[3]
    except Exception:
        pass
    try:
        out = subprocess.run(["df", "-BM", "/"], capture_output=True, text=True, timeout=5)
        parts = out.stdout.strip().splitlines()[-1].split()
        metrics["disk_total_gb"] = round(int(parts[1].rstrip("M")) / 1024, 1)
        metrics["disk_used_gb"]  = round(int(parts[2].rstrip("M")) / 1024, 1)
        metrics["disk_pct"]      = int(parts[4].rstrip("%"))
    except Exception:
        pass
    try:
        with open("/proc/uptime") as f:
            secs = float(f.read().split()[0])
        days, rem = divmod(int(secs), 86400)
        hrs, rem  = divmod(rem, 3600)
        mins      = rem // 60
        metrics["uptime"] = f"{days}d {hrs}h {mins}m" if days else f"{hrs}h {mins}m"
    except Exception:
        pass
    return metrics


@app.route("/api/metrics")
@login_required
def api_metrics():
    if _psutil:
        try:
            vm   = _psutil.virtual_memory()
            disk = _psutil.disk_usage("/")
            cpu  = _psutil.cpu_percent(interval=0.3)
            boot = _psutil.boot_time()
            secs = time.time() - boot
            days, rem = divmod(int(secs), 86400)
            hrs, rem  = divmod(rem, 3600)
            mins      = rem // 60
            return jsonify({
                "ram_total_mb": round(vm.total / 1024 / 1024),
                "ram_used_mb":  round(vm.used  / 1024 / 1024),
                "ram_pct":      vm.percent,
                "cpu_pct":      cpu,
                "disk_total_gb": round(disk.total / 1024**3, 1),
                "disk_used_gb":  round(disk.used  / 1024**3, 1),
                "disk_pct":      disk.percent,
                "uptime": f"{days}d {hrs}h {mins}m" if days else f"{hrs}h {mins}m",
                "source": "psutil",
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    # fallback: Linux /proc
    import platform
    if platform.system() == "Linux":
        m = _get_metrics_linux()
        m["source"] = "proc"
        return jsonify(m)
    return jsonify({"error": "psutil não instalado e plataforma não suportada para fallback"}), 501


# ---------------------------------------------------------------------------
# Pairing approvals
# ---------------------------------------------------------------------------

def _load_pairings() -> dict:
    if PAIRINGS_PATH.exists():
        try:
            with open(PAIRINGS_PATH, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {"pending": [], "approved": [], "blocked": []}


def _save_pairings(data: dict):
    PAIRINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PAIRINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


@app.route("/api/pairings")
@login_required
def api_pairings():
    return jsonify(_load_pairings())


@app.route("/api/pairings/approve", methods=["POST"])
@login_required
def api_pairings_approve():
    req = request.json or {}
    pairing_id = req.get("id")
    if not pairing_id:
        return jsonify({"error": "id obrigatório"}), 400
    data = _load_pairings()
    target = next((p for p in data["pending"] if p.get("id") == pairing_id), None)
    if not target:
        return jsonify({"error": "pairing não encontrado"}), 404
    data["pending"].remove(target)
    target["approved_at"] = datetime.utcnow().isoformat() + "Z"
    data["approved"].append(target)
    _save_pairings(data)
    return jsonify({"ok": True, "pairing": target})


@app.route("/api/pairings/reject", methods=["POST"])
@login_required
def api_pairings_reject():
    req = request.json or {}
    pairing_id = req.get("id")
    if not pairing_id:
        return jsonify({"error": "id obrigatório"}), 400
    data = _load_pairings()
    target = next((p for p in data["pending"] if p.get("id") == pairing_id), None)
    if not target:
        return jsonify({"error": "pairing não encontrado"}), 404
    data["pending"].remove(target)
    target["rejected_at"] = datetime.utcnow().isoformat() + "Z"
    data["blocked"].append(target)
    _save_pairings(data)
    return jsonify({"ok": True, "pairing": target})


if __name__ == "__main__":
    print(f"Config: {CONFIG_PATH}  |  Existe: {CONFIG_PATH.exists()}")
    app.run(debug=os.environ.get("FLASK_DEBUG", "0") == "1", host="127.0.0.1", port=5050)