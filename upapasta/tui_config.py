"""
tui_config.py

Wizard de configuração visual via curses.
Invocado por `upapasta --config` quando o terminal suportar curses.
Fallback automático para o wizard textual de config.py se não suportar.
"""

from __future__ import annotations

import curses
import time

from .config import DEFAULT_ENV_FILE, _write_full_env, load_env_file, resolve_env_file
from .nntp_test import check_nntp_connection
from .tui_widgets import (
    CP_DIM,
    CP_ERROR,
    CP_FOCUSED,
    CP_HEADER,
    CP_MODIFIED,
    CP_NORMAL,
    CP_SECTION,
    CP_SUCCESS,
    Button,
    CheckBox,
    CollapsibleSection,
    Dropdown,
    FormPage,
    HelpPanel,
    PasswordField,
    RadioGroup,
    RadioOption,
    SectionHeader,
    Slider,
    TextField,
    Widget,
    init_colors,
    safe_addstr,
)

# ── Constantes de layout ──────────────────────────────────────────────────────

_HELP_WIDTH = 30  # largura do painel de ajuda (colunas)
_TAB_MARGIN = 2  # recuo horizontal do formulário
_FORM_TOP = 5  # linha onde o formulário começa (abaixo do cabeçalho + abas)
_STATUS_ROWS = 2  # linhas reservadas para barra de status

# ── Textos de ajuda por campo ─────────────────────────────────────────────────

