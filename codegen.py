#!/usr/bin/env python3
"""
Gerador de código para DiceLang.

Percorre a AST (depois do léxico, sintático e semântico) e escreve um programa
Python equivalente. O arquivo gerado roda sozinho, sem depender deste projeto.

Uso:
    python codegen.py programa.dice                 # gera programa.py e executa
    python codegen.py programa.dice -o saida.py     # escolhe o arquivo de saída
    python codegen.py programa.dice --nao-executar  # só gera o código
    python codegen.py < programa.dice               # lê da entrada padrão

Tradução:
    func f(a) { ... }     ->  def f(a): ...        (sempre termina com 'return 0')
    x = expr;             ->  x = expr
    print(expr);          ->  print(expr)
    if/else if/else       ->  if/elif/else
    while (cond) { ... }  ->  while cond: ...
    a / b                 ->  a // b               (divisão inteira)
    && e ||               ->  and e or
    NdM                   ->  _rolar(N, M)         (soma de N dados de M faces)
"""
import argparse
import keyword
import os
import sys

from Parser import (
    No, NoPrograma, NoFuncao, NoAtribuicao, NoImpressao,
    NoSelecao, NoRepeticao, NoRetorno, NoChamada, NoBinaria,
    NoRolagem, NoNumero, NoId, parsear,
)
from semantic import analisar_semantica, ErroSemantico

# Nomes que o código gerado usa e que, portanto, um identificador do
# DiceLang não pode ocupar (ganham um "_" no final).
_RESERVADOS = {"random", "print", "sum", "range", "_rolar",
               "True", "False", "None"}

_CABECALHO = '''\
# Código gerado automaticamente pelo compilador DiceLang -> Python.
import random


def _rolar(qtd, faces):
    """Soma de `qtd` dados de `faces` lados cada."""
    return sum(random.randint(1, faces) for _ in range(qtd))
'''

# Precedência dos operadores aritméticos (maior = liga mais forte)
_PREC = {"+": 1, "-": 1, "*": 2, "/": 2}
_OP_LOGICO = {"&&": "and", "||": "or"}


def _nome(ident: str) -> str:
    """Evita colisão com palavras reservadas do Python (ex.: 'class', 'def')."""
    if keyword.iskeyword(ident) or ident in _RESERVADOS:
        return ident + "_"
    return ident


class GeradorPython:
    def __init__(self):
        self.linhas = []
        self.nivel = 0

    # --- Utilitários ---

    def _emitir(self, texto: str = ""):
        self.linhas.append("    " * self.nivel + texto if texto else "")

    def _bloco(self, comandos: list):
        """Emite uma lista de comandos indentada (com 'pass' se vazia)."""
        self.nivel += 1
        if not comandos:
            self._emitir("pass")
        for cmd in comandos:
            self._comando(cmd)
        self.nivel -= 1

    # --- Ponto de entrada ---

    def gerar(self, programa: NoPrograma) -> str:
        funcoes = [d for d in programa.declaracoes if isinstance(d, NoFuncao)]
        comandos = [d for d in programa.declaracoes if not isinstance(d, NoFuncao)]

        # No DiceLang as funções valem em qualquer ponto do programa;
        # por isso todas são emitidas antes dos comandos.
        for func in funcoes:
            self._emitir()
            self._emitir()
            self._funcao(func)

        if comandos:
            self._emitir()
            self._emitir()
            self._emitir("# --- Programa principal ---")
            for cmd in comandos:
                self._comando(cmd)

        return _CABECALHO + "\n".join(self.linhas) + "\n"

    # --- Declarações e comandos ---

    def _funcao(self, no: NoFuncao):
        params = ", ".join(_nome(p) for p in no.parametros)
        self._emitir(f"def {_nome(no.nome)}({params}):")
        self.nivel += 1
        for cmd in no.corpo:
            self._comando(cmd)
        # Função sem 'return' no fim devolve 0 (mesmo comportamento do interpretador)
        if not no.corpo or not isinstance(no.corpo[-1], NoRetorno):
            self._emitir("return 0")
        self.nivel -= 1

    def _comando(self, no: No):
        if isinstance(no, NoAtribuicao):
            self._emitir(f"{_nome(no.alvo)} = {self._expr(no.expr)}")
        elif isinstance(no, NoImpressao):
            self._emitir(f"print({self._expr(no.expr)})")
        elif isinstance(no, NoSelecao):
            self._selecao(no)
        elif isinstance(no, NoRepeticao):
            self._emitir(f"while {self._cond(no.cond)}:")
            self._bloco(no.bloco)
        elif isinstance(no, NoRetorno):
            self._emitir(f"return {self._expr(no.expr)}")
        elif isinstance(no, NoChamada):
            self._emitir(self._expr(no))
        else:
            raise NotImplementedError(f"Comando não suportado no gerador: {type(no).__name__}")

    def _selecao(self, no: NoSelecao):
        self._emitir(f"if {self._cond(no.cond)}:")
        self._bloco(no.bloco_se)
        senao = no.bloco_senao
        # Encadeia 'else if' como 'elif'
        while senao is not None and len(senao) == 1 and isinstance(senao[0], NoSelecao):
            interno = senao[0]
            self._emitir(f"elif {self._cond(interno.cond)}:")
            self._bloco(interno.bloco_se)
            senao = interno.bloco_senao
        if senao is not None:
            self._emitir("else:")
            self._bloco(senao)

    # --- Expressões aritméticas ---

    def _expr(self, no: No, prec_pai: int = 0, direita: bool = False) -> str:
        if isinstance(no, NoNumero):
            return str(no.valor)
        if isinstance(no, NoId):
            return _nome(no.nome)
        if isinstance(no, NoRolagem):
            return f"_rolar({no.qtd}, {no.faces})"
        if isinstance(no, NoChamada):
            args = ", ".join(self._expr(a) for a in no.argumentos)
            return f"{_nome(no.nome)}({args})"
        if isinstance(no, NoBinaria) and no.op in _PREC:
            prec = _PREC[no.op]
            op = "//" if no.op == "/" else no.op
            texto = f"{self._expr(no.esq, prec, False)} {op} {self._expr(no.dire, prec, True)}"
            # Parênteses só quando necessários (operadores são associativos à esquerda)
            if prec < prec_pai or (direita and prec == prec_pai):
                return f"({texto})"
            return texto
        raise NotImplementedError(f"Expressão não suportada no gerador: {type(no).__name__}")

    # --- Condições (comparações ligadas por && e ||) ---

    def _cond(self, no: NoBinaria) -> str:
        if no.op in _OP_LOGICO:
            esq = self._cond(no.esq)
            dire = self._cond(no.dire)
            # No DiceLang && e || têm a mesma precedência (esquerda para a direita);
            # no Python 'and' liga mais forte que 'or'. Por isso, parênteses sempre
            # que o operador do filho for diferente, e no filho da direita.
            if isinstance(no.esq, NoBinaria) and no.esq.op in _OP_LOGICO and no.esq.op != no.op:
                esq = f"({esq})"
            if isinstance(no.dire, NoBinaria) and no.dire.op in _OP_LOGICO:
                dire = f"({dire})"
            return f"{esq} {_OP_LOGICO[no.op]} {dire}"
        # Comparação: ==, !=, <, >, <=, >= têm o mesmo significado no Python
        return f"{self._expr(no.esq)} {no.op} {self._expr(no.dire)}"


