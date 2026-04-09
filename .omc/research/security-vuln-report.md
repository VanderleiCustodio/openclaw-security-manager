# Relatório de Auditoria de Segurança — app.py

**Arquivo auditado:** `C:/Users/vande/OneDrive/Documents/files/app.py` (1514 linhas)
**Escopo:** OWASP Top 10 + vetores específicos Flask
**Auditor:** worker-4 (time openclaw-auth-mapping)
**Data:** 2026-04-08

> **Nota de escopo:** Esta é uma aplicação Flask defensiva — um painel administrativo local (porta 5050) para gerenciar o arquivo de configuração `openclaw.json`. Apesar de rodar em loopback por padrão, possui várias vulnerabilidades sérias que devem ser corrigidas, especialmente porque o aplicativo manipula configurações críticas de segurança e tokens de autenticação.
>
> Em conformidade com as diretrizes, este relatório apenas **analisa** as vulnerabilidades existentes — correções são apresentadas como **recomendações**, não como edições aplicadas ao código.

---

## Resumo Executivo

| Severidade | Quantidade |
|------------|------------|
| CRÍTICO    | 4          |
| ALTO       | 7          |
| MÉDIO      | 4          |
| BAIXO      | 3          |

**Top 3 descobertas mais graves:**

1. **Path Traversal em `/restore/<backup_name>`** (CRÍTICO) — permite ler/sobrescrever arquivos arbitrários fora de `BACKUP_DIR`.
2. **Debug mode ativo em produção** (CRÍTICO) — expõe o Werkzeug debugger com execução remota de código via PIN.
3. **Ausência total de proteção CSRF** (CRÍTICO) — todas as rotas POST manipulam configurações sem token, permitindo cross-site request forgery contra o usuário local.

---

## 1. INJECTION

### 1.1 Path Traversal — `/restore/<backup_name>` [CRÍTICO]

**Linhas afetadas:** 1075–1086

```python
@app.route("/restore/<backup_name>", methods=["POST"])
def restore_backup(backup_name):
    src = BACKUP_DIR / backup_name
    if not src.exists():
        return jsonify({"success": False, "error": "Backup não encontrado."})
    try:
        with open(src, encoding="utf-8") as f:
            cfg = json.load(f)
        save_config(cfg)
```

**Vetor de ataque:**
`backup_name` vem diretamente da URL sem sanitização. O Flask aceita traversal via encoding:
```
POST /restore/..%2F..%2F..%2F..%2FUsers%2Fvande%2F.ssh%2Fid_rsa
POST /restore/..%2F..%2Fetc%2Fpasswd
```
Como `Path("/backup/dir") / "../../etc/passwd"` resolve para `/etc/passwd`, o atacante consegue:
- Ler qualquer arquivo JSON do sistema (via exceção que vaza `str(e)`)
- **Sobrescrever** `openclaw.json` com conteúdo de um arquivo JSON arbitrário do sistema (ainda pior: `save_config` então **escreve** essa configuração maliciosa)

**Risco combinado:** atacante pode apontar `backup_name` para um arquivo JSON controlado em qualquer lugar do FS (ex: `/tmp/evil.json` baixado via outra rota ou já presente) e injetar configuração maliciosa — incluindo remover `tools.deny`, desabilitar sandbox, mudar `gateway.auth.token`.

**Mesma vulnerabilidade em `/compare`** (linhas 1041–1064): `request.args.get("a")` e `"b"` são concatenados a `BACKUP_DIR / name` sem validação, permitindo ler qualquer JSON do sistema.

**Correção recomendada:**
```python
import re
SAFE_BACKUP_RE = re.compile(r"^openclaw_\d{8}_\d{6}\.json$")

@app.route("/restore/<backup_name>", methods=["POST"])
def restore_backup(backup_name):
    if not SAFE_BACKUP_RE.match(backup_name):
        return jsonify({"success": False, "error": "Nome inválido."}), 400
    src = (BACKUP_DIR / backup_name).resolve()
    # Garante que src está dentro de BACKUP_DIR
    try:
        src.relative_to(BACKUP_DIR.resolve())
    except ValueError:
        return jsonify({"success": False, "error": "Path traversal detectado."}), 400
    if not src.exists():
        return jsonify({"success": False, "error": "Backup não encontrado."}), 404
    ...
```

