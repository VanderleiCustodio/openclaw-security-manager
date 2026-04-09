# Login Design System — OpenClaw Security Manager

Extracted from `templates/index.html` (DashStack-inspired design system).

---

## 1. CSS Variables Available

### Shared constants (theme-independent)
```css
--sp1: 8px;  --sp2: 16px;  --sp3: 24px;
--sp4: 32px; --sp5: 40px;  --sp6: 48px;
--r1: 4px; --r2: 6px; --r3: 10px; --r4: 14px;
--font: 'Inter', system-ui, sans-serif;
--mono: 'JetBrains Mono', 'Fira Code', monospace;
--accent:      #4361EE;
--accent-h:    #3451D1;
--accent-dim:  rgba(67,97,238,.12);
--accent-ring: rgba(67,97,238,.30);
--accent-sh:   0 2px 8px rgba(67,97,238,.35);
```

### Light theme (`[data-theme="light"]`, default)
```css
--bg:  #F5F6FA;   /* page background */
--s1:  #FFFFFF;   /* card/surface 1 */
--s2:  #F0F2F8;   /* input background */
--s3:  #E8EBEF;   /* deeper surface */
--b1:  #E0E4EC;   /* border light */
--b2:  #CDD2DC;   /* border medium */
--t1:  #1B2431;   /* primary text */
--t2:  #4A5568;   /* secondary text */
--t3:  #718096;   /* muted text */
--t4:  #A0AEC0;   /* disabled/label text */
--sh1: 0 1px 3px rgba(0,0,0,.07), 0 1px 2px rgba(0,0,0,.05);
--sh2: 0 4px 16px rgba(0,0,0,.10);
--red: #DC2626; --red-dim: rgba(220,38,38,.10);
```

### Dark theme (`[data-theme="dark"]`)
```css
--bg:  #111827;
--s1:  #1E2A3B;
--s2:  #273142;
--s3:  #2D3A4D;
--b1:  #2D3F56;
--b2:  #3D5166;
--t1:  #F0F4FF;
--t2:  #C8D8E8;
--t3:  #8A9BB0;
--t4:  #5A6A7E;
--a-light: #7B93F5;
--sh1: 0 1px 3px rgba(0,0,0,.4);
--sh2: 0 4px 16px rgba(0,0,0,.5);
--red: #F87171; --red-dim: rgba(248,113,113,.12);
```

---

## 2. Form & Input Classes

### Field wrapper
```css
.field         { margin-bottom: 10px; }
.field:last-child { margin-bottom: 0; }

.field-label {
  font-size: 10px; color: var(--t3);
  font-family: var(--mono); margin-bottom: 4px;
  display: block;
}
.field-label.warn { color: var(--amber); }
.hint { font-size: 11px; color: var(--t4); margin-top: 4px; }
```

### Input element (text/password)
```css
input[type="text"], input[type="number"] {
  background: var(--s2); color: var(--t1);
  border: 1px solid var(--b1); border-radius: var(--r2);  /* 6px */
  padding: 7px 11px; font-size: 13px; font-family: var(--font);
  outline: none; transition: border-color .15s, box-shadow .15s;
  width: 100%; appearance: none;
}
input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-dim);
}
```

Note: `input[type="password"]` is NOT explicitly styled in index.html but follows the same rules as `input[type="text"]` — apply identical styles manually in login.html.

---

## 3. Button Patterns

Base button:
```css
button {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 8px 16px; border: 1px solid transparent;
  border-radius: var(--r2);  /* 6px */
  font-size: 13px; font-weight: 500; font-family: var(--font);
  transition: background .15s, box-shadow .15s, opacity .15s;
  letter-spacing: -.01em;
}
button:hover  { opacity: .88; }
button:active { opacity: .72; }
```

Available variants:

| Class        | Use case         | Style |
|--------------|------------------|-------|
| `.btn-apply` | Primary/submit   | `background: var(--accent); color: #fff; font-weight: 600; box-shadow: var(--accent-sh)` |
| `.btn-ghost` | Secondary/cancel | `background: var(--s1); color: var(--t2); border-color: var(--b1)` |
| `.btn-audit` | Subtle/outline   | `background: var(--accent-dim); color: var(--accent); border-color: var(--accent-ring)` |