def gerar_codigo(ast: NoPrograma) -> str:
    """Recebe a AST já validada e devolve o código Python como texto."""
    return GeradorPython().gerar(ast)


def executar_codigo(codigo: str, nome_arquivo: str = "<dicelang>"):
    """Executa o código Python gerado num espaço de nomes próprio."""
    exec(compile(codigo, nome_arquivo, "exec"), {"__name__": "__main__"})


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="codegen.py",
        description="Compila DiceLang para Python e (por padrão) executa o resultado.")
    ap.add_argument("arquivo", nargs="?", help="programa .dice (sem isso, lê da entrada padrão)")
    ap.add_argument("-o", "--saida", help="arquivo .py de saída (padrão: mesmo nome do .dice)")
    ap.add_argument("-n", "--nao-executar", action="store_true",
                    help="apenas gera o código, sem executar")
    args = ap.parse_args(argv)

    if args.arquivo:
        with open(args.arquivo, encoding="utf-8") as f:
            fonte = f.read()
    else:
        fonte = sys.stdin.read()

    ast, erros_lex, erro_sin = parsear(fonte)
    if erros_lex:
        for linha, coluna, msg in erros_lex:
            print(f"Erro léxico ({linha}:{coluna}): {msg}", file=sys.stderr)
        return 1
    if erro_sin:
        print(str(erro_sin), file=sys.stderr)
        return 1
    try:
        analisar_semantica(ast)
    except ErroSemantico as e:
        print(str(e), file=sys.stderr)
        return 1

    codigo = gerar_codigo(ast)

    destino = args.saida
    if destino is None and args.arquivo:
        destino = os.path.splitext(args.arquivo)[0] + ".py"
        if os.path.abspath(destino) == os.path.abspath(args.arquivo):
            destino += ".py"  # nunca sobrescreve o próprio arquivo de entrada
    if destino:
        with open(destino, "w", encoding="utf-8") as f:
            f.write(codigo)
        print(f"Código gerado em: {destino}", file=sys.stderr)

    if args.nao_executar:
        if not destino:
            print(codigo, end="")
        return 0

    try:
        executar_codigo(codigo, destino or "<dicelang>")
    except NameError as e:  # inclui UnboundLocalError
        nome = getattr(e, "name", None) or str(e)
        print(f"Erro de execução: Variável não definida em tempo de execução: '{nome}'",
              file=sys.stderr)
        return 1
    except (ZeroDivisionError, RuntimeError) as e:
        print(f"Erro de execução: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
