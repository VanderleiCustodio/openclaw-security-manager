# Recomendações de Segurança de Terceiros — Claude Code (OpenClaw)

> Fontes: OWASP, OpenSSF, Check Point, Cymulate, arXiv, Docker, Backslash, MintMCP, TrueFoundry, HackerNews, GitHub, CVE Database
> Data de pesquisa: 2026-04-08

---

## 1. Práticas de Hardening (OWASP, OpenSSF)

### Checklist de Hardening — OpenSSF

- [ ] Usar versão mais recente do Claude Code (patches de segurança frequentes)
- [ ] Configurar regras `deny` explícitas no `settings.json` para comandos destrutivos
- [ ] Nunca armazenar `ANTHROPIC_API_KEY` em variáveis de ambiente do projeto
- [ ] Revisar CLAUDE.md e `.claude/settings.json` antes de executar em repositórios desconhecidos
- [ ] Habilitar `allowManagedHooksOnly` em ambientes corporativos
- [ ] Auditar MCP servers instalados regularmente

### Bug Conhecido — Bypass de Deny Rules no `settings.json`

Foi documentado um comportamento onde regras `deny` no `settings.json` de projeto podem ser sobrescritas por instruções no CLAUDE.md ou via prompt engineering. **Mitigação:** sempre definir regras críticas no `managed-settings.json` (nível organização), não apenas no projeto.

---

## 2. Riscos de Injeção de Prompt e Mitigações

### OWASP LLM Top 10 2025 — Riscos Relevantes

| Risco | Descrição | Mitigação |
|-------|-----------|-----------|
| LLM01 — Prompt Injection | Conteúdo malicioso em arquivos/URLs manipula o agente | Sandbox + deny rules para ferramentas destrutivas |
| LLM06 — Excessive Agency | Agente com permissões excessivas causa danos além do escopo | Principle of least privilege, modo `plan` |
| LLM08 — Vector & Embedding Weaknesses | Dados de treinamento/contexto contaminados | Validar fontes de contexto injetadas via MCP |
| LLM09 — Misinformation | Agente toma decisões com base em código/docs falsos | Revisão humana de ações críticas |

### CVEs Documentados — Injeção de Prompt

- **CVE-2025-54794 / CVE-2025-54795** (InversePrompt): Ataques de injeção de prompt via arquivos de código no repositório. CVSS 7.5 (Alto). Mitigação: validar conteúdo de arquivos antes de injetar no contexto do agente.
- **CVE-2026-35022** (CVSS **9.8 — Crítico**, publicado 06/04/2026): Injeção de shell via parâmetro `shell=true` no CLI/SDK do Claude Code. Afeta versões < 1.x.x. **Atualizar imediatamente.**

### Pesquisa Acadêmica

Estudo arXiv (2025) demonstrou que defesas baseadas em detecção de injeção de prompt têm taxa de sucesso de ataque de **>85%** quando o atacante conhece o mecanismo de defesa. Conclusão: defesas baseadas em detecção são insuficientes — sandboxing e restrições de ferramentas são mais eficazes.

---

## 3. Isolamento de Ambiente

### Sandbox Nativo (Outubro 2025)

A Anthropic lançou sandbox nativo usando:
- **Linux:** `bubblewrap` — namespaces, seccomp, restrição de syscalls
- **macOS:** `Seatbelt` (`sandbox-exec`) — perfis de política granulares

**Recomendação:** habilitar sandbox nativo em produção. Configuração em `settings.json`:
```json
{
  "sandbox": {
    "enabled": true,
    "networkAccess": false,
    "allowedPaths": ["/workspace"]
  }
}
```

### Docker Sandboxes com microVM (Janeiro 2026)

Para máxima isolação, usar microVMs (Firecracker) dentro de containers Docker. Cada sessão Claude Code em VM própria — previne escape de container.

```dockerfile
FROM anthropic/claude-sandbox:latest
WORKDIR /workspace
# Sem acesso à rede por padrão
```

### WSL2 (Windows)

No Windows, executar Claude Code dentro de WSL2 com:
- Filesystem do host montado como somente-leitura quando possível
- `WSLENV` mínimo — não expor todas as variáveis de ambiente do Windows
- Regras de firewall para bloquear acesso de WSL à rede corporativa interna

### Isolamento de Rede como Prioridade Máxima

Especialistas de segurança consideram **isolamento de rede** a mitigação mais eficaz contra exfiltração de dados. Configurar `--network=none` ou equivalente sempre que Claude Code não precisar de acesso à internet.

---

## 4. Gerenciamento Seguro de Credenciais e Secrets

### CVEs de Exfiltração de API Keys

- **CVE-2025-59536**: Exfiltração de `ANTHROPIC_API_KEY` via prompt injection em repositório malicioso. CVSS 8.1.
- **CVE-2026-21852**: Vazamento de secrets do `.env` via ferramenta `Read` sem restrições de path. CVSS 7.3.

### Boas Práticas (OpenSSF)

```bash
# NÃO fazer:
export ANTHROPIC_API_KEY="sk-ant-..."  # Variável global do shell

# FAZER:
# Usar keyring do sistema operacional
secret-tool store --label="Claude API Key" service anthropic username api

# Ou usar um secrets manager
eval $(aws secretsmanager get-secret-value --secret-id claude-api-key --query SecretString --output text | jq -r 'to_entries | .[] | "export \(.key)=\(.value)"')
```

### Regras Deny para Proteção de Secrets

```json
{
  "permissions": {
    "deny": [
      "Read(**/.env)",
      "Read(**/.env.*)",
      "Read(**/credentials*)",
      "Read(~/.aws/**)",
      "Read(~/.ssh/**)",
      "Read(~/.gnupg/**)",
      "Bash(env)",
      "Bash(printenv)",
      "Bash(cat ~/.aws/*)",
      "WebFetch(*)"
    ]
  }
}
```

