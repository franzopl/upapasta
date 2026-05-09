# FAQ — UpaPasta

Respostas diretas para as dúvidas mais comuns. Para diagnóstico passo a passo, veja [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

---

## Instalação e configuração

**P: `upapasta: command not found` depois de `pip install upapasta`.**

R: O diretório de scripts do pip não está no PATH. Adicione ao `~/.bashrc` ou `~/.zshrc`:
```bash
export PATH="$HOME/.local/bin:$PATH"
```
Depois: `source ~/.bashrc` e tente novamente.

---

**P: `nyuu: command not found`.**

R: Instale via npm: `npm install -g nyuu`. Se o Node não estiver instalado: `apt install nodejs npm`. Confirme com `nyuu --version`.

---

**P: `parpar: command not found`.**

R: Instale via npm: `npm install -g @animetosho/parpar`. Confirme com `parpar --version`.

---

**P: `7z: command not found` (usando `--compressor 7z`).**

R: Instale o utilitário: `apt install p7zip-full` (Debian/Ubuntu), `brew install p7zip` (macOS), ou de [7-zip.org](https://www.7-zip.org/) (Windows).

---

**P: SSL handshake falha ao conectar no servidor NNTP.**

R: Primeiro teste: `upapasta --test-connection`. Se falhar com erro de certificado, seu servidor tem um certificado autoassinado ou expirado. Opções:
1. Defina `NNTP_IGNORE_CERT=true` no `.env` (apenas em ambiente confiável)
2. Use `upapasta --test-connection --insecure` para confirmar que é isso antes de alterar o `.env`

---

**P: `upapasta --config` não atualiza as credenciais.**

R: Enter sem digitar nada **mantém** o valor atual. Para limpar um campo, pressione espaço e Enter (grava espaço) — depois edite o `.env` diretamente com um editor de texto.

---

## Upload

**P: Erro 401 ou 403 do nyuu.**

R: Credenciais inválidas. Verifique `NNTP_USER` e `NNTP_PASS` no `.env`. Se usar failover, verifique também `NNTP_USER_2`, `NNTP_PASS_2` etc. Use `upapasta --test-connection` para validar.

---

**P: Erro 502 / Bad Gateway do nyuu.**

R: O servidor NNTP está sobrecarregado ou em manutenção. Tente novamente em alguns minutos. Configure `--upload-retries 3` para retry automático com backoff exponencial.

---

**P: Upload para no meio sem mensagem de erro clara.**

R: Provável timeout de conexão. Adicione `--upload-timeout 300` (5 minutos). Se o problema persistir, configure um servidor de failover — veja [DOCS.md § 7](../DOCS.md#7-múltiplos-servidores-nntp).

---

**P: Como retomar um upload que foi interrompido com Ctrl+C?**

R: Use `--resume` com as mesmas flags do upload original:
```bash
upapasta Pasta/ --resume
# ou com as flags originais:
upapasta Pasta/ --obfuscate --par-profile safe --resume
```
O UpaPasta detecta o `.upapasta-state.json` salvo e faz upload apenas dos arquivos restantes.

---

**P: `--resume` diz que não encontrou state file.**

R: O arquivo `.upapasta-state.json` é salvo no mesmo diretório do NZB de saída. Se foi deletado, movido ou nunca foi criado (upload falhou antes de começar), será necessário refazer o upload completo sem `--resume`.

---

## PAR2

**P: Geração de PAR2 falha com mensagem de erro do parpar.**

R: Causas mais comuns:
1. **Espaço em disco:** o UpaPasta precisa de aproximadamente 2× o tamanho da fonte. Verifique com `df -h`.
2. **Permissões:** o diretório de destino precisa ser gravável.
3. **Memória insuficiente:** adicione `--max-memory 512` para limitar o uso.

O UpaPasta tenta automaticamente uma segunda vez com menos threads e perfil `safe`. Se ainda falhar, veja a mensagem de instrução impressa na tela para retomar manualmente.

---

**P: `par2: command not found` (usando `--backend par2`).**

R: Instale: `apt install par2` (Debian/Ubuntu) ou `brew install par2` (macOS). Alternativa recomendada: use `--backend parpar` (mais rápido, suporta subpastas).

---

**P: SABnzbd não reconstrói a estrutura de pastas depois do download.**

R: Duas opções:
1. Certifique-se de ter usado `--filepath-format common` (padrão) ao fazer o upload com `parpar`. O SABnzbd precisa ter "Repair Archive" ativo.
2. Se o SABnzbd está com "Recursive Unpacking" ativo, **desative** — ele pode desestruturar o conteúdo.

---

## Ofuscação

**P: Qual a diferença entre `--obfuscate` e `--strong-obfuscate`?**

R: Desde a v0.28.0, o flag `--obfuscate` é a única e **recomendada** forma de stealth. Ela oferece privacidade máxima por padrão: nomes de arquivos aleatórios na Usenet E subjects aleatórios no NZB. Downloaders modernos (SABnzbd) restauram os nomes automaticamente usando os headers do NZB.

---

**P: Usei `--obfuscate` e os arquivos locais ficaram com nomes aleatórios após o upload.**

R: Isso não deveria acontecer — o rollback é garantido via `finally`. Verifique se o terminal mostrou algum aviso de "reversão falhou". Se sim, a instrução de reversão manual foi impressa na tela. Se não, pode ser um bug — abra uma issue com o log (`--log-file`).

---

**P: `--password` sem `--rar` funciona?**

R: `--password` presume empacotamento automaticamente desde a versão 0.18.0. Ele usará seu `DEFAULT_COMPRESSOR` (do `.env`) ou uma flag `--compressor {rar,7z}` explícita. A combinação `--skip-rar --password` ainda é erro fatal.

---

## Catálogo

**P: `history.db not found` ou erro de sqlite3.**

R: O catálogo mudou para JSONL na versão 0.12.0. O arquivo correto é `~/.config/upapasta/history.jsonl`. Não existe mais `history.db`. Para consultar:
```bash
tail -5 ~/.config/upapasta/history.jsonl | python3 -m json.tool
upapasta --stats
```

---

**P: `upapasta --stats` não mostra nada.**

R: Ainda não há uploads registrados. O arquivo `history.jsonl` é criado na primeira execução com upload bem-sucedido.

---

**P: Como recuperar a senha de um upload ofuscado?**

R: A senha está registrada no campo `senha_rar` do catálogo:
```bash
grep "NomeDoRelease" ~/.config/upapasta/history.jsonl | python3 -m json.tool
```
Os NZBs também têm a senha injetada em `<meta type="password">` — SABnzbd e NZBGet a leem automaticamente.

---

## SABnzbd

**P: SABnzbd adiciona `.txt` em arquivos sem extensão.**

R: Use `--rename-extensionless` ao fazer o upload. O UpaPasta renomeia os arquivos para `.bin` antes do upload e reverte ao final. O SABnzbd recebe os arquivos como `.bin` e não adiciona `.txt`.

---

**P: SABnzbd descompacta `.zip` internos que deveriam ser preservados.**

R: Desative "Recursive Unpacking" nas configurações do SABnzbd (`Config → General → Recursive Unpacking`).

---

## Pastas e estrutura

**P: Subpastas vazias somem depois do download.**

R: Usenet e PAR2 só transportam arquivos. Sem um container (RAR ou 7z), diretórios vazios não existem. Solução:
- Use um container via `--rar` ou `--compressor 7z`
- Ou coloque um arquivo sentinela (`.keep`) em cada subpasta vazia antes do upload

---

**P: Tenho uma pasta com um único arquivo. O UpaPasta cria um arquivo compactado?**

R: Não por padrão. Um container só é criado com `--rar`, `--compressor`, `--password` ou `--obfuscate` em arquivo único. Se não usar nenhuma dessas flags, o arquivo é enviado diretamente.
