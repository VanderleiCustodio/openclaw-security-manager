# Guia Consolidado de Segurança — Claude Code (OpenClaw)

> Síntese das recomendações oficiais (Anthropic) e de terceiros (OWASP, OpenSSF, CVEs, pesquisa acadêmica)
> Data: 2026-04-08 | Versão: 1.0

---

## Sumário Executivo

Claude Code (internamente chamado de "OpenClaw") é uma ferramenta de agente de IA com amplo acesso a sistema de arquivos, terminal, rede e ferramentas externas via MCP. Essa amplitude de acesso cria uma superfície de ataque significativa que requer configuração cuidadosa.

Este guia consolida as recomendações oficiais da Anthropic com achados de segurança independentes (OWASP, OpenSSF, CVEs documentados e pesquisa acadêmica), organiza as configurações por criticidade e oferece exemplos práticos para desenvolvedores individuais e equipes corporativas.

**Alerta Crítico:** O CVE-2026-35022 (CVSS 9.8) afeta versões antigas do Claude Code via shell injection. **Atualize imediatamente para a versão mais recente.**

---

## 1. Comparação: Recomendações Oficiais vs. Terceiros

### Pontos de Consenso

| Área | Oficial (Anthropic) | Terceiros (OWASP/OpenSSF/CVEs) | Consenso |
|------|--------------------|---------------------------------|----------|
| `bypassPermissions` | Apenas em sandbox isolado | Nunca em produção | **Unanimidade** |
| `allowManagedHooksOnly` | Recomendado para orgs | Obrigatório em enterprise | **Forte consenso** |
| Regras `deny` explícitas | Sim, com exemplos | Sim, com escopo expandido | **Unanimidade** |
| Sandbox de execução | Docker/macOS/WSL2 | microVMs + bubblewrap/Seatbelt | **Consenso ampliado** |
| Auditoria de ações | Via hooks PostToolUse | MCP Gateway + SIEM | **Consenso ampliado** |
| MCP allowlist | `allowedMcpServers` | Allowlist + auditoria de código-fonte | **Consenso** |

### Divergências e Complementações

| Área | Oficial | Terceiros | Avaliação |
|------|---------|-----------|-----------|
| Sandbox nativo | Menciona Docker/macOS | Aponta bubblewrap (Linux) e Seatbelt (macOS) como padrão nativo desde out/2025 | Terceiros mais atualizados |
| Regras `deny` no projeto | Confia no `settings.json` de projeto | Alerta: regras podem ser sobrescritas por CLAUDE.md/prompt — usar `managed-settings.json` | **Terceiros identificam vulnerabilidade crítica** |
| Proteção de secrets | Menciona `deny` para `~/.aws`, `~/.ssh` | CVEs específicos (2025-59536, 2026-21852) — escopo mais detalhado para `.env`, `.gnupg` | Terceiros mais abrangentes |
| Supply chain MCP | Não discutido em detalhes | 655 tools maliciosas identificadas em repositórios públicos | **Ponto cego oficial** |
| CVEs | Não referenciados | 5 CVEs documentados, incluindo 1 crítico | **Informação essencial de terceiros** |

### Insight Principal

A documentação oficial é o ponto de partida correto, mas **subestima vulnerabilidades de supply chain (MCP malicioso) e o bypass de deny rules via CLAUDE.md**. As recomendações de terceiros são complementares e devem ser tratadas como extensões obrigatórias, não opcionais.

---

## 2. Guia de Configuração de Segurança por Criticidade

### CRÍTICO — Implementar Imediatamente

#### C1. Atualizar o Claude Code
```bash
npm update -g @anthropic-ai/claude-code
# Verificar versão
claude --version
```
Mitiga CVE-2026-35022 (CVSS 9.8 — shell injection).

#### C2. Nunca usar `bypassPermissions` fora de sandbox isolado
```bash
# ERRADO — risco máximo:
claude --permission-mode bypassPermissions "faça tudo"

# CORRETO — apenas dentro de container sem acesso ao host:
docker run --rm --network=none -v $(pwd):/workspace:rw \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  anthropic/claude-sandbox:latest \
  claude --permission-mode bypassPermissions "tarefa controlada"
```

