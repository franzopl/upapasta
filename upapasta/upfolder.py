#!/usr/bin/env python3
"""
upfolder.py

Upload de arquivo .rar e arquivos de paridade (.par2) para Usenet usando nyuu.

Lê credenciais do arquivo .env global (~/.config/upapasta/.env) ou via variáveis de ambiente.

Uso:
  python3 upfolder.py /caminho/para/arquivo.rar

Opções:
  --dry-run              Mostra comando nyuu sem executar
  --nyuu-path PATH       Caminho para executável nyuu (padrão: detecta em PATH)
  --subject SUBJECT      Subject da postagem (padrão: nome do arquivo .rar)
  --group GROUP          Newsgroup para upload (pode sobrescrever .env)

Retornos:
  0: sucesso
  1: arquivo .rar não encontrado
  2: credenciais faltando/inválidas
  3: arquivo .par2 não encontrado
  4: nyuu não encontrado
  5: erro ao executar nyuu
"""

import argparse
import glob
import os
import shutil
import subprocess
import sys
import random
import string
import xml.etree.ElementTree as ET


def fix_nzb_subjects(nzb_path: str, file_list: list[str], folder_name: str = None) -> None:
    """Corrige os subjects no NZB para incluir o caminho relativo do arquivo."""
    try:
        tree = ET.parse(nzb_path)
        root = tree.getroot()

        # Encontrar todos os elementos <file>
        files = root.findall(".//{http://www.newzbin.com/DTD/2003/nzb}file")

        if len(files) == len(file_list):
            for i, file_elem in enumerate(files):
                filename = file_list[i]
                # Manter subjects dos PAR2 inalterados para reparo funcionar
                if not filename.lower().endswith('.par2'):
                    if folder_name and '/' not in filename:
                        # Para pastas, adicionar prefixo da pasta aos arquivos na raiz
                        new_subject = f"{folder_name}/{filename}"
                    else:
                        new_subject = filename
                    file_elem.set("subject", new_subject)

        # Salvar o NZB corrigido
        tree.write(nzb_path, encoding="UTF-8", xml_declaration=True)
        print(f"NZB corrigido: subjects dos arquivos de dados atualizados para preservar estrutura.")
    except Exception as e:
        print(f"Aviso: não foi possível corrigir o NZB: {e}")


def find_nyuu() -> str | None:
    """Procura executável 'nyuu' no PATH."""
    for cmd in ("nyuu", "nyuu.exe"):
        path = shutil.which(cmd)
        if path:
            return path
    return None


def find_mediainfo() -> str | None:
    """Procura executável 'mediainfo' no PATH."""
    for cmd in ("mediainfo", "mediainfo.exe"):
        path = shutil.which(cmd)
        if path:
            return path
    return None


def parse_args():
    p = argparse.ArgumentParser(
        description="Upload de .rar + .par2 para Usenet com nyuu"
    )
    p.add_argument("rarfile", help="Caminho para o arquivo .rar a fazer upload")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra comando nyuu sem executar",
    )
    p.add_argument(
        "--nyuu-path",
        default=None,
        help="Caminho para executável nyuu (padrão: detecta em PATH)",
    )
    p.add_argument(
        "--subject",
        default=None,
        help="Subject da postagem (padrão: nome do arquivo .rar)",
    )
    p.add_argument(
        "--group",
        default=None,
        help="Newsgroup (pode sobrescrever variável USENET_GROUP do .env)",
    )
    p.add_argument(
        "--env-file",
        default=os.path.expanduser("~/.config/upapasta/.env"),
        help="Caminho para arquivo .env (padrão: ~/.config/upapasta/.env)",
    )
    return p.parse_args()


