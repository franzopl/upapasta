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

from __future__ import annotations

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
from typing import Optional, Tuple

from ._process import managed_popen


def find_rar():
	"""Procura o executável 'rar' no PATH."""
	for cmd in ("rar", "rar.exe"):
		path = shutil.which(cmd)
		if path:
			return path
	return None


# Regex compartilhado — compilado uma vez, tolerante a formatos variados.
_PCT_RE = re.compile(r"(?:^(.+?)[:\s]+)?(\d{1,3}(?:\.\d+)?)\s*%")

_CHUNK_SIZE = 4096  # bytes por read() — reduz syscalls vs. read(1)


def _read_output(pipe, queue: Queue) -> None:
	"""
	Thread worker que lê o pipe do subprocess em chunks de 4 KB e envia
	linhas individuais para a fila, tratando tanto \\r quanto \\n como
	separadores (necessário para barras de progresso que usam \\r sem \\n).
	"""
	if pipe is None:
		queue.put(None)
		return
	buf = ""
	try:
		while True:
			chunk = pipe.read(_CHUNK_SIZE)
			if not chunk:
				break
			buf += chunk
			# Emite cada "linha" separada por \r ou \n
			while True:
				for sep in ("\r\n", "\r", "\n"):
					idx = buf.find(sep)
					if idx != -1:
						token = buf[:idx]
						buf = buf[idx + len(sep):]
						if token:
							queue.put(token)
						break
				else:
					# Nenhum separador no buffer — aguarda mais dados
					break
	finally:
		if buf:
			queue.put(buf)
		queue.put(None)  # Sinal de fim de stream


def _process_output(queue: Queue) -> Tuple[int, bool]:
	"""
	Processa linhas de output da fila na thread principal.

	Lógica de exibição:
	  1. Se a linha contém "XX%" → barra de progresso animada.
	  2. Caso contrário → spinner + texto truncado (fallback robusto).

	Retorna (last_percent, teve_percentual).
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

	clear = "\r" + " " * (term_columns - 1) + "\r"

	while True:
		line = queue.get()
		if line is None:
			break

		line = line.strip()
		if not line:
			continue

		sys.stdout.write(clear)

		# ── Tenta parsear porcentagem ──────────────────────────────────────
		m = _PCT_RE.search(line)
		if m:
			try:
				pct = float(m.group(2))
				if 0.0 <= pct <= 100.0:
					last_percent = int(pct)
					teve_percentual = True
					filled = int((pct / 100.0) * bar_width)
					bar = "#" * filled + "-" * (bar_width - filled)
					clean = line[:m.start()].strip().rstrip(".").rstrip(":").strip()
					msg = f"[{bar}] {last_percent:3d}% {clean}"
					sys.stdout.write(msg[:term_columns - 1])
					sys.stdout.flush()
					continue
			except (ValueError, TypeError):
				pass  # cai para spinner abaixo

		# ── Fallback: spinner + texto (formato desconhecido ou mensagem info) ──
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


def _volume_size_bytes(total_bytes: int) -> Optional[int]:
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


def make_rar(folder_path: str, force: bool = False, threads: Optional[int] = None, password: Optional[str] = None) -> Tuple[int, Optional[str]]:
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

	num_threads = min(threads if threads is not None else (os.cpu_count() or 4), 64)

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
		# Executa o rar e captura stdout/stderr para parsear progresso.
		# managed_popen garante SIGTERM → SIGKILL no filho se o Python receber
		# KeyboardInterrupt (Ctrl+C) ou qualquer outra exceção.
		with managed_popen(
			cmd,
			cwd=parent,
			stdout=subprocess.PIPE,
			stderr=subprocess.STDOUT,
			text=True,
			bufsize=1,
		) as proc:
			# Fila para comunicação entre threads
			output_queue: Queue = Queue()

			# Thread daemon: morrerá automaticamente quando o processo filho morrer
			reader_thread = threading.Thread(
				target=_read_output,
				args=(proc.stdout, output_queue),
				daemon=True,
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
	except KeyboardInterrupt:
		# managed_popen já terminou o filho; propaga para o orquestrador
		raise
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


