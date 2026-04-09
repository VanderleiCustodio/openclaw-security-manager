# Profile Mapping — OpenClaw Security Manager

> Worker-1 output for team "openclaw-integration"
> Date: 2026-04-08

---

## 1. Mapping Table: Security Recommendations → openclaw.json Fields

Each row maps a security recommendation from the consolidated guide (official + third-party) to the exact openclaw.json field and the value that satisfies the recommendation.

| # | Recommendation Source | openclaw.json Field | Recommended Value | Risk if Missing | Notes |
|---|----------------------|--------------------|--------------------|-----------------|-------|
| 1 | Official + Third-party | `gateway.bind` | `"loopback"` | critical | Prevents external network exposure of the gateway |
| 2 | Official + Third-party | `gateway.auth.mode` | `"token"` | critical | Token auth is stronger than no auth or password |
| 3 | Official | `gateway.auth.token` | `<non-empty string>` | critical | Must be set; any non-empty value satisfies the check |
| 4 | Official | `gateway.port` | `3000` (personal) / any non-public | low | Avoid well-known ports; loopback binding already mitigates exposure |
| 5 | Official + Third-party | `discovery.mdns.mode` | `"off"` (enterprise) / `"minimal"` (team) / `"full"` (personal) | low | mDNS broadcasts presence on the local network; restrict in shared/prod environments |
| 6 | Official | `channels.whatsapp.dmPolicy` | `"pairing"` (team) / `"allowlist"` (enterprise) / `"open"` (personal) | high | Controls who can initiate DM conversations via WhatsApp |
| 7 | Official | `channels.telegram.dmPolicy` | `"pairing"` (team) / `"allowlist"` (enterprise) / `"open"` (personal) | high | Same rationale as WhatsApp dmPolicy |
| 8 | Official | `channels.discord.dm.policy` | `"pairing"` (team) / `"allowlist"` (enterprise) / `"open"` (personal) | high | Discord DM policy; field path differs from other channels |
| 9 | Official | `channels.whatsapp.groups.*.requireMention` | `true` | medium | Prevents the agent from responding to every group message without being addressed |
| 10 | Official + Third-party | `agents.defaults.sandbox.mode` | `"all"` (enterprise) / `"non-main"` (personal/team) | critical | Controls which agent processes are sandboxed; `"all"` is strictest |
| 11 | Official | `agents.defaults.sandbox.scope` | `"agent"` (enterprise) / `"session"` (personal/team) | medium | `"agent"` scope isolates each agent individually; stronger than session |
| 12 | Official + Third-party | `agents.defaults.sandbox.workspaceAccess` | `"none"` | high | Prevents sandboxed agents from reading/writing the host workspace |
| 13 | Official + Third-party | `tools.profile` | `"minimal"` (enterprise) / `"restricted"` (team) / `"standard"` (personal) | high | Profile controls the set of built-in tools available to agents |
| 14 | Third-party (OWASP) | `tools.deny` | e.g. `["Bash(sudo *)", "Bash(curl *)", ...]` | high | Explicit deny list; supplements or replaces profile when fine-grained control is needed |
| 15 | Third-party | `plugins.deny` | `["*"]` or list of blocked plugins | high | Prevents untrusted plugins from loading; no check exists in current RECOMMENDED dict |
| 16 | Official | `logging.level` | `"warn"` (enterprise) / `"info"` (team) / `"debug"` (personal) | low | Controls verbosity; `"warn"` reduces log noise in production |
| 17 | Official + Third-party | `logging.redactSensitive` | `"all"` (enterprise) / `"tools"` (team) / `"none"` (personal) | high | Redacts secrets from logs; `"all"` is strictest |
| 18 | Official | `logging.consoleLevel` | `"error"` (enterprise) / `"warn"` (team) / `"debug"` (personal) | low | Console output level; not currently checked in RECOMMENDED |
| 19 | Third-party | `logging.file` | absolute path string | low | Persistent audit log file; no check in RECOMMENDED |
| 20 | Official | `agents.defaults.model.primary` | `"anthropic/claude-opus-4-5"` (team/enterprise) / `"anthropic/claude-sonnet-4-5"` (personal) | medium | Stronger models have better instruction-following for safety-critical tasks |
| 21 | Third-party | `agents.defaults.tools.elevated.enabled` | `false` | high | Disabling elevated tools prevents privilege escalation from within an agent session |
| 22 | Official | `session.dmScope` | `"contacts"` or `"none"` | medium | Restricts which users can open DM sessions; not currently in RECOMMENDED |

---

## 2. Three Complete Security Profiles

### PESSOAL (Individual / Local Dev — Usability First)

Suitable for: a single developer running OpenClaw locally, experimenting, no shared access.