---

### 1.2 Command Injection — `/run-cmd` e `/run-audit` [BAIXO / observação]

**Linhas afetadas:** 821–854, 914–955, 1118–1126, 1249–1293

```python
result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
```

**Análise:** o código usa `subprocess.run` com listas estáticas (`CMD_MAP`) em vez de `shell=True`. O único valor controlado pelo usuário é `cmd_type` (chave de dicionário) e `deep` (boolean). Não há injeção direta de comando.

**Porém**, observa-se que `build_nono_systemd` (linha 1188) faz:
```python
nono_bin = subprocess.run(["which", "nono"], capture_output=True, text=True).stdout.strip()
```
e depois insere `nono_bin` no template systemd via `.format()`. Se um atacante puder manipular o `PATH`, pode apontar `which nono` para um binário malicioso, mas isso requer comprometimento prévio do ambiente — **risco muito baixo**.

**Recomendação:** documentar a suposição de `PATH` confiável; não é exploração remota.

---

## 2. CROSS-SITE SCRIPTING (XSS)

### 2.1 XSS via template Jinja2 — `index.html` [MÉDIO]

**Linhas afetadas:** 770–774

```python
@app.route("/")
def index():
    cfg = load_config()
    state = get_ui_state(cfg)
    return render_template("index.html", state=state)
```

**Análise:** por padrão Jinja2 faz escape HTML automaticamente, o que mitiga XSS refletido via variáveis do `state`. **Porém**, o template `index.html` não foi auditado. Campos como `tools_allow`, `tools_deny`, `gateway_auth_token`, e `model_primary` vêm diretamente do JSON de configuração — se o template usar `{{ var | safe }}` ou `{% autoescape false %}`, qualquer string escrita em `openclaw.json` (que pode ser modificada via a própria UI) vira XSS armazenado.

**Vetor de ataque:**
1. Atacante explora CSRF (ver §3) ou outra rota para escrever `"<script>fetch('/apply',{method:'POST',...})</script>"` no campo `auth_token`.
2. Na próxima visita a `/`, o script é renderizado e executa com contexto do app.

**Correção recomendada:**
- Auditar `templates/index.html` para verificar uso de `| safe` ou `autoescape false`
- Nunca desativar autoescape em campos vindos de `openclaw.json`
- Adicionar header `Content-Security-Policy: default-src 'self'; script-src 'self'`

---

### 2.2 Log de erros retornado diretamente — `/gateway/errors` [MÉDIO]

**Linhas afetadas:** 1002–1033

O conteúdo de `msg` vem de `entry.get("message", line)` — arquivo de log que pode conter bytes arbitrários. Retornado via `jsonify` (seguro contra JSON injection), mas se o frontend usar `innerHTML` em vez de `textContent` para exibir, vira XSS.

**Correção recomendada:** auditar o JS do frontend; preferir `textContent`.

---

## 3. CSRF — CROSS-SITE REQUEST FORGERY

### 3.1 Ausência total de proteção CSRF [CRÍTICO]

**Linhas afetadas:** todas as rotas POST

| Rota                         | Linha | Efeito                                     |
|------------------------------|-------|--------------------------------------------|
| `/preview-change`            | 777   | Leitura (baixo risco)                      |
| `/apply`                     | 790   | **Escreve openclaw.json**                  |
| `/run-cmd`                   | 821   | **Executa subprocess**                     |
| `/run-audit`                 | 851   | Executa subprocess                         |
| `/restore/<backup_name>`     | 1075  | **Sobrescreve openclaw.json**              |
| `/nono/preview`              | 1241  | Leitura                                    |
| `/nono/install-check`        | 1249  | **Executa nono setup**                     |
| `/nono/run-check`            | 1280  | Executa nono ps                            |

