---
name: openclaw-validate-config-reload
description: Validar mudancas que escrevem no openclaw.json iniciando gateway, exercitando UI e confirmando aceite nos logs (sem reload skipped invalid config)
triggers:
  - validar config openclaw
  - teste gateway
  - reload skipped invalid config
  - config changed log
  - validar toggle tools
  - validar perfil
argument-hint: "<feature|section> [toggle|perfil|campo]"
---

# OpenClaw - Validacao de Config via Gateway Logs

## Quando usar

Use esta skill sempre que uma mudanca no codigo puder alterar o arquivo `~/.openclaw/openclaw.json`, por exemplo:

- novo campo no painel
- novo toggle
- alteracao de perfil
- mudanca em `build_patch()`, `save_config()`, presets ou UI de configuracao

## Objetivo

Garantir que a mudanca:

1. escreve configuracao valida no `openclaw.json`
2. e aceita pelo gateway em runtime (reload ok)
3. sem mensagens de invalidacao no log (`reload skipped (invalid config)`)

## Protocolo obrigatorio

### 1) Levantar estado do gateway

No PowerShell:

```powershell
openclaw gateway 2>&1 | Select-Object -First 30
```

Interpretacao:

- se subir e ficar ouvindo: ok
- se retornar `gateway already running`: ok, ja existe processo ativo
- se retornar `Config invalid`: pare e corrija antes de continuar

### 2) Rodar o teste funcional da mudanca

Executar o fluxo real na UI que voce acabou de implementar:

- exemplo toggle: abrir secao, alternar estado, clicar `Aplicar`
- exemplo perfil: selecionar perfil, clicar `Aplicar`
- exemplo campo: preencher valor, `Preview`, depois `Aplicar`

Nao valide apenas por diff local; valide por comportamento no gateway.

### 3) Validar logs do gateway

Checar log do gateway imediatamente apos aplicar:

```powershell
Get-Content "$env:LOCALAPPDATA\Temp\openclaw\openclaw-$(Get-Date -Format yyyy-MM-dd).log" | Select-Object -Last 200
```

### 4) Critério de aprovacao (PASS/FAIL)

PASS quando:

- existe evento de aplicacao/recarga sem erro (ex.: `Config overwrite`, `tools.effective`, reconnect normal)
- **nao** existe `config reload skipped (invalid config)`
- **nao** existe `Invalid config at ...`

FAIL quando existir qualquer um:

- `config reload skipped (invalid config): ...`
- `Invalid config at ...`
- erro de schema (`Unrecognized key`, `Invalid input`, etc)

## Consulta rapida de erros (recomendada)

```powershell
$log = "$env:LOCALAPPDATA\Temp\openclaw\openclaw-$(Get-Date -Format yyyy-MM-dd).log"
rg "reload skipped \(invalid config\)|Invalid config at|Unrecognized key|Invalid input" "$log"
```

Se houver match, o teste falhou.

## Loop de correcao (obrigatorio em caso de FAIL)

1. identificar campo/path exato no erro de schema
2. corrigir codigo (backend/preset/UI)
3. aplicar novamente o fluxo na UI
4. revalidar logs
5. repetir ate PASS

## Pitfalls recorrentes do schema OpenClaw

- `logging.redactSensitive`: somente `off` ou `tools`
- `session.dmScope`: somente `main`, `per-peer`, `per-channel-peer`, `per-account-channel-peer`
- `channels.*.dmPolicy = allowlist`: requer `allowFrom` valido
- `agents.defaults`: nao aceitar chaves fora do schema (ex.: `tools` em local errado)
- `tools.elevated.allowFrom`: validar tipo conforme schema atual (evitar assumir array)

## Evidencia minima no retorno ao usuario

Ao concluir, sempre informar:

1. comando/teste executado
2. trecho-resumo do resultado do gateway
3. status final: `PASS` ou `FAIL`
4. se FAIL, qual campo/path ficou invalido

