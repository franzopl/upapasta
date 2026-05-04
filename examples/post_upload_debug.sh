#!/bin/bash
# Script de debug pós-upload - imprime todas as variáveis UPAPASTA_*

echo "=== Variáveis UPAPASTA_* Recebidas ==="
echo ""
echo "UPAPASTA_NZB:              $UPAPASTA_NZB"
echo "UPAPASTA_NFO:              $UPAPASTA_NFO"
echo "UPAPASTA_SENHA:            $UPAPASTA_SENHA"
echo "UPAPASTA_NOME_ORIGINAL:    $UPAPASTA_NOME_ORIGINAL"
echo "UPAPASTA_NOME_OFUSCADO:    $UPAPASTA_NOME_OFUSCADO"
echo "UPAPASTA_TAMANHO:          $UPAPASTA_TAMANHO bytes"
echo "UPAPASTA_GRUPO:            $UPAPASTA_GRUPO"
echo ""
echo "=== Timestamp ==="
date
