# UpaPasta — Upload para Usenet com RAR + Paridade

Uma suite completa de scripts Python para fazer upload de pastas na Usenet com compressão RAR e paridade PAR2.

## 🚀 Quick Start

```bash
# 1. Configurar credenciais (uma única vez)
cp .env.example .env
# Editar .env com suas credenciais

# 2. Fazer upload de uma pasta
python3 main.py /caminho/para/pasta
```

Pronto! O script vai:
1. ✅ Criar arquivo `.rar` (sem compressão)
2. ✅ Gerar paridade `.par2` (otimizada para Usenet)
3. ✅ Fazer upload para Usenet com `nyuu`

## 📋 Scripts Principais

### `main.py` — Workflow Completo (RECOMENDADO)

Orquestra todo o processo em uma única linha.

**Uso básico:**
```bash
python3 main.py /pasta/para/upload
```

**Verificar antes (dry-run):**
```bash
python3 main.py /pasta/para/upload --dry-run
```

**Opções completas:**
```
--dry-run                    Mostra o que seria feito sem executar
-r, --redundancy PCT         Redundância PAR2 (padrão: 15%)
--post-size SIZE             Tamanho alvo de post (padrão: 20M)
-s, --subject SUBJECT        Subject da postagem
-g, --group GROUP            Newsgroup
--skip-rar                   Pula criação de RAR
--skip-par                   Pula geração de paridade
--skip-upload                Pula upload para Usenet
-f, --force                  Força sobrescrita
--env-file FILE              Arquivo .env customizado
--keep-files                 Mantém arquivos RAR/PAR2 (padrão: deleta)
```

**Limpeza Automática:**

Por padrão, após upload bem-sucedido, os arquivos `.rar` e `.par2` são **deletados automaticamente** para liberar espaço. Use `--keep-files` para mantê-los:

```bash
python3 main.py /pasta/para/upload --keep-files
```

### `makerar.py` — Criar RAR

Cria arquivo `.rar` sem compressão de uma pasta.

```bash
python3 makerar.py /pasta [-f]
```

### `makepar.py` — Gerar PAR2

Cria paridade `.par2` para um arquivo `.rar`.

```bash
python3 makepar.py arquivo.rar [opções]
```

### `upfolder.py` — Upload para Usenet

Faz upload de `.rar` + `.par2` para Usenet.

```bash
python3 upfolder.py arquivo.rar [opções]
```

## ⚙️ Configuração

### 1. Criar `.env` com suas credenciais

```bash
cp .env.example .env
```

Editar com suas credenciais Usenet. Exemplo:

```properties
NNTP_HOST=sanews.blocknews.net
NNTP_PORT=443
NNTP_SSL=true
NNTP_USER=seu_usuario
NNTP_PASS=sua_senha
NNTP_CONNECTIONS=50
USENET_GROUP=alt.binaries.test
ARTICLE_SIZE=700K

# Arquivo NZB de saída (substitui {filename} pelo nome da pasta)
NZB_OUT={filename}.nzb
NZB_OVERWRITE=true
```

### 2. Arquivo NZB

O arquivo `.nzb` é gerado automaticamente durante o upload e contém informações para fazer download da postagem novamente. 

- **Salvo em:** O caminho especificado em `NZB_OUT` (padrão: `{filename}.nzb`)
- **Localização:** Será salvo no diretório de trabalho onde o script é executado
- **Para especificar caminho absoluto:** Edite `.env` e configure `NZB_OUT=/caminho/completo/{filename}.nzb`

## 📦 Dependências

**Obrigatórias:**
- Python 3.10+
- `rar` → `sudo apt install rar`
- `parpar` ou `par2` → `npm install -g @catsblues/parpar` ou `sudo apt install par2`
- `nyuu` → https://github.com/Piorosen/nyuu

**Python:**
```bash
pip install tqdm
```

## 💡 Exemplos

```bash
# Workflow completo
python3 main.py ~/Videos/minha_colecao

# Dry-run (verificar antes)
python3 main.py ~/Videos/minha_colecao --dry-run

# Apenas preparar arquivos (sem upload)
python3 main.py ~/Videos/minha_colecao --skip-upload

# Com custom redundância e post-size
python3 main.py ~/Videos/minha_colecao -r 20 --post-size 25M

# Com custom subject
python3 main.py ~/Videos/minha_colecao -s "[1/1] - Meu Arquivo - yEnc"
```

## 📖 Documentação Detalhada

Veja documentação completa de cada script com `--help`:

```bash
python3 main.py --help
python3 makerar.py --help
python3 makepar.py --help
python3 upfolder.py --help
```

## 🔧 Troubleshooting

- `rar not found` → `sudo apt install rar` ou baixar de https://www.rarlab.com
- `parpar not found` → `npm install -g @catsblues/parpar`
- `nyuu not found` → Compilar de https://github.com/Piorosen/nyuu
- Credenciais inválidas → Verifique `.env` e teste telnet manualmente

## 📝 Notas

- Sempre use `--dry-run` antes de fazer upload real
- Redundância PAR2: 15% é bom padrão (10-20% recomendado)
- Slice-size é calculado automaticamente baseado em post-size
- Não commitar `.env` em git (credenciais sensíveis)

## 📄 Licença

Fornecido como-está. Use por sua conta e risco.
