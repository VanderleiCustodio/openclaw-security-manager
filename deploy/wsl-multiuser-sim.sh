#!/usr/bin/env bash
# Cria usuários locais com ~/.openclaw/openclaw.json mínimo (simulação multi-usuário).
# Uso: sudo bash wsl-multiuser-sim.sh
# Senha inicial: changeme (troque com: sudo passwd dev01)

set -euo pipefail

MINIMAL_JSON='{"gateway":{"bind":"loopback","auth":{"mode":"token","token":"REPLACE_ME"}}}'

users=(dev01 dev02 dev03)

for u in "${users[@]}"; do
  if id "$u" &>/dev/null; then
    echo "== $u já existe, só garantindo ~/.openclaw"
  else
    echo "== Criando usuário $u"
    useradd -m -s /bin/bash "$u" || true
    echo "${u}:changeme" | chpasswd
  fi
  home=$(getent passwd "$u" | cut -d: -f6)
  oc="$home/.openclaw"
  mkdir -p "$oc"
  cfg="$oc/openclaw.json"
  if [[ ! -f "$cfg" ]]; then
    echo "$MINIMAL_JSON" >"$cfg"
    chown -R "$u:$u" "$oc"
    chmod 700 "$oc"
    chmod 600 "$cfg"
    echo "   -> $cfg criado"
  else
    chown -R "$u:$u" "$oc" 2>/dev/null || true
    echo "   -> $cfg já existia"
  fi
done

echo ""
echo "Pronto. Usuários: ${users[*]}"
echo "Troque o token em cada openclaw.json e a senha: sudo passwd dev01"
echo "Liste paths: python3 -c \"import pwd,glob; [print(p.pw_name, p.pw_dir+'/.openclaw/openclaw.json') for p in pwd.getpwall() if p.pw_uid>=1000 or p.pw_name=='root']\""
