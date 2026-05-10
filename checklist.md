# ✅ Checklist de Homologação Final - UpaPasta v1.0.0

Este checklist contém os testes práticos que devem ser realizados manualmente antes do lançamento da versão 1.0.0.

---

## 1. Fluxos de Compactação e Senha
- [ ] **Teste 1.1: RAR com Senha**
  - **Comando:** `upapasta arquivo.mkv --password "minhasenha"`
  - **Validar:**
    - Se o arquivo foi compactado em volumes `.part01.rar`.
    - Se o NZB gerado contém a tag `<meta type="password">minhasenha</meta>`.
    - **Download:** Importar NZB no SABnzbd e verificar se a extração automática funciona.
- [ ] **Teste 1.2: 7z com Senha**
  - **Comando:** `upapasta pasta/ --7z --password "7zpass"`
  - **Validar:**
    - Se os volumes são `.7z.001`.
    - Se os headers estão criptografados (tentar abrir o `.001` e ver se pede senha para listar arquivos).
    - **Download:** Verificar se o cliente Usenet reconhece a senha no NZB.
- [ ] **Teste 1.3: Sem Compactação (Direto)**
  - **Comando:** `upapasta arquivo.mkv` (sem flags de compressão)
  - **Validar:** Se o upload foi feito diretamente do arquivo original (ou via hardlink se não houver ofuscação).

## 2. Elite Obfuscation Suite
- [ ] **Teste 2.1: Ofuscação Total**
  - **Comando:** `upapasta "Filme Com Nome Comum.mkv" --obfuscate`
  - **Validar:**
    - Os nomes dos arquivos na Usenet devem ser aleatórios (ex: `asdf123.mkv`).
    - O Subject do post deve ser aleatório.
    - O NFO **não** deve estar ofuscado no NZB (para facilitar a leitura em indexadores).
    - **Download:** Ao baixar o NZB, os arquivos devem ser renomeados de volta para o nome original pelo cliente (via par2).

## 3. Metadados e TMDb
- [ ] **Teste 3.1: Busca Automática (--tmdb)**
  - **Comando:** `upapasta "The Matrix 1999.mkv" --tmdb`
  - **Validar:**
    - Se o log exibe `✅ TMDb: The Matrix encontrado`.
    - Se o NFO gerado contém a sinopse e o link do IMDB.
    - Se o NZB contém as tags `<meta>` de poster e IMDB.
- [ ] **Teste 3.2: Busca Manual e Forçada**
  - **Comando:** `upapasta --tmdb-search "Fight Club"` (anotar o ID)
  - **Comando:** `upapasta "clube.da.luta.1999.1080p.mkv" --tmdb-id <ID>`
  - **Validar:** Se o metadado foi aplicado corretamente mesmo com nome de arquivo "ruim".
- [ ] **Teste 3.3: Template de NFO Customizado**
  - **Ação:** Criar `meu.txt` com `Titulo: {{title}} | Sinopse: {{synopsis}}`.
  - **Comando:** `upapasta pasta/ --tmdb --nfo-template meu.txt`
  - **Validar:** Se o arquivo `.nfo` final segue rigorosamente o seu design.

## 4. Modos de Processamento
- [ ] **Teste 4.1: Modo Season (Séries)**
  - **Ação:** Pasta com `Ep01.mkv`, `Ep02.mkv`.
  - **Comando:** `upapasta Serie.S01/ --season`
  - **Validar:** Se foi gerado **um único** NZB para a temporada inteira.
- [ ] **Teste 4.2: Modo Each (Lote)**
  - **Comando:** `upapasta PastaComVariosFilmes/ --each --tmdb`
  - **Validar:** Se o UpaPasta disparou uma busca no TMDb e gerou um NZB individual para cada arquivo dentro da pasta.

## 5. Extensibilidade (Hooks)
- [ ] **Teste 5.1: Hook Python Nativo**
  - **Ação:** Criar `~/.config/upapasta/hooks/notify.py` que dê um `print(metadata['nzb_path'])`.
  - **Comando:** Executar qualquer upload.
  - **Validar:** Se o caminho do NZB apareceu no final do log do console.
- [ ] **Teste 5.2: Hook Shell (Legado)**
  - **Ação:** Definir `POST_UPLOAD_SCRIPT` no `.env`.
  - **Validar:** Se o script foi chamado e recebeu as variáveis `UPAPASTA_*`.

## 6. Resiliência e UI
- [ ] **Teste 6.1: Retomada (--resume)**
  - **Ação:** Iniciar um upload grande e cancelar com `Ctrl+C` no meio do UPLOAD.
  - **Comando:** `upapasta a_mesma_pasta/ --resume`
  - **Validar:** Se o programa detectou o estado anterior e não re-enviou os arquivos que já estavam no NZB.
- [ ] **Teste 6.2: Validação de Espaço**
  - **Ação:** Tentar subir algo maior que o espaço livre em disco.
  - **Validar:** Se o erro é claro e impede o início do processo (sem quebrar no meio).

---
**Nota:** Para testes de download, recomenda-se o uso do **SABnzbd** (versão mais recente), que é o padrão da indústria para leitura de metadados e senhas em NZBs.