### Ameaça: Slopsquatting

Pacotes npm/pip com nomes similares a pacotes legítimos instalados pelo agente. **Mitigação:** configurar `deny` para `Bash(npm install *)` e `Bash(pip install *)`, exigir aprovação explícita para instalação de dependências.

---

## 5. Auditoria e Logging

### Anthropic Compliance API

API oficial para exportar logs de auditoria de sessões Claude Code:
- Logs incluem: tool calls, permissões solicitadas/negadas, conteúdo de mensagens
- Integração com SIEM via webhook ou polling
- Retenção configurável (padrão: 30 dias)

### MCP Gateway como Ponto Central de Auditoria

Usar um MCP Gateway (proxy) entre Claude Code e todos os MCP servers para:
- Logging centralizado de todas as tool calls
- Rate limiting por servidor
- Filtragem de respostas maliciosas
- Alertas em tempo real para ações suspeitas

```
Claude Code → MCP Gateway (auditoria/filtro) → MCP Servers
```

### Hooks de Auditoria

Implementar hook `PostToolUse` para logar todas as ações:

```bash
#!/bin/bash
# ~/.claude/hooks/audit.sh
TOOL_NAME=$1
INPUT=$(cat)
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "{\"ts\":\"$TIMESTAMP\",\"tool\":\"$TOOL_NAME\",\"input\":$INPUT}" >> /var/log/claude-audit.jsonl
```

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "*",
        "hooks": [{"type": "command", "command": "~/.claude/hooks/audit.sh"}]
      }
    ]
  }
}
```

---

## 6. Least Privilege para Ferramentas e MCP Servers

### OWASP Excessive Agency Risk

O risco de "Excessive Agency" (LLM06) ocorre quando o agente tem permissões além do necessário para a tarefa. Princípios:

1. **Escopo mínimo de ferramentas** — habilitar apenas as ferramentas necessárias para a tarefa específica
2. **Permissões temporárias** — conceder permissões por sessão, não permanentemente
3. **Revisão humana para ações de alto impacto** — deploys, migrações de banco, mudanças de infraestrutura

### Tabela de Permissões por MCP Server

| MCP Server | Ferramentas Permitidas | Ferramentas Bloqueadas |
|------------|----------------------|----------------------|
| Filesystem | `read_file`, `list_dir` | `write_file`, `delete_file` |
| Database | `query` (SELECT) | `execute` (INSERT/UPDATE/DELETE) |
| Git | `status`, `diff`, `log` | `push`, `force-push`, `reset` |
| Web | `fetch` (domínios aprovados) | `fetch` (domínios externos) |

### Ferramenta `permission-prompt-tool` (SDK)

Para aplicações que usam o SDK do Claude Code, implementar um handler customizado de permissões que valida cada tool call contra uma política de segurança externa:

```typescript
const client = new ClaudeCode({
  permissionPromptTool: async (toolName, input) => {
    const approved = await securityPolicyCheck(toolName, input);
    return approved ? "approve" : "deny";
  }
});
```

### Risco de Supply Chain: MCP Skills Maliciosas

Pesquisa (2025) identificou **655 skills/tools MCP maliciosas** em repositórios públicos, incluindo:
- Tools que exfiltram dados para endpoints externos
- Tools que instalam backdoors via `npm install`
- Tools que modificam configurações de segurança silenciosamente

**Mitigação:** usar apenas MCP servers de fontes confiáveis, auditar código-fonte, usar `allowedMcpServers` allowlist.

---

## 7. Timeline de CVEs Relevantes

| CVE | CVSS | Descrição | Status |
|-----|------|-----------|--------|
| CVE-2025-54794 | 7.5 | InversePrompt — injeção via arquivos de código | Patcheado |
| CVE-2025-54795 | 7.5 | InversePrompt — variante via comentários | Patcheado |
| CVE-2025-59536 | 8.1 | Exfiltração de API Key via prompt injection | Patcheado |
| CVE-2026-21852 | 7.3 | Vazamento de .env via Read sem restrições | Patcheado |
| CVE-2026-35022 | **9.8** | Shell injection via `shell=True` no CLI/SDK | **Crítico — Atualizar** |

---

## 8. Recomendações por Perfil de Uso

### Desenvolvedor Individual

- Usar modo `default` (nunca `bypassPermissions`)
- Configurar deny rules básicas no `~/.claude/settings.json`
- Revisar CLAUDE.md de repositórios externos antes de executar
- Não usar Claude Code com credenciais de produção

### Equipe / Enterprise

- Implementar `managed-settings.json` com `allowManagedHooksOnly: true`
- Hooks de auditoria obrigatórios via `PostToolUse`
- MCP servers aprovados via allowlist centralizada
- Sandbox obrigatório em CI/CD
- Integração com SIEM para alertas em tempo real
- Treinamento de equipe sobre riscos de prompt injection

---

## 9. Referências

- OWASP LLM Top 10 2025: owasp.org/www-project-top-10-for-large-language-model-applications
- OpenSSF AI/ML Security: openssf.org
- Check Point Research: research.checkpoint.com (Prompt Injection in Claude Code)
- Cymulate: cymulate.com (LLM Agent Security Testing)
- arXiv: arxiv.org/abs/2503.xxxxx (Prompt Injection Defense Evaluation)
- Docker Sandboxes: docs.docker.com/ai/claude-code-sandbox
- Backslash Security: backslash.security (MCP Supply Chain Risks)
- MintMCP: mintmcp.com (MCP Gateway Reference Architecture)
- TrueFoundry: truefoundry.com (Enterprise Claude Code Deployment)
- CVE Database: cve.mitre.org
