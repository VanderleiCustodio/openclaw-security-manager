# Relatório de Auditoria de Segurança — settings.local.json
> Data: 2026-04-08 | Auditor: worker-1 (security-integration team)
> Referência: openclaw-security-guide.md v1.0

---

## Sumário Executivo

O arquivo `settings.local.json` auditado contém **34 regras `allow`** e **zero regras `deny`**. Esta configuração apresenta múltiplas falhas críticas de segurança: duas regras permitem execução arbitrária de código Python e Node.js, há ausência total de deny rules, e nenhuma proteção para secrets ou credenciais está configurada. O risco geral é **CRÍTICO**.

---

## 1. Inventário Completo das Regras `allow`

| # | Regra | Classificação |
|---|-------|---------------|
| 1 | `Bash(python -c "import ast, sys; ast.parse(...)")` | MÉDIO |
| 2 | `Bash(python -c "import ast; ast.parse(...)")` | MÉDIO |
| 3 | `Bash(curl -s --max-time 3 http://localhost:53497/)` | MÉDIO |
| 4 | `Bash(ls "C:\...\state" 2>/dev/null \|\| dir "C:\...\state")` | BAIXO |
| 5 | `Bash(dir "C:\...\state")` | BAIXO |
| 6 | `Bash(dir "C:\...\state\events")` | BAIXO |
| 7 | `Bash(cat "C:\...\state\events"/*)` | BAIXO |
| 8 | `WebSearch` | MÉDIO |
| 9 | `Bash(curl -s http://localhost:53497/)` | MÉDIO |
| 10 | `Bash(curl -s http://localhost:53497/screen/design-system)` | BAIXO |
| 11 | `Bash(curl -s "http://localhost:53497/screen/layout-compare")` | BAIXO |
| 12 | `Bash(curl -s "http://localhost:53497/screens")` | BAIXO |
| 13 | `Bash(curl -s "http://localhost:53497/api/screens")` | BAIXO |
| 14 | `Bash(curl -s "http://localhost:53497/list")` | BAIXO |
| 15 | `Bash(curl -sv "http://localhost:53497/")` | MÉDIO |
| 16 | `Bash(curl -s http://localhost:53497/content/design-sistema.html)` | BAIXO |
| 17 | `Bash(curl -s http://localhost:53497/design-system)` | BAIXO |
| 18 | `Bash(curl -s http://localhost:53497/design-system.html)` | BAIXO |
| 19 | `WebFetch(domain:www.figma.com)` | BAIXO |
| 20 | `WebFetch(domain:github.com)` | MÉDIO |
| 21 | `WebFetch(domain:dribbble.com)` | BAIXO |
| 22 | `WebFetch(domain:speckyboy.com)` | BAIXO |
| 23 | **`Bash(python -c ":*)`** | **CRÍTICO** |
| 24 | `Bash(bash "C:/Users/vande/.claude/.../setup-progress.sh" resume)` | ALTO |
| 25 | `Bash(CLAUDE_PLUGIN_ROOT="..." bash ".../setup-claude-md.sh" global overwrite)` | ALTO |
| 26 | `Bash(bash "C:/Users/vande/.claude/.../setup-claude-md.sh" global overwrite)` | ALTO |
| 27 | `Bash(bash "C:/Users/vande/.claude/.../setup-progress.sh" save 2 global)` | ALTO |
| 28 | **`Bash(node:*)`** | **CRÍTICO** |
| 29 | `Bash(CONFIG_TYPE="global")` | MÉDIO |
| 30 | `Bash(bash "C:/Users/vande/.claude/.../setup-progress.sh" save 3 "$CONFIG_TYPE")` | ALTO |
| 31 | `mcp__plugin_oh-my-claudecode_t__state_write` | MÉDIO |

---

## 2. Análise por Categoria de Risco

---

### CRÍTICO

#### CRIT-01 — `Bash(python -c ":*)`
**Regra:** `"Bash(python -c \":*)"`