def generate_anonymous_uploader() -> str:
    """Gera um nome de uploader aleatório e anônimo para proteger privacidade."""
    # Lista de nomes comuns para anonimato
    first_names = [
        "Anonymous", "User", "Poster", "Uploader", "Contributor", "Member",
        "Guest", "Visitor", "Participant", "Sender", "Provider", "Supplier"
    ]
    
    # Adiciona um sufixo aleatório de 4 dígitos
    suffix = ''.join(random.choices(string.digits, k=4))
    
    # Escolhe um nome aleatório
    name = random.choice(first_names)
    
    # Gera um domínio aleatório
    domains = ["anonymous.net", "upload.net", "poster.com", "user.org", "generic.mail"]
    domain = random.choice(domains)
    
    return f"{name}{suffix} <{name}{suffix}@{domain}>"


def upload_to_usenet(
    input_path: str,
    env_vars: dict,
    dry_run: bool = False,
    nyuu_path: str | None = None,
    subject: str | None = None,
    group: str | None = None,
) -> int:
    """Upload de arquivos para Usenet usando nyuu."""

    input_path = os.path.abspath(input_path)

    # Validar entrada
    if not os.path.exists(input_path):
        print(f"Erro: '{input_path}' não existe.")
        return 1

    is_folder = os.path.isdir(input_path)
    if not is_folder and not os.path.isfile(input_path):
        print(f"Erro: '{input_path}' não é um arquivo nem pasta.")
        return 1

    # Preparar arquivos para upload
    import tempfile
    import shutil

    if is_folder:
        # Para pastas, criar diretório temporário e copiar estrutura
        temp_dir = tempfile.mkdtemp(prefix="upapasta_")
        folder_name = os.path.basename(input_path)
        temp_folder_path = os.path.join(temp_dir, folder_name)
        
        # Copiar a pasta inteira para temp
        shutil.copytree(input_path, temp_folder_path)
        
        # Coletar arquivos relativos à temp
        files_to_upload = []
        for root, dirs, files in os.walk(temp_folder_path):
            for file in files:
                rel_path = os.path.relpath(os.path.join(root, file), temp_dir)
                files_to_upload.append(rel_path)
        
        # Copiar arquivos PAR2 para temp
        base_name = input_path
        par2_pattern = glob.escape(base_name) + "*par2*"
        par2_files_abs = sorted(glob.glob(par2_pattern))
        par2_files = []
        for par2 in par2_files_abs:
            temp_par2 = os.path.join(temp_dir, os.path.basename(par2))
            shutil.copy2(par2, temp_par2)
            par2_files.append(os.path.basename(par2))
        
        working_dir = temp_dir
    else:
        # Para arquivos únicos, comportamento normal
        files_to_upload = [os.path.basename(input_path)]
        base_name = os.path.splitext(input_path)[0]
        par2_pattern = glob.escape(base_name) + "*par2*"
        par2_files = [os.path.basename(f) for f in sorted(glob.glob(par2_pattern))]
        working_dir = os.path.dirname(input_path)
        temp_dir = None

    if not par2_files:
        print(f"Erro: nenhum arquivo de paridade encontrado para '{input_path}'.")
        print("Execute 'python3 makepar.py' primeiro para gerar os arquivos .par2")
        return 3

    # Carrega credenciais do .env
    # env_vars = load_env_file(env_file)

    nntp_host = env_vars.get("NNTP_HOST") or os.environ.get("NNTP_HOST")
    nntp_port = env_vars.get("NNTP_PORT") or os.environ.get("NNTP_PORT", "119")
    nntp_ssl = env_vars.get("NNTP_SSL", "false").lower() in ("true", "1", "yes")
    nntp_ignore_cert = env_vars.get("NNTP_IGNORE_CERT", "false").lower() in ("true", "1", "yes")
    nntp_user = env_vars.get("NNTP_USER") or os.environ.get("NNTP_USER")
    nntp_pass = env_vars.get("NNTP_PASS") or os.environ.get("NNTP_PASS")
    nntp_connections = env_vars.get("NNTP_CONNECTIONS") or os.environ.get("NNTP_CONNECTIONS", "50")
    usenet_group = group or env_vars.get("USENET_GROUP") or os.environ.get("USENET_GROUP")
    article_size = env_vars.get("ARTICLE_SIZE") or os.environ.get("ARTICLE_SIZE", "700K")
    check_connections = env_vars.get("CHECK_CONNECTIONS") or os.environ.get("CHECK_CONNECTIONS", "5")
    check_tries = env_vars.get("CHECK_TRIES") or os.environ.get("CHECK_TRIES", "2")
    check_delay = env_vars.get("CHECK_DELAY") or os.environ.get("CHECK_DELAY", "5s")
    check_retry_delay = env_vars.get("CHECK_RETRY_DELAY") or os.environ.get("CHECK_RETRY_DELAY", "30s")
    check_post_tries = env_vars.get("CHECK_POST_TRIES") or os.environ.get("CHECK_POST_TRIES", "2")
    nzb_out_template = env_vars.get("NZB_OUT") or os.environ.get("NZB_OUT")
    if not nzb_out_template:
        nzb_out_template = "{filename}_content.nzb" if is_folder else "{filename}.nzb"
    nzb_overwrite = env_vars.get("NZB_OVERWRITE", "true").lower() in ("true", "1", "yes")
    skip_errors = env_vars.get("SKIP_ERRORS") or os.environ.get("SKIP_ERRORS", "all")
    dump_failed_posts = env_vars.get("DUMP_FAILED_POSTS") or os.environ.get("DUMP_FAILED_POSTS")
    quiet = env_vars.get("QUIET", "false").lower() in ("true", "1", "yes")
    log_time = env_vars.get("LOG_TIME", "true").lower() in ("true", "1", "yes")

    # Processar template NZB_OUT: substitui {filename} pelo nome da pasta/arquivo
    nzb_out = None
    if nzb_out_template:
        # {filename} é substituído pelo nome base sem extensão
        if is_folder:
            basename = os.path.basename(input_path) + "_content"
        else:
            basename = os.path.splitext(os.path.basename(input_path))[0]
        nzb_out = nzb_out_template.replace("{filename}", basename)

    if not all([nntp_host, nntp_user, nntp_pass, usenet_group]):
        print("Erro: credenciais incompletas. Configure .env com:")
        print("  NNTP_HOST=<seu_servidor>")
        print("  NNTP_PORT=119")
        print("  NNTP_USER=<seu_usuario>")
        print("  NNTP_PASS=<sua_senha>")
        print("  USENET_GROUP=<seu_grupo>")
        return 2

    # Encontra nyuu
    if nyuu_path:
        if not os.path.exists(nyuu_path):
            print(f"Erro: nyuu não encontrado em '{nyuu_path}'")
            return 4
    else:
        nyuu_path = find_nyuu()
        if not nyuu_path:
            print("Erro: nyuu não encontrado. Instale-o (https://github.com/Piorosen/nyuu)")
            return 4

    # Define subject
    if not subject:
        if is_folder:
            subject = os.path.basename(input_path)
        else:
            subject = os.path.basename(os.path.splitext(input_path)[0])

    # Single-file: generate .nfo and save to the same directory as NZB (if defined), otherwise to the working_dir
    if not is_folder:
        # create nfo filename based on nzb (same basename) or the input filename
        if nzb_out:
            nfo_filename = os.path.splitext(os.path.basename(nzb_out))[0] + ".nfo"
            nzb_dir_part = os.path.dirname(nzb_out)
        else:
            nfo_filename = os.path.splitext(os.path.basename(input_path))[0] + ".nfo"
            nzb_dir_part = ""

        # Determine absolute path where we should write the .nfo file
        if nzb_dir_part:
            if os.path.isabs(nzb_dir_part):
                nfo_dir_abs = nzb_dir_part
            else:
                # resolve relative nzb_out path against the working_dir
                nfo_dir_abs = os.path.join(working_dir, nzb_dir_part)
        else:
            nfo_dir_abs = working_dir

        # Ensure destination directory exists
        try:
            os.makedirs(nfo_dir_abs, exist_ok=True)
        except Exception:
            pass

        nfo_path = os.path.join(nfo_dir_abs, nfo_filename)
        mediainfo_path = find_mediainfo()
        if mediainfo_path:
            try:
                mi_proc = subprocess.run([mediainfo_path, input_path], capture_output=True, text=True, check=True)
                with open(nfo_path, "w", encoding="utf-8") as f:
                    f.write(mi_proc.stdout)
                print(f"  ✔️ Arquivo NFO gerado: {nfo_filename} (salvo em: {nfo_dir_abs})")
                # Do not upload .nfo to Usenet; it's saved locally for archiving only.
            except Exception as e:
                print(f"Atenção: falha ao gerar NFO com mediainfo: {e}")
        else:
            print("Atenção: 'mediainfo' não encontrado. Pulando geração de .nfo.")

    # Constrói comando nyuu com todas as opções
    # nyuu -h <host> [-P <port>] [-S] [-i] -u <user> -p <pass> -c <connections> -g <group> -a <article-size> -s <subject> <files>
    cmd = [
        nyuu_path,
        "-h", nntp_host,
        "-P", str(nntp_port),
    ]

    if nntp_ssl:
        cmd.append("-S")

    if nntp_ignore_cert:
        cmd.append("-i")

    cmd.extend([
        "-u", nntp_user,
        "-p", nntp_pass,
        "-n", str(nntp_connections),
        "-g", usenet_group,
        "-a", article_size,
        "-f", generate_anonymous_uploader(),  # Nome anônimo para proteger privacidade
        "--date", "now",  # Fixar timestamp para proteger privacidade
        "-s", subject,
    ])
    
    # Adicionar opção -o para arquivo NZB se configurado
    if nzb_out:
        cmd.extend(["-o", nzb_out])
    
    # Adicionar opção -O para sobrescrever NZB se configurado
    if nzb_overwrite:
        cmd.append("-O")
    
    # Adicionar arquivos a fazer upload
    cmd.extend(files_to_upload)
    # Adicionar todos os arquivos .par2
    cmd.extend(par2_files)

    if dry_run:
        # Print the nyuu command but do not run it. The .nfo (for single-file uploads)
        # is already generated above (if mediainfo was found) and written to the
        # resolved `nfo_path` directory. No further .nfo writing should occur here.
        print("Comando nyuu (dry-run):")
        print(" ".join(str(x) for x in cmd))
        return 0

    print("Iniciando upload para Usenet...")
    print(f"  Host: {nntp_host}:{nntp_port}")
    print(f"  Grupo: {usenet_group}")
    print(f"  Subject: {subject}")
    all_files = files_to_upload + par2_files
    print(f"  Arquivos: {len(all_files)} arquivos ({', '.join(os.path.basename(f) for f in all_files[:3])}{'...' if len(all_files) > 3 else ''})")
    if nzb_out:
        print(f"  NZB será salvo em: {nzb_out}")
    print()

    try:
        # Executar nyuu e deixar que ele controle o output diretamente
        # Isso permite que a barra de progresso nativa do nyuu funcione
        subprocess.run(cmd, check=True, cwd=working_dir)

        # Corrigir NZB para preservar estrutura de pastas
        if nzb_out and os.path.exists(nzb_out) and is_folder:
            folder_name = os.path.basename(input_path)
            fix_nzb_subjects(nzb_out, files_to_upload + par2_files, folder_name)

        # Limpar diretório temporário se foi criado
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        
        return 0
    except subprocess.CalledProcessError as e:
        print(f"\nErro: nyuu retornou código {e.returncode}.")
        # Limpar temp_dir mesmo em erro
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        return 5
    except Exception as e:
        print(f"Erro ao executar nyuu: {e}")
        return 5