```json
{
  "gateway": {
    "bind": "loopback",
    "port": 3000,
    "auth": {
      "mode": "token",
      "token": "<set-your-token>"
    }
  },
  "discovery": {
    "mdns": {
      "mode": "full"
    }
  },
  "channels": {
    "whatsapp": {
      "dmPolicy": "open",
      "groups": {
        "*": {
          "requireMention": false
        }
      }
    },
    "telegram": {
      "dmPolicy": "open"
    },
    "discord": {
      "dm": {
        "policy": "open"
      }
    }
  },
  "agents": {
    "defaults": {
      "sandbox": {
        "mode": "non-main",
        "scope": "session",
        "workspaceAccess": "ro"
      },
      "model": {
        "primary": "anthropic/claude-sonnet-4-5"
      },
      "tools": {
        "elevated": {
          "enabled": false
        }
      }
    }
  },
  "tools": {
    "profile": "standard"
  },
  "plugins": {
    "deny": []
  },
  "logging": {
    "level": "debug",
    "redactSensitive": "none",
    "consoleLevel": "debug"
  }
}
```

**Design rationale:**
- `gateway.bind: loopback` — still enforced; no reason to expose even locally
- `discovery.mdns.mode: full` — convenient for local dev, mDNS lets other local tools find the gateway
- `dmPolicy: open` for all channels — personal use, single user, no shared risk
- `sandbox.mode: non-main` / `scope: session` / `workspaceAccess: ro` — light sandboxing; read-only workspace access lets agents read files without writing
- `tools.profile: standard` — full standard toolset available
- `logging.level: debug` / `redactSensitive: none` — maximum visibility for debugging; acceptable on a personal machine with no other users
- Model: `claude-sonnet-4-5` — faster and cheaper for iterative dev work

---

### EQUIPE (Team / Shared Server — Balanced)

Suitable for: a shared team server, internal tooling, multiple users with different trust levels.

```json
{
  "gateway": {
    "bind": "loopback",
    "auth": {
      "mode": "token",
      "token": "<set-your-token>"
    }
  },
  "discovery": {
    "mdns": {
      "mode": "minimal"
    }
  },
  "channels": {
    "whatsapp": {
      "dmPolicy": "pairing",
      "groups": {
        "*": {
          "requireMention": true
        }
      }
    },
    "telegram": {
      "dmPolicy": "pairing"
    },
    "discord": {
      "dm": {
        "policy": "pairing"
      }
    }
  },
  "agents": {
    "defaults": {
      "sandbox": {
        "mode": "non-main",
        "scope": "session",
        "workspaceAccess": "none"
      },
      "model": {
        "primary": "anthropic/claude-opus-4-5"
      },
      "tools": {
        "elevated": {
          "enabled": false
        }
      }
    }
  },
  "tools": {
    "profile": "restricted"
  },
  "plugins": {
    "deny": ["*"]
  },
  "logging": {
    "level": "info",
    "redactSensitive": "tools",
    "consoleLevel": "warn",
    "file": "/var/log/openclaw/openclaw.jsonl"
  }
}
```

**Design rationale:**
- `discovery.mdns.mode: minimal` — presence advertised minimally; avoids broadcasting on every interface
- `dmPolicy: pairing` for all channels — users must pair before they can DM the agent; prevents unsolicited access
- `requireMention: true` for groups — agent only responds when explicitly addressed, avoids accidental triggers
- `sandbox.workspaceAccess: none` — agents cannot read or write the host workspace; strongest protection for shared servers
- `tools.profile: restricted` — reduced toolset; blocks tools not needed for typical team tasks
- `plugins.deny: ["*"]` — no plugins allowed by default; admins must explicitly allowlist plugins
- `logging.redactSensitive: tools` — tool inputs/outputs are redacted in logs; protects user data from appearing in shared logs
- Model: `claude-opus-4-5` — better instruction following for safer behavior in multi-user environments

---

### ENTERPRISE (Production / Controlled — Maximum Security)

Suitable for: production deployments, regulated environments, enterprise IT control.

```json
{
  "gateway": {
    "bind": "loopback",
    "auth": {
      "mode": "token",
      "token": "<set-your-token>"
    }
  },
  "discovery": {
    "mdns": {
      "mode": "off"
    }
  },
  "channels": {
    "whatsapp": {
      "dmPolicy": "allowlist",
      "groups": {
        "*": {
          "requireMention": true
        }
      }
    },
    "telegram": {
      "dmPolicy": "allowlist"
    },
    "discord": {
      "dm": {
        "policy": "allowlist"
      }
    }
  },
  "agents": {
    "defaults": {
      "sandbox": {
        "mode": "all",
        "scope": "agent",
        "workspaceAccess": "none"
      },
      "model": {
        "primary": "anthropic/claude-opus-4-5"
      },
      "tools": {
        "elevated": {
          "enabled": false
        }
      }
    }
  },
  "tools": {
    "profile": "minimal"
  },
  "plugins": {
    "deny": ["*"]
  },
  "logging": {
    "level": "warn",
    "redactSensitive": "all",
    "consoleLevel": "error",
    "file": "/var/log/openclaw/openclaw.jsonl"
  }
}
```