_HELP: dict[str, tuple[str, str]] = {
    "NNTP_HOST": (
        "Servidor NNTP",
        "Endereço do seu provedor Usenet.\n\nExemplos:\n news.eweka.nl\n news.usenetexpress.com\n news.frugalusenet.com\n\nSem 'https://' — apenas o hostname.",
    ),
    "NNTP_PORT": (
        "Porta NNTP",
        "119 → sem criptografia\n563 → SSL/TLS (recomendado)\n443 → SSL em firewalls\n\nA maioria dos provedores modernos usa 563.",
    ),
    "NNTP_SSL": (
        "SSL/TLS",
        "Ativa criptografia na conexão.\n\nRecomendado: Sim.\nDesative apenas se o seu provedor não suportar SSL na porta escolhida.",
    ),
    "NNTP_IGNORE_CERT": (
        "Ignorar certificado",
        "Ignora erros de verificação SSL.\n\nUse apenas em redes privadas ou provedores com cert auto-assinado.\n\nNão use em produção.",
    ),
    "NNTP_USER": (
        "Usuário NNTP",
        "Login fornecido pelo provedor Usenet.\n\nNormalmente é um e-mail ou usuário curto.",
    ),
    "NNTP_PASS": (
        "Senha NNTP",
        "Senha do provedor Usenet.\n\nArmazenada em texto simples no .env — mantenha o arquivo com permissões restritas (chmod 600).",
    ),
    "NNTP_CONNECTIONS": (
        "Conexões simultâneas",
        "Número de conexões paralelas ao servidor.\n\nVerifique o limite do seu plano:\n Eweka       → 50\n UsenetExpr  → 30\n Frugal      → 10\n\nExceder causa desconexões.",
    ),
    "USENET_GROUP": (
        "Grupo Usenet",
        "Grupo(s) para upload.\n\nModo pool: lista separada por vírgulas — o UpaPasta sorteia um grupo por upload, aumentando ofuscação.\n\nModo único: um grupo fixo.",
    ),
    "ARTICLE_SIZE": (
        "Tamanho do artigo",
        "Tamanho máximo de cada post NNTP.\n\n700K → padrão universal\n500K → provedores conservadores\n1M   → alta velocidade\n\nAltere só se o provedor recusar artigos grandes.",
    ),
    "DEFAULT_COMPRESSOR": (
        "Compressor padrão",
        "Usado por --compress quando nenhum compressor é especificado.\n\nRAR5 → máxima compatibilidade\n7-Zip → livre, headers criptografados\n\nNenhum → parpar direto (recomendado).",
    ),
    "CHECK_CONNECTIONS": (
        "Conexões de verificação",
        "Conexões usadas para checar se os posts chegaram ao servidor após o upload.\n\n5 é suficiente para a maioria dos casos.",
    ),
    "CHECK_TRIES": (
        "Tentativas de verificação",
        "Quantas vezes tentar verificar cada artigo antes de considerá-lo perdido.",
    ),
    "CHECK_DELAY": (
        "Delay inicial",
        "Espera antes da primeira verificação.\n\nExemplos: 5s, 30s, 2m\n\nServidores lentos podem precisar de mais tempo para propagar.",
    ),
    "CHECK_RETRY_DELAY": (
        "Delay entre retries",
        "Espera entre tentativas de verificação subsequentes quando um artigo não é encontrado.",
    ),
    "NZB_OUT": (
        "Saída do NZB",
        "Caminho e nome do arquivo .nzb gerado.\n\nVariáveis:\n {filename} → nome do upload\n\nExemplos:\n {filename}.nzb\n /mnt/nzb/{filename}.nzb",
    ),
    "NZB_OVERWRITE": (
        "Conflito de nome NZB",
        "O que fazer se já existir um .nzb com o mesmo nome:\n\nSobrescrever → substitui\nRenomear    → adiciona _1, _2…\nFalhar       → aborta com erro",
    ),
    "WEBHOOK_URL": (
        "Webhook de notificação",
        "URL para notificar após cada upload.\n\nDiscord:\n discord.com/api/webhooks/…\n\nSlack:\n hooks.slack.com/services/…\n\nTelegram:\n api.telegram.org/bot…/sendMessage?chat_id=…",
    ),
    "TMDB_API_KEY": (
        "Chave TMDb",
        "Chave de API do The Movie Database.\n\nObtenha gratuitamente em:\n themoviedb.org/settings/api\n\nUsada para buscar título, sinopse e gêneros automaticamente com --tmdb.",
    ),
    "TMDB_LANGUAGE": (
        "Idioma TMDb",
        "Idioma para retorno dos metadados.\n\nExemplos:\n pt-BR → Português (Brasil)\n en-US → Inglês\n es-ES → Espanhol",
    ),
    "QUIET": (
        "Modo silencioso",
        "Suprime a saída detalhada do nyuu durante o upload.\n\nRecomendado: desativado — o dashboard do UpaPasta já filtra o output.",
    ),
    "LOG_TIME": (
        "Timestamp nos logs",
        "Adiciona horário em cada linha de log.\n\nÚtil para diagnóstico de uploads longos ou falhas intermitentes.",
    ),
    "_btn_test": (
        "Testar Conexão",
        "Abre uma conexão NNTP de teste com os dados acima.\n\nVerifica host, porta, SSL e credenciais.\n\nNão faz upload — é apenas um handshake.",
    ),
    "_btn_webhook": (
        "Testar Webhook",
        "Envia uma mensagem de teste para a URL configurada.\n\nSuporta Discord, Slack, Telegram e URLs genéricas que aceitem POST JSON.",
    ),
    "_default": (
        "Configuração",
        "Use Tab / Shift+Tab ou ↑↓ para navegar entre campos.\n\nEnter ou Espaço ativa checkboxes, radio buttons e botões.\n\nF10 salva todas as alterações.\nEsc / Q descarta e sai.",
    ),
}


# ── Fábrica de abas ───────────────────────────────────────────────────────────


