---
name: openclaw-add-profile
description: Adicionar novo perfil de segurança ao OpenClaw (preset + card UI + metadata)
triggers:
  - adicionar perfil
  - novo perfil
  - novo preset
  - openclaw perfil
argument-hint: "<profile_name> <use_case>"
---

# OpenClaw — Adicionar Perfil de Segurança

## Quando usar

Quando um novo preset de configuração de segurança precisa ser criado para um caso de uso específico (ex: DataScience, Security Researcher, Mobile Dev).

## Checklist de implementação

### 1. `app.py` — criar `_patch_X_preset(current)`
```python
def _patch_X_preset(current: dict) -> dict:
    """X profile — descrição do caso de uso."""
    return {
        "gateway": {"bind": "loopback", "auth": {"mode": "token"}},
        "discovery": {"mdns": {"mode": "minimal"}},  # off para enterprise
        "channels": {
            "whatsapp": {"dmPolicy": "pairing", "groups": {"*": {"requireMention": True}}},
            "telegram": {"dmPolicy": "pairing"},
            "discord":  {"dm": {"policy": "pairing"}},
            "teams":    {"dmPolicy": "pairing"},
        },
        "agents": {
            "defaults": {
                "sandbox": {"mode": "non-main", "scope": "session", "workspaceAccess": "ro"},
                "model": {"primary": "anthropic/claude-opus-4-5"},
                "tools": {"elevated": {"enabled": False}},
            }
        },
        "tools": {
            "allow": [...],  # listar ferramentas específicas do perfil
            "deny":  [...],  # NÃO incluir "profile" — openclaw não reconhece
        },
        "plugins": {"deny": []},       # [] para pessoal, ["*"] para restritivo
        "session": {"dmScope": "contacts"},  # "none" para enterprise
        "logging": {"level": "info", "redactSensitive": "tools"},
    }
```

⚠️ **NUNCA adicionar `"profile": "..."` dentro de `tools`** — openclaw rejeita com `unrecognized key: tools`

### 2. `app.py` — `PATCH_BUILDERS`
```python
"x_preset": lambda changes, current: _patch_x_preset(current),
```

### 3. `app.py` — `build_patch()`
```python
if section == "x_preset":
    return _patch_x_preset(current)
```

### 4. `app.py` — rota `/profiles`
```python
for name, builder_key in [
    ...
    ("x", "x_preset"),   # adicionar aqui
]:
```

### 5. `app.py` — `PROFILE_META`
```python
"x": {
    "tagline": "Descrição curta do perfil",
    "use_case": "Caso de uso específico, ferramentas utilizadas",
    "tools_enabled": ["Ferramenta A", "Ferramenta B (leitura)"],
    "tools_restricted": ["sudo", "rm -rf", "credenciais"],
    "highlights": ["DM por pairing", "Sandbox non-main", "Plugins: lista específica"],
    "channels": "pairing",
    "sandbox": "non-main / session",
},
```

### 6. `index.html` — card do perfil
```html
<div class="profile-card" id="profile-card-x">
  <div class="profile-card-header">
    <span class="profile-card-icon">🔬</span>
    <span class="profile-card-title">Nome do Perfil</span>
  </div>
  <div class="profile-card-desc" id="profile-desc-x">
    Descrição breve.
  </div>
  <div class="profile-card-meta">
    <span class="profile-changes-badge" id="profile-changes-x">— mudanças</span>
    <span class="profile-level-badge" style="background:var(--blue-dim);color:var(--blue)">X</span>
  </div>
  <div class="profile-card-actions">
    <button class="btn-preview" onclick="previewProfile('x')">👁 Pré-visualizar</button>
    <button class="btn-apply"   onclick="applyProfile('x_preset')">Aplicar</button>
  </div>
  <div class="profile-diff-panel" id="profile-diff-x"></div>
</div>
```

## Pitfalls críticos

- `tools.profile` não é reconhecido pelo openclaw — nunca incluir
- Cada preset deve cobrir **todos** os canais (whatsapp, telegram, discord, teams) — senão o deep_merge deixa valores antigos
- O `id="profile-desc-X"` no HTML é obrigatório para `loadProfiles()` popular dinamicamente
- Após adicionar, verificar sintaxe: `python -c "import ast; ast.parse(open('app.py', encoding='utf-8').read())"`
