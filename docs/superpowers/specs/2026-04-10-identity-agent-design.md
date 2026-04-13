# Design: Seção "12. Identidade do Agente"

**Data:** 2026-04-10 (revisado após review)
**Projeto:** OpenClaw Security Manager (Flask + Vanilla JS)
**Item:** 1 de 5 — CRÍTICO

---

## Resumo

Adicionar a seção "12. Identidade do Agente" em Configurações. A seção possui duas abas: **Editor** (leitura/edição de arquivos de identidade com diff client-side antes de salvar) e **Integridade / FIM** (File Integrity Monitor com comparação de hashes SHA-256).

---

## Stack

- **Backend:** Python Flask, adicionando rotas em `app.py`
- **Frontend:** HTML/CSS/JS vanilla em `templates/index.html`
- **Padrão:** seguir exatamente os padrões existentes (classes CSS, funções JS, patch builders Python)

---

## Arquivos Monitorados

| Arquivo       | Editor | FIM | Observação |
|---------------|--------|-----|------------|
| SOUL.md       | ✓      | ✓   | |
| AGENTS.md     | ✓      | ✓   | |
| IDENTITY.md   | ✓      | ✓   | |
| MEMORY.md     | ✓      | —   | Excluído do FIM intencionalmente — é escrito pelo agente durante operação normal e geraria falsos positivos constantes. Monitorado apenas para edição manual no Editor. |

Caminho base dos arquivos: `~/.openclaw/workspace/`
Backups com timestamp: `~/.openclaw/backups/soul/<FILENAME>.<TIMESTAMP>.bak` (ex: `SOUL.md.2026-04-10T0200.bak`)
Máximo de backups por arquivo: 5 (remove o mais antigo ao exceder)
Baseline salvo em: `~/.openclaw/security/identity_baseline.json`

---

## Rotas de API

### `GET /api/openclaw/identity/files?include_diff=false`

Retorna para cada arquivo (`soul`, `agents`, `identity`, `memory`):
```json
{
  "soul": {
    "content": "...",
    "hash_current": "abc123...",
    "hash_baseline": "abc123...",
    "baseline_timestamp": "2026-04-10T02:00:00",
    "status": "OK",
    "exists": true,
    "diff": null
  }
}
```

- `status` possíveis: `"OK"` | `"DRIFT"` | `"NOT_BASELINE"` | `"NOT_FOUND"`
- Quando `?include_diff=true` e `status === "DRIFT"`: o campo `diff` contém lista de linhas `["-linha antiga", "+linha nova", " igual"]`
- Quando `status !== "DRIFT"` ou `include_diff` não informado: `diff` é `null` (não calcular desnecessariamente)
- **Substitui** a rota separada `/api/openclaw/identity/integrity` — use `include_diff=true` na aba FIM

### `POST /api/openclaw/identity/files`

Body:
```json
{
  "filename": "SOUL.md",
  "content": "..."
}
```

- Salva o arquivo em `~/.openclaw/workspace/<filename>`
- SHA-256 calculado sobre o conteúdo em **UTF-8** (sempre no backend, nunca no frontend)
- Atualiza `~/.openclaw/security/identity_baseline.json` com novo hash + timestamp (sempre — sem flag)
- Cria backup timestampado: `~/.openclaw/backups/soul/<filename>.<ISO8601>.bak`
- Remove backup mais antigo se total > 5 por arquivo
- **Response:** `{ "ok": true, "hash": "...", "timestamp": "..." }` — sem `diff` (calculado client-side antes do POST)

### `POST /api/openclaw/identity/restore`

Body: `{ "filename": "SOUL.md", "backup": "SOUL.md.2026-04-10T0200.bak" }`
- Copia o backup selecionado → `~/.openclaw/workspace/<filename>`
- Recalcula SHA-256 do arquivo restaurado (UTF-8)
- Atualiza `identity_baseline.json` com o novo hash + timestamp (evita DRIFT falso pós-restore)
- **Response:** `{ "ok": true, "hash": "...", "timestamp": "..." }`
- Retorna erro inline se backup não existir

### `GET /api/openclaw/identity/backups`

Body: `{ "filename": "SOUL.md" }`
Retorna lista de backups disponíveis para um arquivo, ordenados do mais recente ao mais antigo:
```json
{
  "backups": [
    { "name": "SOUL.md.2026-04-10T0200.bak", "timestamp": "2026-04-10T02:00:00" }
  ]
}
```

---

## Armazenamento

### `~/.openclaw/security/identity_baseline.json`
```json
{
  "SOUL.md":     { "hash": "abc123...", "timestamp": "2026-04-10T02:00:00" },
  "AGENTS.md":   { "hash": "def456...", "timestamp": "2026-04-10T02:00:00" },
  "IDENTITY.md": { "hash": "ghi789...", "timestamp": "2026-04-10T02:00:00" },
  "MEMORY.md":   { "hash": "jkl012...", "timestamp": "2026-04-10T02:00:00" }
}
```

