#!/usr/bin/env python3
"""
makerar.py

Recebe um caminho para uma pasta e cria um arquivo .rar com o mesmo nome
na pasta pai. Requer o utilitário de linha de comando `rar` (instale via
`sudo apt install rar` em Debian/Ubuntu ou baixe de RARLAB).

Uso:
  python3 makerar.py /caminho/para/minha_pasta

Opções:
  -f, --force    Sobrescrever arquivo .rar existente

Saídas:
  Código 0  -> sucesso
  Código 2  -> pasta de entrada inexistente / não é diretório
  Código 3  -> arquivo .rar já existe (use --force para sobrescrever)
  Código 4  -> utilitário `rar` não encontrado
  Código 5  -> erro ao executar o comando rar
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
import threading
from queue import Queue
from typing import Optional


def find_rar():
	"""Procura o executável 'rar' no PATH."""
	for cmd in ("rar", "rar.exe"):
		path = shutil.which(cmd)
		if path:
			return path
	return None


def _read_output(pipe, queue: Queue):
	"""Thread worker para ler linhas do subprocess stdout."""
	if pipe is None:
		return
	try:
		for line in pipe:
			queue.put(line.rstrip("\n"))
	except:
		pass
	finally:
		queue.put(None)  # Sinal de fim


def _process_output(queue: Queue) -> tuple[int, bool]:
	"""
	Processa linhas de output da fila em thread principal.
	Retorna (último_percent, teve_percentual).
	"""
	last_percent = -1
	teve_percentual = False
	spinner = "|/-\\"
	spin_idx = 0
	bar_width = 40

	while True:
		line = queue.get()
		if line is None:  # Fim da leitura
			break

		# Tenta encontrar porcentagem no formato 'xx%'
		m = re.search(r"(\d{1,3})%", line)
		if m:
			pct = None
			try:
				pct = int(m.group(1))
			except ValueError:
				pass
			if pct is not None:
				last_percent = pct
				teve_percentual = True
				filled = int((pct / 100.0) * bar_width)
				bar = "#" * filled + "-" * (bar_width - filled)
				sys.stdout.write(f"\r[{bar}] {pct:3d}%")
				sys.stdout.flush()
				continue

		# Se não houver porcentagem, mostra linha compacta com spinner
		sys.stdout.write(f"\r{spinner[spin_idx % len(spinner)]} {line[:70]}")
		sys.stdout.flush()
		spin_idx += 1

	return last_percent, teve_percentual


def make_rar(folder_path: str, force: bool = False, threads: int | None = None) -> int:
	folder_path = os.path.abspath(folder_path)
	if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
		print(f"Erro: '{folder_path}' não existe ou não é um diretório.")
		return 2

	parent = os.path.dirname(folder_path)
	base = os.path.basename(os.path.normpath(folder_path))
	out_rar = os.path.join(parent, base + ".rar")

	if os.path.exists(out_rar) and not force:
		print(f"Erro: '{out_rar}' já existe. Use --force para sobrescrever.")
		return 3

	rar_exec = find_rar()
	if not rar_exec:
		print(
			"Erro: utilitário 'rar' não encontrado. Instale-o (ex: sudo apt install rar)"
		)
		return 4

	# Executar o comando no diretório pai para que o arquivo inclua a
	# pasta com seu nome (em vez de incluir caminhos absolutos).
	# -m0 -> store (sem compressão)
	# -ma5 -> algoritmo de compressão RAR5
	# -mt -> usar múltiplos threads
	num_threads = threads if threads is not None else (os.cpu_count() or 4)
	cmd = [rar_exec, "a", "-r", "-m0", f"-mt{num_threads}", "-ma5", out_rar, base]

	print(f"Criando '{out_rar}' a partir de '{folder_path}' (usando {num_threads} threads)...")

	try:
		# Executa o rar e captura stdout/stderr para parsear progresso
		proc = subprocess.Popen(
			cmd,
			cwd=parent,
			stdout=subprocess.PIPE,
			stderr=subprocess.STDOUT,
			text=True,
			bufsize=1,
		)

		# Fila para comunicação entre threads
		output_queue: Queue = Queue()

		# Thread para ler output do subprocess
		reader_thread = threading.Thread(
			target=_read_output,
			args=(proc.stdout, output_queue),
			daemon=True
		)
		reader_thread.start()

		# Processa output na thread principal
		last_percent, teve_percentual = _process_output(output_queue)

		# Aguarda o fim do processo
		rc = proc.wait()

		# Se parseamos uma porcentagem final, garante newline limpo
		if teve_percentual and last_percent >= 0:
			sys.stdout.write("\n")

		if rc == 0:
			print("Arquivo .rar criado com sucesso.")
			return 0
		else:
			print(f"Erro: 'rar' retornou código {rc}.")
			return 5
	except Exception as e:
		print("Erro ao executar 'rar':", e)
		return 5


def parse_args():
	p = argparse.ArgumentParser(description="Cria um .rar de uma pasta com o mesmo nome")
	p.add_argument("folder", help="Caminho para a pasta a ser compactada")
	p.add_argument("-f", "--force", action="store_true", help="Sobrescrever .rar existente")
	return p.parse_args()


