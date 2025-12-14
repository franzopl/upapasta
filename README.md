# UpaPasta

**UpaPasta** é uma ferramenta de linha de comando (CLI) em Python para automatizar o processo de upload de pastas para a Usenet. O script orquestra um fluxo de trabalho completo, que inclui:

1.  **Compactação**: Cria um arquivo `.rar` a partir da pasta de origem.
2.  **Geração de Paridade**: Gera arquivos de paridade `.par2` para garantir a integridade dos dados.
3.  **Upload**: Faz o upload dos arquivos `.rar` e `.par2` para o grupo de notícias Usenet especificado.

A ferramenta foi projetada para ser simples, eficiente e exibir barras de progresso em cada etapa do processo.

## Funcionalidades

-   **Workflow Automatizado**: Orquestra a compactação, geração de paridade e upload com um único comando.
-   **Flexibilidade**: Permite pular etapas individuais (`--skip-rar`, `--skip-par`, `--skip-upload`).
-   **Customização**: Opções para configurar a redundância dos arquivos PAR2, o tamanho dos posts e o assunto da postagem.
-   **Segurança**: Carrega as credenciais da Usenet a partir de um arquivo `.env` para não expor informações sensíveis.
-   **Geração de NZB**: Cria automaticamente um arquivo `.nzb` na pasta de execução para facilitar downloads.
 -   **Geração de NFO (arquivo único)**: Para uploads de arquivo único, gera automaticamente um arquivo `.nfo` com a saída do `mediainfo` e o salva no mesmo destino do `.nzb` para arquivamento local. **Este `.nfo` não será enviado para a Usenet.**
-   **Limpeza Automática**: Remove os arquivos `.rar` e `.par2` gerados após o upload (pode ser desativado com `--keep-files`).
-   **Dry Run**: Permite simular a execução sem criar ou enviar arquivos (`--dry-run`).

## Instalação

### Via PyPI (Recomendado)
```bash
pip install upapasta
```

### Para Desenvolvimento
1.  **Clone o repositório:**
    ```bash
    git clone https://github.com/franzopl/upapasta.git
    cd upapasta
    ```

2.  **Instale em modo editável:**
    Recomenda-se o uso de um ambiente virtual (`venv`).
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -e .
    ```

3.  **Dependências Externas:**
    Certifique-se de ter o `rar`, `parpar` (ou `par2`) e `nyuu` instalados e disponíveis no seu `PATH`.
  - Para uploads de arquivo único, recomenda-se também ter `mediainfo` instalado para gerar o arquivo `.nfo` automaticamente.

### Configuração de Credenciais
O script usa um arquivo de configuração global em `~/.config/upapasta/.env` por padrão. Na primeira execução, será solicitado que você forneça as credenciais, que serão salvas automaticamente.

Para configurar manualmente:
- Copie o arquivo de exemplo `.env.example` para `~/.config/upapasta/.env` e edite:
  ```bash
  mkdir -p ~/.config/upapasta
  cp .env.example ~/.config/upapasta/.env
  ```
- Edite o arquivo `~/.config/upapasta/.env`:
  ```ini
  NNTP_HOST=news.your-provider.com
  NNTP_PORT=563
  NNTP_USER=your-username
  NNTP_PASS=your-password
  USENET_GROUP=alt.binaries.test
  NNTP_SSL=true
  ```

## Como Usar

Após a instalação via PyPI, use o comando `upapasta` diretamente.

**Sintaxe:**
```bash
upapasta /caminho/para/sua/pasta [OPÇÕES]
```

**Exemplo básico:**
```bash
upapasta /home/user/documentos/meu-arquivo-importante
```

**Exemplo para arquivo único (.mkv):**
```bash
upapasta /home/user/Videos/filme.mkv
```

**Exemplo para uploads sequenciais (aborta se .nzb já existe):**
```bash
# Útil para enviar múltiplos vídeos de uma pasta em sequência
# sem sobrescrever NZBs existentes
for video in /home/user/Videos/*.mkv; do
    upapasta "$video" --nzb-conflict fail
done
```

**Exemplo para uploads sequenciais de pastas (aborta se .nzb já existe):**
```bash
# Útil para enviar múltiplas pastas em sequência
# sem sobrescrever NZBs existentes
for pasta in /home/user/Pastas/*/; do
    upapasta "$pasta" --nzb-conflict fail
done
```
"""

### Opções de Linha de Comando

| Opção              | Descrição                                                                      | Padrão                                  |
| ------------------ | ------------------------------------------------------------------------------ | --------------------------------------- |
| `input`            | **(Obrigatório)** Arquivo ou pasta que será enviada. Para arquivo único (ex: .mkv) o comportamento padrão é pular a criação do `.rar` e gerar apenas `.par2`.
|                    |                                                                              | N/A                                     |
| `--dry-run`        | Simula a execução sem criar ou enviar arquivos.                                | Desativado                              |
| `-r`, `--redundancy` | Define a porcentagem de redundância para os arquivos PAR2.                       | `15`                                    |
| `--backend`        | Escolhe o backend para a geração de paridade (`parpar` ou `par2`).               | `parpar`                                |
| `--post-size`      | Define o tamanho alvo para cada post na Usenet (ex: `20M`, `700k`).               | `20M`                                   |
| `-s`, `--subject`    | Define o assunto da postagem na Usenet.                                        | Nome da pasta                           |
| `-g`, `--group`      | Define o grupo de notícias (newsgroup) para o upload.                          | Valor definido no arquivo `.env`        |
| `--skip-rar`       | Pula a etapa de criação do arquivo `.rar`.                                     | Desativado                              |
| `--skip-par`       | Pula a etapa de geração dos arquivos de paridade `.par2`.                        | Desativado                              |
| `--skip-upload`    | Pula a etapa de upload para a Usenet.                                          | Desativado                              |
| `-f`, `--force`      | Força a sobrescrita de arquivos `.rar` ou `.par2` que já existam.              | Desativado                              |
| `--env-file`       | Especifica um caminho alternativo para o arquivo `.env`.                         | `~/.config/upapasta/.env`              |
| `--keep-files`     | Mantém os arquivos `.rar` e `.par2` no disco após o upload.                    | Desativado                              |
| `--nzb-conflict`     | Como tratar conflitos quando o `.nzb` já existe na pasta de destino (`rename`, `overwrite`, `fail`). | `rename` (padrão: renomeia para evitar perda) |

## Estrutura do Projeto

```
upapasta/
├── upapasta/
│   ├── __init__.py    # Inicialização do pacote
│   ├── main.py        # Orquestrador principal
│   ├── makerar.py     # Lógica para criar arquivos .rar
│   ├── makepar.py     # Lógica para gerar arquivos .par2
│   └── upfolder.py    # Lógica para fazer o upload
├── .env.example       # Exemplo de arquivo de configuração
├── LICENSE            # Licença MIT
├── MANIFEST.in        # Arquivos extras para incluir no pacote
├── pyproject.toml     # Configuração do pacote
├── tests/
│   └── test_upapasta.py # Testes unitários
├── INSTALL.md         # Instruções de instalação detalhadas
└── README.md          # Este arquivo
```

## Licença

Este projeto está licenciado sob a Licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

## Contribuição

Contribuições são bem-vindas! Se você encontrar um bug ou tiver uma sugestão de melhoria, sinta-se à vontade para abrir uma *issue* ou enviar um *pull request*.