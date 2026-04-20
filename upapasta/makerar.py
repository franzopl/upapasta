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
import glob
import math
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
	"""Thread worker para ler output do subprocess tratando \r e \n."""
	if pipe is None:
		return
	try:
		buffer = ""
		while True:
			char = pipe.read(1)
			if not char:
				break
			if char in ("\r", "\n"):
				if buffer:
					queue.put(buffer)
					buffer = ""
			else:
				buffer += char
		if buffer:
			queue.put(buffer)
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
	bar_width = 25

	try:
		term_columns = shutil.get_terminal_size().columns
	except Exception:
		term_columns = 80

	while True:
		line = queue.get()
		if line is None:
			break

		line = line.strip()
		if not line:
			continue

		sys.stdout.write("\r" + " " * (term_columns - 1) + "\r")

		m = re.search(r"(\d{1,3})%", line)
		pct = None
		if m:
			try:
				pct = int(m.group(1))
			except ValueError:
				pass
		elif line.strip().isdigit():
			val = int(line.strip())
			if 0 <= val <= 100:
				pct = val

		if pct is not None:
			last_percent = pct
			teve_percentual = True
			filled = int((pct / 100.0) * bar_width)
			bar = "#" * filled + "-" * (bar_width - filled)

			# Limpa o texto da linha para mostrar detalhes
			clean_line = re.sub(r"\d{1,3}%?", "", line).strip().strip("...").strip(":")
			if clean_line.isdigit(): clean_line = ""

			msg = f"[{bar}] {pct:3d}% {clean_line}"
			sys.stdout.write(msg[:term_columns - 1])
			sys.stdout.flush()
			continue


		msg = f"{spinner[spin_idx % len(spinner)]} {line}"
		sys.stdout.write(msg[:term_columns - 1])
		sys.stdout.flush()
		spin_idx += 1

	sys.stdout.write("\n")
	sys.stdout.flush()

	return last_percent, teve_percentual


_MIN_SPLIT_SIZE = 10 * 1024 * 1024 * 1024  # 10 GB — abaixo disso, RAR único
_MIN_VOLUME_SIZE = 1024 * 1024 * 1024      # 1 GB — tamanho mínimo de cada parte
_MAX_VOLUMES = 100


def _folder_size(path: str) -> int:
	"""Retorna o tamanho total em bytes de todos os arquivos sob path."""
	total = 0
	for dirpath, _, filenames in os.walk(path):
		for fname in filenames:
			try:
				total += os.path.getsize(os.path.join(dirpath, fname))
			except OSError:
				pass
	return total


def _volume_size_bytes(total_bytes: int) -> int | None:
	"""
	Calcula o tamanho ideal de cada volume RAR em bytes.
	Retorna None quando o conteúdo é pequeno o suficiente para um RAR único.

	Regras:
	  - Abaixo de _MIN_SPLIT_SIZE → sem volumes (None)
	  - Tamanho = max(_MIN_VOLUME_SIZE, ceil(total / _MAX_VOLUMES))
	  - Arredondado para o próximo múltiplo de 5 MB para ficar redondo
	"""
	if total_bytes < _MIN_SPLIT_SIZE:
		return None

	raw = math.ceil(total_bytes / _MAX_VOLUMES)
	vol = max(_MIN_VOLUME_SIZE, raw)

	five_mb = 5 * 1024 * 1024
	vol = math.ceil(vol / five_mb) * five_mb
	return vol


def make_rar(folder_path: str, force: bool = False, threads: int | None = None, password: str | None = None) -> tuple[int, str | None]:
	"""Cria um arquivo RAR para a pasta fornecida.

	Retorna (código_de_retorno, primeiro_arquivo_gerado).
	Sem volumes: ("nome.rar",). Com volumes: primeiro é "nome.part001.rar".
	Em caso de erro o segundo elemento é sempre None.
	"""
	folder_path = os.path.abspath(folder_path)
	if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
		print(f"Erro: '{folder_path}' não existe ou não é um diretório.")
		return 2, None

	parent = os.path.dirname(folder_path)
	base = os.path.basename(os.path.normpath(folder_path))
	out_rar = os.path.join(parent, base + ".rar")
	existing_parts = glob.glob(os.path.join(parent, glob.escape(base) + ".part*.rar"))
	if (os.path.exists(out_rar) or existing_parts) and not force:
		print(f"Erro: '{out_rar}' ou volumes parciais já existem. Use --force para sobrescrever.")
		return 3, None
	if force:
		if os.path.exists(out_rar):
			try:
				os.remove(out_rar)
			except OSError:
				pass
		for part in existing_parts:
			try:
				os.remove(part)
			except OSError:
				pass

	rar_exec = find_rar()
	if not rar_exec:
		print(
			"Erro: utilitário 'rar' não encontrado. Instale-o (ex: sudo apt install rar)"
		)
		return 4, None

	total_bytes = _folder_size(folder_path)
	vol_bytes = _volume_size_bytes(total_bytes)

	num_threads = threads if threads is not None else (os.cpu_count() or 4)

	# -m0 → store, -ma5 → RAR5, -mt → threads, -v → volumes
	# -hp cifra conteúdo E nomes de arquivo internos (mais forte que -p)
	cmd = [rar_exec, "a", "-r", "-m0", f"-mt{num_threads}", "-ma5"]
	if password:
		cmd.append(f"-hp{password}")
	if force:
		cmd.append("-o+")
	if vol_bytes is not None:
		cmd.append(f"-v{vol_bytes}b")
		num_vols = max(1, -(-total_bytes // vol_bytes))  # ceil division
		print(
			f"Criando '{out_rar}' em volumes de {vol_bytes // (1024*1024)} MB"
			f" (~{num_vols} partes, {total_bytes // (1024*1024)} MB total)..."
		)
	else:
		print(f"Criando '{out_rar}' a partir de '{folder_path}' (usando {num_threads} threads)...")

	cmd += [out_rar, base]

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

		if rc == 0:
			print("Arquivo .rar criado com sucesso.")
			if vol_bytes is None:
				return 0, out_rar
			matches = glob.glob(os.path.join(parent, glob.escape(base) + ".part*.rar"))
			if matches:
				return 0, sorted(matches)[0]
			# Volumes esperados mas não encontrados — rar gerou arquivo único
			print("Aviso: volumes RAR não encontrados, usando arquivo único.")
			return 0, out_rar
		else:
			print(f"Erro: 'rar' retornou código {rc}.")
			return 5, None
	except FileNotFoundError:
		print("Erro: binário 'rar' não encontrado no PATH.")
		return 4, None
	except PermissionError as e:
		print(f"Erro de permissão ao executar 'rar': {e}")
		return 5, None
	except OSError as e:
		print(f"Erro de I/O ao executar 'rar': {e}")
		return 5, None


def parse_args():
	p = argparse.ArgumentParser(description="Cria um .rar de uma pasta com o mesmo nome")
	p.add_argument("folder", help="Caminho para a pasta a ser compactada")
	p.add_argument("-f", "--force", action="store_true", help="Sobrescrever .rar existente")
	return p.parse_args()


