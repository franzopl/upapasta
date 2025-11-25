# Guia de Instalação — UpaPasta

Este guia irá ajudá-lo a instalar o **UpaPasta** e suas dependências para que você possa começar a usá-lo o mais rápido possível.

## 1. Pré-requisitos

Antes de começar, você precisará ter os seguintes softwares instalados em seu sistema:

-   **Python 3.10+**: A linguagem de programação na qual o UpaPasta é construído.
-   **Git**: O sistema de controle de versão usado para baixar o código-fonte do UpaPasta.
-   **RAR**: O utilitário de compressão usado para criar os arquivos `.rar`.
-   **par2** ou **parpar**: As ferramentas de linha de comando usadas para gerar os arquivos de paridade. O `parpar` é recomendado por ser mais rápido.

## 2. Instalação

Siga os passos abaixo para instalar o UpaPasta e suas dependências.

### Passo 1: Clone o Repositório

Primeiro, clone o repositório do UpaPasta para a sua máquina local usando o Git:

```bash
git clone https://github.com/franzopl/upapasta.git
cd upapasta
```

### Passo 2: Instale as Dependências do Python

Em seguida, instale as dependências do Python listadas no arquivo `requirements.txt`. É altamente recomendável que você faça isso em um ambiente virtual para evitar conflitos com outros pacotes Python em seu sistema.

```bash
python3 -m venv venv
source venv/bin/activate  # Em sistemas baseados em Unix (Linux, macOS)
# ou
venv\Scripts\activate  # Em Windows

pip install -r requirements.txt
```

### Passo 3: Instale as Dependências Externas

Agora, você precisará instalar as dependências externas. As instruções abaixo cobrem os sistemas operacionais mais comuns.

#### Em Debian/Ubuntu:

```bash
sudo apt-get update
sudo apt-get install -y rar par2
```

Se você preferir usar o `parpar`, pode instalá-lo via `npm`:

```bash
sudo apt-get install -y npm
sudo npm install -g parpar
```

#### Em macOS (usando [Homebrew](https://brew.sh/)):

```bash
brew install rar par2
```

Para instalar o `parpar`, você pode usar o `npm`:

```bash
brew install npm
npm install -g parpar
```

#### Em Windows:

A maneira mais fácil de instalar as dependências externas no Windows é usando o [Chocolatey](https://chocolatey.org/).

```bash
choco install winrar par2
```

Para o `parpar`, você pode usar o `npm`, que pode ser instalado via Chocolatey também:

```bash
choco install nodejs
npm install -g parpar
```

### Passo 4: Configure o Arquivo de Ambiente

Finalmente, você precisará configurar o arquivo de ambiente com as suas credenciais da Usenet. Comece copiando o arquivo `.env.example`:

```bash
cp .env.example .env
```

Em seguida, edite o arquivo `.env` com as suas informações.

```bash
nano .env  # ou seu editor de texto preferido
```

O arquivo se parecerá com isto:

```
USENET_HOST=news.your-provider.com
USENET_PORT=563
USENET_USER=your-username
USENET_PASS=your-password
USENET_GROUP=alt.binaries.test
USENET_SSL=true
```

## 3. Verificando a Instalação

Para garantir que tudo foi instalado corretamente, você pode executar o UpaPasta com a flag `--help`:

```bash
python3 -m upapasta.main --help
```

Se a instalação foi bem-sucedida, você verá uma mensagem de ajuda com todas as opções de linha de comando disponíveis.

Agora você está pronto para usar o UpaPasta!