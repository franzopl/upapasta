# Guia de Instalação — UpaPasta

Este guia irá ajudá-lo a instalar o **UpaPasta** e suas dependências.

## 1. Pré-requisitos

Antes de começar, você precisará ter os seguintes softwares instalados em seu sistema:

-   **Python 3.8+**: A linguagem de programação na qual o UpaPasta é construído.
-   **pip**: O instalador de pacotes do Python.

### Dependências de Sistema

O UpaPasta orquestra ferramentas de linha de comando. Você DEVE instalar as seguintes ferramentas e garantir que elas estejam no PATH do seu sistema:

-   **`rar`**: O utilitário de compressão.
    -   *Debian/Ubuntu*: `sudo apt install rar`
    -   *macOS*: `brew install rar`
    -   *Windows*: Instale WinRAR (rar.exe estará no PATH) ou use 7-Zip.
-   **`nyuu`**: O uploader de Usenet.
    -   *Via npm*: `npm install -g nyuu` (certifique-se de que Node.js está instalado)
    -   *Ou baixe o binário*: Visite https://github.com/Piorosen/nyuu/releases e baixe a versão para seu sistema.
-   **`parpar`**: O gerador de paridade (recomendado, mais rápido que `par2`).
    -   *Via pip*: `pip install parpar` (instalação Python, cross-platform)

Alternativas: Em vez de `parpar`, você pode usar `par2` (mais lento):
-   *Debian/Ubuntu*: `sudo apt install par2`
-   *macOS*: `brew install par2`
-   *Windows*: Baixe de https://github.com/Parchive/par2cmdline/releases

Consulte as seções abaixo para mais detalhes.

## 2. Instalação do UpaPasta

Com os pré-requisitos instalados, você pode instalar o UpaPasta como um comando de linha.

### Passo 1: Obtenha o Código-Fonte

Clone o repositório do UpaPasta para a sua máquina local usando Git (ou baixe o ZIP):

```bash
git clone https://github.com/franzopl/upapasta.git
cd upapasta
```

### Passo 2: Instale o Pacote

Use `pip` para instalar o UpaPasta. Este comando irá criar o executável `upapasta` no seu sistema, permitindo que você o execute de qualquer lugar.

É altamente recomendável fazer isso em um ambiente virtual (`venv`).

```bash
# Opcional, mas recomendado: criar e ativar um ambiente virtual
python3 -m venv venv
source venv/bin/activate  # Em sistemas baseados em Unix (Linux, macOS)

# Instalar o UpaPasta
pip install .
```

Para desenvolvimento, use o modo "editável", que permite que as alterações no código-fonte sejam refletidas imediatamente sem a necessidade de reinstalar:

```bash
pip install -e .
```

## 3. Configuração e Uso

### Configuração de Credenciais

Na primeira vez que você executar o `upapasta`, o script irá verificar se as credenciais de Usenet estão configuradas. Se não estiverem, ele solicitará que você as insira e as salvará em um arquivo `.env` no diretório de trabalho atual.

### Executando o UpaPasta

Após a instalação, você pode usar o comando `upapasta` de qualquer lugar no seu terminal:

```bash
upapasta /caminho/para/sua/pasta [OPÇÕES]
```

**Exemplo:**

```bash
upapasta "/media/downloads/meu_projeto_secreto" --redundancy 20
```

Para ver todas as opções disponíveis, use a flag `--help`:

```bash
upapasta --help
```

É isso! Agora você está pronto para usar o UpaPasta.
