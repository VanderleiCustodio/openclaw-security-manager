# Identity Agent Editor + FIM Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Identity Agent section (Item 1) with file editor, integrity monitor, and backup management.

**Architecture:** Backend Flask routes for file I/O and hashing; frontend HTML/CSS/JS for editor and FIM tabs. State stored in memory (originalContent) and persistent JSON (identity_baseline.json). Backups timestamped with max 5 per file.

**Tech Stack:** Python Flask, SHA-256 hashing, JSON persistence, vanilla JavaScript

---

### Task 1: Backend — Funções auxiliares e hash

**Files:**
- Modify: `app.py` (add helper functions before routes)

- [ ] **Step 1: Add helper functions to `app.py`**

Before the route definitions (look for `@app.route('/')`), add these imports and functions:

```python
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path

def _get_identity_file_path(filename):
    """Retorna caminho absoluto do arquivo de identidade."""
    base = os.path.expanduser('~/.openclaw/workspace')
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, filename)

def _get_baseline_path():
    """Retorna caminho do arquivo identity_baseline.json."""
    base = os.path.expanduser('~/.openclaw/security')
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, 'identity_baseline.json')

def _get_backups_dir(filename):
    """Retorna dir de backups para um arquivo."""
    base = os.path.expanduser('~/.openclaw/backups/soul')
    os.makedirs(base, exist_ok=True)
    return base

def _hash_file(filepath):
    """Calcula SHA-256 do arquivo em UTF-8."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    except Exception as e:
        return None

def _load_baseline():
    """Carrega identity_baseline.json. Retorna {} se não existir."""
    baseline_file = _get_baseline_path()
    if not os.path.exists(baseline_file):
        return {}
    try:
        with open(baseline_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def _save_baseline(data):
    """Salva identity_baseline.json atomicamente."""
    baseline_file = _get_baseline_path()
    tmp_file = baseline_file + '.tmp'
    try:
        with open(tmp_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_file, baseline_file)
        return True
    except Exception as e:
        if os.path.exists(tmp_file):
            os.remove(tmp_file)
        return False

def _update_baseline(filename, hash_value):
    """Atualiza baseline para um arquivo + timestamp."""
    baseline = _load_baseline()
    baseline[filename] = {
        'hash': hash_value,
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    }
    return _save_baseline(baseline)

def _create_backup(filename, content):
    """Cria backup timestampado. Remove o mais antigo se > 5."""
    backups_dir = _get_backups_dir(filename)
    timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H%M')
    backup_name = f'{filename}.{timestamp}.bak'
    backup_file = os.path.join(backups_dir, backup_name)

    try:
        with open(backup_file, 'w', encoding='utf-8') as f:
            f.write(content)

        # Remove o mais antigo se > 5
        backups = sorted([b for b in os.listdir(backups_dir) if b.startswith(filename)])
        if len(backups) > 5:
            os.remove(os.path.join(backups_dir, backups[0]))

        return True
    except Exception as e:
        return False

def _list_backups(filename):
    """Retorna lista de backups para um arquivo, ordenado por recente."""
    backups_dir = _get_backups_dir(filename)
    try:
        files = [f for f in os.listdir(backups_dir) if f.startswith(filename)]
        files_with_time = []
        for f in files:
            # Parse timestamp do nome
            parts = f.replace(filename + '.', '').replace('.bak', '')
            files_with_time.append((f, parts))
        files_with_time.sort(key=lambda x: x[1], reverse=True)
        return [{'name': f[0], 'timestamp': f[1]} for f in files_with_time]
    except:
        return []
```

- [ ] **Step 2: Validate syntax**

```bash
cd "C:\Users\vande\OneDrive\Documents\files"
python -m py_compile app.py
echo "Syntax OK"
```

Expected: No error output, script returns cleanly.

---

### Task 2: Backend — GET /api/openclaw/identity/files

**Files:**
- Modify: `app.py` (add route)

- [ ] **Step 1: Add GET route**

After the existing config routes (look for `@app.route('/config')`), add:

