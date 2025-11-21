# 📦 Guia Completo de Instalação — UpaPasta

## 📋 Índice

1. [Pré-requisitos](#pré-requisitos)
2. [Instalação Rápida](#instalação-rápida)
3. [Instalação Detalhada por SO](#instalação-detalhada-por-so)
4. [Instalação para Desenvolvimento](#instalação-para-desenvolvimento)
5. [Verificação de Instalação](#verificação-de-instalação)
6. [Troubleshooting](#troubleshooting)

---

## 🔧 Pré-requisitos

### Python
- **Python 3.10+** (obrigatório)
- Verificar: `python3 --version`

### Ferramentas Externas
- **RAR** — Compactador
- **PAR2 ou parpar** — Gerador de paridade
- **Nyuu** — Cliente upload Usenet

---

## ⚡ Instalação Rápida

### Para Usuários Finais (Tudo Automático)

```bash
# 1. Clonar repositório
git clone https://github.com/seu-usuario/upapasta.git
cd upapasta

# 2. Executar script de instalação (Linux/macOS)
bash install.sh

# OU instalar manualmente:
pip install -r requirements.txt
cp .env.example .env
nano .env  # Editar credenciais

# 3. Testar
python3 main.py --help
```

### Para Desenvolvedores

```bash
# Clonar + instalar em modo desenvolvimento
git clone https://github.com/seu-usuario/upapasta.git
cd upapasta
pip install -e ".[dev]"  # Instala com dependências dev
```

---

## 🖥️ Instalação Detalhada por SO

### Ubuntu / Debian / Linux Mint

#### Passo 1: Instalar ferramentas externas
```bash
sudo apt-get update
sudo apt-get install -y python3 python3-pip git

# RAR
sudo apt-get install -y rar

# PAR2
sudo apt-get install -y par2

# Nyuu (via npm)
sudo apt-get install -y npm
sudo npm install -g nyuu
```

#### Passo 2: Clonar e configurar
```bash
git clone https://github.com/seu-usuario/upapasta.git
cd upapasta
pip3 install -r requirements.txt
```

#### Passo 3: Configurar credenciais
```bash
cp .env.example .env
nano .env
# Editar com suas credenciais Usenet
```

#### Passo 4: Verificar instalação
```bash
python3 main.py --help
which rar par2 nyuu
```

---

### macOS

#### Passo 1: Instalar Homebrew (se não tiver)
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

#### Passo 2: Instalar ferramentas
```bash
# Python (já deve vir com macOS 10.14+)
# Verificar: python3 --version

# RAR (versão trial gratuita)
brew install rar

# PAR2
brew install par2

# Nyuu (via npm)
brew install npm
npm install -g nyuu
```

#### Passo 3: Clonar e configurar
```bash
git clone https://github.com/seu-usuario/upapasta.git
cd upapasta
pip3 install -r requirements.txt
```

#### Passo 4: Configurar credenciais
```bash
cp .env.example .env
nano .env
```

---

### Fedora / RHEL / CentOS

#### Passo 1: Instalar ferramentas
```bash
sudo dnf update

# RAR
sudo dnf install -y rar

# PAR2 (versão MT otimizada)
sudo dnf install -y par2cmdline-mt

# Python + Nyuu
sudo dnf install -y python3 python3-pip npm
sudo npm install -g nyuu
```

#### Passo 2: Clonar e configurar
```bash
git clone https://github.com/seu-usuario/upapasta.git
cd upapasta
pip3 install -r requirements.txt
```

#### Passo 3: Configurar credenciais
```bash
cp .env.example .env
nano .env
```

---

### Windows (WSL2 Recomendado)

#### Opção 1: WSL2 (Recomendado)

1. **Instalar WSL2:**
   ```powershell
   # No PowerShell como administrador
   wsl --install
   # Reiniciar computador
   ```

2. **Dentro do WSL2 (Ubuntu):**
   ```bash
   # Seguir instruções da seção Ubuntu/Debian
   ```

#### Opção 2: Windows Nativo (Mais Complexo)

1. **Instalar Python:** https://www.python.org/downloads/
2. **Instalar RAR:** https://www.win-rar.com/
3. **Instalar PAR2:** Compilar do source ou buscar builds
4. **Instalar Nyuu:** Via npm (instalar Node.js primeiro)
5. **Ajustar PATHs** em variáveis de ambiente do Windows

**Não recomendado.** Use WSL2 para melhor compatibilidade.

---

## 👨‍💻 Instalação para Desenvolvimento

### Setup Completo para Contribuidores

```bash
# 1. Clonar repositório
git clone https://github.com/seu-usuario/upapasta.git
cd upapasta

# 2. Criar virtual environment (RECOMENDADO)
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# ou
venv\Scripts\activate  # Windows

# 3. Instalar em modo desenvolvimento
pip install -e ".[dev]"

# 4. Instalar pré-commit hooks (opcional)
pip install pre-commit
pre-commit install

# 5. Rodar testes
pytest -v
pytest --cov

# 6. Rodar linter
black .
flake8 .
mypy main.py

# 7. Criar branch para sua feature
git checkout -b feature/minha-feature
```

### Estrutura de Desenvolvimento

```
upapasta/
├── main.py              ← Script orquestrador
├── makerar.py
├── makepar.py
├── upfolder.py
├── tests/               ← Testes unitários
│   ├── test_main.py
│   ├── test_makerar.py
│   ├── test_makepar.py
│   └── test_upfolder.py
├── requirements.txt
├── setup.py
└── README.md
```

### Rodando Testes

```bash
# Todos os testes
pytest

# Com cobertura
pytest --cov=. --cov-report=html

# Teste específico
pytest tests/test_main.py::test_dry_run -v
```

---

## ✅ Verificação de Instalação

### Checklist Completo

```bash
# 1. Verificar Python
python3 --version
# Deve mostrar 3.10+

# 2. Verificar ferramentas externas
which rar
which par2
which nyuu
# Todos devem mostrar um path

# 3. Verificar repo
cd upapasta
git status
# Não deve ter mudanças não commitadas

# 4. Verificar dependências Python
pip list | grep -E "tqdm|pytest|black"

# 5. Rodar help
python3 main.py --help
# Deve mostrar menu de ajuda

# 6. Testar imports
python3 -c "import sys, os, subprocess, pathlib, glob, argparse, re, time, json, logging; print('✅ Imports OK')"

# 7. Fazer teste de dry-run
python3 main.py /tmp --dry-run
# Deve mostrar processo sem executar
```

### Testes Rápidos

```bash
# Teste 1: Criar RAR (em arquivo de teste)
mkdir -p /tmp/teste_upapasta
echo "teste" > /tmp/teste_upapasta/arquivo.txt
python3 makerar.py /tmp/teste_upapasta
ls -lh /tmp/teste_upapasta.rar
# Deve criar arquivo .rar

# Teste 2: Gerar PAR2
python3 makepar.py /tmp/teste_upapasta.rar -r 10
ls -lh /tmp/teste_upapasta.par2
# Deve criar arquivo .par2

# Teste 3: Dry-run completo
python3 main.py /tmp/teste_upapasta --dry-run
# Deve mostrar workflow sem executar
```

---

## 🐛 Troubleshooting

### Erro: "python3: command not found"

**Causa:** Python não está instalado ou não está no PATH

**Solução:**
```bash
# Ubuntu/Debian
sudo apt-get install python3 python3-pip

# macOS
brew install python3

# Verificar
python3 --version
```

---

### Erro: "rar: command not found"

**Causa:** RAR não está instalado

**Solução:**
```bash
# Ubuntu/Debian
sudo apt-get install rar

# macOS
brew install rar

# Fedora
sudo dnf install rar

# Verificar
rar --version
```

---

### Erro: "par2: command not found"

**Causa:** PAR2 não está instalado

**Solução:**
```bash
# Ubuntu/Debian
sudo apt-get install par2

# macOS
brew install par2

# Fedora
sudo dnf install par2cmdline-mt

# Verificar
par2 --version
```

---

### Erro: "nyuu: command not found"

**Causa:** Nyuu não está instalado

**Solução:**
```bash
# Instalar via npm
sudo npm install -g nyuu

# Ou compilar do source
git clone https://github.com/Piorosen/nyuu.git
cd nyuu
npm install
npm run build

# Verificar
nyuu --version
```

---

### Erro: "ModuleNotFoundError: No module named 'tqdm'"

**Causa:** Dependências opcionais não instaladas

**Solução:**
```bash
# Instalar todas
pip install -r requirements.txt

# Ou apenas a que falta
pip install tqdm
```

---

### Erro: "Permission denied" em .env

**Causa:** Arquivo de credenciais com permissão incorreta

**Solução:**
```bash
# Dar permissão apenas ao usuário
chmod 600 .env

# Verificar
ls -la .env
# Deve mostrar: -rw------- (600)
```

---

### Erro: ".env file not found"

**Causa:** Arquivo não foi criado

**Solução:**
```bash
# Criar de exemplo
cp .env.example .env

# Editar
nano .env

# Verificar que foi criado
ls -la .env
```

---

## 🎯 Próximos Passos

Após instalar com sucesso:

1. **Editar `.env`** com suas credenciais Usenet
2. **Testar com `--dry-run`:**
   ```bash
   python3 main.py /sua/pasta --dry-run
   ```
3. **Se OK, fazer upload real:**
   ```bash
   python3 main.py /sua/pasta
   ```

---

## 📚 Documentação Relacionada

- [README.md](./README.md) — Guia principal
- [ROADMAP.md](./ROADMAP.md) — Features e próximos passos
- [requirements.txt](./requirements.txt) — Dependências Python

---

## 💬 Precisa de Ajuda?

- **Issues no GitHub:** Reporte bugs e problemas
- **Discussions:** Pergunte sobre instalação
- **Email:** seu-email@exemplo.com

---

**Última atualização:** 20 de novembro de 2025  
**Versão:** 1.1
