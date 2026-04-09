#!/bin/bash
# OpenClaw Security Manager — instalação Linux
set -e

echo "=== OpenClaw — Instalação ==="

# Verifica Python 3.10+
python3 --version || { echo "Erro: Python 3.10+ necessário."; exit 1; }

# Cria e ativa virtualenv
python3 -m venv venv
source venv/bin/activate

# Instala dependências
pip install --upgrade pip
pip install -r requirements.txt

# Cria usuário admin
echo ""
echo "=== Criar usuário de acesso ao painel ==="
python create_user.py

echo ""
echo "=== Instalação concluída ==="
echo "Para iniciar: source venv/bin/activate && python app.py"
