import os
import sys
import re
import time
import shutil
import subprocess
import requests
import threading
from dotenv import load_dotenv
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor
from tqdm import tqdm
from qbittorrentapi import Client

# Carrega variáveis de ambiente
load_dotenv()

WATCH_DIR        = os.getenv("WATCH_DIR")
NZB_DIR          = os.getenv("NZB_OUTPUT_DIR")
BOT_TOKEN        = os.getenv("TELEGRAM_TOKEN")
CHAT_ID          = os.getenv("TELEGRAM_CHAT_ID")
TOPIC_ID         = os.getenv("TELEGRAM_TOPIC_ID")
QBIT_URL         = os.getenv("QBIT_HOST")
QBIT_USER        = os.getenv("QBIT_USER")
QBIT_PASS        = os.getenv("QBIT_PASS")
UPAPASTA_NZB_DIR = os.getenv("UPAPASTA_NZB_DIR", "/home/batata/nzb/omg/enviar_omg")

# ─────────────────────────────────────────────
# CONFIGURAÇÕES DO CAPYLABS
# ─────────────────────────────────────────────
APP_URL        = "https://capylabs.duckdns.org"
SECRET_API_KEY = "RZIgI6ykQvm3cuzZfVEtMHKfy5PYUw8ONFPj5HtSLUy"

SENT_FILE = "sent_folders.txt"

# ─────────────────────────────────────────────
# HELPERS GERAIS
# ─────────────────────────────────────────────

def load_sent():
    if not os.path.exists(SENT_FILE):
        return set()
    with open(SENT_FILE, "r") as f:
        return {line.strip() for line in f.readlines()}

def save_sent(folder):
    with open(SENT_FILE, "a") as f:
        f.write(folder + "\n")

def folder_size(path):
    total = 0
    for root, _, files in os.walk(path):
        for file in files:
            try: total += os.path.getsize(os.path.join(root, file))
            except: pass
    return total

def wait_stable(path, wait_seconds=5):
    stable_time = 0
    last_size = folder_size(path)
    print(f"[*] Aguardando estabilização: {os.path.basename(path)}")
    while stable_time < wait_seconds:
        time.sleep(1)
        current_size = folder_size(path)
        if current_size == last_size:
            stable_time += 1
        else:
            stable_time = 0
            last_size = current_size
    print("[+] Pasta estabilizada.")

# ─────────────────────────────────────────────
# QBITTORRENT
# ─────────────────────────────────────────────

def get_qbit_data_safe(folder_name, local_size):
    try:
        qbt_client = Client(host=QBIT_URL, username=QBIT_USER, password=QBIT_PASS)
        qbt_client.auth_log_in()
        torrents = qbt_client.torrents_info()

        candidates = []
        for t in torrents:
            t_name = t.name.lower()
            f_name = folder_name.lower()
            name_match = (f_name == t_name or f_name in t_name or t_name in f_name)
            if name_match:
                size_diff = abs(t.total_size - local_size)
                margin = t.total_size * 0.01
                if size_diff <= margin:
                    score = 10 if f_name == t_name else 5
                    candidates.append({'hash': t.hash, 'comment': t.comment, 'score': score, 'name': t.name})

        if not candidates: return None, "Link não encontrado"
        best_match = sorted(candidates, key=lambda x: x['score'], reverse=True)[0]
        link = "Link não encontrado"
        if "http" in best_match['comment']:
            link = "https" + best_match['comment'].split("https")[-1]
        print(f"[OK] Torrent validado: {best_match['name']}")
        return best_match['hash'], link
    except Exception as e:
        print(f"[!] Erro qBittorrent: {e}")
        return None, "Erro na conexão"

def qbit_delete(torrent_hash):
    try:
        qbt_client = Client(host=QBIT_URL, username=QBIT_USER, password=QBIT_PASS)
        qbt_client.auth_log_in()
        qbt_client.torrents_delete(delete_files=True, torrent_hashes=torrent_hash)
        return True
    except: return False

# ─────────────────────────────────────────────
# CAPYLABS — Lookup e Upload
# ─────────────────────────────────────────────

def capylabs_get_metadata(nome_busca: str):
    """Tenta obter metadados: qBit primeiro (apenas TID), depois API remota (Full)."""
    # 1. Tenta via qBit para obter ao menos o TID
    tid_qbit = None
    try:
        qbt = Client(host=QBIT_URL, username=QBIT_USER, password=QBIT_PASS)
        qbt.auth_log_in()
        for t in qbt.torrents_info():
            if nome_busca.lower() in t.name.lower():
                match = re.search(r"/(\d+)\s*$", (t.comment or ""))
                if match:
                    tid_qbit = int(match.group(1))
                    break
    except: pass

    # 2. Consulta API remota
    print(f"  🔍 Consultando metadados no CapyLabs para: {nome_busca}")
    url = f"{APP_URL}/api/torrents/search-by-path"
    headers = {"X-API-Key": SECRET_API_KEY}
    api_error = None
    try:
        r = requests.get(url, params={"path": nome_busca}, headers=headers, timeout=20)
        if r.status_code == 200:
            data = r.json()
            print(f"  ✅ Metadados recuperados via API (ID: {data.get('id')})")
            return data, None
        elif r.status_code == 404:
            print(f"  ℹ️ Metadados não encontrados na API para: {nome_busca}")
            if tid_qbit:
                return {"id": tid_qbit, "name": nome_busca}, None
            return None, None
        else:
            api_error = f"Erro HTTP {r.status_code}"
    except Exception as e:
        api_error = str(e)
        print(f"  ⚠️ Erro na conexão com a API: {e}")

    # Retorna erro para permitir retry se a API caiu
    return None, api_error

