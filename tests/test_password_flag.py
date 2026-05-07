"""Testes para a flag --password: senha aleatória e ativação implícita de --rar."""

from __future__ import annotations

import argparse

from upapasta.cli import _validate_flags


def _make_args(**kwargs) -> argparse.Namespace:
    defaults = dict(
        input="/tmp/fake",
        password=None,
        rar=False,
        skip_rar_deprecated=False,
        obfuscate=False,
        strong_obfuscate=False,
        each=False,
        season=False,
        watch=False,
    )
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


class TestPasswordRandomGeneration:
    def test_password_sem_argumento_gera_senha_aleatoria(self):
        """--password sem argumento (const=__random__) deve gerar senha de 16 chars."""
        args = _make_args(password="__random__")
        _validate_flags(args)
        assert args.password is not None
        assert args.password != "__random__"
        assert len(args.password) == 16
        assert args.password.isalnum()

    def test_password_sem_argumento_ativa_rar(self):
        """--password sem argumento deve ativar --rar automaticamente."""
        args = _make_args(password="__random__")
        _validate_flags(args)
        assert args.rar is True

    def test_password_explicito_ativa_rar(self):
        """--password com valor explícito deve ativar --rar automaticamente."""
        args = _make_args(password="minhaSenha123")
        _validate_flags(args)
        assert args.rar is True
        assert args.password == "minhaSenha123"

    def test_password_explicito_com_rar_ja_ativo(self):
        """--password --rar não deve mudar a senha fornecida."""
        args = _make_args(password="minhaSenha123", rar=True)
        _validate_flags(args)
        assert args.rar is True
        assert args.password == "minhaSenha123"

    def test_sem_password_nao_ativa_rar(self):
        """Sem --password, --rar deve permanecer False."""
        args = _make_args(password=None)
        _validate_flags(args)
        assert args.rar is False

    def test_geracoes_consecutivas_sao_distintas(self):
        """Duas execuções com __random__ devem gerar senhas diferentes (com alta probabilidade)."""
        args1 = _make_args(password="__random__")
        args2 = _make_args(password="__random__")
        _validate_flags(args1)
        _validate_flags(args2)
        # Probabilidade de colisão: (62^16)^-1 ≈ 0
        assert args1.password != args2.password