#### C3. Regras `deny` críticas no `managed-settings.json` (não apenas no projeto)

**Por que `managed-settings.json` e não `settings.json` de projeto?**
Terceiros documentaram que regras `deny` no `settings.json` de projeto podem ser contornadas via instruções no `CLAUDE.md` ou por prompt engineering. Regras no `managed-settings.json` têm precedência absoluta e não podem ser sobrescritas.

```json
// ~/.claude/managed-settings.json
{
  "allowManagedHooksOnly": true,
  "permissions": {
    "deny": [
      "Bash(sudo *)",
      "Bash(chmod *)",
      "Bash(rm -rf *)",
      "Bash(curl *)",
      "Bash(wget *)",
      "Bash(ssh *)",
      "Bash(scp *)",
      "Bash(nc *)",
      "Bash(ncat *)",
      "Bash(env)",
      "Bash(printenv)",
      "Write(/etc/**)",
      "Write(~/.ssh/**)",
      "Write(~/.aws/**)",
      "Write(~/.gnupg/**)",
      "Read(**/.env)",
      "Read(**/.env.*)",
      "Read(**/credentials*)",
      "Read(~/.aws/**)",
      "Read(~/.ssh/**)",
      "Read(~/.gnupg/**)"
    ]
  }
}
```

#### C4. Isolamento de rede em CI/CD
```yaml
# .github/workflows/claude.yml (exemplo)
jobs:
  claude-task:
    runs-on: ubuntu-latest
    container:
      image: anthropic/claude-sandbox:latest
      options: --network none  # Sem acesso à internet
    steps:
      - uses: actions/checkout@v4
      - run: claude --permission-mode dontAsk "tarefa de CI"
```

---

### ALTO — Implementar na Próxima Sprint

#### A1. Sandbox nativo habilitado

```json
// ~/.claude/settings.json ou managed-settings.json
{
  "sandbox": {
    "enabled": true,
    "networkAccess": false,
    "allowedPaths": ["/workspace", "/tmp/claude"]
  }
}
```

#### A2. MCP servers — allowlist estrita e auditoria de código-fonte

```json
// ~/.claude/settings.json
{
  "allowedMcpServers": ["servidor-interno-auditado", "docs-aprovado"],
  "deniedMcpServers": ["*"]
}
```

**Checklist para cada MCP server aprovado:**
- [ ] Código-fonte revisado por engenheiro de segurança
- [ ] Repositório com histórico de commits auditável
- [ ] Sem dependências de terceiros não verificadas
- [ ] Escopo de ferramentas limitado ao mínimo necessário

#### A3. Proteção total de secrets

```json
{
  "permissions": {
    "deny": [
      "Read(**/.env)",
      "Read(**/.env.*)",
      "Read(**/.env.local)",
      "Read(**/.env.production)",
      "Read(**/credentials*)",
      "Read(**/secrets*)",
      "Read(**/keystore*)",
      "Read(~/.aws/**)",
      "Read(~/.ssh/**)",
      "Read(~/.gnupg/**)",
      "Bash(env)",
      "Bash(printenv)",
      "Bash(export *)",
      "WebFetch(*)"
    ]
  }
}
```

#### A4. Bloquear instalação de dependências não supervisionada

```json
{
  "permissions": {
    "deny": [
      "Bash(npm install *)",
      "Bash(npm i *)",
      "Bash(yarn add *)",
      "Bash(pip install *)",
      "Bash(pip3 install *)",
      "Bash(gem install *)",
      "Bash(cargo add *)"
    ]
  }
}
```
Mitiga o risco de **slopsquatting** (pacotes maliciosos com nomes similares a pacotes legítimos).

#### A5. Hook de auditoria obrigatório

```bash
# ~/.claude/hooks/audit-logger.sh
#!/bin/bash
TOOL_NAME="$1"
INPUT="$(cat)"
TIMESTAMP="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
SESSION_ID="${CLAUDE_SESSION_ID:-unknown}"
LOG_FILE="/var/log/claude-audit.jsonl"

echo "{\"ts\":\"$TIMESTAMP\",\"session\":\"$SESSION_ID\",\"tool\":\"$TOOL_NAME\",\"input\":$INPUT}" >> "$LOG_FILE"
```

