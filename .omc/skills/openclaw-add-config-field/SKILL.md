---
name: openclaw-add-config-field
description: Adicionar um novo campo de configuração do openclaw.json ao painel OpenClaw (RECOMMENDED + build_status + presets + UI)
triggers:
  - adicionar campo
  - novo campo config
  - openclaw campo
  - recommended check
argument-hint: "<field_path> <label> <recommended_value> <risk>"
---

# OpenClaw — Adicionar Campo de Configuração

## Quando usar

Sempre que um novo campo do `openclaw.json` precisar aparecer no painel (checklist de segurança, formulário, status).

## Checklist de implementação

### 1. `app.py` — RECOMMENDED dict
```python
"minha_chave": ("Label visível", "campo.path.json", "valor_recomendado", ["val_seguro1", "val_seguro2"], "high"),
```
Risks: `critical`, `high`, `medium`, `low`

### 2. `app.py` — `build_status()` raw dict
```python
"minha_chave": str(_get(cfg, "campo", "path", "json", default="")),
```
Se for verificação de presença (não-vazio), usar sentinela `"<set>"` ou `"<non-empty>"`.

### 3. `app.py` — `build_status()` lógica especial
Adicionar ao bloco `if key in (...)` apenas se não usar `safe_vals`:
```python
elif key == "minha_chave":
    ok = current == "<non-empty>"
```

### 4. `app.py` — `get_ui_state()`
```python
"minha_chave": _get(cfg, "campo", "path", "json", default=""),
```

### 5. `app.py` — todos os presets
Adicionar o campo em cada `_patch_X_preset()` com valor adequado ao perfil:
- `_patch_personal_preset` → valor mais permissivo
- `_patch_team_preset`     → valor intermediário
- `_patch_enterprise_preset` → valor mais restritivo
- `_patch_devops_preset`   → valor adequado ao contexto CI/CD

### 6. `index.html` — seção correspondente
Adicionar input/select/checkbox no HTML da seção onde o campo faz sentido.

## Pitfalls críticos

- **TESTAR se o campo existe no openclaw antes de adicionar** — ex: `tools.profile` foi adicionado mas openclaw não reconhecia, causando erro `unrecognized key`
- Discord usa `channels.discord.dm.policy` (aninhado), outros usam `.dmPolicy` diretamente — verificar path exato
- Campos booleanos: openclaw retorna `False` Python, comparar com `["false", "False"]`
- `plugins.deny = []` (lista vazia) não é o mesmo que ausente — usar verificação `if (_get(...) or [])` para checar se é non-empty

## Validação

```bash
python -c "import ast; ast.parse(open('app.py', encoding='utf-8').read()); print('OK')"
```
