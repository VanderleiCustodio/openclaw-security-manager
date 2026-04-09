# Auth Route Mapping — app.py

**Gerado em:** 2026-04-08
**Arquivo analisado:** `C:/Users/vande/OneDrive/Documents/files/app.py`

---

## Resumo Flask

### Imports Flask presentes (linha 10)
```python
from flask import Flask, jsonify, render_template, request
```
- `Flask` — framework principal
- `jsonify` — respostas JSON
- `render_template` — renderização HTML (usado em `/`)
- `request` — acesso a dados da requisição

### Flask SECRET_KEY
**NÃO configurada.** Nenhuma linha com `SECRET_KEY`, `app.secret_key` ou `app.config['SECRET_KEY']` foi encontrada no arquivo.

### Sessões Flask
**NÃO utilizadas.** Não há imports de `session` do Flask, nem uso de `flask.session` em qualquer rota.

### @login_required
**NÃO existe.** Não há nenhum decorator `@login_required` nem import de Flask-Login ou equivalente.

---

## Mapeamento de Rotas

| # | Rota | Métodos | Acessa/Modifica Config Sensível | Classificação |
|---|------|---------|----------------------------------|---------------|
| 1 | `/` | GET | Lê config completa (inclui gateway token, sandbox, etc.) via `get_ui_state()` | **PROTEGER** |
| 2 | `/security-status` | GET | Lê config e avalia status de segurança (inclui token gateway) | **PROTEGER** |
| 3 | `/preview-change` | POST | Lê config atual e simula patches (inclui seções sensíveis) | **PROTEGER** |
| 4 | `/apply` | POST | **ESCREVE** config no disco (gateway, sandbox, tools, auth token, etc.) | **PROTEGER** |
| 5 | `/run-cmd` | POST | Executa subprocessos: `openclaw`, `nono` | **PROTEGER** |
| 6 | `/run-audit` | POST | Alias de `/run-cmd` (compatibilidade) — executa subprocessos | **PROTEGER** |
| 7 | `/docker/status` | GET | Verifica estado do daemon Docker/Podman (informação de infraestrutura) | **PROTEGER** |
| 8 | `/gateway/errors` | GET | Lê arquivo de log do gateway (pode conter tokens, IPs, erros sensíveis) | **PROTEGER** |
| 9 | `/config` | GET | Expõe config **completa** em JSON (inclui auth token do gateway) | **PROTEGER** |
| 10 | `/compare` | GET | Lê config atual e backups para diff | **PROTEGER** |
| 11 | `/backups` | GET | Lista arquivos de backup (nomes com timestamps) | **PROTEGER** |
| 12 | `/restore/<backup_name>` | POST | **RESTAURA** config a partir de backup (modifica config no disco) | **PROTEGER** |
| 13 | `/platform/info` | GET | Expõe OS, paths de config, diretório openclaw | **PROTEGER** |
| 14 | `/nono/status` | GET | Verifica instalação de nono (informação de infraestrutura) | **PROTEGER** |
| 15 | `/nono/preview` | POST | Gera comandos nono (sandbox) e unidade systemd | **PROTEGER** |
| 16 | `/nono/install-check` | POST | Executa `nono setup --check-only` (subprocesso) | **PROTEGER** |
| 17 | `/nono/run-check` | POST | Executa `nono ps` (subprocesso) | **PROTEGER** |
| 18 | `/profiles` | GET | Lê config e computa diffs para todos os perfis de segurança | **PROTEGER** |
| 19 | `/checklist` | GET | Lê config e avalia checklist de segurança | **PROTEGER** |

---

## Detalhamento por Rota

### 1. `GET /` — index (linha 770)
- **Função:** `index()`
- **Sensível:** Lê config completa via `load_config()` e `get_ui_state()`, que expõe `gateway_auth_token`, `sandbox_mode`, `tools_allow/deny`, etc.
- **Classificação:** PROTEGER

### 2. `GET /security-status` (linha 761)
- **Função:** `security_status()`
- **Sensível:** Lê config completa e verifica token gateway (via `build_status()`).
- **Classificação:** PROTEGER

### 3. `POST /preview-change` (linha 777)
- **Função:** `preview_change()`
- **Sensível:** Lê config atual e permite simular qualquer patch, incluindo seções com `auth_token`.
- **Classificação:** PROTEGER

### 4. `POST /apply` (linha 790)
- **Função:** `apply_route()`
- **Sensível:** **Escrita crítica.** Modifica e persiste config no disco (inclui gateway auth token, sandbox, tools). Também pode chamar `fix_permissions()`.
- **Classificação:** PROTEGER (alta prioridade)

