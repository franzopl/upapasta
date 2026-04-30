
import os
import nntplib
import xml.etree.ElementTree as ET
from dotenv import dotenv_values

def verify_nntp_header(nzb_path):
    # 1. Carrega configurações do UpaPasta
    config_path = os.path.expanduser("~/.config/upapasta/.env")
    env = dotenv_values(config_path)
    
    host = env.get("NNTP_HOST")
    port = int(env.get("NNTP_PORT", 119))
    user = env.get("NNTP_USER")
    password = env.get("NNTP_PASS")
    use_ssl = env.get("NNTP_SSL", "false").lower() == "true"

    print(f"Conectando a {host}...")
    
    # 2. Pega o primeiro Message-ID do NZB
    tree = ET.parse(nzb_path)
    ns = {"nzb": "http://www.newzbin.com/DTD/2003/nzb"}
    segment = tree.find(".//nzb:segment", ns)
    if segment is None:
        print("Não foi possível encontrar segmentos no NZB.")
        return
    
    msg_id = segment.text
    print(f"Verificando Message-ID: <{msg_id}>")

    # 3. Conecta e busca o Header
    try:
        if use_ssl:
            server = nntplib.NNTP_SSL(host, port, user=user, password=password)
        else:
            server = nntplib.NNTP(host, port, user=user, password=password)
            
        # O comando 'HEAD' retorna apenas os headers do artigo
        resp, info = server.head(f"<{msg_id}>")
        
        # Filtra o header 'Subject'
        headers = [line.decode('utf-8', errors='ignore') for line in info.lines]
        subject_line = next((h for h in headers if h.lower().startswith("subject:")), "Subject não encontrado")
        
        print("\n" + "="*50)
        print("RESULTADO DO SERVIDOR (O QUE É PÚBLICO):")
        print("="*50)
        print(subject_line)
        print("="*50)
        
        server.quit()
        
    except Exception as e:
        print(f"Erro ao consultar servidor: {e}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        verify_nntp_header(sys.argv[1])
    else:
        print("Uso: python3 check_header.py /caminho/para/seu.nzb")
