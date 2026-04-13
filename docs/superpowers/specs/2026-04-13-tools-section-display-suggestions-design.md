# Design: Ferramentas — exibição e sugestões fixas no painel

**Data:** 2026-04-13  
**Projeto:** OpenClaw Security Manager  
**Status:** aprovado pelo solicitante (brainstorm opção A + abordagem 1+2)

---

## 1. Objetivo

Melhorar a **seção 4. Ferramentas (Tools)** do painel para:

1. Exibir o estado real de `tools.profile` e manter consistência com `openclaw.json`.
2. Oferecer **sugestões fixas** (copy, avisos, botões de atalho) que ajudem a aplicar postura segura em `tools.deny`, sem integração com audit/IA nesta entrega.

**Fora de escopo:** sugestões dinâmicas a partir de `openclaw security audit` ou IA Review.

---

## 2. Problema atual (evidência)

- O template usa `state.tools_profile`, mas `get_ui_state()` em `app.py` **não define** `tools_profile` a partir de `cfg["tools"]["profile"]`. O select e o badge “valor atual” podem ficar **desalinhados** do JSON.
- A UI já documenta o mutex **perfil vs allow/deny** (`_patch_tools`); faltam **atalhos** que orientem denies recomendados e **reforço de risco** para `tools.profile: full`.

---

## 3. Comportamento desejado

### 3.1 Estado e exibição

- Incluir em `get_ui_state(cfg)` a chave **`tools_profile`**: string do perfil atual (`full` | `coding` | `messaging` | `minimal`) ou vazio/`None` quando ausente.
- O `<select id="tools_profile">` e o hint “valor atual” devem refletir esse valor após reload da página.

### 3.2 Aviso para perfil `full`

- Ao selecionar **`full`** (ou equivalente), manter/reforçar aviso explícito de risco (já existe `markWarn` em parte do fluxo — alinhar mensagem ao texto de segurança do painel).
- Mensagem em pt-BR: deixar claro que é o perfil mais permissivo e só deve ser usado em ambientes confiáveis.

### 3.3 Faixa “Sugestões rápidas” (deny)

- Adicionar uma linha de **botões** (rótulos curtos) que acrescentam entradas típicas a **`tools.deny`**, alinhadas às verificações já usadas no status de segurança, por exemplo:
  - negar padrões relacionados a **sudo**;
  - negar padrões relacionados a **segredos** (ex.: `.ssh`, `.aws`);
  - negar padrões relacionados a **arquivos `.env`** / vazamento de ambiente (coerente com as linhas `tools_deny_*` do `RECOMMENDED` em `app.py`).
- **Normalização:** merge na lista existente (split por vírgula, trim, **deduplicar** tokens); não apagar denies já definidos pelo usuário sem ação explícita.

### 3.4 Mutex perfil × allow/deny

- Se **`tools_profile`** estiver **preenchido** (valor não vazio no select), o backend remove `allow`/`deny` ao aplicar perfil. Portanto:
  - Os botões de sugestão rápida **não devem** aplicar mudanças silenciosas que seriam descartadas ou contraditórias.
  - **Comportamento padrão recomendado:** se houver perfil selecionado, ao clicar em um botão rápido mostrar **toast ou hint** fixo: para usar denies granulares, o usuário deve **limpar o perfil** (valor vazio / “usar allow+deny”).
  - **Opcional (uma única ação explícita):** botão “Limpar perfil e aplicar pacote de denies” com **confirmação** (`confirm` ou modal leve) que: (1) zera o select de perfil no cliente, (2) preenche `tools_deny` com o pacote escolhido. Se este fluxo for implementado, documentar no hint para evitar surpresa.

**Decisão de implementação:** começar pelo comportamento **toast + não alterar** quando perfil ativo; o fluxo opcional com confirmação fica como melhoria se couber no mesmo PR sem inflar demais o JS.

### 3.5 Accordion “Avançado” (opcional)

- Colapsar **allow / deny / elevated** sob um bloco **“Avançado”** (aberto por padrão na primeira visita ou fechado — preferência: **aberto** para não esconder o que já existe hoje, ou **fechado** se a faixa de sugestões + perfil bastar; **recomendação:** manter aberto na v1 para não mudar hábito; accordion pode ser v2).

**Decisão v1:** accordion **não obrigatório** na primeira implementação; pode ser omitido para reduzir diff. Se implementado, usar `<details>`/`<summary>` ou padrão CSS já usado no projeto.

---

## 4. Arquivos impactados

| Arquivo | Mudança |
|---------|---------|
| `app.py` | `get_ui_state`: adicionar `tools_profile`. |
| `templates/index.html` | Hints, faixa de botões, JS para merge/deny e checagem de perfil; alinhar `markWarn` / mensagem `full`. |

Nenhuma rota nova obrigatória; Preview/Aplicar existentes permanecem.

---

## 5. Testes manuais

1. Config só com `tools.profile: coding` — reload: select mostra `coding`; allow/deny vazios na UI coerentes com JSON.
2. Config só com `allow`/`deny`, sem profile — sugestões rápidas acrescentam denies; Preview mostra patch esperado.
3. Com profile preenchido — clique em sugestão rápida: **não** altera lista (ou só após confirmação “limpar perfil”, se implementado).
4. Selecionar `full` — aviso visível ou confirm alinhado ao copy de segurança.

---

## 6. Riscos e mitigação

| Risco | Mitigação |
|-------|-----------|
| Strings de deny divergem do que o OpenClaw aceita | Reutilizar padrões já assumidos em `RECOMMENDED` / comentários existentes no painel; não inventar sintaxe nova sem doc. |
| Usuário acha que “sugestão” alterou o JSON com perfil ativo | Toast claro + documentação inline na faixa de botões. |

---

## 7. Próximo passo (fora deste documento)

Após revisão deste spec: plano de implementação (tarefas pequenas em `app.py` + `index.html`) e PR único.