**Problema:** O padrão `:*` após `python -c "` é um wildcard que efetivamente permite **qualquer comando Python arbitrário**. Qualquer prompt ou instrução maliciosa que induza o agente a usar `python -c "..."` será automaticamente aprovado sem intervenção do usuário.

**Impacto:**
- Execução de código arbitrário no sistema host
- Leitura de qualquer arquivo (incluindo `.env`, `~/.aws/credentials`, `~/.ssh/id_rsa`)
- Exfiltração de dados via módulos `urllib`, `socket`, `subprocess`
- Instalação de pacotes maliciosos via `subprocess.run(['pip', 'install', ...])`
- Vetor direto para exploração de CVE-2026-35022 (shell injection, CVSS 9.8)

**Conflito com guia:** Seção C3 exige `deny` para `Bash(curl *)`, `Bash(wget *)` e proteção de secrets. Esta regra bypassa todos esses controles via Python.

**Ação:** Remover imediatamente. Se necessário executar scripts Python específicos, usar regras com caminhos absolutos e argumentos completos fixos.

---

#### CRIT-02 — `Bash(node:*)`
**Regra:** `"Bash(node:*)"`

**Problema:** Wildcard `node:*` permite execução de **qualquer script Node.js**. Combinado com o ecossistema npm disponível localmente, representa acesso irrestrito ao sistema.

**Impacto:**
- Execução de código JavaScript arbitrário via `node -e "..."` ou arquivos `.js`
- Acesso ao filesystem via módulo `fs` nativo do Node
- Conexões de rede via módulos `http`, `https`, `net`
- Execução de subprocessos via `child_process.exec()`
- Leitura de variáveis de ambiente via `process.env`

**Conflito com guia:** Seção A3 exige proteção de secrets. `node -e "console.log(require('fs').readFileSync('/caminho/.env').toString())"` seria aprovado automaticamente por esta regra.

**Ação:** Remover imediatamente. Não há justificativa legítima para um wildcard irrestrito em Node.

---

### ALTO

#### ALTO-01 — Scripts de setup com caminhos hardcoded e sem versionamento seguro
**Regras afetadas:** #24, #25, #26, #27, #30

**Problema:** Permissões permanentes para execução de scripts de setup do plugin OMC com parâmetros `global overwrite`. Estes scripts modificam o arquivo `CLAUDE.md` global com o parâmetro `overwrite`, o que pode:
- Sobrescrever configurações de segurança existentes
- Ser explorado se o caminho do plugin for comprometido (supply chain attack)
- Persistir mesmo após a conclusão do setup, ampliando a superfície de ataque

**Conflito com guia:** Seção A2 (auditoria de MCP/plugins). A regra `global overwrite` em `setup-claude-md.sh` é especialmente preocupante à luz do alerta do guia sobre bypass de deny rules via `CLAUDE.md`.

**Ação:** Remover após conclusão do setup. Se necessário manter, restringir ao período de configuração e remover em seguida.

---

#### ALTO-02 — Ausência total de regras `deny`
**Problema:** O arquivo não contém **nenhuma** regra `deny`. Segundo o guia (seção C3), deny rules no `managed-settings.json` têm precedência absoluta e não podem ser sobrescritas. Sem deny rules, não há proteção contra:

- Leitura de `~/.aws/credentials`, `~/.ssh/id_rsa`, arquivos `.env`
- Execução de `sudo`, `rm -rf`, `curl` para hosts externos
- Instalação de pacotes via `pip install`, `npm install`
- Enumeração de variáveis de ambiente via `env` ou `printenv`

**Conflito com guia:** Seções C3, A3, A4 — todas exigem deny rules explícitas.

**Ação:** Adicionar bloco `deny` completo conforme template do guia (seção 3).

---

### MÉDIO

#### MED-01 — Regras `curl` para localhost excessivamente granulares e redundantes
**Regras afetadas:** #3, #9, #10, #11, #12, #13, #14, #15, #16, #17, #18