**Design rationale:**
- `discovery.mdns.mode: off` — zero network presence broadcasting; appropriate for production environments where service discovery must be explicit and controlled
- `dmPolicy: allowlist` for all channels — only pre-approved contacts/accounts can interact; blocks all unsolicited access
- `sandbox.mode: all` — every agent process is sandboxed, not just non-main; maximizes process isolation
- `sandbox.scope: agent` — each agent gets its own isolated sandbox; stronger than session-level isolation
- `sandbox.workspaceAccess: none` — no workspace access from any sandboxed agent
- `tools.profile: minimal` — absolute minimum toolset; every additional tool is an attack surface
- `plugins.deny: ["*"]` — all plugins blocked; explicit allowlist required for any plugin use
- `logging.redactSensitive: all` — all sensitive data redacted from logs; prevents credential leakage in audit trails
- `logging.level: warn` — only warnings and errors logged; reduces log volume and sensitive data exposure
- Model: `claude-opus-4-5` — best instruction-following fidelity; critical for policy compliance in production

---

## 3. Missing RECOMMENDED Items

The current `RECOMMENDED` dict in `app.py` has 15 checks (lines 427–444). Based on the guides, the following items are covered by security recommendations but are **not currently checked**:

### 3.1 tools.profile

**Guide coverage:** Both official and third-party sources emphasize least-privilege toolsets. The `tools.profile` field controls the set of tools available to agents.

**Suggested RECOMMENDED entry:**
```python
"tools_profile": (
    "Tools profile",
    "tools.profile",
    "restricted",
    ["restricted", "minimal"],
    "high"
),
```

**Current state in app.py:** The `_patch_tools` builder and `get_ui_state` already read/write `tools.profile`, but no check exists in `RECOMMENDED`.

---

### 3.2 plugins.deny

**Guide coverage:** Third-party research identified 655 malicious MCP skills/plugins in public repositories (supply chain risk). Blocking untrusted plugins is a high-priority mitigation.

**Suggested RECOMMENDED entry:**
```python
"plugins_deny": (
    "Plugins bloqueados",
    "plugins.deny",
    "<non-empty>",
    [],
    "high"
),
```

**Note:** The safe check here would be: warn if `plugins.deny` is absent or empty. Any non-empty deny list (especially `["*"]`) satisfies the recommendation.

---

### 3.3 logging.consoleLevel

**Guide coverage:** Console log level controls what appears in stdout/stderr. In shared/production environments, `debug` or `info` console output can expose sensitive data to anyone with access to process output.

**Suggested RECOMMENDED entry:**
```python
"log_console_level": (
    "Log consoleLevel",
    "logging.consoleLevel",
    "warn",
    ["warn", "error"],
    "low"
),
```

**Current state:** The `_patch_logging` builder and `get_ui_state` already handle `logging.consoleLevel`, but no RECOMMENDED check exists.

---

### 3.4 agents.defaults.tools.elevated.enabled

**Guide coverage:** Elevated tools represent a privilege escalation vector. Both OWASP Excessive Agency (LLM06) and OpenSSF guidelines recommend disabling elevated permissions by default.

**Suggested RECOMMENDED entry:**
```python
"elevated_enabled": (
    "Elevated tools desabilitados",
    "agents.defaults.tools.elevated.enabled",
    "false",
    ["false"],
    "high"
),
```

**Current state:** The `_patch_tools` builder and `get_ui_state` already read/write `elevated.enabled`, but no RECOMMENDED check exists. The check logic would need to treat absence or `False` as "ok" and `True` as "warn".

---

### 3.5 session.dmScope

**Guide coverage:** The official docs and the existing `get_ui_state` function already read `session.dmScope`, suggesting it is a meaningful security field. Restricting which users can open DM sessions is a medium-risk control.

**Suggested RECOMMENDED entry:**
```python
"dm_scope": (
    "DM scope",
    "session.dmScope",
    "contacts",
    ["contacts", "none"],
    "medium"
),
```

---

### 3.6 Summary Table of Missing Checks

| Key | Field | Recommended Value | Safe Values | Risk | Already in patch builders? |
|-----|-------|-------------------|-------------|------|---------------------------|
| `tools_profile` | `tools.profile` | `"restricted"` | `["restricted", "minimal"]` | high | Yes (`_patch_tools`) |
| `plugins_deny` | `plugins.deny` | `<non-empty>` | any non-empty list | high | Yes (`_patch_plugins`) |
| `log_console_level` | `logging.consoleLevel` | `"warn"` | `["warn", "error"]` | low | Yes (`_patch_logging`) |
| `elevated_enabled` | `agents.defaults.tools.elevated.enabled` | `"false"` | `["false"]` | high | Yes (`_patch_tools`) |
| `dm_scope` | `session.dmScope` | `"contacts"` | `["contacts", "none"]` | medium | No (read-only in `get_ui_state`) |

---

*End of profile-mapping.md — produced by worker-1 for team-lead review.*