Se o arquivo existir mas estiver corrompido (JSON inválido): exibir erro inline e oferecer opção "Recriar do zero" (sem restaurar de backup automaticamente).

### Backups timestampados
- Formato: `~/.openclaw/backups/soul/<FILENAME>.<YYYY-MM-DDTHHMM>.bak`
- Máximo 5 por arquivo; o mais antigo é removido ao exceder
- Diretório criado automaticamente se não existir

---

## UI — Aba Editor

**Fluxo de carregamento:**
1. Ao abrir a aba, chama `GET /api/openclaw/identity/files` (sem `include_diff`)
2. Armazena o conteúdo original em `originalContent[filename]` em memória no JS
3. Popula o `<textarea>` com o conteúdo

**Comportamento:**
- Tabs: `SOUL.md` · `AGENTS.md` · `IDENTITY.md` · `MEMORY.md`
- Se arquivo não existe: banner amarelo "Arquivo não encontrado — será criado ao salvar"
- Se DRIFT detectado: banner vermelho "⚠ DRIFT DETECTADO" com botão "Ver diff"
- `<textarea>` monospace, ~400px altura (`--mono`, `--s2`)
- Rodapé: hash atual (12 chars) + data/hora do baseline (ou "Sem baseline" em amarelo)

**Fluxo de salvar (sem GET extra):**
1. Usuário clica "Salvar"
2. Frontend calcula diff entre `originalContent[filename]` e `textarea.value` (client-side, linha a linha)
3. Exibe painel de diff inline estilo terminal
4. Botões: **"Confirmar"** e **"Cancelar"**
5. Ao confirmar: `POST /api/openclaw/identity/files` com `{ filename, content: textarea.value }`
6. Response `{ ok, hash, timestamp }`: se hash do response ≠ hash do `originalContent`, exibe alerta de conflito de edição concorrente
7. Atualiza `originalContent[filename]` com o novo conteúdo
8. Fecha painel de diff

---

## UI — Aba Integridade (FIM)

**Carregamento:** `GET /api/openclaw/identity/files?include_diff=true`

Tabela com 3 linhas (SOUL.md, AGENTS.md, IDENTITY.md):

- **Coluna Status:** badge colorido — 🟢 OK | 🔴 DRIFT | ⚪ NOT\_BASELINE
- **Coluna Hash atual:** 12 primeiros chars do SHA-256
- **Coluna Baseline:** 12 primeiros chars do hash salvo (ou "—" se ausente)
- **Coluna Ações:**
  - Botão "Registrar baseline" — POST salvar conteúdo atual (sem alteração) para forçar atualização de baseline
  - Botão "Restaurar" — abre seletor de backup (lista de backups via `GET /api/openclaw/identity/backups`), pede confirmação inline, então POST restore
- Status DRIFT: clique expande diff inline abaixo da linha
- Botão "Restaurar" sem backups disponíveis: não usar `disabled`. Usar `<span title="Nenhum backup disponível">` wrapper + `pointer-events: none; opacity: 0.4` no botão interno, + texto muted abaixo: "Nenhum backup disponível"
- Erros aparecem inline na linha do arquivo, não como `alert()`

---

## Comportamento de Diff

Calculado **client-side** (comparação linha a linha entre `originalContent` e `textarea.value`).
Estilo terminal:
```
- linha removida  (cor: var(--red))
+ linha adicionada (cor: var(--green))
  linha igual     (cor: var(--t4))
```

SHA-256 é sempre calculado no **backend** sobre conteúdo UTF-8. O frontend nunca recalcula hash.

---

## Tratamento de Erros

| Situação | Comportamento |
|----------|---------------|
| Arquivo não existe | Banner amarelo, textarea vazio, permite criar |
| Backup não existe | Texto muted "Nenhum backup disponível" (não `disabled`) |
| Erro de permissão | Mensagem inline na seção |
| `identity_baseline.json` não existe | Criado automaticamente na primeira operação |
| `identity_baseline.json` corrompido | Erro inline + botão "Recriar do zero" |
| Diretório `backups/soul` não existe | Criado automaticamente antes de salvar backup |
| Conflito de edição concorrente | Alerta inline após POST se hash divergir do esperado |

---

## Integração com Navegação

Adicionar item na nav lateral de Configurações:
```html
<a class="nav-item" onclick="showSection('identity-section')" data-section="identity-section">
  <span class="nav-icon"><i data-lucide="shield-check"></i></span>
  <span class="nav-label">12. Identidade do Agente</span>
</a>
```

---

## Fora do Escopo (Item 1)

- Itens 2–5 da especificação (Canais, Auditoria de Skill, Red Lines, Auditoria Noturna)
- Syntax highlight no editor (usar fonte monospace simples)
- Diff lado a lado (usar estilo terminal)
- Autenticação separada (usar `@login_required` existente)
