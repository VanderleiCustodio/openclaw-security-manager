# AI Config Review Design

## Context

O painel já executa auditoria (`openclaw security audit`) e coleta sinais operacionais (`/gateway/errors`, `/docker/status`), mas hoje o resultado chega em texto bruto e exige interpretação manual. A proposta adiciona uma camada de análise com IA para transformar esses sinais em diagnóstico priorizado e sugestões acionáveis.

Restrições acordadas:
- Implementação deve ficar diretamente em `app.py` e `templates/index.html`.
- Provedor de IA: Anthropic.
- Modelo padrão: `claude-opus-4-5`, com seletor de opções na UI.
- Chave da API deve ser persistente, fora de hardcode, editável pela UI.
- Persistência da chave em variável de ambiente no arquivo `~/.openclaw/.env`.

## Goals

- Permitir configurar API key e modelo da IA na aba de IA do painel.
- Persistir essas configurações de forma segura e alterável.
- Executar uma revisão de configuração baseada em contexto real (deep audit + telemetria local).
- Retornar recomendações estruturadas com prioridade e impacto.

## Non-Goals

- Não aplicar alterações automaticamente na configuração do OpenClaw.
- Não criar módulo Python separado (sem `ai_review.py`).
- Não adicionar suporte multi-provider nesta etapa inicial.

## High-Level Architecture

### Backend (`app.py`)

Adicionar funções auxiliares e rotas HTTP no próprio arquivo:

1. **Configuração IA**
   - `GET /api/ai/settings`
   - `POST /api/ai/settings`

2. **Análise IA**
   - `POST /api/ai/review-config`

3. **Helpers internos**
   - Leitura/escrita idempotente de `~/.openclaw/.env`.
   - Resolução do modelo ativo.
   - Coleta de contexto para análise.
   - Chamada HTTP ao endpoint Anthropic.
   - Validação/parsing da resposta JSON da IA.

### Frontend (`templates/index.html`)

Na aba de IA:
- Card de configurações (API key + seletor de modelo + salvar).
- Card de execução da análise (botão + loading + resultados).
- Renderização estruturada de summary, risco, achados, sugestões e ações prioritárias.

## Data Flow

1. Usuário abre aba IA.
2. Front chama `GET /api/ai/settings`.
3. UI mostra status da chave (`configurada` / `não configurada`) e modelo atual.
4. Usuário salva settings em `POST /api/ai/settings`.
5. Usuário dispara `POST /api/ai/review-config`.
6. Backend coleta contexto:
   - config atual (`load_config()`, sanitizada),
   - audit deep (`openclaw security audit --deep`),
   - erros de gateway (lógica já existente),
   - status docker/podman (lógica já existente).
7. Backend monta prompt estruturado e chama Anthropic.
8. IA retorna JSON estruturado.
9. Backend valida e devolve para UI.
10. UI renderiza recomendações e prioridades.

## API Contract

### `GET /api/ai/settings`

Response:

```json
{
  "success": true,
  "provider": "anthropic",
  "model": "claude-opus-4-5",
  "api_key_configured": true
}
```

### `POST /api/ai/settings`

Request:

```json
{
  "api_key": "sk-ant-...",
  "model": "claude-opus-4-5"
}
```

Response:

```json
{
  "success": true,
  "provider": "anthropic",
  "model": "claude-opus-4-5",
  "api_key_configured": true
}
```

Rules:
- `api_key` pode ser vazio para manter a existente.
- Se vier valor novo, sobrescreve `ANTHROPIC_API_KEY`.
- `model` deve estar em allowlist de modelos aceitos pela UI/backend.

### `POST /api/ai/review-config`

Request:

```json
{
  "deep": true
}
```

Response:

```json
{
  "success": true,
  "analysis": {
    "summary": "string",
    "risk_level": "low|medium|high|critical",
    "findings": [
      {
        "title": "string",
        "evidence": "string",
        "impact": "string",
        "severity": "low|medium|high|critical"
      }
    ],
    "suggestions": [
      {
        "title": "string",
        "why": "string",
        "recommended_change": "string",
        "how": [
          "string"
        ],
        "openclaw_reference": "string",
        "target_section": "tools|sandbox|plugins|identity|session|other",
        "priority": "P1|P2|P3"
      }
    ],
    "priority_actions": [
      "string"
    ]
  },
  "meta": {
    "model": "claude-opus-4-5",
    "context": {
      "audit_deep_used": true,
      "gateway_error_count": 0
    }
  }
}
```

## Prompting Strategy

O prompt da IA deve:
- incluir contexto consolidado em JSON;
- forçar saída estritamente em JSON com schema esperado;
- pedir evidência explícita para cada finding;
- exigir fundamentação na documentação oficial do OpenClaw para cada recomendação;
- explicar claramente o **porquê** (risco/impacto) e o **como** (passos objetivos) de cada sugestão;
- proibir recomendações fora do escopo do contexto recebido.

Estrutura:
1. System prompt com papel (security config reviewer).
2. Developer constraints (responder somente JSON válido, com campos `why`, `how` e `openclaw_reference` obrigatórios em `suggestions`).
3. User payload com dados coletados (`config`, `audit`, `errors`, `docker`) + trechos relevantes da documentação OpenClaw local.
4. Instrução explícita para citar seção/tópico de referência da doc usada em cada recomendação.

## Security & Secrets

- Segredo em `~/.openclaw/.env`, nunca hardcoded.
- Nunca retornar API key completa para frontend.
- No máximo retornar `api_key_configured: true/false`.
- Em Linux/macOS, ajustar permissão para `600` quando criar/atualizar o arquivo.
- Logs não devem incluir o conteúdo da chave nem payload completo de segredo.

## Error Handling

Casos cobertos:
- chave ausente;
- modelo inválido;
- timeout na API Anthropic;
- falha de rede / HTTP não-200;
- resposta IA sem JSON válido ou schema incompleto.

Formato de erro padronizado:

```json
{
  "success": false,
  "error": "mensagem amigável",
  "details": "opcional para debug"
}
```

## Testing Strategy

### Manual backend
- Salvar settings com e sem chave.
- Validar persistência após restart da app.
- Rodar review com chave válida.
- Rodar review sem chave (erro esperado).
- Simular timeout/rede indisponível.

### Manual frontend
- Campo senha mascarado e editável.
- Troca de modelo persistida.
- Loading durante análise.
- Renderização robusta com listas vazias.
- Mensagens de erro claras.

## Rollout Plan

1. Implementar rotas e helpers de settings IA.
2. Implementar rota de review + integração Anthropic.
3. Implementar UI da aba IA para settings e resultados.
4. Validar fluxo ponta a ponta com deep audit.

## Open Questions Resolved

- Provider inicial: Anthropic.
- Modelo padrão: `claude-opus-4-5`.
- Troca de modelo: sim, por seletor de opções na UI.
- Persistência de chave: variável de ambiente em `~/.openclaw/.env`.
- Escopo de implementação: somente `app.py` + `templates/index.html`.