**Login submit button should use `.btn-apply`** — it is the primary CTA style in the system.

---

## 4. Card Pattern

```css
.card {
  background: var(--s1);
  border: 1px solid var(--b1);
  border-radius: var(--r3);  /* 10px */
  padding: var(--sp2);       /* 16px */
  box-shadow: var(--sh1);
}
```

---

## 5. Dark/Light Theme Support

- Theme is toggled via `data-theme="light"` or `data-theme="dark"` on the `<html>` element.
- All colors use CSS variables so they switch automatically.
- The `<html>` tag defaults to `data-theme="light"`.
- The sidebar has its own fixed dark navy palette (`--sb-*`) that never changes with theme.
- login.html does NOT need the sidebar — it should use only the content-area variables.

---

## 6. How login.html Should Be Structured

### Structural approach
- No sidebar, no `.layout` wrapper.
- Full-page centered layout: `min-height: 100vh; display: flex; align-items: center; justify-content: center; background: var(--bg)`.
- Single `.card` centered on screen with `max-width: 360px; width: 100%`.
- Import the same Google Fonts (Inter + JetBrains Mono).
- Copy the `:root`, `[data-theme="light"]`, and `[data-theme="dark"]` token blocks verbatim.
- Add `data-theme="light"` on `<html>` (matches index.html default).

### Visual consistency rules
1. Use `var(--s1)` for card background, `var(--b1)` for border, `var(--r3)` for border-radius.
2. Use `var(--s2)` for input backgrounds — same as all other inputs in the system.
3. Focus ring: `border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-dim)`.
4. Submit button: `.btn-apply` — blue accent, white text, accent shadow.
5. Labels: `font-family: var(--mono); font-size: 10px; color: var(--t3)` — matches `.field-label`.
6. Error messages: use `var(--red)` text on `var(--red-dim)` background.

---

## 7. Minimal Example — Login Card