def _make_tab_servidor(env: dict[str, str]) -> FormPage:
    host = env.get("NNTP_HOST", "")
    port = env.get("NNTP_PORT", "563")
    ssl_val = env.get("NNTP_SSL", "true").lower() == "true"
    ignore_cert = env.get("NNTP_IGNORE_CERT", "false").lower() == "true"
    user = env.get("NNTP_USER", "")
    passwd = env.get("NNTP_PASS", "")
    conns = int(env.get("NNTP_CONNECTIONS", "50") or "50")

    # Porta como RadioGroup com opções comuns
    port_val = port if port in ("119", "443", "563") else "outro"

    def _port_validator(v: str) -> str | None:
        if not v.isdigit() or not (1 <= int(v) <= 65535):
            return "Porta inválida (1–65535)"
        return None

    port_custom = TextField(
        "NNTP_PORT",
        "Porta personalizada",
        default=port if port_val == "outro" else "",
        help_text=_HELP["NNTP_PORT"][1],
        placeholder="ex: 563",
        validator=_port_validator,
        field_width=10,
    )
    port_custom.enabled = port_val == "outro"

    port_radio = RadioGroup(
        "NNTP_PORT",
        "Porta",
        [
            RadioOption("563", "563", "SSL/TLS — recomendado"),
            RadioOption("119", "119", "sem criptografia"),
            RadioOption("443", "443", "SSL alternativo (firewalls)"),
            RadioOption("outro", "Outra…", ""),
        ],
        default=port_val,
        help_text=_HELP["NNTP_PORT"][1],
    )

    def _host_validator(v: str) -> str | None:
        if not v or " " in v or v.startswith("http"):
            return "Hostname inválido (sem https://)"
        return None

    # Botão de teste de conexão — referencia campos da página via closure
    tf_host = TextField(
        "NNTP_HOST",
        "Servidor",
        default=host,
        help_text=_HELP["NNTP_HOST"][1],
        placeholder="news.eweka.nl",
        validator=_host_validator,
        field_width=34,
    )
    pw_pass = PasswordField(
        "NNTP_PASS",
        "Senha",
        default=passwd,
        help_text=_HELP["NNTP_PASS"][1],
    )
    tf_user = TextField(
        "NNTP_USER",
        "Usuário",
        default=user,
        help_text=_HELP["NNTP_USER"][1],
        field_width=34,
    )
    cb_ssl = CheckBox(
        "NNTP_SSL",
        "SSL/TLS",
        default=ssl_val,
        help_text=_HELP["NNTP_SSL"][1],
        description="Criptografar conexão (recomendado)",
    )
    cb_ignore = CheckBox(
        "NNTP_IGNORE_CERT",
        "Ignorar certificado",
        default=ignore_cert,
        help_text=_HELP["NNTP_IGNORE_CERT"][1],
        description="Aceitar cert inválido (não recomendado)",
    )
    sl_conns = Slider(
        "NNTP_CONNECTIONS",
        "Conexões",
        minimum=1,
        maximum=100,
        default=conns,
        help_text=_HELP["NNTP_CONNECTIONS"][1],
    )

    def _test_connection() -> tuple[bool, str]:
        h = tf_host.value.strip()
        p_str = port_custom.value if port_radio.value == "outro" else port_radio.value
        try:
            p = int(p_str)
        except ValueError:
            return False, "Porta inválida"
        use_ssl = cb_ssl.checked
        u = tf_user.value.strip()
        pw = pw_pass.value
        t0 = time.monotonic()
        ok, msg = check_nntp_connection(
            h, p, use_ssl, u, pw, timeout=10, insecure=cb_ignore.checked
        )
        ms = int((time.monotonic() - t0) * 1000)
        if ok:
            return True, f"Conectado em {ms}ms"
        # remove emoji duplicado se vier da função
        clean = msg.lstrip("❌").strip()
        return False, clean[:50]

    btn_test = Button("F5 Testar Conexão", _test_connection, help_text=_HELP["_btn_test"][1])
    btn_test.key = "_btn_test"

    # Servidor secundário (failover) como seção colapsável
    failover_children: list[Widget] = [
        TextField(
            "NNTP_HOST_2",
            "Host 2",
            default=env.get("NNTP_HOST_2", ""),
            placeholder="news.outro.com",
            field_width=30,
        ),
        TextField("NNTP_PORT_2", "Porta 2", default=env.get("NNTP_PORT_2", "563"), field_width=6),
        TextField("NNTP_USER_2", "Usuário 2", default=env.get("NNTP_USER_2", ""), field_width=30),
        PasswordField("NNTP_PASS_2", "Senha 2", default=env.get("NNTP_PASS_2", "")),
        Slider(
            "NNTP_CONNECTIONS_2",
            "Conexões 2",
            minimum=1,
            maximum=100,
            default=int(env.get("NNTP_CONNECTIONS_2", "50") or "50"),
        ),
    ]

    return FormPage(
        [
            SectionHeader("Servidor Principal"),
            tf_host,
            port_radio,
            port_custom,
            cb_ssl,
            cb_ignore,
            tf_user,
            pw_pass,
            sl_conns,
            btn_test,
            CollapsibleSection("[+] Servidor de Failover (opcional)", failover_children),
        ]
    )