```python
@app.route('/api/openclaw/identity/files')
@login_required
def api_identity_files():
    """GET: Retorna conteúdo + hash + baseline de arquivos de identidade."""
    include_diff = request.args.get('include_diff', 'false').lower() == 'true'

    files_list = ['SOUL.md', 'AGENTS.md', 'IDENTITY.md', 'MEMORY.md']
    baseline = _load_baseline()
    result = {}

    for filename in files_list:
        filepath = _get_identity_file_path(filename)
        exists = os.path.exists(filepath)
        content = ''
        hash_current = None
        status = 'NOT_FOUND'

        if exists:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                hash_current = hashlib.sha256(content.encode('utf-8')).hexdigest()
            except:
                status = 'NOT_FOUND'

        # Determina status
        if not exists:
            status = 'NOT_FOUND'
        elif filename not in baseline:
            status = 'NOT_BASELINE'
        elif baseline[filename]['hash'] == hash_current:
            status = 'OK'
        else:
            status = 'DRIFT'

        # Calcula diff se necessário (not implemented yet, client-side)
        diff = None

        result[filename.lower().replace('.md', '')] = {
            'content': content,
            'hash_current': hash_current,
            'hash_baseline': baseline.get(filename, {}).get('hash'),
            'baseline_timestamp': baseline.get(filename, {}).get('timestamp'),
            'status': status,
            'exists': exists,
            'diff': diff
        }

    return jsonify(result)
```

- [ ] **Step 2: Test the route**

```bash
curl http://localhost:5000/api/openclaw/identity/files
```

Expected: JSON with `soul`, `agents`, `identity`, `memory` keys, all with `status: "NOT_FOUND"`.

---

### Task 3: Backend — POST /api/openclaw/identity/files

**Files:**
- Modify: `app.py` (add route)

- [ ] **Step 1: Add POST route**

After the GET identity files route, add:

```python
@app.route('/api/openclaw/identity/files', methods=['POST'])
@login_required
def api_identity_files_post():
    """POST: Salva arquivo de identidade + atualiza baseline."""
    data = request.get_json()
    filename = data.get('filename')
    content = data.get('content')

    if not filename or content is None:
        return jsonify({'ok': False, 'error': 'filename e content obrigatórios'}), 400

    # Valida filename
    allowed = ['SOUL.md', 'AGENTS.md', 'IDENTITY.md', 'MEMORY.md']
    if filename not in allowed:
        return jsonify({'ok': False, 'error': 'filename inválido'}), 400

    # Salva arquivo
    filepath = _get_identity_file_path(filename)
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
    except Exception as e:
        return jsonify({'ok': False, 'error': f'Erro ao salvar: {str(e)}'}), 500

    # Calcula hash
    hash_value = hashlib.sha256(content.encode('utf-8')).hexdigest()

    # Cria backup
    _create_backup(filename, content)

    # Atualiza baseline
    _update_baseline(filename, hash_value)

    # Retorna resposta
    timestamp = _load_baseline()[filename]['timestamp']
    return jsonify({
        'ok': True,
        'hash': hash_value,
        'timestamp': timestamp
    })
```

- [ ] **Step 2: Test POST**

```bash
curl -X POST http://localhost:5000/api/openclaw/identity/files \
  -H "Content-Type: application/json" \
  -d '{"filename":"SOUL.md","content":"test content"}'
```

Expected: `{ "ok": true, "hash": "...", "timestamp": "..." }`

---

### Task 4: Backend — POST /api/openclaw/identity/restore

**Files:**
- Modify: `app.py` (add route)

- [ ] **Step 1: Add restore route**

After the POST identity files route, add:

```python
@app.route('/api/openclaw/identity/restore', methods=['POST'])
@login_required
def api_identity_restore():
    """POST: Restaura arquivo do backup + atualiza baseline."""
    data = request.get_json()
    filename = data.get('filename')
    backup = data.get('backup')

    if not filename or not backup:
        return jsonify({'ok': False, 'error': 'filename e backup obrigatórios'}), 400

    # Valida filename
    allowed = ['SOUL.md', 'AGENTS.md', 'IDENTITY.md', 'MEMORY.md']
    if filename not in allowed:
        return jsonify({'ok': False, 'error': 'filename inválido'}), 400

    # Lê backup
    backups_dir = _get_backups_dir(filename)
    backup_file = os.path.join(backups_dir, backup)

    if not os.path.exists(backup_file):
        return jsonify({'ok': False, 'error': 'Backup não encontrado'}), 404

    try:
        with open(backup_file, 'r', encoding='utf-8') as f:
            backup_content = f.read()
    except Exception as e:
        return jsonify({'ok': False, 'error': f'Erro ao ler backup: {str(e)}'}), 500

    # Escreve arquivo
    filepath = _get_identity_file_path(filename)
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(backup_content)
    except Exception as e:
        return jsonify({'ok': False, 'error': f'Erro ao restaurar: {str(e)}'}), 500

    # Recalcula hash do arquivo restaurado
    hash_value = hashlib.sha256(backup_content.encode('utf-8')).hexdigest()

    # Atualiza baseline
    _update_baseline(filename, hash_value)

    timestamp = _load_baseline()[filename]['timestamp']
    return jsonify({
        'ok': True,
        'hash': hash_value,
        'timestamp': timestamp
    })
```

