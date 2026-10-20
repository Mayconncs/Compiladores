#!/usr/bin/env python3
"""
Entrada: código-fonte em DiceLang
Saída  : lista de tokens (tipo, lexema, linha, coluna)
"""
import sys
from typing import NamedTuple


class Token(NamedTuple):
    tipo: str
    lexema: str
    linha: int
    coluna: int


PALAVRAS_RESERVADAS = {
    "print": "PRINT", "if": "IF", "else": "ELSE", "while": "WHILE",
    "func": "FUNC", "return": "RETURN",
}

UNITARIOS = {
    "+": "MAIS", "-": "MENOS", "*": "MULT", "/": "DIV",
    "(": "ABRE_PAR", ")": "FECHA_PAR",
    "{": "ABRE_CHAVE", "}": "FECHA_CHAVE",
    ";": "PONTO_VIRG", ",": "VIRGULA",
}
COMPOSTOS = set("=!<>&|")


def classe(c):
    if c == "d":
        return "D"
    if "a" <= c <= "z" or "A" <= c <= "Z":
        return "LETRA"
    if "0" <= c <= "9":
        return "DIGITO"
    if c in UNITARIOS or c in COMPOSTOS:
        return c
    if c in " \t\r\n":
        return "ESPACO"
    return "OUTRO"


TRANSICOES = {
    ("q0", "LETRA"): "ID", ("q0", "D"): "ID",
    ("ID", "LETRA"): "ID", ("ID", "D"): "ID", ("ID", "DIGITO"): "ID",
    ("q0", "DIGITO"): "NUMERO",
    ("NUMERO", "DIGITO"): "NUMERO", ("NUMERO", "D"): "NUM_D",
    ("NUM_D", "DIGITO"): "ROLAGEM", ("ROLAGEM", "DIGITO"): "ROLAGEM",
    ("q0", "="): "ATRIB", ("ATRIB", "="): "IGUAL",
    ("q0", "!"): "EXCL", ("EXCL", "="): "DIF",
    ("q0", "<"): "MENOR", ("MENOR", "="): "MENOR_IGUAL",
    ("q0", ">"): "MAIOR", ("MAIOR", "="): "MAIOR_IGUAL",
    ("q0", "&"): "AMP", ("AMP", "&"): "E",
    ("q0", "|"): "BARRA", ("BARRA", "|"): "OU",
}
for simbolo, nome in UNITARIOS.items():
    TRANSICOES[("q0", simbolo)] = nome

NAO_FINAIS = {"q0", "NUM_D", "EXCL", "AMP", "BARRA"}
FINAIS = set(TRANSICOES.values()) - NAO_FINAIS


def analisar(fonte):
    """Retorna (tokens, erros). O último token é sempre EOF."""
    tokens, erros = [], []
    i, linha, coluna = 0, 1, 1

    while i < len(fonte):
        c = fonte[i]

        if classe(c) == "ESPACO":
            if c == "\n":
                linha, coluna = linha + 1, 1
            else:
                coluna += 1
            i += 1
            continue

        estado, j, ultimo = "q0", i, None
        while j < len(fonte):
            prox = TRANSICOES.get((estado, classe(fonte[j])))
            if prox is None:
                break
            estado, j = prox, j + 1
            if estado in FINAIS:
                ultimo = (j, estado)

        if ultimo is None:
            if classe(c) == "OUTRO":
                msg = f"caractere inválido {c!r}"
            else:
                msg = f"operador incompleto {c!r}"
            erros.append((linha, coluna, msg))
            i, coluna = i + 1, coluna + 1
            continue

        fim, estado = ultimo
        lexema = fonte[i:fim]
        tipo = estado
        if estado == "ID":
            tipo = PALAVRAS_RESERVADAS.get(lexema, "ID")
        tokens.append(Token(tipo, lexema, linha, coluna))
        coluna += fim - i
        i = fim

    tokens.append(Token("EOF", "", linha, coluna))
    return tokens, erros


def main():
    if len(sys.argv) > 2:
        print("uso: python lexer.py [arquivo.dice]", file=sys.stderr)
        return 2
    if len(sys.argv) == 2:
        with open(sys.argv[1], encoding="utf-8") as arquivo:
            fonte = arquivo.read()
    else:
        fonte = sys.stdin.read()

    tokens, erros = analisar(fonte)
    print(f"{'LINHA:COL':<10}{'TOKEN':<14}LEXEMA")
    for t in tokens:
        pos = f"{t.linha}:{t.coluna}"
        print(f"{pos:<10}{t.tipo:<14}{t.lexema}")
    for linha, coluna, msg in erros:
        print(f"Erro léxico ({linha}:{coluna}): {msg}", file=sys.stderr)
    return 1 if erros else 0


if __name__ == "__main__":
    sys.exit(main())