**Análise:** nenhuma rota usa `flask-wtf` CSRFProtect nem valida um token. O app roda em `localhost:5050` sem autenticação. Qualquer site que o usuário visite pode fazer:

```html
<form action="http://localhost:5050/apply" method="POST" enctype="text/plain">
  <input name='{"section":"tools","changes":{"deny":""},"x":"' value='"}'>
</form>
<script>document.forms[0].submit()</script>
```

Ou, pior, usando `fetch` com `mode: 'no-cors'`:
```js
fetch('http://localhost:5050/restore/..%2F..%2Fattacker.json', {method:'POST', mode:'no-cors'})
```

**Impacto:** qualquer página web maliciosa que a vítima visitar pode silenciosamente:
- Desabilitar sandbox (`agents.defaults.sandbox.mode = "off"`)
- Remover todos os `tools.deny`
- Mudar `gateway.auth.token` para um conhecido pelo atacante
- Habilitar `elevated tools`
- Combinar com Path Traversal (§1.1) para restaurar backup arbitrário

**Correção recomendada:**
```python
from flask_wtf.csrf import CSRFProtect
app.config["SECRET_KEY"] = os.urandom(32)  # ou carregar de env
csrf = CSRFProtect(app)

# Para APIs JSON, usar header X-CSRFToken via fetch
# OU verificar cabeçalho Origin/Referer:
@app.before_request
def enforce_same_origin():
    if request.method == "POST":
        origin = request.headers.get("Origin", "")
        if not origin.startswith("http://localhost:5050") and \
           not origin.startswith("http://127.0.0.1:5050"):
            abort(403)
```

---

## 4. SECURITY MISCONFIGURATION

### 4.1 Debug mode ativo [CRÍTICO]

**Linha afetada:** 1514

```python
if __name__ == "__main__":
    print(f"Config: {CONFIG_PATH}  |  Existe: {CONFIG_PATH.exists()}")
    app.run(debug=True, port=5050)
```

**Vetor de ataque:**
Com `debug=True`, o Werkzeug expõe um debugger interativo em qualquer exceção. Se um atacante consegue disparar uma exceção (via `/compare?a=null` → `TypeError` no `compute_diff`, ou `/apply` com JSON malformado), pode obter **execução remota de código** via o debugger PIN console. Mesmo com o PIN habilitado, há bypasses conhecidos quando `127.0.0.1` é acessível e o atacante conhece a máquina.

Adicionalmente, `debug=True` expõe stack traces completos com caminhos de arquivo, versões e variáveis locais.

**Correção recomendada:**
```python
if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=5050)
```
E nunca bindar em `0.0.0.0`.

---

### 4.2 SECRET_KEY ausente [ALTO]

**Análise:** o código não define `app.config["SECRET_KEY"]` em lugar algum. Flask usa sessões assinadas com esta chave; sem ela, `flask-wtf` CSRF não funciona, e qualquer extensão que dependa de `itsdangerous` falha. Também impede adicionar proteção CSRF.

**Correção recomendada:**
```python
app.config["SECRET_KEY"] = os.environ.get("OPENCLAW_UI_SECRET") or os.urandom(32)
```

---

### 4.3 Headers HTTP de segurança ausentes [ALTO]

**Análise:** nenhum header de segurança é adicionado às respostas. Faltam:
- `Content-Security-Policy` (mitiga XSS §2)
- `X-Frame-Options: DENY` (mitiga clickjacking — atacante pode embedar `/` em iframe e enganar usuário a clicar em "Apply")
- `Strict-Transport-Security` (N/A para HTTP local, mas útil se expor via proxy)
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: no-referrer`
- `Permissions-Policy`

**Vetor de ataque — clickjacking:**
Sem `X-Frame-Options`, um site malicioso pode:
```html
<iframe src="http://localhost:5050" style="opacity:0.01"></iframe>
<button style="position:absolute;top:X;left:Y">Ganhe um prêmio!</button>
```
enganando o usuário a clicar em botões sensíveis (aplicar preset que remove denylists, etc.).

**Correção recomendada:**
```python
@app.after_request
def set_security_headers(resp):
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
        "frame-ancestors 'none'"
    )
    return resp