**Problema:** Há 11 regras `curl` distintas para `http://localhost:53497/` cobrindo diferentes endpoints. Além da redundância, a regra #15 usa o flag `-sv` (verbose com detalhes de SSL/TLS e headers), que expõe mais informações do que o necessário.

**Avaliação de necessidade:**
- Regras #3, #9: duplicatas funcionais (`--max-time 3` vs sem timeout) — a sem timeout (#9) é desnecessária
- Regras #10–#18: endpoints específicos de uma sessão de desenvolvimento de design system — provavelmente obsoletos
- Regra #15 (`-sv`): flag verbose desnecessário para uso rotineiro

**Conflito com guia:** O guia recomenda `deny: Bash(curl *)` para ambientes individuais (seção 3). Para casos onde curl localhost é necessário, a recomendação é a regra mais restrita possível.

**Ação:** Consolidar em uma única regra genérica `Bash(curl -s http://localhost:53497/*)` se o serviço ainda estiver ativo. Remover regras obsoletas de endpoints específicos. Remover flag `-sv`.

---

#### MED-02 — `WebSearch` irrestrito
**Regra:** `"WebSearch"`

**Problema:** Permissão de WebSearch sem restrição de domínio ou query. Pode ser explorado em ataques de prompt injection para exfiltrar informações (via queries de busca que contêm dados sensíveis como nomes de arquivos, conteúdo parcial de código, etc.).

**Conflito com guia:** Seção A3 inclui `WebFetch(*)` no bloco de deny para proteção de secrets. WebSearch representa vetor similar.

**Ação:** Avaliar se realmente necessário. Se sim, manter com consciência do risco. Se não, remover.

---

#### MED-03 — `WebFetch(domain:github.com)` sem restrição de path
**Regra:** `"WebFetch(domain:github.com)"`

**Problema:** Permite fetch de qualquer URL no domínio github.com, incluindo repositórios privados (se o agente tiver acesso a tokens), gists, e raw content de arquivos potencialmente maliciosos. Um atacante que controle um repositório pode usar isso para servir instruções de prompt injection via arquivo `CLAUDE.md` em um repositório.

**Conflito com guia:** Seção B3 alerta especificamente sobre revisão de `CLAUDE.md` em repositórios externos antes de executar.

**Ação:** Se necessário, restringir a subdomínios/paths específicos. Considerar remover e usar apenas quando necessário.

---

#### MED-04 — `Bash(CONFIG_TYPE="global")`
**Regra:** `"Bash(CONFIG_TYPE=\"global\")"`

**Problema:** Esta regra permite definir a variável de ambiente `CONFIG_TYPE=global` em qualquer contexto de Bash. A variável é usada pelo script #30 (`setup-progress.sh save 3 "$CONFIG_TYPE"`). Se um atacante induzir o agente a executar outros scripts que usem `CONFIG_TYPE`, o valor `global` pode alterar o comportamento desses scripts de forma inesperada.

**Ação:** Remover após conclusão do setup. Esta é uma regra residual de processo de instalação.

---

#### MED-05 — `mcp__plugin_oh-my-claudecode_t__state_write` irrestrito
**Regra:** `"mcp__plugin_oh-my-claudecode_t__state_write"`

**Problema:** Permissão irrestrita para escrita no state do plugin OMC. Sem restrição de quais keys/valores podem ser escritos, um atacante pode modificar o estado interno do agente para alterar comportamentos futuros.

**Ação:** Avaliar se esta permissão precisa ser permanente ou pode ser removida após o setup.

---

### BAIXO

#### BAIXO-01 — Regras `dir`/`ls`/`cat` para caminhos hardcoded de sessão específica
**Regras afetadas:** #4, #5, #6, #7

**Problema:** Permissões para listar e ler o state de uma sessão específica do brainstorm (`1229-1775623612`). Estas regras são claramente resíduos de uma sessão passada e não têm utilidade futura.

**Ação:** Remover. São regras obsoletas que ampliam desnecessariamente a superfície de ataque.