- [ ] **Step 2: Test restore**

After saving a file (Task 3), test restore:

```bash
curl -X POST http://localhost:5000/api/openclaw/identity/restore \
  -H "Content-Type: application/json" \
  -d '{"filename":"SOUL.md","backup":"SOUL.md.2026-04-10T0200.bak"}'
```

Expected: `{ "ok": true, "hash": "...", "timestamp": "..." }`

---

### Task 5: Backend — GET /api/openclaw/identity/backups

**Files:**
- Modify: `app.py` (add route)

- [ ] **Step 1: Add backups list route**

After the restore route, add:

```python
@app.route('/api/openclaw/identity/backups')
@login_required
def api_identity_backups():
    """GET: Lista backups disponíveis para um arquivo."""
    filename = request.args.get('filename')

    if not filename:
        return jsonify({'ok': False, 'error': 'filename obrigatório'}), 400

    allowed = ['SOUL.md', 'AGENTS.md', 'IDENTITY.md', 'MEMORY.md']
    if filename not in allowed:
        return jsonify({'ok': False, 'error': 'filename inválido'}), 400

    backups = _list_backups(filename)

    return jsonify({'backups': backups})
```

- [ ] **Step 2: Test backups list**

```bash
curl http://localhost:5000/api/openclaw/identity/backups?filename=SOUL.md
```

Expected: `{ "backups": [{"name": "SOUL.md.2026-04-10T0200.bak", "timestamp": "2026-04-10T0200"}] }`

---

### Task 6: Frontend — HTML/CSS para seção Identity

**Files:**
- Modify: `templates/index.html` (add nav item and section HTML and CSS)

- [ ] **Step 1: Add nav item**

Find the line with `<a class="nav-item" onclick="showSection('backups-section')">` and add before it:

```html
      <a class="nav-item" onclick="showSection('identity-section')" data-section="identity-section">
        <span class="nav-icon"><i data-lucide="shield-check"></i></span>
        <span class="nav-label">12. Identidade do Agente</span>
      </a>
```

- [ ] **Step 2: Add CSS**

In the `<style>` section, after the `.diff-grid` rules, add:

```css
    /* ── Identity Section ──────────────────────────────────────── */
    .identity-section { display:none; }
    .identity-section.visible { display:block; }

    .identity-tabs { display:flex; gap:8px; margin-bottom:var(--sp2); border-bottom:1px solid var(--s3); }
    .identity-tab { padding:8px 12px; font-size:13px; font-weight:500; color:var(--t3); cursor:pointer; border-bottom:2px solid transparent; transition:all 0.2s; }
    .identity-tab.active { color:var(--t1); border-bottom-color:var(--blue); }

    .identity-editor-wrapper { display:none; }
    .identity-editor-wrapper.active { display:block; }

    .identity-editor { font-family:var(--mono); font-size:12px; width:100%; height:400px; padding:10px; background:var(--s2); border:1px solid var(--s3); border-radius:var(--r2); color:var(--t1); line-height:1.5; }
    .identity-editor:focus { outline:none; border-color:var(--blue); }

    .identity-footer { display:flex; justify-content:space-between; align-items:center; margin-top:8px; font-size:12px; color:var(--t3); }
    .identity-hash { font-family:var(--mono); }

    .identity-alert { padding:10px; margin:var(--sp1) 0; border-radius:var(--r2); font-size:12px; }
    .identity-alert.warn { background:var(--yellow-dim); color:var(--yellow); border-left:3px solid var(--yellow); }
    .identity-alert.drift { background:var(--red-dim); color:var(--red); border-left:3px solid var(--red); }

    .identity-diff { display:none; background:var(--s2); border:1px solid var(--s3); border-radius:var(--r2); padding:10px; margin:var(--sp1) 0; max-height:300px; overflow-y:auto; }
    .identity-diff.visible { display:block; }
    .identity-diff-line { font-family:var(--mono); font-size:12px; line-height:1.5; margin:2px 0; padding:2px 5px; }
    .identity-diff-remove { background:var(--red-dim); color:var(--red); }
    .identity-diff-add { background:var(--green-dim); color:var(--green); }
    .identity-diff-same { color:var(--t4); }

    .identity-fim-table { width:100%; margin-top:var(--sp2); border-collapse:collapse; }
    .identity-fim-table th { text-align:left; font-size:12px; font-weight:600; color:var(--t3); padding:8px; border-bottom:1px solid var(--s3); background:var(--s2); }
    .identity-fim-table td { padding:8px; border-bottom:1px solid var(--s3); font-size:12px; }
    .identity-fim-table tr:hover { background:var(--s2); }

    .identity-status-ok { color:var(--green); }
    .identity-status-drift { color:var(--red); }
    .identity-status-notbaseline { color:var(--yellow); }
    .identity-status-notfound { color:var(--t4); }

    .identity-backups-list { display:none; max-height:200px; overflow-y:auto; background:var(--s2); border:1px solid var(--s3); border-radius:var(--r2); margin-top:8px; }
    .identity-backups-list.visible { display:block; }
    .identity-backup-item { padding:8px; border-bottom:1px solid var(--s3); cursor:pointer; font-size:12px; }
    .identity-backup-item:hover { background:var(--s3); }
```

