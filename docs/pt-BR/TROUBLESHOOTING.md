# Guia de Diagnóstico — UpaPasta

Diagnóstico por sintoma. Para perguntas frequentes, veja [FAQ.md](FAQ.md).

---

## O upload falhou

```
Upload falhou
│
├─ "nyuu: command not found"
│   └─ Instalar nyuu: npm install -g nyuu
│       Confirmar: nyuu --version
│
├─ Erro 401 / "Authentication required"
│   └─ Credenciais inválidas
│       Verificar NNTP_USER e NNTP_PASS no .env
│       Testar: upapasta --test-connection
│
├─ Erro 403 / "Access denied"
│   └─ Conta sem permissão de posting
│       Contatar o provedor Usenet
│
├─ Erro 502 / "Bad Gateway"
│   └─ Servidor sobrecarregado ou em manutenção
│       Aguardar alguns minutos e tentar novamente
│       Configurar --upload-retries 3 para retry automático
│       Configurar servidor de failover (NNTP_HOST_2 no .env)
│
├─ "Connection refused" / "ECONNREFUSED"
│   └─ Host ou porta incorretos
│       Verificar NNTP_HOST e NNTP_PORT no .env
│       Confirmar: upapasta --test-connection
│
├─ SSL handshake error / "certificate verify failed"
│   └─ Certificado inválido ou autoassinado
│       Testar: upapasta --test-connection --insecure
│       Se funcionar com --insecure → definir NNTP_IGNORE_CERT=true no .env
│       Se não funcionar → host ou porta errados
│
├─ Upload para no meio sem erro claro
│   └─ Provável timeout
│       Adicionar --upload-timeout 300
│       Configurar servidor de failover
│       Verificar: df -h (espaço no disco)
│
└─ Upload interrompido (Ctrl+C ou queda de rede)
    └─ Retomar: upapasta Pasta/ --resume (mesmas flags do original)
        Se "state file não encontrado" → refazer upload completo
```

---

## A geração de PAR2 falhou

```
PAR2 falhou
│
├─ "parpar: command not found"
│   └─ Instalar: pip install parpar
│       Alternativa: apt install par2 e usar --backend par2
│
├─ "par2: command not found" (usando --backend par2)
│   └─ Instalar: apt install par2  /  brew install par2
│
├─ Erro de espaço em disco
│   └─ Verificar: df -h
│       Precisa de ~2× o tamanho da fonte disponível
│       Liberar espaço ou mudar diretório de saída
│
├─ Erro de memória / processo morto
│   └─ Limitar: --max-memory 512
│       Reduzir threads: --par-threads 2
│
├─ Falha na segunda tentativa (retry automático)
│   └─ O UpaPasta imprime instrução na tela para retomar:
│       upapasta arquivo.rar --force --par-profile safe
│
└─ Subpastas não são preservadas (usando --backend par2)
    └─ par2 clássico não suporta paths
        Migrar para parpar (padrão): remover --backend par2
        upapasta Pasta/ --backend parpar --filepath-format common
```

---

## O NZB foi gerado mas o download não funciona

```
NZB inválido ou download quebrado
│
├─ SABnzbd/NZBGet reporta artigos faltando
│   └─ Aumentar paridade: --par-profile safe (20%)
│       Os artigos podem ter expirado no servidor
│       Verificar retenção do seu provedor Usenet
│
├─ Estrutura de pastas não foi reconstruída
│   ├─ Confirmar que upload foi feito com --filepath-format common (padrão)
│   └─ No SABnzbd: ativar "Repair Archive" / desativar "Recursive Unpacking"
│
├─ Arquivos chegam com nomes aleatórios
│   ├─ Se usou --obfuscate: os subjects do NZB devem ter nomes originais
│   │   Verificar se o NZB foi processado (fix_nzb_subjects)
│   │   Sintoma: o NZB foi gerado antes do fix → download com nomes aleatórios
│   └─ Se usou --strong-obfuscate: esperado — renomear manualmente ou via PAR2
│
├─ SABnzbd adiciona .txt em arquivos sem extensão
│   └─ Refazer upload com --rename-extensionless
│
└─ Senha não foi detectada pelo SABnzbd/NZBGet
    └─ A senha é injetada como <meta type="password"> no NZB
        Verificar: grep "password" arquivo.nzb
        Se ausente: o upload foi feito sem --password ou --obfuscate + --rar
        Solução: anotar a senha do catálogo e extrair manualmente
            grep "NomeDoRelease" ~/.config/upapasta/history.jsonl
```