---

#### BAIXO-02 — `WebFetch` para domínios de design (dribbble.com, speckyboy.com)
**Regras afetadas:** #21, #22

**Problema:** Permissões para fetch de sites de design que provavelmente foram usados em uma tarefa específica e não são necessários permanentemente. Domínios de terceiros expandem a superfície de ataque para conteúdo potencialmente malicioso.

**Ação:** Remover se não houver uso ativo. Adicionar temporariamente quando necessário.

---

#### BAIXO-03 — Python scripts com AST parsing (#1 e #2) — regras quase-duplicadas
**Regras afetadas:** #1, #2

**Problema:** Duas regras extremamente similares para parsing de `app.py` via AST. A diferença é apenas `encoding='utf-8'` na segunda. Uma das duas é redundante. Ambas são permissões com argumentos completos fixos (baixo risco), mas a duplicação indica falta de manutenção das regras.

**Ação:** Consolidar em uma única regra com o encoding explícito (mais robusta).

---

## 3. O Que Está FALTANDO (Deny Rules Ausentes)

Comparando com as recomendações do guia (seções C3, A3, A4), as seguintes deny rules estão completamente ausentes:

### Críticas (ausência = risco imediato)
```json
"Bash(sudo *)",
"Bash(rm -rf *)",
"Bash(curl http*)",
"Bash(curl https*)",
"Bash(wget *)",
"Bash(ssh *)",
"Bash(env)",
"Bash(printenv)",
"Read(**/.env)",
"Read(**/.env.*)",
"Read(~/.aws/**)",
"Read(~/.ssh/**)",
"Read(**/credentials*)"
```

### Altas (ausência = risco elevado)
```json
"Bash(npm install *)",
"Bash(pip install *)",
"Bash(pip3 install *)",
"Bash(yarn add *)",
"Bash(nc *)",
"Bash(ncat *)",
"Bash(scp *)",
"Read(~/.gnupg/**)",
"Read(**/secrets*)",
"Write(~/.ssh/**)",
"Write(~/.aws/**)"
```

### Médias (ausência = risco moderado)
```json
"Bash(git push --force *)",
"Bash(git reset --hard *)",
"Bash(chmod *)",
"Bash(chown *)",
"Write(/etc/**)"
```

---

## 4. Tabela Consolidada de Criticidade

