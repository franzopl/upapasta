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
-   **Limpeza Automática**: Remove os arquivos `.rar` e `.par2` gerados após o upload (pode ser desativado com `--keep-files`).
-   **Dry Run**: Permite simular a execução sem criar ou enviar arquivos (`--dry-run`).

## Instalação

1.  **Clone o repositório:**
    ```bash
    git clone https://github.com/franzopl/upapasta.git
    cd upapasta
    ```

2.  **Instale as dependências:**
    Recomenda-se o uso de um ambiente virtual (`venv`).
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    ```
    Além das dependências do Python, certifique-se de ter o `rar` e o `parpar` (ou `par2`) instalados e disponíveis no seu `PATH`.

3.  **Configure as credenciais:**
    Copie o arquivo de exemplo `.env.example` para `.env` e preencha com suas credenciais da Usenet.
    ```bash
    cp .env.example .env
    ```
    Edite o arquivo `.env`:
    ```ini
    USENET_HOST=news.your-provider.com
    USENET_PORT=563
    USENET_USER=your-username
    USENET_PASS=your-password
    USENET_GROUP=alt.binaries.test
    USENET_SSL=true
    ```

## Como Usar

O uso básico do `upapasta` envolve a execução do script `main.py`, passando o caminho da pasta que você deseja enviar.

**Sintaxe:**
```bash
python3 -m upapasta.main /caminho/para/sua/pasta [OPÇÕES]
```

**Exemplo básico:**
```bash
python3 -m upapasta.main /home/user/documentos/meu-arquivo-importante
```

### Opções de Linha de Comando

| Opção              | Descrição                                                                      | Padrão                                  |
| ------------------ | ------------------------------------------------------------------------------ | --------------------------------------- |
| `folder`           | **(Obrigatório)** A pasta que será enviada.                                    | N/A                                     |
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
| `--env-file`       | Especifica um caminho alternativo para o arquivo `.env`.                         | `.env`                                  |
| `--keep-files`     | Mantém os arquivos `.rar` e `.par2` no disco após o upload.                    | Desativado                              |

## Estrutura do Projeto

```
upapasta/
├── upapasta/
│   ├── main.py        # Orquestrador principal
│   ├── makerar.py     # Lógica para criar arquivos .rar
│   ├── makepar.py     # Lógica para gerar arquivos .par2
│   └── upfolder.py    # Lógica para fazer o upload
├── .env.example       # Exemplo de arquivo de configuração
├── requirements.txt   # Dependências do Python
└── README.md          # Este arquivo
```

## Contribuição

Contribuições são bem-vindas! Se você encontrar um bug ou tiver uma sugestão de melhoria, sinta-se à vontade para abrir uma *issue* ou enviar um *pull request*.