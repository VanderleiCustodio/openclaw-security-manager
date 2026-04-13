---
name: openclaw-full-project-validation
description: Validacao completa do projeto OpenClaw Config Panel (todas as secoes), aplicando mudancas por modulo e checando aceite nos logs do gateway
triggers:
  - teste completo
  - validar projeto inteiro
  - validar todos os modulos
  - regressao config panel
  - full validation openclaw
argument-hint: "[quick|full]"
---

# OpenClaw - Teste Completo do Projeto

## Quando usar

Use esta skill:

- antes de declarar que o painel esta pronto
- apos mexer em `app.py` (patch builders, presets, status logic)
- apos mexer na UI de configuracao (`templates/index.html`)
- antes de commit/review/finalizacao de feature

## Objetivo

Verificar que **todas** as secoes de configuracao:

1. escrevem `openclaw.json` valido
2. sao aceitas pelo gateway em runtime
3. nao geram `reload skipped (invalid config)`

## Escopo de modulos obrigatorios

- `dm_pairing`
- `gateway`
- `sandbox`
- `tools`
- `plugins`
- `logging`
- `model`
- `session`
- `hardened_preset`
- `personal_preset`
- `team_preset`
- `enterprise_preset`
- `devops_preset`

## Protocolo

### 1) Pre-check do gateway

```powershell
openclaw gateway 2>&1 | Select-Object -First 30
```

Se aparecer `Config invalid`, parar e corrigir primeiro.

### 2) Snapshot seguro

Salvar estado atual de `~/.openclaw/openclaw.json` e **restaurar no final**, mesmo em erro.

### 3) Aplicar por modulo (um por vez)

Para cada modulo:

1. gerar patch via `build_patch(section, changes, current)`
2. aplicar merge com `deep_merge`
3. gravar config
4. aguardar reload
5. ler apenas o trecho novo do log
6. classificar `PASS`/`FAIL`

### 4) Regras de FAIL

Falha imediata se o trecho novo do log contiver:

- `reload skipped (invalid config)`
- `Invalid config at`
- `Unrecognized key`
- `Invalid input`

### 5) Resultado final

Entregar tabela por modulo + resumo:

- total
- passed
- failed
- `failed_sections`

## Comando base (modo full)

Use um script Python para automacao (com restore final do arquivo):

```bash
python -c "<script que testa os 13 modulos e imprime PASS/FAIL>"
```

## Guardrails de schema (obrigatorios)

Durante os testes, respeitar:

- `logging.redactSensitive` somente `off|tools`
- `session.reset.mode` somente `daily|idle`
- nao escrever `agents.defaults.tools`
- nao escrever `tools.elevated.allowFrom` como array

## Evidencias minimas no retorno

1. comando executado
2. status por modulo
3. resumo final (total/pass/fail)
4. se falhou: path/campo exato e correcao sugerida

