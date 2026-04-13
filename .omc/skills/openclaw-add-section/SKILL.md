---
name: openclaw-add-section
description: Adicionar nova seção/página ao painel OpenClaw (nav + HTML + endpoint Flask + JS)
triggers:
  - adicionar seção
  - nova seção painel
  - nova pagina painel
  - openclaw seção
argument-hint: "<section_id> <title> <lucide_icon> <endpoint>"
---

# OpenClaw — Adicionar Seção ao Painel

## Quando usar

Quando uma nova funcionalidade precisa de uma página/seção própria no painel (ex: métricas, aprovações, logs, etc.).

## Checklist de implementação

### 1. `app.py` — criar endpoint
```python
@app.route("/api/minha-secao")
@login_required
def api_minha_secao():
    # lógica aqui
    return jsonify({...})
```
Para ações POST:
```python
@app.route("/api/minha-secao/acao", methods=["POST"])
@login_required
def api_minha_secao_acao():
    req = request.json or {}
    # ...
    return jsonify({"ok": True})
```

### 2. `index.html` — nav item
Encontrar com grep: `data-section="profiles-section"` e adicionar após:
```html
<a class="nav-item" onclick="showSection('minha-secao-section')" data-section="minha-secao-section">
  <span class="nav-icon"><i data-lucide="ICONE_LUCIDE"></i></span>
  <span class="nav-label">Título da Seção</span>
  <!-- opcional: badge de contagem -->
  <span class="nav-badge" id="minha-secao-nav-badge" style="display:none"></span>
</a>
```
Ícones lucide disponíveis: `activity`, `user-check`, `layers`, `shield`, `terminal`, `database`, etc.

### 3. `index.html` — HTML da seção
Adicionar antes do `<!-- CHECKLIST -->`:
```html
<!-- ============================================================ MINHA SECAO -->
<div class="section" id="minha-secao-section">
  <div class="section-header">
    <span class="section-icon"><i data-lucide="ICONE_LUCIDE"></i></span>
    <h2>Título da Seção</h2>
    <button onclick="loadMinhaSec()" style="background:var(--s2);color:var(--t3);border:1px solid var(--b1);margin-left:auto;font-size:12px;padding:5px 10px;border-radius:var(--r2)">🔄 Atualizar</button>
  </div>
  <p class="hint" style="margin-bottom:var(--sp2)">Descrição breve do que esta seção faz.</p>
  <div id="minha-secao-container">
    <div class="loading-spinner" style="text-align:center;padding:40px;color:var(--t3)">Carregando...</div>
  </div>
</div>
```

### 4. `index.html` — mapa de títulos
Buscar com grep: `SECTION_TITLES` ou `profiles-section.*layers` e adicionar:
```javascript
'minha-secao-section': { icon: 'ICONE_LUCIDE', title: 'Título da Seção' },
```

### 5. `index.html` — `showSection()` auto-load
Buscar com grep: `profiles-section.*loadProfiles` e adicionar:
```javascript
if (id === 'minha-secao-section') loadMinhaSec();
```

### 6. `index.html` — funções JS
```javascript
// ---------------------------------------------------------- minha-secao
async function loadMinhaSec() {
  const el = document.getElementById('minha-secao-container');
  if (!el) return;
  try {
    const res = await fetch('/api/minha-secao');
    const data = await res.json();
    // renderizar data em el.innerHTML
    el.innerHTML = `...`;
  } catch(e) {
    el.innerHTML = '<div style="color:var(--red)">❌ Erro ao carregar</div>';
  }
}

async function acaoMinhaSec(id) {
  const res = await fetch('/api/minha-secao/acao', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({id})
  });
  const d = await res.json();
  if (d.ok) { showToast('✅ Ação realizada'); loadMinhaSec(); }
  else showToast('❌ ' + (d.error || 'Erro'), true);
}
```

## Ordem de busca com grep (não ler arquivos inteiros)

```
grep "data-section=\"profiles-section\""  → onde adicionar nav
grep "<!-- ============.*CHECKLIST -->"   → onde adicionar seção HTML
grep "profiles-section.*layers.*title"   → onde adicionar no SECTION_TITLES
grep "profiles-section.*loadProfiles"    → onde adicionar auto-load
grep "async function previewProfile"     → onde adicionar funções JS
```

## Pitfalls críticos

- `data-lucide="X"` só funciona se o ícone `X` existir no lucide — verificar em lucide.dev
- O `id` do container no HTML deve coincidir com o `document.getElementById(...)` no JS
- `showToast(msg, true)` = toast de erro (vermelho); sem o `true` = sucesso (verde)
- Auto-refresh: usar `setTimeout` + verificar se seção ainda está visível antes de recarregar
- Validar sintaxe Python após editar app.py: `python -c "import ast; ast.parse(open('app.py', encoding='utf-8').read())"`
