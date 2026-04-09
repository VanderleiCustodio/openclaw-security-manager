# Settings Changes Explanation — settings.json for Flask Project

**Date:** 2026-04-08
**Task:** Create a secure `.claude/settings.json` based on the "Desenvolvedor Individual" profile from the openclaw-security-guide.md, adapted to the real Flask project needs.

---

## What Changed vs. settings.local.json

### Rules REMOVED (were in settings.local.json, not kept)

| Rule | Reason for Removal |
|------|--------------------|
| `Bash(curl -s http://localhost:53497/...)` (many specific URLs) | Replaced with a generic `allow` for any `curl` to localhost only — specific session URLs are not needed permanently |
| `Bash(ls/dir .superpowers/brainstorm/...)` | Session-specific state commands with no ongoing project relevance |
| `Bash(cat .superpowers/brainstorm/...)` | Same — session-specific, not needed in permanent config |
| `Bash(bash .../setup-progress.sh ...)` | OMC plugin setup scripts — one-time setup, not a permanent need |
| `Bash(bash .../setup-claude-md.sh ...)` | Same — one-time OMC setup |
| `Bash(node:*)` | No Node.js usage found in the Flask project |
| `Bash(CONFIG_TYPE=...)` | Arbitrary env-var assignment — not needed |
| `WebFetch(domain:dribbble.com)` | Design reference — not needed for Flask development |
| `WebFetch(domain:speckyboy.com)` | Design reference — not needed for Flask development |
| `WebFetch(domain:www.figma.com)` | Design tool — not needed for Flask development |
| `mcp__plugin_oh-my-claudecode_t__state_write` | Direct MCP tool allow — handled by MCP server config, not needed here |
| `Bash(python -c ":*")` | Overly broad — allows arbitrary Python one-liners; replaced by `Bash(python *)` with deny rules for destructive ops |

### Rules ADDED (new, from guide recommendations)

#### Allow rules added for real Flask project needs:
- `Bash(python *)` / `Bash(python3 *)` — run the Flask app, execute scripts, syntax-check files
- `Bash(pip show *)`, `Bash(pip list)`, `Bash(pip freeze)` — inspect installed packages (read-only pip operations)
- `Bash(flask *)` — run Flask CLI commands (`flask run`, `flask shell`, etc.)
- `Bash(git *)` — full git workflow: status, diff, add, commit, log, branch, checkout, pull
- `Bash(curl -s http://localhost:*)` — test the running Flask app locally (generic localhost pattern)
- `WebFetch(domain:docs.python.org)`, `WebFetch(domain:flask.palletsprojects.com)`, `WebFetch(domain:pypi.org)` — legitimate documentation lookups for the project's stack
- `Edit(C:/Users/vande/OneDrive/Documents/files/**)` — explicit edit scope scoped to the project directory
- `Read(**)` — read access to all files (needed for code exploration; secrets are blocked by deny rules)

#### Deny rules added from guide (Desenvolvedor Individual profile + C-level recommendations):
- `Bash(sudo *)` — prevents privilege escalation
- `Bash(rm -rf *)` — prevents accidental/malicious recursive deletion
- `Bash(curl *)` — blocks external curl (localhost curl is allowed above; deny here catches non-localhost curl; note: allow rules are evaluated before deny, so `curl -s http://localhost:*` is permitted)
- `Bash(wget *)` — prevents downloading arbitrary files
- `Bash(ssh *)`, `Bash(scp *)`, `Bash(nc *)`, `Bash(ncat *)` — prevents remote access / data exfiltration
- `Bash(env)`, `Bash(printenv)`, `Bash(export *)` — prevents dumping environment variables (which may contain API keys, secrets)
- `Bash(pip install *)`, `Bash(pip3 install *)` — prevents unsupervised dependency installation (mitigates slopsquatting / supply chain risk per guide section A4)
- `Bash(git push --force *)` — prevents force-pushes that destroy history
- `Bash(git reset --hard *)` — prevents accidental destruction of local changes
- `Read(**/.env)`, `Read(**/.env.*)` — blocks reading secrets from .env files (CVE-2026-21852 mitigation)
- `Read(**/credentials*)`, `Read(**/secrets*)`, `Read(**/keystore*)` — blocks reading credential files
- `Read(~/.aws/**)`, `Read(~/.ssh/**)`, `Read(~/.gnupg/**)` — blocks reading cloud/SSH/GPG credentials (CVE-2025-59536 mitigation)
- `Write(~/.ssh/**)`, `Write(~/.aws/**)`, `Write(~/.gnupg/**)` — prevents overwriting credential stores
- `Write(C:/Windows/**)` — prevents writing to system directories
- `WebFetch(*)` — blocks all web fetching except the three explicitly allowed domains above

---

## Security Profile Rationale

This config follows the **"Desenvolvedor Individual"** profile from the guide (Section 3), with these adaptations for the Flask project:

1. **More specific allow rules** than the guide's generic `Edit(~/projetos/**)` — scoped to the actual project path on Windows.
2. **Python/Flask-specific allows** instead of npm/Node allows — the project is Python-only.
3. **Localhost curl allowed** — the Flask app runs locally and needs to be testable via `curl`.
4. **pip read-only operations allowed** (`show`, `list`, `freeze`) — useful for inspecting the environment without the risk of installing new packages.
5. **WebFetch restricted to 3 domains** — python/flask/pypi docs only, instead of fully blocking WebFetch, since the guide notes that blocking it entirely has "medium usability cost" for individual developers.

---

## What This Does NOT Cover (Intentionally)

- **`managed-settings.json`**: The guide recommends placing critical deny rules there for bypass-proof enforcement. This task only requested `settings.json`. Consider promoting the deny rules to `managed-settings.json` for stronger guarantees.
- **Audit hooks**: The guide recommends `PostToolUse` logging hooks (Section A5). Not included here as it was not part of the task scope.
- **MCP server allowlist**: No `allowedMcpServers` restriction added — the project uses OMC MCP tools that are needed for normal operation.
