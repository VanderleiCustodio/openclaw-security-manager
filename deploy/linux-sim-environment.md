# Ambiente Linux local (vários usuários) — simular notebook / servidor

O painel **OpenClaw Security Manager** lista configs em `~/.openclaw/openclaw.json` **por usuário Unix** quando roda em **Linux** (ou WSL). No Windows nativo, só aparece o seu usuário atual.

## Opção A — WSL2 (recomendado; você já tem Ubuntu)

1. Abra **Ubuntu** no terminal (`wsl` ou menu Iniciar).
2. Rode o script (cria `dev01`–`dev03` com `openclaw.json` mínimo):

   ```bash
   sudo bash /mnt/c/Users/vande/OneDrive/Documents/files/deploy/wsl-multiuser-sim.sh
   ```

   Ajuste o caminho se o repositório estiver noutro lugar.

3. **Rodar o Flask dentro do WSL** para o seletor de usuário enxergar `/etc/passwd`:

   ```bash
   cd /mnt/c/Users/vande/OneDrive/Documents/files
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   export FLASK_APP=app.py
   python app.py
   ```

   Acesse no Windows: `http://127.0.0.1:5050` (WSL encaminha a porta).

4. Senhas dos usuários de teste: defina com `sudo passwd dev01` etc. após o script (o script usa `chpasswd` com senha padrão **changeme** se não alterar o script).

---

## Opção B — Máquina virtual (VirtualBox + Ubuntu Server)

Use quando quiser rede isolada, snapshot ou comportamento idêntico a um PC Linux físico.

### 1) Instalar VirtualBox (PowerShell **como administrador**)

```powershell
winget install Oracle.VirtualBox --accept-package-agreements --accept-source-agreements
```

### 2) ISO Ubuntu Server 24.04 LTS (oficial)

Baixe: [https://ubuntu.com/download/server](https://ubuntu.com/download/server) (imagem `.iso`).

### 3) Nova VM (resumo)

- **Tipo:** Linux, Ubuntu 64-bit  
- **RAM:** 4 GB+ (8 GB confortável)  
- **Disco:** 40 GB+ dinâmico  
- **Rede:** NAT ou **Bridged** (bridged expõe na LAN como um host real)  
- Instale OpenSSH server no assistente do Ubuntu.

### 4) Dentro da VM

Copie o repositório ou use `git clone`, instale Python/venv, rode `deploy/wsl-multiuser-sim.sh` (funciona igual em Ubuntu Server).

---

## Opção C — Hyper-V (Windows Pro/Enterprise)

Ative: “Ativar ou desativar recursos do Windows” → **Hyper-V** → reinicie.  
Crie VM “Rápida” ou importe VHD; use a mesma ISO do Ubuntu Server.

---

## Checklist rápido

| Objetivo                         | Onde rodar o `python app.py` |
|----------------------------------|------------------------------|
| Ver vários usuários no seletor   | Linux ou WSL                 |
| Só editar seu `openclaw.json`    | Windows está OK              |

## Limpeza dos usuários de teste (WSL/VM)

```bash
sudo userdel -r dev01
sudo userdel -r dev02
sudo userdel -r dev03
```

(remova só os que o script criou e que não estiver usando)