### 5. `POST /run-cmd` (linha 821)
- **Função:** `run_cmd()`
- **Sensível:** Executa subprocessos (`openclaw security audit`, `openclaw doctor`, `nono setup`, `nono ps`). Risco de SSRF/execução indevida se não protegido.
- **Classificação:** PROTEGER (alta prioridade)

### 6. `POST /run-audit` (linha 851)
- **Função:** `run_audit()`
- **Sensível:** Alias de `/run-cmd`. Executa subprocessos.
- **Classificação:** PROTEGER

### 7. `GET /docker/status` (linha 914)
- **Função:** `docker_status()`
- **Sensível:** Executa subprocessos (`docker info`, `podman info`), expõe informações sobre infraestrutura de containers.
- **Classificação:** PROTEGER

### 8. `GET /gateway/errors` (linha 1002)
- **Função:** `gateway_errors()`
- **Sensível:** Lê arquivo de log do gateway (pode conter tokens, IPs, mensagens de erro com dados sensíveis).
- **Classificação:** PROTEGER

### 9. `GET /config` (linha 1036)
- **Função:** `config_view()`
- **Sensível:** Expõe **toda a config em JSON**, incluindo `gateway.auth.token`. É a rota mais crítica para vazamento de credenciais.
- **Classificação:** PROTEGER (prioridade máxima)

### 10. `GET /compare` (linha 1041)
- **Função:** `compare_configs()`
- **Sensível:** Lê config atual e backups (path traversal limitado a `BACKUP_DIR`). Expõe diffs com dados sensíveis.
- **Classificação:** PROTEGER

### 11. `GET /backups` (linha 1067)
- **Função:** `list_backups()`
- **Sensível:** Lista arquivos de backup com nomes e timestamps.
- **Classificação:** PROTEGER

### 12. `POST /restore/<backup_name>` (linha 1075)
- **Função:** `restore_backup(backup_name)`
- **Sensível:** **Escrita crítica.** Restaura config a partir de backup (modifica config no disco).
- **Classificação:** PROTEGER (alta prioridade)

### 13. `GET /platform/info` (linha 1218)
- **Função:** `platform_info()`
- **Sensível:** Expõe OS, versão, paths de config e diretório openclaw. Útil para reconhecimento.
- **Classificação:** PROTEGER

### 14. `GET /nono/status` (linha 1236)
- **Função:** `nono_status()`
- **Sensível:** Informação sobre instalação de nono e suporte a kernel sandbox.
- **Classificação:** PROTEGER

### 15. `POST /nono/preview` (linha 1241)
- **Função:** `nono_preview()`
- **Sensível:** Gera comandos nono e unidades systemd. Executa `which nono` via subprocesso.
- **Classificação:** PROTEGER

### 16. `POST /nono/install-check` (linha 1249)
- **Função:** `nono_install_check()`
- **Sensível:** Executa `nono setup --check-only` (subprocesso).
- **Classificação:** PROTEGER

### 17. `POST /nono/run-check` (linha 1280)
- **Função:** `nono_run_check()`
- **Sensível:** Executa `nono ps` (subprocesso).
- **Classificação:** PROTEGER

### 18. `GET /profiles` (linha 1296)
- **Função:** `profiles()`
- **Sensível:** Lê config e computa diffs para todos os perfis (personal, team, enterprise).
- **Classificação:** PROTEGER

### 19. `GET /checklist` (linha 1482)
- **Função:** `checklist()`
- **Sensível:** Lê config e verifica checklist de segurança (inclui verificação de token).
- **Classificação:** PROTEGER

---

## Conclusão

**Todas as 19 rotas devem ser protegidas com `@login_required`** (ou mecanismo equivalente de autenticação).

Não há nenhuma rota genuinamente pública — até o index `/` expõe informações sensíveis de configuração. As rotas de maior risco crítico são:
1. `GET /config` — expõe config completa incluindo auth token
2. `POST /apply` — modifica config no disco
3. `POST /restore/<backup_name>` — restaura config de backup
4. `POST /run-cmd` e `POST /run-audit` — executam subprocessos no servidor

**Problemas adicionais encontrados:**
- `SECRET_KEY` não configurada — sessões Flask não são seguras/assinadas
- `flask-login` não está importado — nenhum sistema de autenticação existe atualmente
- `app.run(debug=True)` na linha 1514 — modo debug ativo em produção é risco crítico
