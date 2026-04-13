---
name: openclaw-add-channel
description: Adicionar novo canal de mensagens ao OpenClaw (WhatsApp, Telegram, Discord, Teams, Slack, etc.)
triggers:
  - adicionar canal
  - novo canal
  - openclaw canal
  - slack signal instagram
argument-hint: "<channel_name>"
---

# OpenClaw — Adicionar Canal de Mensagens

## Quando usar

Quando um novo canal de comunicação precisa ser suportado no painel (configuração de dmPolicy, pairing, grupos).

## Checklist de implementação

### 1. `app.py` — `_patch_dm_pairing()`
Adicionar branch no dict retornado:
```python
# Padrão simples (WhatsApp, Telegram, Teams, Slack)
if changes.get("dm_NOMEDOCANAL"):
    patch["channels"]["nomedocanal"] = {"dmPolicy": changes["dm_NOMEDOCANAL"]}

# Discord — path aninhado diferente
if changes.get("dm_discord"):
    patch["channels"]["discord"] = {"dm": {"policy": changes["dm_discord"]}}
```

### 2. `app.py` — `get_ui_state()`
```python
"dm_pairing_nomedocanal": _get(cfg, "channels", "nomedocanal", "dmPolicy", default=""),
```
⚠️ Discord: `_get(cfg, "channels", "discord", "dm", "policy", default="")`

### 3. `app.py` — `RECOMMENDED` dict
```python
"dm_nomedocanal": ("DM Pairing — NomeCanal", "channels.nomedocanal.dmPolicy", "pairing", ["pairing", "allowlist"], "high"),
```

### 4. `app.py` — `build_status()` raw
```python
"dm_nomedocanal": str(_get(cfg, "channels", "nomedocanal", "dmPolicy", default="")),
```

### 5. `app.py` — todos os presets
Adicionar em `_patch_personal_preset`, `_patch_team_preset`, `_patch_enterprise_preset`, `_patch_devops_preset`:
```python
"channels": {
    ...
    "nomedocanal": {"dmPolicy": "pairing"},   # personal/devops
    "nomedocanal": {"dmPolicy": "allowlist"},  # team/enterprise
}
```

### 6. `index.html` — seção Canais
Adicionar campo select com badge de prioridade se necessário:
```html
<label>NomeCanal DM Policy
  <span class="badge-priority">Prioritário</span>
</label>
<select onchange="...">
  <option value="open">open</option>
  <option value="pairing">pairing</option>
  <option value="allowlist">allowlist</option>
</select>
```

### 7. `index.html` — `getDmChanges()`
```javascript
const nc = val('dm_nomedocanal');
if (nc) c.nomedocanal = nc;
```

## Pitfalls críticos

- **Discord é exceção**: usa `channels.discord.dm.policy` (aninhado), não `channels.discord.dmPolicy`
- Testar se o openclaw realmente suporta o canal antes de adicionar
- Ao adicionar badge `.badge-priority`, verificar se o CSS já existe no template
- PROFILE_META em `app.py` precisa ser atualizado para refletir o canal nos highlights dos perfis