```

---

### 4.4 Host bind implícito (0.0.0.0 em Flask >= alguns defaults) [MÉDIO]

**Linha afetada:** 1514

`app.run(debug=True, port=5050)` — Flask 2.x default host é `127.0.0.1`, então OK. Porém, se alguém rodar com `FLASK_RUN_HOST` ou via `flask run --host=0.0.0.0`, o app fica exposto na rede. Não há defesa em profundidade.

**Correção:** forçar explicitamente `host="127.0.0.1"`.

---

## 5. INSECURE DIRECT OBJECT REFERENCE (IDOR)

### 5.1 `/restore/<backup_name>` sem lista branca [ALTO]

**Linhas afetadas:** 1075–1086

Mesmo sem path traversal, o endpoint permite restaurar **qualquer** arquivo dentro de `BACKUP_DIR`. Isso é IDOR clássico: não há validação de que `backup_name` corresponde a um dos 10 backups legítimos listados em `/backups` (linha 1067).

**Vetor:** um atacante que conseguiu colocar um arquivo malicioso em `BACKUP_DIR` (ex: via escrita em outro backup legítimo, ou via symlink em Linux) pode ativá-lo.

**Correção:** validar que `backup_name` está na lista retornada por `BACKUP_DIR.glob("openclaw_*.json")`.

---

### 5.2 `/compare` aceita qualquer nome de backup [ALTO]

**Linhas afetadas:** 1041–1064

Mesmo problema + path traversal (§1.1). `_load_named()` carrega qualquer JSON existente.

---

## 6. SENSITIVE DATA EXPOSURE

### 6.1 Token de autenticação exposto em `/config` e `/` [ALTO]

**Linhas afetadas:** 613, 1036–1038, 774

```python
@app.route("/config")
def config_view():
    return jsonify(load_config())
```

e

```python
"gateway_auth_token": _get(cfg, "gateway", "auth", "token", default=""),
```

**Análise:** a rota `/config` retorna o **conteúdo completo** do `openclaw.json`, incluindo `gateway.auth.token` em texto claro. A rota `/` passa o mesmo token para o template via `state["gateway_auth_token"]`. Qualquer atacante que consiga ler estas respostas (via CSRF no `/`, via XSS, via vazamento de log) obtém o token que dá acesso ao gateway.

Adicionalmente `/security-status` compara apenas `"<set>"` vs vazio (linha 699) — isso é OK — mas `/config` não redacta nada.

**Vetor:** combinado com §3 (CSRF), um site malicioso pode fazer `fetch('/config')` em modo `no-cors` não é útil (resposta opaca), mas via XSS (§2) o token pode ser exfiltrado.

**Correção recomendada:**
```python
SENSITIVE_PATHS = [("gateway", "auth", "token")]

def redact(cfg):
    c = copy.deepcopy(cfg)
    for path in SENSITIVE_PATHS:
        d = c
        for k in path[:-1]:
            d = d.get(k, {}) if isinstance(d, dict) else {}
        if isinstance(d, dict) and d.get(path[-1]):
            d[path[-1]] = "***REDACTED***"
    return c

@app.route("/config")
def config_view():
    return jsonify(redact(load_config()))
```

E no `get_ui_state`, nunca retornar o token em claro — apenas indicar `"set"` ou `""`.

---

### 6.2 Stack traces vazados via `str(e)` [MÉDIO]

**Linhas afetadas:** 815, 940, 1032, 1086, 1276, 1292

```python
except Exception as e:
    return jsonify({"success": False, "error": f"Erro ao salvar: {e}"})