- [ ] **Step 3: Add HTML section**

Before the `<!-- ============================================================ CONFIG DIFF -->` comment, add the complete identity section HTML (see full HTML in template below)

- [ ] **Step 4: Verify visually**

Start Flask app, navigate to the site, verify "12. Identidade do Agente" appears in sidebar with shield-check icon.

---

### Task 7: Frontend — JavaScript state and tabs

**Files:**
- Modify: `templates/index.html` (add JS before closing `</body>`)

- [ ] **Step 1: Add state variables**

Before the closing `</script>` tag, add:

```javascript
// ── Identity Section State ─────────────────────────────────────
let identityState = {
  originalContent: {},
  currentFile: 'SOUL.md',
  pendingChanges: false,
  pendingSave: null
};
```

- [ ] **Step 2: Add tab switching functions**

```javascript
function switchIdentityTab(tab) {
  const editor = document.getElementById('identity-editor-tab');
  const integrity = document.getElementById('identity-integrity-tab');
  const tabs = document.querySelectorAll('.identity-tab');

  if (tab === 'editor') {
    editor.classList.add('active');
    integrity.classList.remove('active');
    tabs[0].classList.add('active');
    tabs[1].classList.remove('active');
  } else {
    editor.classList.remove('active');
    integrity.classList.add('active');
    tabs[0].classList.remove('active');
    tabs[1].classList.add('active');
    loadIdentityIntegrity();
  }
}

function switchIdentityFile(filename) {
  identityState.currentFile = filename;
  loadIdentityFile(filename);
}
```

- [ ] **Step 3: Add file load function**

```javascript
function loadIdentityFile(filename) {
  const textarea = document.getElementById('identity-textarea');
  const alert = document.getElementById('identity-editor-alert');

  textarea.value = 'Carregando...';
  alert.innerHTML = '';

  fetch('/api/openclaw/identity/files')
    .then(r => r.json())
    .then(data => {
      const key = filename.toLowerCase().replace('.md', '');
      const file = data[key];

      if (!file.exists) {
        alert.innerHTML = '<div class="identity-alert warn">⚠ Arquivo não encontrado — será criado ao salvar</div>';
        textarea.value = '';
      } else {
        textarea.value = file.content;
      }

      identityState.originalContent[filename] = textarea.value;

      const hashDisplay = file.hash_current ? file.hash_current.substring(0, 12) : '—';
      document.getElementById('identity-hash-current').textContent = hashDisplay;

      const timeDisplay = file.baseline_timestamp ? new Date(file.baseline_timestamp).toLocaleString() : '—';
      document.getElementById('identity-baseline-time').textContent = timeDisplay;

      if (file.status === 'DRIFT') {
        alert.innerHTML = '<div class="identity-alert drift">🔴 DRIFT DETECTADO — <button class="btn-ghost" onclick="showIdentityDriftDiff()">Ver diff</button></div>';
      }
    })
    .catch(e => {
      alert.innerHTML = `<div class="identity-alert drift">❌ Erro ao carregar: ${e.message}</div>`;
      textarea.value = '';
    });
}
```

- [ ] **Step 4: Test tabs and file switching**

Click on "12. Identidade" in sidebar, switch between Editor/Integrity tabs, click file buttons (SOUL.md, etc).