---

## O UpaPasta não encontra o `.env`

```
.env não encontrado / credenciais não carregadas
│
├─ Primeira execução
│   └─ Execute upapasta --config para criar o .env interativamente
│
├─ .env em local diferente
│   └─ Usar --env-file /caminho/para/.env
│       Ou --profile nome (carrega ~/.config/upapasta/nome.env)
│
└─ .env existe mas credenciais erradas
    └─ upapasta --config para reconfigurar (Enter mantém valor atual)
        Ou editar diretamente: nano ~/.config/upapasta/.env
```

---

## Modo `--watch` não processa novos arquivos

```
--watch não processa
│
├─ Arquivo apareceu mas não foi processado
│   └─ O arquivo precisa ficar estável por --watch-stable segundos (padrão: 60)
│       Para testes: --watch-stable 5
│       Para downloads lentos: --watch-stable 300
│
├─ --watch com --each ou --season
│   └─ Combinação inválida — erro fatal esperado
│
└─ Processo encerrado silenciosamente
    └─ Verificar log: --log-file /tmp/upapasta.log
        Executar com --verbose para debug detalhado
```

---

## Ofuscação não foi revertida

```
Arquivos locais com nomes aleatórios após upload
│
├─ Reversão falhou durante o processo
│   └─ O UpaPasta imprime instrução manual na tela
│       Seguir as instruções impressas para renomear de volta
│
├─ Ctrl+C durante a ofuscação
│   └─ O rollback é garantido via finally — aguardar a mensagem de confirmação
│       Se o processo foi morto com SIGKILL (kill -9): rollback não executou
│       Usar o obfuscated_map impresso para reverter manualmente
│
└─ Arquivos .par2 com nomes aleatórios persistem
    └─ Normal após --obfuscate sem --keep-files: são removidos no cleanup
        Se --keep-files foi usado: remover manualmente os .par2 aleatórios
```

---

## Catálogo / histórico

```
Problema com histórico
│
├─ "history.db not found" ou erro sqlite3
│   └─ O catálogo mudou para JSONL na versão 0.12.0
│       Arquivo correto: ~/.config/upapasta/history.jsonl
│       Consultar: tail -5 ~/.config/upapasta/history.jsonl | python3 -m json.tool
│       Estatísticas: upapasta --stats
│
├─ --stats não mostra nada
│   └─ Nenhum upload registrado ainda (history.jsonl vazio ou inexistente)
│
└─ NZB arquivado não encontrado
    └─ NZBs são hardlinks em ~/.config/upapasta/nzb/
        Se o disco foi formatado ou hardlink perdido → usar caminho_nzb do catálogo
        ls -la ~/.config/upapasta/nzb/
```

---

## Coleta de informações para reportar um bug

Se nenhum dos cenários acima resolver, colete as informações abaixo antes de abrir uma issue:

```bash
# Versão do UpaPasta
upapasta --help | head -1

# Versão do Python
python3 --version

# Binários disponíveis
which nyuu parpar par2 rar ffprobe mediainfo 2>&1

# Log detalhado da execução que falhou
upapasta Pasta/ --verbose --log-file /tmp/upapasta_debug.log
# Compartilhar o conteúdo de /tmp/upapasta_debug.log (remover senhas antes)
```

Abrir issue em: https://github.com/franzopl/upapasta/issues
