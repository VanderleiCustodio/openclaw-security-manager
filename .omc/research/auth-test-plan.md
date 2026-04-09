# Plano de Testes — Fluxo de Autenticação

**Stack:** Flask-Login + pyotp + SQLite
**Fluxo:** 2 etapas — senha → TOTP
**Data:** 2026-04-08

---

## 1. Casos de Sucesso

| Caso | Ação | Resultado Esperado | Como Testar |
|------|------|--------------------|-------------|
| Login completo com TOTP válido | POST `/login` com credenciais corretas, depois POST `/verify-totp` com código TOTP válido gerado pelo pyotp | Sessão autenticada criada, `current_user.is_authenticated == True`, redirecionamento para dashboard | `client.post('/login', data={...})` → `client.post('/verify-totp', data={'token': pyotp.TOTP(secret).now()})` → assert `302` e `location` aponta para rota protegida |
| Logout limpa sessão | Usuário autenticado acessa GET `/logout` | Sessão encerrada, `current_user.is_anonymous == True`, cookie de sessão invalidado | Autenticar, fazer `client.get('/logout')`, depois `client.get('/dashboard')` → assert `302` para `/login` |
| Acesso a rota protegida após login | Usuário com sessão completa acessa GET `/dashboard` (ou rota com `@login_required`) | Resposta `200` com conteúdo da rota | Autenticar completamente, `client.get('/dashboard')` → assert status `200` |
| TOTP gerado com mesmo secret funciona | Gerar TOTP com `pyotp.TOTP(user.totp_secret).now()` | Token aceito dentro da janela de 30 s | Mockar `time.time()` para instante fixo e verificar que token daquele instante é aceito |

---

## 2. Casos de Falha

| Caso | Ação | Resultado Esperado | Como Testar |
|------|------|--------------------|-------------|
| Senha incorreta na etapa 1 | POST `/login` com senha errada | Status `200` (form reexibido) ou `401`, mensagem de erro, **nenhuma** sessão `pending_user` criada | `client.post('/login', data={'password': 'errada'})` → assert sem cookie de sessão com `pending_user`, mensagem de erro presente |
| TOTP expirado (fora da janela) | POST `/verify-totp` com token gerado há > 30 s | Status `200`/`401`, mensagem "Código expirado ou inválido", sessão `pending_user` mantida mas não elevada | Mockar `time.time()` com offset de 60 s, submeter token antigo → assert `current_user.is_authenticated == False` |
| TOTP inválido (código errado) | POST `/verify-totp` com código de 6 dígitos aleatório | Status `200`/`401`, mensagem de erro, sessão não elevada | `client.post('/verify-totp', data={'token': '000000'})` → assert autenticação não concluída |
| Acesso direto a rota protegida sem login | GET `/dashboard` sem sessão ativa | Redirecionamento `302` para `/login` | `client.get('/dashboard')` em cliente sem autenticação → assert `302` e `location == '/login'` |
| Submissão de TOTP sem etapa 1 | POST `/verify-totp` diretamente sem `pending_user` na sessão | Redirecionamento para `/login` ou erro `403` | Novo cliente sem sessão, `client.post('/verify-totp', data={'token': '123456'})` → assert redirecionamento |

---

## 3. Segurança

| Caso | Ação | Resultado Esperado | Como Testar |
|------|------|--------------------|-------------|
| `pending_user` não dá acesso a rotas protegidas | Após etapa 1 bem-sucedida (senha ok, TOTP pendente), acessar GET `/dashboard` | Redirecionamento `302` para `/verify-totp` ou `/login`; `current_user.is_authenticated == False` | Autenticar somente a etapa 1, `client.get('/dashboard')` → assert não retorna `200` |
| Rate limiting após 5 tentativas falhas | POST `/login` ou `/verify-totp` com credenciais erradas 6+ vezes | Na 6ª tentativa, resposta `429 Too Many Requests` ou bloqueio temporário da conta/IP | Loop de 6 POSTs com dados inválidos → assert última resposta é `429` ou mensagem de bloqueio |
| Cookie de sessão com flags de segurança | Qualquer resposta que defina o cookie de sessão | Cookie contém `Secure`, `HttpOnly` e `SameSite=Lax` (ou `Strict`) | Inspecionar `response.headers['Set-Cookie']` → assert que a string contém `Secure`, `HttpOnly`, `SameSite` |
| Proteção contra replay de TOTP | Usar o mesmo token TOTP duas vezes dentro da janela de 30 s | Segunda tentativa rejeitada (token já consumido) | Submeter token válido → login ok → logout → tentar mesmo token novamente antes de expirar → assert rejeitado |
| Sessão não persiste após expiração | Acessar rota protegida com cookie de sessão expirado | Redirecionamento para `/login` | Configurar `SESSION_LIFETIME` curto, avançar clock, `client.get('/dashboard')` → assert `302` |

---

## Notas de Implementação

- Usar `app.config['TESTING'] = True` e `app.config['WTF_CSRF_ENABLED'] = False` nos testes.
- Usar `unittest.mock.patch('time.time', return_value=...)` para controlar janela TOTP.
- O secret TOTP do usuário de teste deve ser gerado com `pyotp.random_base32()` e armazenado no banco SQLite de teste em memória (`sqlite:///:memory:`).
- Separar fixtures: `authenticated_client` (sessão completa), `pending_client` (só etapa 1 concluída), `anonymous_client` (sem sessão).