def _make_tab_upload(env: dict[str, str]) -> FormPage:
    group = env.get("USENET_GROUP", "")
    # Detecta se é pool (contém vírgula) ou grupo único
    is_pool = "," in group
    group_mode = "pool" if is_pool else "unico"

    article_size = env.get("ARTICLE_SIZE", "700K")
    size_val = article_size if article_size in ("500K", "700K", "1M") else "custom"

    compressor = env.get("DEFAULT_COMPRESSOR", "")
    comp_val = compressor if compressor in ("", "rar", "7z") else ""

    tf_group = TextField(
        "USENET_GROUP",
        "Grupo único",
        default=group if not is_pool else "",
        help_text=_HELP["USENET_GROUP"][1],
        placeholder="alt.binaries.boneless",
        field_width=40,
    )
    tf_group.enabled = group_mode == "unico"

    tf_size_custom = TextField(
        "ARTICLE_SIZE",
        "Tamanho personalizado",
        default=article_size if size_val == "custom" else "",
        placeholder="ex: 400K, 1500K",
        field_width=12,
    )
    tf_size_custom.enabled = size_val == "custom"

    group_radio = RadioGroup(
        "USENET_GROUP",
        "Modo de grupo",
        [
            RadioOption("pool", "Pool (10 grupos)", "distribui uploads para maior ofuscação"),
            RadioOption("unico", "Grupo único", "controle manual do grupo"),
        ],
        default=group_mode,
        help_text=_HELP["USENET_GROUP"][1],
    )

    size_radio = RadioGroup(
        "ARTICLE_SIZE",
        "Tamanho do artigo",
        [
            RadioOption("700K", "700K", "padrão universal"),
            RadioOption("500K", "500K", "provedores conservadores"),
            RadioOption("1M", "1M", "alta velocidade"),
            RadioOption("custom", "Personalizado…", ""),
        ],
        default=size_val,
        help_text=_HELP["ARTICLE_SIZE"][1],
    )

    comp_radio = RadioGroup(
        "DEFAULT_COMPRESSOR",
        "Compressor padrão",
        [
            RadioOption("", "Nenhum", "parpar direto — recomendado"),
            RadioOption("rar", "RAR5", "máxima compatibilidade"),
            RadioOption("7z", "7-Zip", "livre, header encryption"),
        ],
        default=comp_val,
        help_text=_HELP["DEFAULT_COMPRESSOR"][1],
    )

    return FormPage(
        [
            SectionHeader("Grupos Usenet"),
            group_radio,
            tf_group,
            SectionHeader("Artigos"),
            size_radio,
            tf_size_custom,
            SectionHeader("Compressão"),
            comp_radio,
        ]
    )


def _make_tab_verificacao(env: dict[str, str]) -> FormPage:
    check_conns = int(env.get("CHECK_CONNECTIONS", "5") or "5")

    tries_val = env.get("CHECK_TRIES", "2")
    tries_val = tries_val if tries_val in ("1", "2", "3", "5") else "2"

    post_tries = env.get("CHECK_POST_TRIES", "2")
    post_tries = post_tries if post_tries in ("1", "2", "3") else "2"

    def _delay_validator(v: str) -> str | None:
        import re

        if not re.match(r"^\d+[smh]?$", v):
            return "Use ex: 5s, 30s, 2m"
        return None

    return FormPage(
        [
            SectionHeader("Verificação Pós-Upload"),
            Slider(
                "CHECK_CONNECTIONS",
                "Conexões de check",
                minimum=1,
                maximum=20,
                default=check_conns,
                help_text=_HELP["CHECK_CONNECTIONS"][1],
            ),
            RadioGroup(
                "CHECK_TRIES",
                "Tentativas por artigo",
                [
                    RadioOption("1", "1", ""),
                    RadioOption("2", "2", "recomendado"),
                    RadioOption("3", "3", ""),
                    RadioOption("5", "5", "servidores lentos"),
                ],
                default=tries_val,
                help_text=_HELP["CHECK_TRIES"][1],
            ),
            TextField(
                "CHECK_DELAY",
                "Delay inicial",
                default=env.get("CHECK_DELAY", "5s"),
                help_text=_HELP["CHECK_DELAY"][1],
                placeholder="5s",
                validator=_delay_validator,
                field_width=10,
            ),
            TextField(
                "CHECK_RETRY_DELAY",
                "Delay entre retries",
                default=env.get("CHECK_RETRY_DELAY", "30s"),
                help_text=_HELP["CHECK_RETRY_DELAY"][1],
                placeholder="30s",
                validator=_delay_validator,
                field_width=10,
            ),
            RadioGroup(
                "CHECK_POST_TRIES",
                "Tentativas por post",
                [
                    RadioOption("1", "1", ""),
                    RadioOption("2", "2", "recomendado"),
                    RadioOption("3", "3", ""),
                ],
                default=post_tries,
                help_text=_HELP["CHECK_TRIES"][1],
            ),
        ]
    )