| ID | Regra (resumo) | Criticidade | Ação |
|----|----------------|-------------|------|
| CRIT-01 | `Bash(python -c ":*)` | **CRÍTICO** | Remover imediatamente |
| CRIT-02 | `Bash(node:*)` | **CRÍTICO** | Remover imediatamente |
| ALTO-01 | Scripts setup com `global overwrite` (#24-#27, #30) | **ALTO** | Remover após setup |
| ALTO-02 | Ausência total de deny rules | **ALTO** | Adicionar bloco deny completo |
| MED-01 | Curl localhost redundante/verbose (#3, #9-#18) | **MÉDIO** | Consolidar, remover obsoletos |
| MED-02 | `WebSearch` irrestrito | **MÉDIO** | Avaliar necessidade |
| MED-03 | `WebFetch(domain:github.com)` sem path | **MÉDIO** | Restringir ou remover |
| MED-04 | `CONFIG_TYPE="global"` residual | **MÉDIO** | Remover |
| MED-05 | `state_write` irrestrito | **MÉDIO** | Avaliar necessidade permanente |
| BAIXO-01 | Regras `dir`/`cat` de sessão obsoleta (#4-#7) | **BAIXO** | Remover |
| BAIXO-02 | WebFetch dribbble/speckyboy (#21-#22) | **BAIXO** | Remover se inativo |
| BAIXO-03 | Python AST duplicado (#1-#2) | **BAIXO** | Consolidar em uma regra |

---

## 5. Configuração Recomendada Pós-Auditoria

```json
{
  "permissions": {
    "allow": [
      "Bash(python -c \"import ast; ast.parse(open('app.py', encoding='utf-8').read()); print('app.py OK')\")",
      "Bash(curl -s --max-time 3 http://localhost:53497/*)",
      "WebSearch",
      "WebFetch(domain:www.figma.com)"
    ],
    "deny": [
      "Bash(sudo *)",
      "Bash(rm -rf *)",
      "Bash(curl http*)",
      "Bash(curl https*)",
      "Bash(wget *)",
      "Bash(ssh *)",
      "Bash(scp *)",
      "Bash(nc *)",
      "Bash(ncat *)",
      "Bash(env)",
      "Bash(printenv)",
      "Bash(npm install *)",
      "Bash(pip install *)",
      "Bash(pip3 install *)",
      "Bash(yarn add *)",
      "Bash(chmod *)",
      "Bash(git push --force *)",
      "Read(**/.env)",
      "Read(**/.env.*)",
      "Read(**/credentials*)",
      "Read(**/secrets*)",
      "Read(~/.aws/**)",
      "Read(~/.ssh/**)",
      "Read(~/.gnupg/**)",
      "Write(~/.ssh/**)",
      "Write(~/.aws/**)",
      "Write(/etc/**)"
    ]
  }
}
```

**Nota:** A regra `Bash(curl http*)` e `Bash(curl https*)` nos deny bloqueará curl para hosts externos. A regra allow `Bash(curl -s --max-time 3 http://localhost:53497/*)` deve ser avaliada pelo sistema de permissões antes do deny — verifique a precedência de allow vs. deny na versão do Claude Code em uso. Se allow tem precedência sobre deny, a regra de localhost continuará funcionando enquanto curls externos são bloqueados. Se deny tem precedência, será necessário usar um padrão diferente ou aceitar que curl localhost precise de aprovação manual.

---

## 6. Conflitos Diretos com o Guia de Segurança

| Seção do Guia | Recomendação | Status Atual | Conflito |
|---------------|-------------|--------------|----------|
| C3 | `deny: Bash(curl *)` | AUSENTE | Conflito direto — curl permitido sem restrição |
| C3 | `deny: Bash(env)` / `deny: Bash(printenv)` | AUSENTE | Conflito direto — variáveis de ambiente acessíveis |
| C3 | `deny: Read(**/.env)` / `deny: Read(~/.aws/**)` | AUSENTE | Conflito direto — secrets acessíveis |
| A3 | Proteção total de secrets | AUSENTE | Conflito direto — nenhuma proteção |
| A4 | `deny: Bash(pip install *)` / `deny: Bash(npm install *)` | AUSENTE | Conflito direto — instalação irrestrita |
| C1 | Mitigação CVE-2026-35022 (shell injection) | CRIT-01 expõe | `python -c ":*` é vetor de shell injection |
| A2 | Allowlist MCP + auditoria | `state_write` sem restrição | Conflito parcial |

---

## 7. Priorização de Ações

### Imediato (hoje)
1. Remover `Bash(python -c ":*)` — CRIT-01
2. Remover `Bash(node:*)` — CRIT-02
3. Adicionar bloco `deny` mínimo: `sudo`, `rm -rf`, `curl` externo, `env`, `printenv`, `Read(.env)`, `Read(~/.aws/**)`, `Read(~/.ssh/**)`

### Curto prazo (esta semana)
4. Remover regras de setup residuais (#24-#27, #29, #30)
5. Remover regras `dir`/`cat` de sessão obsoleta (#4-#7)
6. Consolidar regras curl localhost
7. Expandir bloco `deny` com proteção de pacotes (`pip install`, `npm install`)

### Médio prazo (próxima sprint)
8. Criar `managed-settings.json` em `~/.claude/` com deny rules de precedência absoluta
9. Avaliar e remover `WebFetch(domain:github.com)` ou restringir a paths específicos
10. Configurar hook de auditoria `PostToolUse` conforme seção A5 do guia

---

*Relatório gerado por worker-1 — security-integration team | 2026-04-08*