def capylabs_upload_arquivo(torrent_id: int, file_path: str) -> bool:
    if not os.path.isfile(file_path): return False
    url = f"{APP_URL}/api/torrents/{torrent_id}/upload"
    headers = {"X-API-Key": SECRET_API_KEY}
    tamanho = os.path.getsize(file_path)
    nome = os.path.basename(file_path)
    print(f"\n  📤 CapyLabs — enviando '{nome}'...")
    try:
        with open(file_path, "rb") as f:
            with tqdm(total=tamanho, unit="B", unit_scale=True, desc=f"  {nome}", leave=True) as barra:
                class ProgressReader:
                    def __init__(self, fobj, cb): self._f, self._cb = fobj, cb
                    def read(self, size=-1):
                        chunk = self._f.read(size)
                        if chunk: self._cb(len(chunk))
                        return chunk
                reader = ProgressReader(f, barra.update)
                files = {"file": (nome, reader, "application/octet-stream")}
                r = requests.post(url, files=files, headers=headers, timeout=120)
        if r.status_code == 200:
            print(f"  ✅ Upload CapyLabs OK!")
            return True
        print(f"  ❌ Falha {r.status_code}: {r.text}")
    except: print("  ❌ Erro na conexão com CapyLabs")
    return False

# ─────────────────────────────────────────────
# PROCESSO PRINCIPAL
# ─────────────────────────────────────────────

def process_folder(folder, is_retry=False):
    folder_path = os.path.join(WATCH_DIR, folder)
    if folder in load_sent(): return

    wait_stable(folder_path)
    local_folder_size = folder_size(folder_path)

    print(f"[*] Validando metadados no qBittorrent para: {folder}")
    torrent_hash, link_torrent = get_qbit_data_safe(folder, local_folder_size)

    # Localizar e Mover NZB + NFO
    nzb_name, nfo_name = folder + ".nzb", folder + ".nfo"
    dest_nzb = os.path.join(NZB_DIR, nzb_name)
    dest_nfo = os.path.join(NZB_DIR, nfo_name)

    if not is_retry or not os.path.exists(dest_nzb):
        print(f"[*] Rodando upapasta...")
        try:
            subprocess.run(["upapasta", folder_path, "--skip-rar"], check=True)
        except Exception as e:
            print(f"[!] Erro ao rodar upapasta: {e}")

        # Tenta pegar da pasta do upapasta e mover para o destino final
        for name, dest in [(nzb_name, dest_nzb), (nfo_name, dest_nfo)]:
            src = os.path.join(UPAPASTA_NZB_DIR, name)
            if os.path.exists(src):
                shutil.copy2(src, dest)
                print(f"  [✓] Arquivo copiado de {UPAPASTA_NZB_DIR}")
            else:
                # Fallback: procura recursivamente na WATCH_DIR caso o upapasta tenha salvo em outro lugar
                found = next((os.path.join(r, f) for r, _, fs in os.walk(WATCH_DIR) for f in fs if f.lower() == name.lower()), None)
                if found:
                    shutil.copy2(found, dest)
                    print(f"  [✓] Arquivo encontrado via fallback e copiado: {found}")

    if not os.path.exists(dest_nzb):
        print(f"[!] NZB não encontrado para {folder}. Abortando.")
        return

    # Busca Metadados do CapyLabs (checkCBR)
    print(f"\n[*] CapyLabs — identificando torrent: {folder}")
    metadata, api_error = capylabs_get_metadata(folder)

    error_file = os.path.join(folder_path, "capylabs_error.txt")

    if api_error:
        with open(error_file, "w") as f:
            f.write(f"Erro na API do CapyLabs: {api_error}")
        print(f"  ❌ API indisponível. Erro salvo em '{error_file}'. O upload será tentado novamente mais tarde.")
        return

    # Envio Telegram (com metadados se disponíveis)
    telegram_ok = send_telegram_with_progress(dest_nzb, link_torrent, metadata=metadata)
    if not telegram_ok:
        with open(error_file, "w") as f:
            f.write("Erro ao enviar para o Telegram.")
        print(f"  ❌ Erro no Telegram. Erro salvo em '{error_file}'. Será tentado novamente mais tarde.")
        return

    # Envio CapyLabs (Upload de arquivos extras)
    if metadata and metadata.get('id'):
        tid = metadata.get('id')
        ok_nzb = capylabs_upload_arquivo(tid, dest_nzb)
        ok_nfo = capylabs_upload_arquivo(tid, dest_nfo)

        if not ok_nzb:
            with open(error_file, "w") as f:
                f.write("Erro ao fazer upload do NZB para o CapyLabs.")
            print(f"  ❌ Erro de upload no CapyLabs. Erro salvo. Retentando depois.")
            return

        print("\n  " + "─" * 30)
        print(f"  NZB : {'✅ OK' if ok_nzb else '❌ Falhou'}")
        print(f"  NFO : {'✅ OK' if ok_nfo else '❌ Falhou/Ignorado'}")
        print("  " + "─" * 30)
    else:
        print("  ❌ CapyLabs: TID não encontrado, upload de extras cancelado.")

    if os.path.exists(error_file):
        os.remove(error_file)

    save_sent(folder)
    if torrent_hash:
        qbit_delete(torrent_hash)
        print(f"[+] Finalizado: {folder} — torrent removido.")

