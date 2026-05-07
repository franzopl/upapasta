"""Testes para managed_popen context manager."""

import subprocess
import sys
import time
from unittest.mock import patch

import pytest

from upapasta._process import _terminate_process, managed_popen


def wait_for_proc(proc, timeout=1.0):
    start = time.time()
    while time.time() - start < timeout:
        if proc.poll() is None:
            time.sleep(0.001)
            # Try to see if it's actually running by checking if it's responsive
            # for these tests, just ensuring it exists is usually enough
            continue
        break


class TestTerminateProcess:
    """Testes para _terminate_process."""

    def test_already_terminated_process(self):
        """Processo já finalizado não deve gerar erro."""
        proc = subprocess.Popen(
            [sys.executable, "-c", "import sys; sys.exit(0)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        proc.wait()  # Aguarda conclusão

        # Não deve gerar erro ao terminar processo já finalizado
        _terminate_process(proc)
        assert proc.poll() is not None

    def test_terminate_signal_sent(self):
        """Processo deve receber SIGTERM e terminar gracefully."""
        # Script que ignora SIGTERM e executa até recebê-lo
        script = """
import signal
import time
def handler(sig, frame):
    exit(0)
signal.signal(signal.SIGTERM, handler)
while True:
    time.sleep(0.01)
"""
        proc = subprocess.Popen(
            [sys.executable, "-c", script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Aguarda o processo estar vivo
        start = time.time()
        while proc.poll() is not None and time.time() - start < 1.0:
            time.sleep(0.001)

        _terminate_process(proc, timeout=2)

        assert proc.poll() is not None, "Processo não terminou após SIGTERM"

    def test_kill_as_fallback(self):
        """Processo que não responde a SIGTERM deve receber SIGKILL."""
        # Script que ignora SIGTERM (vai precisar de SIGKILL)
        script = """
import signal
import time
signal.signal(signal.SIGTERM, signal.SIG_IGN)
while True:
    time.sleep(0.001)
"""
        proc = subprocess.Popen(
            [sys.executable, "-c", script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Aguarda o processo estar vivo
        start = time.time()
        while proc.poll() is not None and time.time() - start < 1.0:
            time.sleep(0.001)

        _terminate_process(proc, timeout=0.05)  # timeout curto força SIGKILL

        assert proc.poll() is not None, "Processo não terminou após SIGKILL"

    def test_idempotent_termination(self):
        """Chamar _terminate_process múltiplas vezes não deve causar erro."""
        proc = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(1)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Chamar múltiplas vezes
        _terminate_process(proc)
        _terminate_process(proc)
        _terminate_process(proc)

        assert proc.poll() is not None


class TestManagedPopen:
    """Testes para managed_popen context manager."""

    def test_normal_completion(self):
        """Processo que termina normalmente não deve gerar erro."""
        with managed_popen(
            [sys.executable, "-c", "print('hello')"],
            stdout=subprocess.PIPE,
            text=True,
        ) as proc:
            rc = proc.wait()
            assert rc == 0

    def test_cleanup_on_normal_exit(self):
        """Cleanup deve ser chamado mesmo em exit normal."""
        with patch("upapasta._process._terminate_process") as mock_term:
            with managed_popen(
                [sys.executable, "-c", "import time; time.sleep(0.05)"],
                stdout=subprocess.PIPE,
            ) as proc:
                _ = proc.wait()

            # _terminate_process deve ter sido chamado ao menos uma vez
            assert mock_term.called

    def test_cleanup_on_keyboard_interrupt(self):
        """Cleanup deve ser chamado em KeyboardInterrupt."""
        script = "import time; time.sleep(10)"

        with patch("upapasta._process._terminate_process") as mock_term:
            try:
                with managed_popen(
                    [sys.executable, "-c", script],
                    stdout=subprocess.PIPE,
                ) as _:
                    # Sem sleep fixo, apenas gera a interrupção
                    raise KeyboardInterrupt()
            except KeyboardInterrupt:
                pass  # Esperado

            assert mock_term.called

    def test_keyboard_interrupt_propagates(self):
        """KeyboardInterrupt deve ser re-lançado após cleanup."""
        script = "import time; time.sleep(10)"

        with pytest.raises(KeyboardInterrupt):
            with managed_popen(
                [sys.executable, "-c", script],
                stdout=subprocess.PIPE,
            ) as _:
                raise KeyboardInterrupt()

    def test_cleanup_on_exception(self):
        """Cleanup deve ser chamado quando exceção é lançada."""
        with patch("upapasta._process._terminate_process") as mock_term:
            try:
                with managed_popen(
                    [sys.executable, "-c", "import time; time.sleep(10)"],
                    stdout=subprocess.PIPE,
                ) as _:
                    raise ValueError("test error")
            except ValueError:
                pass  # Esperado

            assert mock_term.called

    def test_exception_propagates(self):
        """Exceção deve ser re-lançada após cleanup."""
        with pytest.raises(ValueError, match="test error"):
            with managed_popen(
                [sys.executable, "-c", "import time; time.sleep(10)"],
                stdout=subprocess.PIPE,
            ) as _:
                raise ValueError("test error")

    def test_early_return_cleanup(self):
        """Cleanup deve ser chamado em early return."""
        with patch("upapasta._process._terminate_process") as mock_term:

            def run_with_early_return():
                with managed_popen(
                    [sys.executable, "-c", "import time; time.sleep(10)"],
                    stdout=subprocess.PIPE,
                ) as _:
                    return "early"

            result = run_with_early_return()
            assert result == "early"
            assert mock_term.called

    def test_process_is_popen_instance(self):
        """Processo passado deve ser uma instância de subprocess.Popen."""
        with managed_popen(
            [sys.executable, "-c", "print('test')"],
            stdout=subprocess.PIPE,
        ) as proc:
            assert isinstance(proc, subprocess.Popen)

    def test_stdout_capture(self):
        """Stdout do processo deve ser capturável."""
        with managed_popen(
            [sys.executable, "-c", "print('hello world')"],
            stdout=subprocess.PIPE,
            text=True,
        ) as proc:
            output = proc.stdout.read()
            assert "hello world" in output

    def test_stderr_capture(self):
        """Stderr do processo deve ser capturável."""
        with managed_popen(
            [sys.executable, "-c", "import sys; sys.stderr.write('error')"],
            stderr=subprocess.PIPE,
            text=True,
        ) as proc:
            error = proc.stderr.read()
            assert "error" in error

    def test_return_code_propagation(self):
        """Return code do processo deve ser disponível."""
        with managed_popen(
            [sys.executable, "-c", "exit(42)"],
        ) as proc:
            rc = proc.wait()
            assert rc == 42