def _make_tab_nzb(env: dict[str, str]) -> FormPage:
    nzb_out = env.get("NZB_OUT", "{filename}.nzb")
    overwrite = env.get("NZB_OVERWRITE", "true").lower()
    overwrite_val = overwrite if overwrite in ("true", "false") else "true"
    skip_errors = env.get("SKIP_ERRORS", "all")
    skip_val = skip_errors if skip_errors in ("all", "none") else "all"

    def _nzb_validator(v: str) -> str | None:
        if not v:
            return "Caminho não pode ser vazio"
        return None

    return FormPage(
        [
            SectionHeader("Arquivo NZB"),
            TextField(
                "NZB_OUT",
                "Saída do NZB",
                default=nzb_out,
                help_text=_HELP["NZB_OUT"][1],
                placeholder="{filename}.nzb",
                validator=_nzb_validator,
                field_width=40,
            ),
            RadioGroup(
                "NZB_OVERWRITE",
                "Conflito de nome",
                [
                    RadioOption("true", "Sobrescrever", "substitui o .nzb existente"),
                    RadioOption("false", "Renomear", "adiciona sufixo _1, _2…"),
                    RadioOption("fail", "Falhar", "aborta se já existir"),
                ],
                default=overwrite_val,
                help_text=_HELP["NZB_OVERWRITE"][1],
            ),
            SectionHeader("Erros de Upload"),
            RadioGroup(
                "SKIP_ERRORS",
                "Erros tolerados",
                [
                    RadioOption("all", "Ignorar todos", "continua mesmo com falhas (recomendado)"),
                    RadioOption("none", "Abortar ao primeiro", "para ao menor erro"),
                ],
                default=skip_val,
            ),
        ]
    )


