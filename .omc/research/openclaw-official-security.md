# Recomendações Oficiais de Segurança — Claude Code (OpenClaw)

> Fontes: docs.anthropic.com/en/docs/claude-code — Security, Settings, Hooks, MCP, SDK, Team/IAM, Sandboxing, Enterprise
> Data de pesquisa: 2026-04-08

---

## 1. Permissões e Controle de Acesso

### Modos de Permissão (`--permission-mode`)

Claude Code oferece 4 modos de permissão que controlam o nível de autonomia do agente:

| Modo | Comportamento | Uso Recomendado |
|------|--------------|-----------------|
| `default` | Pergunta ao usuário para ações potencialmente destrutivas | Uso geral interativo |
| `acceptEdits` | Aceita automaticamente edições de arquivo; pergunta para Bash | Fluxos semi-automatizados |
| `dontAsk` | Nunca pergunta — executa tudo autonomamente | CI/CD controlado |
| `bypassPermissions` | Ignora todas as verificações de permissão | APENAS em ambientes sandbox isolados |
| `plan` | Modo somente leitura — não executa ações | Revisão e planejamento |

**Recomendação oficial:** Nunca usar `bypassPermissions` fora de um ambiente sandbox isolado (container, VM).

### Fluxo de Avaliação de Permissões

```
Regras Managed Settings (deny) → Regras Managed Settings (allow)
→ Regras User Settings (deny) → Regras User Settings (allow)
→ Regras Project Settings (deny) → Regras Project Settings (allow)
→ Pergunta ao usuário
```

**Regras deny têm precedência absoluta sobre regras allow.**

---

## 2. Configurações de Hooks de Segurança

Hooks permitem executar scripts externos antes/depois de ações do agente, possibilitando auditoria e bloqueio.

### Tipos de Hooks

- **`PreToolUse`** — executado antes de cada chamada de ferramenta; pode bloquear a execução
- **`PostToolUse`** — executado após cada ferramenta; útil para auditoria/logging
- **`Stop`** — executado quando o agente para; útil para relatórios de sessão
- **`SubagentStop`** — executado quando um subagente para
- **`PreCompact`** — executado antes de compactação de contexto

### Bloqueio via `permissionDecision`

Um hook `PreToolUse` pode retornar `permissionDecision: "deny"` para bloquear qualquer ferramenta:

```json
{
  "permissionDecision": "deny",
  "reason": "Acesso negado pela política de segurança"
}
```

### `allowManagedHooksOnly`

Configuração em managed settings que **impede usuários de adicionar hooks próprios**, garantindo que apenas hooks aprovados pela organização sejam executados:

```json
{
  "allowManagedHooksOnly": true
}
```

### `allowedHttpHookUrls`

Lista de URLs permitidas para hooks HTTP — impede que hooks façam chamadas para endpoints não autorizados:

```json
{
  "allowedHttpHookUrls": ["https://hooks.empresa.com/*"]
}
```

---

## 3. Allowlist/Denylist para Ferramentas

### Sintaxe de Regras (`settings.json`)

```json
{
  "permissions": {
    "allow": [
      "Read(*)",
      "Edit(src/**)",
      "Bash(git *)",
      "WebFetch(https://docs.empresa.com/*)"
    ],
    "deny": [
      "Bash(rm *)",
      "Bash(curl *)",
      "Write(/etc/*)",
      "WebFetch(*)"
    ]
  }
}
```

### Especificadores de Ferramenta

| Padrão | Significado |
|--------|-------------|
| `Read(*)` | Qualquer leitura de arquivo |
| `Edit(src/**)` | Edições dentro de src/ |
| `Bash(git *)` | Comandos bash começando com "git" |
| `WebFetch(https://api.*)` | Fetch para URLs matching |
| `MCP(servidor:ferramenta)` | Ferramenta específica de MCP server |
| `Agent(*)` | Subagentes |

### Wildcards

- `*` — corresponde a qualquer coisa exceto `/`
- `**` — corresponde a qualquer coisa incluindo `/`

---

## 4. MCP Servers — Configurações de Segurança

### `allowedMcpServers` e `deniedMcpServers`

Controla quais MCP servers o agente pode usar:

```json
{
  "allowedMcpServers": ["servidor-interno", "docs-server"],
  "deniedMcpServers": ["servidor-externo-nao-confiavel"]
}
```