```

Mensagens de exceção podem conter paths completos do FS, versões de bibliotecas e partes do stack. Útil para reconhecimento. Menor que debug mode, mas ainda leakage.

**Correção:** logar o erro completo no servidor, retornar mensagem genérica ao cliente.

---

### 6.3 Log file lido e retornado integralmente [MÉDIO]

**Linhas afetadas:** 1002–1033

`/gateway/errors` lê `openclaw-YYYY-MM-DD.log` inteiro (limitado a últimas 100 entradas) e retorna via JSON. Se o log contiver tokens, chaves API, ou PII (que dependendo de `redactSensitive` podem não estar redactados na origem), isso é exposição. Não há autenticação na rota.

**Correção:** exigir autenticação; re-redactar conhecidos padrões sensíveis na resposta.

---

## 7. BROKEN ACCESS CONTROL

### 7.1 Nenhuma autenticação em todas as rotas [CRÍTICO]

**Análise:** o aplicativo não tem **nenhum** mecanismo de autenticação. Qualquer processo local (ou atacante via CSRF) pode:
- `POST /apply` para alterar `openclaw.json`
- `POST /restore/<x>` para restaurar backups
- `POST /run-cmd` para executar `openclaw security audit`, `nono ps`, etc.
- `GET /config` para vazar tokens

Mesmo sendo bind loopback, processos locais não privilegiados (incluindo outros usuários na mesma máquina multi-user, ou código JS rodando no navegador via CSRF) têm acesso total.

**Correção recomendada:**
- Gerar um token único por sessão no startup, exibir no console
- Exigir `Authorization: Bearer <token>` ou cookie `SameSite=Strict; HttpOnly`
- Validar via `before_request`

---

### 7.2 Ausência de validação de entrada em `/apply` [ALTO]

**Linhas afetadas:** 790–818

```python
data = request.json
section = data.get("section")
changes = data.get("changes", {})
```

Não há schema validation. Se `data` for `None` (body não-JSON), `data.get` lança `AttributeError` → stack trace. Se `changes` tiver chaves desconhecidas, `build_patch` as ignora silenciosamente, mas alguns patch builders fazem `int(changes["port"])` (linha 153) sem tratamento de exceção → crash em input não-numérico.

Mais grave: **não há whitelist de valores**. Um `POST /apply` com `section="tools"` e `changes={"allow": "Read(**), Bash(sudo rm -rf /)"}` é aceito sem questionamento — o app **ajuda** a construir políticas inseguras.

**Correção:**
- Validar `section` contra `PATCH_BUILDERS.keys() | {"hardened_preset", ...}`
- Validar tipos com `jsonschema` ou `pydantic`
- Rejeitar valores obviamente inseguros (ex: `gateway.bind="0.0.0.0"`)
- Capturar `request.get_json(silent=True)` e retornar 400 se None

---

### 7.3 `save_config` sem limites de tamanho [MÉDIO]

**Linhas afetadas:** 81–95

`json.dumps` + `json.loads` em um dict arbitrário vindo do usuário. Um POST com JSON de ~100MB causa DoS (memória + disco). Sem `MAX_CONTENT_LENGTH` configurado no Flask.

**Correção:**
```python
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024  # 1MB
```

---

## 8. OUTROS

### 8.1 Rotas GET modificando estado — não observadas [OK]
As rotas GET (`/`, `/security-status`, `/config`, `/backups`, `/compare`, `/docker/status`, `/nono/status`, `/platform/info`, `/profiles`, `/checklist`, `/gateway/errors`) não modificam estado. Conformidade com REST/safe methods — OK.

### 8.2 `/run-audit` quebrado [BAIXO — bug funcional]
**Linha 854:** `return run_cmd.__wrapped__() if hasattr(run_cmd,'__wrapped__') else jsonify({"output":"use /run-cmd"})` — `run_cmd` não é decorada, sempre retornará a fallback. Isso é um bug, não vulnerabilidade, mas deveria ser removido.

### 8.3 `shutil.copy2` em `backup_config` [BAIXO]
Se `CONFIG_PATH` for um symlink criado por atacante local apontando para arquivo privilegiado, `copy2` seguirá o symlink e copiará conteúdo sensível para `BACKUP_DIR`. Risco baixo porque requer acesso local prévio.

### 8.4 Timing attacks em token comparison [BAIXO]
Não aplicável pois não há comparação de token no código atual, mas se for adicionada autenticação, usar `hmac.compare_digest`.

---

## Matriz Resumida

| # | Vulnerabilidade                          | Severidade | Linhas             | OWASP         |
|---|------------------------------------------|------------|--------------------|---------------|
| 1.1 | Path Traversal `/restore/<backup_name>` | CRÍTICO    | 1075–1086, 1041–1064 | A01/A03     |
| 3.1 | CSRF em todas as rotas POST             | CRÍTICO    | 777,790,821,851,1075,1241,1249,1280 | A01 |
| 4.1 | Debug mode ativo                        | CRÍTICO    | 1514               | A05           |
| 7.1 | Nenhuma autenticação                    | CRÍTICO    | global             | A01/A07       |
| 4.2 | SECRET_KEY ausente                      | ALTO       | global             | A05           |
| 4.3 | Headers de segurança ausentes           | ALTO       | global             | A05           |
| 5.1 | IDOR `/restore`                         | ALTO       | 1075               | A01           |
| 5.2 | IDOR `/compare`                         | ALTO       | 1041               | A01           |
| 6.1 | Token exposto em `/config` e `/`        | ALTO       | 613, 1036, 774     | A02           |
| 7.2 | Falta validação de entrada `/apply`     | ALTO       | 790                | A03           |
| 1.2 | Command injection (baixo risco)         | BAIXO      | 1188               | A03           |
| 2.1 | XSS potencial em templates              | MÉDIO      | 770                | A03           |
| 2.2 | XSS via log messages                    | MÉDIO      | 1002               | A03           |
| 4.4 | Host bind implícito                     | MÉDIO      | 1514               | A05           |
| 6.2 | Stack trace leakage                     | MÉDIO      | 815,940,1032,etc   | A09           |
| 6.3 | Log file exposure                       | MÉDIO      | 1002               | A02           |
| 7.3 | Sem MAX_CONTENT_LENGTH                  | MÉDIO      | global             | A04           |
| 8.2 | `/run-audit` quebrado                   | BAIXO      | 851–854            | — (bug)       |
| 8.3 | Symlink follow em backup                | BAIXO      | 73                 | A01           |

---

## Recomendações Priorizadas

1. **IMEDIATO (CRÍTICO):**
   - Desabilitar `debug=True`
   - Adicionar validação de path em `/restore` e `/compare` (whitelist + `Path.resolve().relative_to`)
   - Adicionar proteção CSRF (flask-wtf ou validação de `Origin`)
   - Implementar autenticação por token mesmo para loopback

2. **CURTO PRAZO (ALTO):**
   - Definir `SECRET_KEY`
   - Adicionar headers de segurança via `@app.after_request`
   - Redactar `gateway.auth.token` em `/config` e `state`
   - Validar schema de entrada em `/apply`

3. **MÉDIO PRAZO (MÉDIO):**
   - Auditar `templates/index.html` para XSS
   - Configurar `MAX_CONTENT_LENGTH`
   - Mensagens de erro genéricas, log completo apenas no servidor
   - Limitar leitura de log file

4. **BAIXO / higiene:**
   - Remover ou consertar `/run-audit`
   - Detectar symlinks em `backup_config`
   - Adicionar rate limiting (flask-limiter)

---

**Conclusão:** apesar de ser uma ferramenta de **gestão de segurança** (ironicamente, ajuda o usuário a endurecer a config do openclaw), o painel em si tem falhas de segurança significativas. As vulnerabilidades mais graves (CSRF + debug mode + path traversal) são facilmente exploráveis por qualquer site malicioso visitado enquanto a UI está aberta, e podem resultar no **comprometimento total do próprio sistema de segurança** que o app tenta configurar — desabilitando sandbox, removendo denylists de tools, e vazando o token do gateway.