```json
// ~/.claude/settings.json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/audit-logger.sh"
          }
        ]
      }
    ]
  }
}
```

---

### MÉDIO — Implementar no Próximo Trimestre

#### M1. Usar modo `plan` para revisão de ações críticas

```bash
# Revisar o que o agente faria antes de executar
claude --permission-mode plan "refatorar o módulo de autenticação"
# Revisar o plano, então executar com permissões adequadas
claude --permission-mode acceptEdits "refatorar o módulo de autenticação"
```

#### M2. Hook de bloqueio para ações de alto risco

```bash
# ~/.claude/hooks/block-dangerous.sh
#!/bin/bash
TOOL_NAME="$1"
INPUT="$(cat)"

# Bloquear git push --force
if echo "$INPUT" | grep -q "force\|--force\|-f"; then
  if echo "$TOOL_NAME" | grep -q "Bash"; then
    echo '{"permissionDecision":"deny","reason":"git push --force requer aprovação manual"}'
    exit 0
  fi
fi

# Bloquear comandos de produção
if echo "$INPUT" | grep -qE "(production|prod|\.prod\.)"; then
  echo '{"permissionDecision":"deny","reason":"Acesso a ambiente de produção requer aprovação explícita"}'
  exit 0
fi
```

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/block-dangerous.sh"
          }
        ]
      }
    ]
  }
}
```

#### M3. MCP Gateway como ponto central de controle

Para equipes com múltiplos MCP servers, implementar um gateway proxy:

```
Claude Code → MCP Gateway → MCP Servers (filesystem, db, git, web)
```

O gateway centraliza: logging, rate limiting, filtragem de respostas suspeitas e alertas em tempo real.

#### M4. SSO e SCIM para enterprise

```json
// managed-settings.json com controle de identidade
{
  "allowManagedHooksOnly": true,
  "allowedHttpHookUrls": ["https://security-hooks.empresa.com/*"],
  "permissions": {
    "deny": ["Bash(sudo *)", "Write(/etc/**)"]
  }
}
```

Configurar SAML 2.0/OIDC para SSO e SCIM para provisionamento automático de acesso.

---

### BAIXO — Boas Práticas Recomendadas

#### B1. Gerenciamento de API Key via keyring do SO

```bash
# macOS — usar Keychain
security add-generic-password -a "claude" -s "anthropic-api-key" -w "sk-ant-..."
export ANTHROPIC_API_KEY=$(security find-generic-password -a "claude" -s "anthropic-api-key" -w)

# Linux — usar secret-tool (libsecret)
secret-tool store --label="Claude API Key" service anthropic username api
export ANTHROPIC_API_KEY=$(secret-tool lookup service anthropic username api)