---

### Task 8: Frontend — Diff calculation and save

**Files:**
- Modify: `templates/index.html` (add JS)

- [ ] **Step 1: Add diff calculation function**

```javascript
function calculateFileDiff(original, current) {
  const origLines = original.split('\n');
  const currLines = current.split('\n');

  const diff = [];
  const maxLen = Math.max(origLines.length, currLines.length);

  for (let i = 0; i < maxLen; i++) {
    const o = origLines[i] || '';
    const c = currLines[i] || '';

    if (o !== c) {
      if (o) diff.push('- ' + o);
      if (c) diff.push('+ ' + c);
    } else {
      if (o) diff.push('  ' + o);
    }
  }

  return diff;
}
```

- [ ] **Step 2: Add save trigger function**

```javascript
function saveIdentityFile() {
  const filename = identityState.currentFile;
  const textarea = document.getElementById('identity-textarea');
  const currentContent = textarea.value;
  const originalContent = identityState.originalContent[filename] || '';

  const diff = calculateFileDiff(originalContent, currentContent);

  if (diff.length === 0) {
    alert('Nenhuma mudança');
    return;
  }

  const diffPanel = document.getElementById('identity-diff-panel');
  const diffLines = document.getElementById('identity-diff-lines');

  diffLines.innerHTML = diff.map(line => {
    let className = 'identity-diff-same';
    if (line.startsWith('-')) className = 'identity-diff-remove';
    else if (line.startsWith('+')) className = 'identity-diff-add';

    return `<div class="identity-diff-line ${className}">${line.substring(2)}</div>`;
  }).join('');

  diffPanel.classList.add('visible');

  identityState.pendingSave = { filename, content: currentContent };
}

function confirmIdentitySave() {
  const { filename, content } = identityState.pendingSave;

  fetch('/api/openclaw/identity/files', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filename, content })
  })
  .then(r => r.json())
  .then(data => {
    if (data.ok) {
      identityState.originalContent[filename] = content;
      identityState.pendingSave = null;

      document.getElementById('identity-diff-panel').classList.remove('visible');

      document.getElementById('identity-editor-alert').innerHTML = '<div class="identity-alert warn">✓ Arquivo salvo com sucesso</div>';
      setTimeout(() => {
        document.getElementById('identity-editor-alert').innerHTML = '';
      }, 3000);

      loadIdentityFile(filename);
    } else {
      alert('Erro ao salvar: ' + (data.error || 'desconhecido'));
    }
  })
  .catch(e => alert('Erro ao salvar: ' + e.message));
}

function cancelIdentitySave() {
  identityState.pendingSave = null;
  document.getElementById('identity-diff-panel').classList.remove('visible');
}
```

- [ ] **Step 3: Test save flow**

1. Load Identity section, switch to Editor tab
2. Type some text in textarea
3. Click "Salvar"
4. Verify diff shows correctly
5. Click "Confirmar"
6. Verify success message and file reloaded

---

### Task 9: Frontend — FIM (Integrity Monitor)

**Files:**
- Modify: `templates/index.html` (add JS for integrity tab)

- [ ] **Step 1: Add integrity load function**