def _make_tab_notificacoes(env: dict[str, str]) -> FormPage:
    webhook_url = env.get("WEBHOOK_URL", "")
    tmdb_key = env.get("TMDB_API_KEY", "")
    tmdb_lang = env.get("TMDB_LANGUAGE", "pt-BR")
    tmdb_lang = tmdb_lang if tmdb_lang in ("pt-BR", "en-US", "es-ES", "fr-FR", "de-DE") else "pt-BR"

    # Detecta serviço pelo prefixo da URL
    def _detect_service(url: str) -> str:
        if "discord.com" in url:
            return "discord"
        if "slack.com" in url:
            return "slack"
        if "api.telegram.org" in url:
            return "telegram"
        if url:
            return "generico"
        return "off"

    service_val = _detect_service(webhook_url)

    tf_webhook = PasswordField(
        "WEBHOOK_URL",
        "URL do webhook",
        default=webhook_url,
        help_text=_HELP["WEBHOOK_URL"][1],
        field_width=40,
    )
    tf_webhook.enabled = service_val != "off"

    service_radio = RadioGroup(
        "_webhook_service",
        "Serviço",
        [
            RadioOption("off", "Desativado", ""),
            RadioOption("discord", "Discord", ""),
            RadioOption("slack", "Slack", ""),
            RadioOption("telegram", "Telegram", ""),
            RadioOption("generico", "URL genérica", "qualquer POST JSON"),
        ],
        default=service_val,
        help_text=_HELP["WEBHOOK_URL"][1],
    )

    def _test_webhook() -> tuple[bool, str]:
        url = tf_webhook.value.strip()
        if not url:
            return False, "URL não configurada"
        import json
        import urllib.error
        import urllib.request

        payload = json.dumps({"content": "✅ UpaPasta — teste de webhook"}).encode()
        req = urllib.request.Request(
            url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=8):
                return True, "Mensagem entregue"
        except urllib.error.HTTPError as e:
            return False, f"HTTP {e.code}"
        except Exception as e:
            return False, str(e)[:50]

    btn_webhook = Button("F6 Testar Webhook", _test_webhook, help_text=_HELP["_btn_webhook"][1])
    btn_webhook.key = "_btn_webhook"

    lang_dropdown = Dropdown(
        "TMDB_LANGUAGE",
        "Idioma TMDb",
        [
            ("pt-BR", "Português (Brasil)"),
            ("en-US", "English (US)"),
            ("es-ES", "Español"),
            ("fr-FR", "Français"),
            ("de-DE", "Deutsch"),
        ],
        default=tmdb_lang,
        help_text=_HELP["TMDB_LANGUAGE"][1],
    )

    def _test_tmdb() -> tuple[bool, str]:
        key = tf_tmdb.value.strip()
        if not key:
            return False, "Chave não configurada"
        import urllib.error
        import urllib.request

        url = f"https://api.themoviedb.org/3/configuration?api_key={key}"
        try:
            with urllib.request.urlopen(url, timeout=8):
                return True, "Chave válida"
        except urllib.error.HTTPError as e:
            return False, "Chave inválida" if e.code == 401 else f"HTTP {e.code}"
        except Exception as e:
            return False, str(e)[:50]

    tf_tmdb = PasswordField(
        "TMDB_API_KEY",
        "Chave TMDb",
        default=tmdb_key,
        help_text=_HELP["TMDB_API_KEY"][1],
        field_width=36,
    )

    btn_tmdb = Button("Testar chave TMDb", _test_tmdb)
    btn_tmdb.key = "_btn_tmdb"

    return FormPage(
        [
            SectionHeader("Notificações"),
            service_radio,
            tf_webhook,
            btn_webhook,
            SectionHeader("TMDb Metadata"),
            tf_tmdb,
            lang_dropdown,
            btn_tmdb,
        ]
    )


def _make_tab_avancado(env: dict[str, str]) -> FormPage:
    quiet = env.get("QUIET", "false").lower() == "true"
    log_time = env.get("LOG_TIME", "true").lower() == "true"
    dump = env.get("DUMP_FAILED_POSTS", "")
    nyuu_extra = env.get("NYUU_EXTRA_ARGS", "")
    nfo_tmpl = env.get("NFO_TEMPLATE", "")
    external_nzb = env.get("EXTERNAL_NZB_DIR", "")

    return FormPage(
        [
            SectionHeader("Comportamento"),
            CheckBox(
                "QUIET",
                "Modo silencioso",
                default=quiet,
                description="Suprime saída detalhada do nyuu",
            ),
            CheckBox(
                "LOG_TIME",
                "Timestamp",
                default=log_time,
                description="Exibe horário em cada linha de log",
            ),
            SectionHeader("Caminhos"),
            TextField(
                "DUMP_FAILED_POSTS",
                "Posts falhos",
                default=dump,
                placeholder="(vazio = desativado)",
                field_width=36,
                help_text="Pasta para salvar artigos que falharam no upload.",
            ),
            TextField(
                "NFO_TEMPLATE",
                "Template NFO",
                default=nfo_tmpl,
                placeholder="(vazio = padrão)",
                field_width=36,
                help_text="Caminho para arquivo .txt com placeholders de NFO customizado.",
            ),
            TextField(
                "EXTERNAL_NZB_DIR",
                "NZB externo",
                default=external_nzb,
                placeholder="(vazio = desativado)",
                field_width=36,
                help_text="Diretórios separados por vírgula para buscar .nzb externos.",
            ),
            SectionHeader("nyuu"),
            TextField(
                "NYUU_EXTRA_ARGS",
                "Args extras nyuu",
                default=nyuu_extra,
                placeholder="ex: --article-threads=8",
                field_width=36,
                help_text="Argumentos extras repassados ao nyuu via shlex. Use com cautela.",
            ),
        ]
    )