# Nunca fazer:
# export ANTHROPIC_API_KEY="sk-ant-..."  # Exposto em histórico do shell
```

#### B2. `allowedHttpHookUrls` restrito

```json
{
  "allowedHttpHookUrls": [
    "https://security-audit.empresa.com/hooks",
    "https://siem.empresa.com/ingest"
  ]
}
```
Previne SSRF (Server-Side Request Forgery) via hooks HTTP.

#### B3. Revisar CLAUDE.md antes de executar em repositórios desconhecidos

```bash
# Antes de executar Claude Code em repositório externo:
cat CLAUDE.md
cat .claude/settings.json
# Verificar se há instruções que expandem permissões ou bypass de deny rules
```

#### B4. Integração com SIEM

Exportar logs de auditoria para SIEM corporativo via Anthropic Compliance API ou via hooks de auditoria. Configurar alertas para:
- Tentativas de acesso a `~/.aws`, `~/.ssh`, `.env`
- Comandos `sudo`, `curl`, `wget` bloqueados (indicam tentativa de exfiltração)
- Múltiplos erros de permissão em sequência (indicam prompt injection ativa)

---

## 3. Configurações `settings.json` Prontas para Uso

### Desenvolvedor Individual — Configuração Base Segura

```json
// ~/.claude/settings.json
{
  "permissions": {
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
      "Bash(npx *)"
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
      "WebFetch(*)"
    ]
  }
}
```

### Equipe / CI-CD — Configuração Restritiva

```json
// .claude/settings.json (nível projeto, em repositório)
{
  "permissions": {
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
      "Bash(git commit *)"
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
      "Agent(*)"
    ]
  },
  "allowedMcpServers": [],
  "sandbox": {
    "enabled": true,
    "networkAccess": false
  }
}
```

### Enterprise — `managed-settings.json` Centralizado

```json
// ~/.claude/managed-settings.json (distribuído via MDM/Ansible/Chef)
{
  "allowManagedHooksOnly": true,
  "allowedHttpHookUrls": [
    "https://security-audit.empresa.com/hooks",
    "https://siem.empresa.com/claude/ingest"
  ],
  "allowedMcpServers": [
    "empresa-filesystem",
    "empresa-docs",
    "empresa-git"
  ],
  "deniedMcpServers": ["*"],
  "permissions": {
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
      "Agent(*)"
    ]
  },
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "/usr/local/bin/claude-audit-logger"
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "/usr/local/bin/claude-policy-enforcer"
          }
        ]
      }
    ]
  }
}
```

---

## 4. Trade-offs: Segurança vs. Usabilidade

| Configuração | Ganho de Segurança | Custo de Usabilidade | Recomendação |
|---|---|---|---|
| `deny: WebFetch(*)` | Alto — previne exfiltração de dados | Médio — agente não acessa docs online | Aplicar em CI/CD; condicional para dev |
| `deny: npm install *` | Alto — previne slopsquatting e supply chain | Alto — requer aprovação manual para toda nova dep | Obrigatório em produção; condicional para dev |
| `allowedMcpServers: []` | Alto — elimina supply chain MCP | Alto — remove funcionalidades de MCP | CI/CD e prod; usar allowlist em dev |
| `sandbox.networkAccess: false` | Máximo — previne toda exfiltração | Alto — agente não acessa internet | Obrigatório em CI/CD; recomendado em dev |
| `--permission-mode plan` | Médio — revisão antes de execução | Alto — cada tarefa requer aprovação | Para ações críticas; não para tarefas rotineiras |
| `allowManagedHooksOnly: true` | Alto — previne hooks maliciosos | Baixo — impacto mínimo no fluxo | Obrigatório em enterprise |
| `deny: Bash(git push *)` | Médio — previne pushes acidentais | Médio — requer push manual | Recomendado; ajustar por equipe |

### Configuração por Contexto

| Contexto | Perfil Recomendado |
|----------|-------------------|
| Exploração / aprendizado | `default` + deny rules básicas |
| Desenvolvimento ativo individual | `acceptEdits` + deny rules médias |
| Revisão de código em repos externos | `plan` (somente leitura) |
| CI/CD automatizado | `dontAsk` + sandbox + deny rules completas |
| Análise de repositório desconhecido | `plan` + `allowedMcpServers: []` |
| Ambiente de alta segurança | `bypassPermissions` APENAS dentro de container isolado sem rede |

---

## 5. Checklist de Segurança para Equipes

### Antes de Adotar Claude Code na Equipe

- [ ] Versão mais recente instalada (mitigar CVE-2026-35022 e outros)
- [ ] `managed-settings.json` criado e distribuído via MDM/Ansible
- [ ] `allowManagedHooksOnly: true` configurado
- [ ] Lista de MCP servers aprovados definida e documentada
- [ ] Política de uso documentada e comunicada à equipe
- [ ] Treinamento sobre riscos de prompt injection realizado

### Antes de Executar em Repositório Externo

- [ ] Revisar `CLAUDE.md` para instruções suspeitas (bypass de permissões, exfiltração)
- [ ] Revisar `.claude/settings.json` para regras que expandem permissões
- [ ] Usar `--permission-mode plan` na primeira execução
- [ ] Verificar MCP servers configurados no projeto
- [ ] Executar em sandbox isolado quando possível

### Configuração de Ambiente Seguro

- [ ] `deny` para: `sudo`, `rm -rf`, `curl`, `wget`, `ssh`, `env`, `printenv`
- [ ] `deny` para leitura de: `.env`, `.aws/`, `.ssh/`, `.gnupg/`, `credentials*`
- [ ] `deny` para instalação de pacotes: `npm install`, `pip install`, `yarn add`
- [ ] Hook `PostToolUse` de auditoria configurado e funcionando
- [ ] Logs de auditoria integrados ao SIEM corporativo
- [ ] API Key gerenciada via keyring do SO (não em variável de ambiente global)
- [ ] Sandbox habilitado para sessões automatizadas

### Manutenção Contínua

- [ ] Atualizar Claude Code mensalmente (ou via patch automático)
- [ ] Auditar MCP servers instalados trimestralmente
- [ ] Revisar logs de auditoria semanalmente para anomalias
- [ ] Revisar e atualizar `managed-settings.json` com novas deny rules
- [ ] Monitorar CVE database e advisories da Anthropic
- [ ] Testar bypasses de configuração de segurança semestralmente

### Resposta a Incidentes

- [ ] Procedimento documentado para suspeita de prompt injection
- [ ] Procedimento para revogação imediata de API Key comprometida
- [ ] Lista de contatos para report de vulnerabilidades (security@anthropic.com)
- [ ] Runbook para isolamento de sessão Claude Code comprometida

---

## 6. CVEs Críticos — Resumo de Ação Imediata

| CVE | CVSS | Ação Requerida | Urgência |
|-----|------|----------------|----------|
| **CVE-2026-35022** | **9.8** | Atualizar Claude Code imediatamente | **CRÍTICO** |
| CVE-2025-59536 | 8.1 | Verificar se API Key foi exposta; revogar se necessário | Alta |
| CVE-2026-21852 | 7.3 | Adicionar deny rules para Read de `.env` e credentials | Alta |
| CVE-2025-54794 | 7.5 | Validar conteúdo de repositórios externos antes de usar | Média |
| CVE-2025-54795 | 7.5 | Idem CVE-2025-54794 | Média |

---

## 7. Arquitetura de Segurança Recomendada

```
┌─────────────────────────────────────────────────────────┐
│                    USUÁRIO / CI/CD                       │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────┐
│              CLAUDE CODE (sandbox nativo)                │
│  • permission-mode: dontAsk (CI) / default (dev)        │
│  • managed-settings.json aplicado                       │
│  • sandbox.networkAccess: false                         │
└──────┬──────────────┬──────────────┬────────────────────┘
       │              │              │