**Regra:** `deniedMcpServers` tem precedência absoluta sobre `allowedMcpServers`.

### `managed-mcp.json` (Enterprise)

Arquivo gerenciado centralmente pela organização que define MCP servers aprovados:

```json
{
  "mcpServers": {
    "servidor-aprovado": {
      "command": "npx",
      "args": ["-y", "@empresa/mcp-server"],
      "env": {
        "API_KEY": "${EMPRESA_API_KEY}"
      }
    }
  }
}
```

### Segurança de Transporte MCP

- Preferir servidores MCP locais (stdio) sobre HTTP/SSE quando possível
- Para MCP HTTP: validar origem, usar HTTPS, autenticar com tokens de curta duração
- Nunca expor MCP servers na rede pública sem autenticação

---

## 5. Recomendações Oficiais do `settings.json`

### Hierarquia de Configurações

```
Managed Settings (~/.claude/managed-settings.json)  ← mais alta prioridade
    ↓
User Settings (~/.claude/settings.json)
    ↓
Project Settings (.claude/settings.json)            ← menor prioridade
```

### Exemplo de `settings.json` Seguro para Produção/CI

```json
{
  "permissions": {
    "allow": [
      "Read(**)",
      "Edit(src/**)",
      "Edit(tests/**)",
      "Bash(npm test)",
      "Bash(npm run build)",
      "Bash(git status)",
      "Bash(git diff *)",
      "Bash(git add *)",
      "Bash(git commit *)"
    ],
    "deny": [
      "Bash(rm *)",
      "Bash(curl *)",
      "Bash(wget *)",
      "Bash(ssh *)",
      "Bash(sudo *)",
      "WebFetch(*)",
      "Agent(*)"
    ]
  },
  "allowedMcpServers": [],
  "allowManagedHooksOnly": true
}
```

### Exemplo de `managed-settings.json` para Organizações

```json
{
  "allowManagedHooksOnly": true,
  "allowedHttpHookUrls": ["https://security-audit.empresa.com/hooks"],
  "permissions": {
    "deny": [
      "Bash(sudo *)",
      "Bash(chmod *)",
      "Write(/etc/**)",
      "Write(~/.ssh/**)",
      "Write(~/.aws/**)"
    ]
  }
}
```

---

## 6. Sandboxing Oficial

A Anthropic recomenda e documenta o uso de sandboxing para ambientes de produção:

### Opções de Sandbox

1. **Docker container** — isola o filesystem e processos
2. **macOS Sandbox** — usa `sandbox-exec` para restrições granulares de syscall
3. **WSL2** — no Windows, proporciona isolamento do filesystem do host
4. **Firecracker/microVMs** — para ambientes de alta segurança

### Configuração com `bypassPermissions` + Sandbox

A única situação onde `bypassPermissions` é seguro é dentro de um container isolado sem acesso ao filesystem do host:

```bash
docker run --rm \
  -v $(pwd):/workspace:rw \
  --network none \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  claude-sandbox \
  claude --permission-mode bypassPermissions "tarefa aqui"
```

---

## 7. Identity and Access Management (Enterprise)

### SSO e Provisionamento

- Suporte a SAML 2.0 / OIDC para SSO corporativo
- SCIM para provisionamento/desativação automática de usuários
- Roles: Owner, Admin, Member, Billing

### Auditoria

- Logs de auditoria disponíveis no dashboard de admin
- Exportação de logs via API para SIEM
- Eventos auditados: login, criação de sessão, uso de ferramentas, erros de permissão

---

## Resumo de Prioridades

| Prioridade | Configuração | Impacto |
|-----------|-------------|---------|
| CRÍTICA | Nunca usar `bypassPermissions` fora de sandbox | Evita execução arbitrária |
| CRÍTICA | `allowManagedHooksOnly: true` em org | Previne hooks maliciosos |
| ALTA | `deny` explícito para `rm`, `curl`, `sudo`, `ssh` | Reduz superfície de ataque |
| ALTA | `deniedMcpServers` para servidores não aprovados | Controla exfiltração de dados |
| MÉDIA | Usar `--permission-mode plan` para revisão | Revisão antes de execução |
| MÉDIA | Hooks de auditoria para todas as ações | Rastreabilidade |
| BAIXA | `allowedHttpHookUrls` restrito | Previne SSRF via hooks |