# ── Wizard principal ──────────────────────────────────────────────────────────

_TAB_NAMES = ["Servidor", "Upload", "Verificação", "NZB", "Notificações", "Avançado"]
_TAB_KEYS = ["F1", "F2", "F3", "F4", "F5", "F6"]

# Mapeamento de tecla de função → índice da aba
_FKEY_TO_TAB: dict[int, int] = {
    curses.KEY_F1: 0,
    curses.KEY_F2: 1,
    curses.KEY_F3: 2,
    curses.KEY_F4: 3,
    curses.KEY_F5: 4,
    curses.KEY_F6: 5,
}


class ConfigWizard:
    """Wizard de configuração visual com abas, painel de ajuda e barra de status."""

    def __init__(self, env_file: str = DEFAULT_ENV_FILE) -> None:
        self._env_file = env_file
        self._env = load_env_file(env_file)
        self._tab_idx = 0
        self._scroll_tops = [0] * len(_TAB_NAMES)
        self._status: str = ""
        self._status_ok: bool = True
        self._running = True
        self._saved = False
        self._help = HelpPanel()
        self._pages: list[FormPage] = []

    def _build_pages(self) -> None:
        self._pages = [
            _make_tab_servidor(self._env),
            _make_tab_upload(self._env),
            _make_tab_verificacao(self._env),
            _make_tab_nzb(self._env),
            _make_tab_notificacoes(self._env),
            _make_tab_avancado(self._env),
        ]

    @property
    def _page(self) -> FormPage:
        return self._pages[self._tab_idx]

    # ── Renderização ──────────────────────────────────────────────────────

    def _draw(self, win: curses.window) -> None:
        win.erase()
        max_y, max_x = win.getmaxyx()

        self._draw_header(win, max_x)
        self._draw_tabs(win, max_x)
        self._draw_form(win, max_y, max_x)
        self._draw_help(win, max_y, max_x)
        self._draw_status(win, max_y, max_x)
        win.refresh()

    def _draw_header(self, win: curses.window, max_x: int) -> None:
        title = " UpaPasta — Configuração Visual"
        bar = " " * (max_x - len(title) - 1)
        safe_addstr(win, 0, 0, title + bar, curses.color_pair(CP_HEADER) | curses.A_BOLD)

    def _draw_tabs(self, win: curses.window, max_x: int) -> None:
        safe_addstr(win, 2, 0, " " * max_x, curses.color_pair(CP_NORMAL))
        x = 1
        for i, (name, fkey) in enumerate(zip(_TAB_NAMES, _TAB_KEYS)):
            label = f" {fkey}:{name} "
            any_dirty = any(w.dirty for w in self._pages[i]._widgets)
            if i == self._tab_idx:
                attr: int = curses.color_pair(CP_FOCUSED) | curses.A_BOLD
            elif any_dirty:
                attr = curses.color_pair(CP_MODIFIED) | curses.A_BOLD
            else:
                attr = curses.color_pair(CP_DIM)
            safe_addstr(win, 2, x, label, attr)
            x += len(label) + 1

        # Linha separadora
        safe_addstr(win, 3, 0, "─" * max_x, curses.color_pair(CP_SECTION))

    def _draw_form(self, win: curses.window, max_y: int, max_x: int) -> None:
        help_col = max_x - self._help.width - 1
        form_width = help_col - _TAB_MARGIN - 2
        form_height = max_y - _FORM_TOP - _STATUS_ROWS

        self._page.render(
            win,
            y=_FORM_TOP,
            x=_TAB_MARGIN,
            width=form_width,
            height=form_height,
            scroll_top=self._scroll_tops[self._tab_idx],
        )

    def _draw_help(self, win: curses.window, max_y: int, max_x: int) -> None:
        focused = self._page.focused_widget
        if focused and focused.help_text:
            title, _ = _HELP.get(focused.key, _HELP["_default"])
            self._help.set(title, focused.help_text)
        else:
            t, txt = _HELP["_default"]
            self._help.set(t, txt)

        help_x = max_x - self._help.width - 1
        help_h = max_y - _FORM_TOP - _STATUS_ROWS
        self._help.render(win, y=_FORM_TOP, x=help_x, height=help_h)

    def _draw_status(self, win: curses.window, max_y: int, max_x: int) -> None:
        row = max_y - _STATUS_ROWS
        # Atalhos
        shortcuts = "  Tab Próximo  Shift+Tab Anterior  F10 Salvar  Q Sair"
        safe_addstr(
            win,
            row,
            0,
            shortcuts + " " * (max_x - len(shortcuts)),
            curses.color_pair(CP_DIM) | curses.A_DIM,
        )
        # Mensagem de status
        if self._status:
            attr = curses.color_pair(CP_SUCCESS) if self._status_ok else curses.color_pair(CP_ERROR)
            safe_addstr(win, row + 1, 2, self._status, attr | curses.A_BOLD)

    # ── Teclado ───────────────────────────────────────────────────────────

    def _handle_key(self, key: int) -> None:
        # Navegação de abas por F1–F6
        if key in _FKEY_TO_TAB:
            self._tab_idx = _FKEY_TO_TAB[key]
            self._status = ""
            return

        # Salvar
        if key == curses.KEY_F10:
            self._do_save()
            return

        # Sair
        if key in (ord("q"), ord("Q"), 27):  # 27 = Esc
            self._running = False
            return

        # Scroll da página
        if key == curses.KEY_PPAGE:
            self._scroll_tops[self._tab_idx] = max(0, self._scroll_tops[self._tab_idx] - 5)
            return
        if key == curses.KEY_NPAGE:
            max_scroll = max(0, self._page.total_height() - 10)
            self._scroll_tops[self._tab_idx] = min(max_scroll, self._scroll_tops[self._tab_idx] + 5)
            return

        # Repassa ao FormPage
        self._page.handle_key(key)
        self._status = ""  # limpa status ao interagir

    # ── Persistência ──────────────────────────────────────────────────────

    def _collect_all(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for page in self._pages:
            for k, v in page.collect_values().items():
                if not k.startswith("_"):  # ignora chaves internas como _webhook_service
                    result[k] = v
        return result

    def _do_save(self) -> None:
        # Valida todas as páginas
        all_errors: list[str] = []
        for page in self._pages:
            all_errors.extend(page.validate_all())

        if all_errors:
            self._status = f"⚠ {all_errors[0]}"
            self._status_ok = False
            return

        changes = self._collect_all()
        if not changes:
            self._status = "Nenhuma alteração para salvar."
            self._status_ok = True
            return

        try:
            _write_full_env(self._env_file, changes)
            self._saved = True
            self._status = f"✓ Salvo em {self._env_file}  ({len(changes)} campo(s) atualizado(s))"
            self._status_ok = True
        except OSError as e:
            self._status = f"Erro ao salvar: {e}"
            self._status_ok = False

    # ── Loop principal ────────────────────────────────────────────────────

    def run(self, stdscr: curses.window) -> bool:
        """Executa o wizard. Retorna True se o usuário salvou."""
        curses.curs_set(1)
        curses.noecho()
        stdscr.keypad(True)
        init_colors()
        self._build_pages()

        while self._running:
            self._draw(stdscr)
            try:
                key = stdscr.getch()
            except KeyboardInterrupt:
                break
            self._handle_key(key)

        return self._saved


# ── Entrypoint público ────────────────────────────────────────────────────────


def run_config_wizard(profile: str | None = None) -> bool:
    """
    Abre o wizard visual se o terminal suportar curses.
    Retorna True se o usuário salvou alguma alteração.
    Lança RuntimeError se o terminal não suportar curses (o chamador deve
    fazer fallback para prompt_for_credentials).
    """
    env_file = resolve_env_file(profile)

    def _main(stdscr: curses.window) -> bool:
        return ConfigWizard(env_file).run(stdscr)

    try:
        return bool(curses.wrapper(_main))
    except curses.error as exc:
        raise RuntimeError(f"Terminal não suporta modo curses: {exc}") from exc


__all__ = ["run_config_wizard", "ConfigWizard"]