┌──────▼──────┐ ┌─────▼──────┐ ┌───▼──────────────────────┐
│  Filesystem  │ │   Bash     │ │      MCP Gateway          │
│  (restrito)  │ │ (deny list)│ │  (logging + filtragem)    │
└─────────────┘ └────────────┘ └──────┬───────────────────┘
                                       │
                         ┌─────────────▼────────────┐
                         │     MCP Servers           │
                         │  (apenas allowlist)       │
                         └──────────────────────────┘
                                       │
                         ┌─────────────▼────────────┐
                         │  SIEM / Audit Log         │
                         │  (via PostToolUse hook)   │
                         └──────────────────────────┘
```

---

## Referências

### Fontes Oficiais
- Anthropic Claude Code Docs: docs.anthropic.com/en/docs/claude-code
- Anthropic Security: anthropic.com/security
- Compliance API: docs.anthropic.com/en/api/compliance

### Fontes de Terceiros
- OWASP LLM Top 10 2025: owasp.org/www-project-top-10-for-large-language-model-applications
- OpenSSF AI/ML Security Guidelines: openssf.org
- CVE Database: cve.mitre.org
- Check Point Research (Prompt Injection in Claude Code): research.checkpoint.com
- Cymulate LLM Agent Security Testing: cymulate.com
- Backslash Security — MCP Supply Chain Risks: backslash.security
- MintMCP Gateway Reference Architecture: mintmcp.com
- TrueFoundry Enterprise Claude Code Deployment: truefoundry.com
- Docker AI Sandbox Documentation: docs.docker.com/ai/claude-code-sandbox

---

*Este guia deve ser revisado trimestralmente ou sempre que novos CVEs relevantes forem publicados.*