```javascript
function loadIdentityIntegrity() {
  const tbody = document.getElementById('identity-fim-tbody');
  tbody.innerHTML = '<tr><td colspan="5" style="text-align:center">Carregando...</td></tr>';

  fetch('/api/openclaw/identity/files?include_diff=true')
    .then(r => r.json())
    .then(data => {
      const files = ['SOUL.md', 'AGENTS.md', 'IDENTITY.md'];
      let html = '';

      files.forEach(filename => {
        const key = filename.toLowerCase().replace('.md', '');
        const file = data[key];

        let statusIcon = '⚪';
        let statusClass = 'identity-status-notfound';

        if (file.status === 'OK') {
          statusIcon = '🟢';
          statusClass = 'identity-status-ok';
        } else if (file.status === 'DRIFT') {
          statusIcon = '🔴';
          statusClass = 'identity-status-drift';
        } else if (file.status === 'NOT_BASELINE') {
          statusIcon = '⚠';
          statusClass = 'identity-status-notbaseline';
        }

        const hashCurr = file.hash_current ? file.hash_current.substring(0, 12) : '—';
        const hashBase = file.hash_baseline ? file.hash_baseline.substring(0, 12) : '—';

        html += `<tr>
          <td>${filename}</td>
          <td><span class="${statusClass}">${statusIcon} ${file.status}</span></td>
          <td><code style="font-family:var(--mono);font-size:11px">${hashCurr}</code></td>
          <td><code style="font-family:var(--mono);font-size:11px">${hashBase}</code></td>
          <td>
            <button class="btn-ghost" onclick="registerIdentityBaseline('${filename}')" style="font-size:11px">Registrar baseline</button>
            <button class="btn-ghost" onclick="openIdentityRestore('${filename}')" style="font-size:11px">Restaurar</button>
          </td>
        </tr>`;
      });

      tbody.innerHTML = html;
    })
    .catch(e => {
      tbody.innerHTML = `<tr><td colspan="5" style="color:var(--red)">Erro: ${e.message}</td></tr>`;
    });
}

function registerIdentityBaseline(filename) {
  fetch('/api/openclaw/identity/files')
    .then(r => r.json())
    .then(data => {
      const key = filename.toLowerCase().replace('.md', '');
      const content = data[key].content;

      fetch('/api/openclaw/identity/files', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename, content })
      })
      .then(r => r.json())
      .then(data => {
        if (data.ok) {
          alert('Baseline registrado para ' + filename);
          loadIdentityIntegrity();
        } else {
          alert('Erro: ' + (data.error || 'desconhecido'));
        }
      });
    });
}

function openIdentityRestore(filename) {
  fetch('/api/openclaw/identity/backups?filename=' + filename)
    .then(r => r.json())
    .then(data => {
      if (data.backups.length === 0) {
        alert('Nenhum backup disponível para ' + filename);
        return;
      }

      const choice = prompt('Backups disponíveis:\n' + data.backups.map(b => b.name).join('\n') + '\n\nQual restaurar? (nome exato)');
      if (choice) {
        const backup = data.backups.find(b => b.name === choice);
        if (backup) {
          restoreIdentityFile(filename, backup.name);
        } else {
          alert('Backup não encontrado');
        }
      }
    });
}

function restoreIdentityFile(filename, backup) {
  if (!confirm('Restaurar ' + filename + ' do backup ' + backup + '?')) {
    return;
  }

  fetch('/api/openclaw/identity/restore', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filename, backup })
  })
  .then(r => r.json())
  .then(data => {
    if (data.ok) {
      alert('Arquivo restaurado com sucesso');
      loadIdentityIntegrity();
    } else {
      alert('Erro ao restaurar: ' + (data.error || 'desconhecido'));
    }
  })
  .catch(e => alert('Erro ao restaurar: ' + e.message));
}
```

- [ ] **Step 2: Test FIM**

1. Switch to Integrity tab
2. Verify 3 files show (SOUL.md, AGENTS.md, IDENTITY.md)
3. Click "Registrar baseline"
4. Verify status changes to OK
5. Click "Restaurar" and verify backup list

---

### Task 10: Final integration and commit

**Files:**
- `app.py` (all routes)
- `templates/index.html` (nav, section, CSS, JS)

- [ ] **Step 1: Verify Flask app starts without errors**

```bash
cd "C:\Users\vande\OneDrive\Documents\files"
python app.py &
sleep 2
curl http://localhost:5000
echo "App running"
```

Expected: App starts, serves homepage

- [ ] **Step 2: Smoke test complete workflow**

Via browser:
1. Click "12. Identidade do Agente"
2. Load Editor tab
3. Type content in SOUL.md
4. Click "Salvar", verify diff, click "Confirmar"
5. Switch to Integrity tab
6. Verify SOUL.md shows OK status
7. Click "Registrar baseline"
8. Verify hash updates

- [ ] **Step 3: Commit changes**

```bash
cd "C:\Users\vande\OneDrive\Documents\files"
git add app.py templates/index.html docs/superpowers/specs/2026-04-10-identity-agent-design.md
git commit -m "feat: implement identity agent editor + FIM (item 1)

- 4 API routes for file I/O, hashing, baseline management
- Editor with 4 identity files (SOUL.md, AGENTS.md, IDENTITY.md, MEMORY.md)
- File Integrity Monitor (FIM) with SHA-256 tracking
- Timestamped backups (max 5 per file)
- Client-side diff calculation
- Baseline stored in ~/.openclaw/security/identity_baseline.json
- Full HTML/CSS/JS frontend integration"
```

Expected: Commit succeeds

- [ ] **Step 4: Verify nothing broke existing functionality**

Check that existing sections still work (backups, config diff, etc.)

---

## Complete

All 10 tasks implemented. Ready for review.