```html
<!DOCTYPE html>
<html lang="pt-BR" data-theme="light">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>OpenClaw — Login</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    /* ── Design tokens (copy from index.html) ── */
    :root {
      --sp1:8px; --sp2:16px; --sp3:24px;
      --r2:6px; --r3:10px;
      --font:'Inter',system-ui,sans-serif;
      --mono:'JetBrains Mono','Fira Code',monospace;
      --accent:#4361EE; --accent-h:#3451D1;
      --accent-dim:rgba(67,97,238,.12);
      --accent-ring:rgba(67,97,238,.30);
      --accent-sh:0 2px 8px rgba(67,97,238,.35);
    }
    :root, [data-theme="light"] {
      --bg:#F5F6FA; --s1:#FFFFFF; --s2:#F0F2F8;
      --b1:#E0E4EC; --b2:#CDD2DC;
      --t1:#1B2431; --t2:#4A5568; --t3:#718096; --t4:#A0AEC0;
      --red:#DC2626; --red-dim:rgba(220,38,38,.10);
      --sh1:0 1px 3px rgba(0,0,0,.07),0 1px 2px rgba(0,0,0,.05);
      --sh2:0 4px 16px rgba(0,0,0,.10);
    }
    [data-theme="dark"] {
      --bg:#111827; --s1:#1E2A3B; --s2:#273142;
      --b1:#2D3F56; --b2:#3D5166;
      --t1:#F0F4FF; --t2:#C8D8E8; --t3:#8A9BB0; --t4:#5A6A7E;
      --red:#F87171; --red-dim:rgba(248,113,113,.12);
      --sh1:0 1px 3px rgba(0,0,0,.4);
      --sh2:0 4px 16px rgba(0,0,0,.5);
    }

    /* ── Reset ── */
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: var(--font); font-size: 14px;
      background: var(--bg); color: var(--t1);
      line-height: 1.5; letter-spacing: -.01em;
      min-height: 100vh;
      display: flex; align-items: center; justify-content: center;
    }

    /* ── Login card ── */
    .login-card {
      background: var(--s1);
      border: 1px solid var(--b1);
      border-radius: var(--r3);
      padding: var(--sp3);
      box-shadow: var(--sh2);
      width: 100%; max-width: 360px;
    }

    .login-header {
      text-align: center;
      margin-bottom: var(--sp3);
    }
    .login-header h1 {
      font-size: 18px; font-weight: 700; color: var(--t1);
    }
    .login-header p {
      font-size: 12px; color: var(--t3); margin-top: 4px;
    }

    /* ── Field (matches .field + .field-label from index.html) ── */
    .field { margin-bottom: 14px; }
    .field:last-of-type { margin-bottom: 0; }
    .field-label {
      display: block;
      font-size: 10px; font-family: var(--mono);
      color: var(--t3); margin-bottom: 4px;
      text-transform: uppercase; letter-spacing: .04em;
    }

    /* ── Input (matches index.html input[type="text"] pattern) ── */
    input[type="text"],
    input[type="password"] {
      background: var(--s2); color: var(--t1);
      border: 1px solid var(--b1); border-radius: var(--r2);
      padding: 7px 11px; font-size: 13px; font-family: var(--font);
      outline: none; transition: border-color .15s, box-shadow .15s;
      width: 100%; appearance: none;
    }
    input:focus {
      border-color: var(--accent);
      box-shadow: 0 0 0 3px var(--accent-dim);
    }

    /* ── Submit button (.btn-apply) ── */
    .btn-apply {
      display: inline-flex; align-items: center; justify-content: center;
      width: 100%; padding: 9px 16px;
      background: var(--accent); color: #fff;
      border: 1px solid var(--accent);
      border-radius: var(--r2);
      font-size: 13px; font-weight: 600; font-family: var(--font);
      box-shadow: var(--accent-sh);
      cursor: pointer; letter-spacing: -.01em;
      transition: background .15s, box-shadow .15s, opacity .15s;
      margin-top: var(--sp2);
    }
    .btn-apply:hover { background: var(--accent-h); border-color: var(--accent-h); }
    .btn-apply:active { opacity: .72; }

    /* ── Error message ── */
    .login-error {
      background: var(--red-dim); color: var(--red);
      border-radius: var(--r2); padding: 8px 11px;
      font-size: 12px; margin-bottom: var(--sp2);
      display: none;
    }
    .login-error.visible { display: block; }
  </style>
</head>
<body>
  <div class="login-card">
    <div class="login-header">
      <h1>OpenClaw</h1>
      <p>Security Manager — Sign in to continue</p>
    </div>

    <!-- Error banner (shown on failed login via Flask flash) -->
    {% with messages = get_flashed_messages() %}
      {% if messages %}
        <div class="login-error visible">{{ messages[0] }}</div>
      {% endif %}
    {% endwith %}

    <form method="POST" action="{{ url_for('login') }}">
      <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">

      <div class="field">
        <label class="field-label" for="username">Username</label>
        <input type="text" id="username" name="username"
               autocomplete="username" required autofocus>
      </div>

      <div class="field">
        <label class="field-label" for="password">Password</label>
        <input type="password" id="password" name="password"
               autocomplete="current-password" required>
      </div>

      <button type="submit" class="btn-apply">Sign In</button>
    </form>
  </div>
</body>
</html>
```

---

## 8. Checklist — Visual Consistency

- [ ] `data-theme="light"` on `<html>` (same as index.html)
- [ ] Same Google Fonts import (Inter + JetBrains Mono)
- [ ] Card uses `var(--s1)` background, `var(--b1)` border, `var(--r3)` radius
- [ ] Inputs use `var(--s2)` background, accent focus ring
- [ ] Labels use `var(--mono)` font, `var(--t3)` color
- [ ] Submit uses `.btn-apply` (blue accent, white, bold)
- [ ] Error banner uses `var(--red)` / `var(--red-dim)`
- [ ] Dark theme works automatically via CSS variable switching