# ─────────────────────────────────────────────
# TELEGRAM E WATCHDOG
# ─────────────────────────────────────────────

def human_size(nbytes):
    suffixes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    i = 0
    while nbytes >= 1024 and i < len(suffixes)-1:
        nbytes /= 1024.
        i += 1
    f = ('%.2f' % nbytes).rstrip('0').rstrip('.')
    return '%s %s' % (f, suffixes[i])

def send_telegram_with_progress(file_path, link_torrent, metadata=None):
    file_name = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)

    # Construção da mensagem estilizada
    if metadata:
        course_name = metadata.get('name', 'N/A')
        folder = metadata.get('root_path', 'N/A')
        uploader = metadata.get('uploader', 'Sistema')
        raw_size = metadata.get('size', 0)
        formatted_size = human_size(raw_size) if isinstance(raw_size, (int, float)) else raw_size
        date_str = metadata.get('created_at', 'N/A')

        caption_text = (
            f"<b>🎓 CURSO:</b> <code>{course_name}</code>\n"
            f"<b>📁 PASTA:</b> <code>{folder}</code>\n"
            f"<b>👤 UPLOADER:</b> <code>{uploader}</code>\n"
            f"<b>⚖️ TAMANHO:</b> <code>{formatted_size}</code>\n"
            f"<b>📅 DATA:</b> <code>{date_str}</code>\n\n"
            f"<b>🔗 LINK DO TORRENT:</b>\n{link_torrent}\n\n"
            f"🚀 <i>NZB enviado com sucesso via CapyLabs</i>"
        )
    else:
        caption_text = f"<b>Arquivo enviado:</b> <code>{file_name}</code>\n\n<b>🔗 Link do Torrent:</b>\n{link_torrent}"

    progresso = tqdm(total=file_size, unit='B', unit_scale=True, desc=f"🚀 Upload {file_name[:20]}")
    def callback(monitor): progresso.update(monitor.bytes_read - progresso.n)

    try:
        with open(file_path, "rb") as f_obj:
            encoder = MultipartEncoder(fields={
                "chat_id": str(CHAT_ID),
                "message_thread_id": str(TOPIC_ID),
                "parse_mode": "HTML",
                "caption": caption_text,
                "document": (file_name, f_obj, "application/octet-stream")
            })
            monitor = MultipartEncoderMonitor(encoder, callback)
            r = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument", 
                              data=monitor, 
                              headers={'Content-Type': monitor.content_type},
                              timeout=120)
            progresso.close()
            return r.status_code == 200
    except Exception as e:
        print(f"  ❌ Erro ao enviar para o Telegram: {e}")
        progresso.close()
        return False

class Handler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            try:
                process_folder(os.path.basename(event.src_path))
            except Exception as e:
                print(f"[!] Erro crítico ao processar pasta {event.src_path}: {e}")

def retry_failed_uploads():
    while True:
        time.sleep(300) # Checa a cada 5 minutos
        if not WATCH_DIR or not os.path.exists(WATCH_DIR):
            continue
        try:
            for folder in os.listdir(WATCH_DIR):
                folder_path = os.path.join(WATCH_DIR, folder)
                if os.path.isdir(folder_path):
                    error_file = os.path.join(folder_path, "capylabs_error.txt")
                    if os.path.exists(error_file) and folder not in load_sent():
                        print(f"\n[*] Iniciando retentativa para: {folder}")
                        process_folder(folder, is_retry=True)
        except: pass

if __name__ == "__main__":
    retry_thread = threading.Thread(target=retry_failed_uploads, daemon=True)
    retry_thread.start()

    print(f"[*] Vigiando: {WATCH_DIR}")
    if not os.path.exists(NZB_DIR): os.makedirs(NZB_DIR)
    observer = Observer()
    observer.schedule(Handler(), WATCH_DIR, recursive=False)
    observer.start()
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt: observer.stop()
    observer.join()
