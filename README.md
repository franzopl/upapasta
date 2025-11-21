# 🚀 UpaPasta — Upload para Usenet com RAR + PAR2

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Status: Production Ready](https://img.shields.io/badge/Status-Production%20Ready-green.svg)]()

Upload automático de pastas para Usenet com compressão RAR e paridade PAR2. **100% funcional, testado com 1.6GB+**.

## ⚡ Quick Start

```bash
# 1. Instalar dependências
bash install.sh

# 2. Configurar credenciais
cp .env.example .env
nano .env  # Editar com suas credenciais Usenet

# 3. Fazer upload
python3 main.py /caminho/para/pasta
```

## 📋 O que faz

1. ✅ Cria arquivo RAR (sem compressão, apenas store)
2. ✅ Gera paridade PAR2 com **parpar** (15% redundância padrão)
3. ✅ Faz upload para Usenet via nyuu
4. ✅ Mostra progresso em tempo real
5. ✅ Limpa arquivos temporários automaticamente

## 📦 Requisitos

### Sistema
- Linux, macOS ou Windows (WSL2)
- Python 3.10+

### Ferramentas Externas
```bash
# Ubuntu/Debian (RECOMENDADO)
sudo apt-get install rar nyuu
npm install -g parpar  # parpar é o backend padrão (mais rápido)

# Alternativa: par2 (mais lento, mas compatível)
sudo apt-get install par2

# macOS (RECOMENDADO)
brew install rar
npm install -g nyuu parpar  # parpar é o backend padrão (mais rápido)

# Alternativa: par2 (mais lento, mas compatível)
brew install par2

# Fedora (RECOMENDADO)
sudo dnf install rar
sudo npm install -g nyuu parpar  # parpar é o backend padrão (mais rápido)

# Alternativa: par2 (mais lento, mas compatível)
sudo dnf install par2cmdline-mt
```

## 🔧 Instalação

### Automática (Recomendado)
```bash
bash install.sh
```

### Manual
```bash
pip install -r requirements.txt
cp .env.example .env
nano .env
```

## 🚀 Uso Básico

### Upload Simples
```bash
python3 main.py /sua/pasta
```

### Modo Teste (Dry-run)
```bash
python3 main.py /sua/pasta --dry-run
```

### Opções Principais
```
--dry-run                    Mostra o que seria feito
-r, --redundancy PCT         Redundância PAR2 (padrão: 15)
--backend BACKEND            Backend PAR2: parpar (padrão) ou par2
--post-size SIZE             Tamanho alvo (padrão: 20M)
-s, --subject SUBJECT        Subject da postagem
-g, --group GROUP            Newsgroup
--skip-rar                   Pula criação RAR
--skip-par                   Pula geração PAR2
--skip-upload                Pula upload Usenet
-f, --force                  Sobrescreve arquivos
--env-file FILE              Arquivo .env customizado
--keep-files                 Não deleta RAR/PAR2 após upload
```

## ⚙️ Configuração

Editar `.env` com suas credenciais Usenet:

```properties
NNTP_HOST=seu.servidor.net
NNTP_PORT=443
NNTP_SSL=true
NNTP_USER=seu_usuario
NNTP_PASS=sua_senha
NNTP_CONNECTIONS=50
USENET_GROUP=alt.binaries.test
ARTICLE_SIZE=700K
NZB_OUT={filename}.nzb
```

## 🔧 Backends PAR2

### parpar (Padrão - Recomendado)
- **Mais rápido** e moderno
- Melhor otimização para Usenet
- Suporte a slice-size automático
- Instalação: `npm install -g parpar`

### par2 (Alternativa)
- Mais lento, mas tradicional
- Compatível com ferramentas antigas
- Instalação: `sudo apt-get install par2` (Ubuntu/Debian)

**Por que parpar é padrão?** Ele é significativamente mais rápido e otimizado para uploads Usenet modernos.

## 📚 Scripts

### main.py (RECOMENDADO)
Orquestra tudo: RAR → PAR2 → Upload

```bash
python3 main.py /pasta [opções]
```

### makerar.py
Cria apenas o arquivo RAR

```bash
python3 makerar.py /pasta [-f]
```

### makepar.py
Gera apenas paridade PAR2

```bash
python3 makepar.py arquivo.rar [-r 15] [--force]
```

### upfolder.py
Faz apenas upload para Usenet

```bash
python3 upfolder.py arquivo.rar [--dry-run]
```

## 🐛 Troubleshooting

### "RAR/PAR2/Nyuu não encontrado"
Instale a ferramenta externa para seu SO (ver requisitos)

### "Espaço em disco insuficiente"
Remova arquivos antigos ou use `--keep-files` para liberar espaço

### "Upload lento"
Aumente `NNTP_CONNECTIONS` em `.env` (até 100-200)

### "Arquivo .nzb não foi criado"
Certifique que `NZB_OUT={filename}.nzb` está em `.env`

## 📊 Performance Típica

Arquivo testado:
- **Tamanho:** 1,401 MB
- **Arquivos:** 8 (1 RAR + 7 PAR2)
- **Artigos:** 2,363
- **Velocidade:** 34.8 MiB/s (média)
- **Tempo:** 2m 34s
- **Resultado:** ✅ Sucesso

## 📝 Exemplos

```bash
# Verificar antes de fazer upload
python3 main.py /pasta --dry-run

# Upload com subject customizado
python3 main.py /pasta -s "Meu Upload [2025]"

# Usar backend par2 (alternativo ao padrão parpar)
python3 main.py /pasta --backend par2

# Maior redundância
python3 main.py /pasta -r 20

# Manter arquivos RAR/PAR2
python3 main.py /pasta --keep-files

# Múltiplas contas
python3 main.py /pasta --env-file .env.server2
```

## 📖 Mais Informações

- **INSTALL.md** — Guia de instalação detalhado por SO
- **requirements.txt** — Dependências Python

## 📞 Suporte

- **Issues:** GitHub Issues
- **Discussions:** GitHub Discussions

## 📄 Licença

MIT License

## 🎉 Status

✅ **Pronto para Produção** — Testado e funcional

---

**Versão:** 1.1  
**Última atualização:** 20 de novembro de 2025  
**Happy uploading! 🚀**
