#!/usr/bin/env python3
"""Analisador sintático da DiceLang.

Entrada: código-fonte em DiceLang (arquivo como argumento ou stdin)
Saida  : a arvore sintatica (AST) em formato indentado, ou os
         erros sintaticos encontrados
"""
import sys
from typing import NamedTuple, Optional
from lexer import analisar, Token


# -- 1. Nos da AST -------------------------------------------------

class NoPrograma(NamedTuple):
    declaracoes: list


class NoFuncao(NamedTuple):
    nome: str
    parametros: list
    corpo: list
    linha: int


class NoAtribuicao(NamedTuple):
    alvo: str
    expr: "No"
    linha: int


class NoImpressao(NamedTuple):
    expr: "No"
    linha: int


class NoSelecao(NamedTuple):
    cond: "No"
    bloco_se: list
    bloco_senao: Optional[list]
    linha: int


class NoRepeticao(NamedTuple):
    cond: "No"
    bloco: list
    linha: int


class NoRetorno(NamedTuple):
    expr: "No"
    linha: int


class NoChamada(NamedTuple):
    nome: str
    argumentos: list
    linha: int


class NoBinaria(NamedTuple):
    op: str
    esq: "No"
    dire: "No"
    linha: int


class NoRolagem(NamedTuple):
    qtd: int
    faces: int
    linha: int


class NoNumero(NamedTuple):
    valor: int
    linha: int


class NoId(NamedTuple):
    nome: str
    linha: int


No = (NoPrograma | NoFuncao | NoAtribuicao | NoImpressao | NoSelecao |
      NoRepeticao | NoRetorno | NoChamada | NoBinaria | NoRolagem |
      NoNumero | NoId)

OPS_IGUALDADE = {"IGUAL", "DIF"}
OPS_RELACIONAIS = {"MENOR", "MAIOR", "MENOR_IGUAL", "MAIOR_IGUAL"}
OPS_ADITIVOS = {"MAIS", "MENOS"}
OPS_MULTIPLICATIVOS = {"MULT", "DIV"}


# -- 2. Erro sintatico ----------------------------------------------
class ErroSintatico(Exception):
    def __init__(self, linha, coluna, msg):
        super().__init__(f"Erro sintático ({linha}:{coluna}): {msg}")
        self.linha, self.coluna, self.msg = linha, coluna, msg


def _descrever(tok: Token) -> str:
    """'TIPO' ou 'TIPO <lexema>', usado nas mensagens de erro."""
    if tok.lexema:
        return f"{tok.tipo} {tok.lexema!r}"
    return tok.tipo


# -- 3. Parser: uma funcao por producao da BNF ----------------------
class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0

    def atual(self) -> Token:
        return self.tokens[self.pos]

    def olhar(self, k=1) -> Token:
        j = self.pos + k
        if j < len(self.tokens):
            return self.tokens[j]
        return self.tokens[-1] 

    def casa(self, *tipos) -> Token:
        """Consome o token atual se seu tipo estiver em `tipos`;
        caso contrario, levanta ErroSintatico."""
        tok = self.atual()
        if tok.tipo not in tipos:
            esperado = " ou ".join(tipos)
            achado = _descrever(tok)
            raise ErroSintatico(tok.linha, tok.coluna,
                f"esperado {esperado}, encontrado {achado}")
        self.pos += 1
        return tok

    # <programa> ::= <lista_decl>
    def programa(self) -> NoPrograma:
        decls = []
        while self.atual().tipo != "EOF":
            decls.append(self.declaracao())
        return NoPrograma(decls)

    # <declaracao> ::= <funcao> | <comando>
    def declaracao(self):
        if self.atual().tipo == "FUNC":
            return self.funcao()
        return self.comando()

    # <funcao> ::= "func" <id> "(" [ <parametros> ] ")" "{" <lista_comandos> "}"
    def funcao(self) -> NoFuncao:
        t_func = self.casa("FUNC")
        nome = self.casa("ID").lexema
        self.casa("ABRE_PAR")
        params = []
        if self.atual().tipo == "ID":
            params.append(self.casa("ID").lexema)
            while self.atual().tipo == "VIRGULA":
                self.casa("VIRGULA")
                params.append(self.casa("ID").lexema)
        self.casa("FECHA_PAR")
        corpo = self.bloco()
        return NoFuncao(nome, params, corpo, t_func.linha)

    # <lista_comandos> dentro de "{" ... "}"
    def bloco(self) -> list:
        self.casa("ABRE_CHAVE")
        comandos = []
        while self.atual().tipo != "FECHA_CHAVE":
            if self.atual().tipo == "EOF":
                t = self.atual()
                raise ErroSintatico(t.linha, t.coluna,
                    "'}' esperado antes do fim do arquivo")
            comandos.append(self.comando())
        self.casa("FECHA_CHAVE")
        return comandos

    # <comando> ::= <atribuicao> | <impressao> | <selecao>
    #             | <repeticao> | <retorno> | <chamada> ";"
    def comando(self):
        tipo = self.atual().tipo
        if tipo == "ID":
            if self.olhar(1).tipo == "ATRIB":
                return self.atribuicao()
            no = self.chamada()
            self.casa("PONTO_VIRG")
            return no
        if tipo == "PRINT":
            return self.impressao()
        if tipo == "IF":
            return self.selecao()
        if tipo == "WHILE":
            return self.repeticao()
        if tipo == "RETURN":
            return self.retorno()
        t = self.atual()
        raise ErroSintatico(t.linha, t.coluna,
            f"início de comando esperado, encontrado {_descrever(t)}")

    # <atribuicao> ::= <id> "=" <expressao> ";"
    def atribuicao(self) -> NoAtribuicao:
        alvo = self.casa("ID")
        self.casa("ATRIB")
        expr = self.expressao()
        self.casa("PONTO_VIRG")
        return NoAtribuicao(alvo.lexema, expr, alvo.linha)

    # <impressao> ::= "print" "(" <expressao> ")" ";"
    def impressao(self) -> NoImpressao:
        t = self.casa("PRINT")
        self.casa("ABRE_PAR")
        expr = self.expressao()
        self.casa("FECHA_PAR")
        self.casa("PONTO_VIRG")
        return NoImpressao(expr, t.linha)

    # <selecao> ::= "if" "(" <condicao> ")" "{" <lista_comandos> "}"
    #               [ "else" "{" <lista_comandos> "}" ]
    def selecao(self) -> NoSelecao:
        t = self.casa("IF")
        self.casa("ABRE_PAR")
        cond = self.condicao()
        self.casa("FECHA_PAR")
        bloco_se = self.bloco()
        bloco_senao = None
        if self.atual().tipo == "ELSE":
            self.casa("ELSE")
            bloco_senao = self.bloco()
        return NoSelecao(cond, bloco_se, bloco_senao, t.linha)

    # <repeticao> ::= "while" "(" <condicao> ")" "{" <lista_comandos> "}"
    def repeticao(self) -> NoRepeticao:
        t = self.casa("WHILE")
        self.casa("ABRE_PAR")
        cond = self.condicao()
        self.casa("FECHA_PAR")
        bloco = self.bloco()
        return NoRepeticao(cond, bloco, t.linha)

    # <retorno> ::= "return" <expressao> ";"
    def retorno(self) -> NoRetorno:
        t = self.casa("RETURN")
        expr = self.expressao()
        self.casa("PONTO_VIRG")
        return NoRetorno(expr, t.linha)

    # <chamada> ::= <id> "(" [ <argumentos> ] ")"
    def chamada(self) -> NoChamada:
        nome = self.casa("ID")
        self.casa("ABRE_PAR")
        args = []
        if self.atual().tipo != "FECHA_PAR":
            args.append(self.expressao())
            while self.atual().tipo == "VIRGULA":
                self.casa("VIRGULA")
                args.append(self.expressao())
        self.casa("FECHA_PAR")
        return NoChamada(nome.lexema, args, nome.linha)

    # <condicao> ::= <condicao> "&&" <cond_simples>
    #              | <condicao> "||" <cond_simples> | <cond_simples>
    def condicao(self):
        esq = self.cond_simples()
        while self.atual().tipo in ("E", "OU"):
            op = self.casa("E", "OU")
            dire = self.cond_simples()
            esq = NoBinaria(op.lexema, esq, dire, op.linha)
        return esq

    # <cond_simples> ::= <expressao> <op_rel> <expressao>
    #                   | "(" <condicao> ")"
    def cond_simples(self):
        abre_par = self.atual().tipo == "ABRE_PAR"
        if abre_par and self._tentar_condicao_parentizada():
            self.casa("ABRE_PAR")
            no = self.condicao()
            self.casa("FECHA_PAR")
            return no
        esq = self.expressao()
        op = self.casa("IGUAL", "DIF", "MENOR", "MAIOR",
                        "MENOR_IGUAL", "MAIOR_IGUAL")
        dire = self.expressao()
        return NoBinaria(op.lexema, esq, dire, op.linha)

    def _tentar_condicao_parentizada(self):
        """Tenta casar '(' <condicao> ')' a partir da posição atual,
        sem efeito colateral: sempre restaura self.pos antes de sair.
        True  = deu certo -> cond_simples() refaz esse caminho "pra valer".
        False = não é esse caso -> cond_simples() segue para <expressao>."""
        pos_salva = self.pos
        try:
            self.casa("ABRE_PAR")
            self.condicao()
            self.casa("FECHA_PAR")
            return True
        except ErroSintatico:
            return False
        finally:
            self.pos = pos_salva

    # <expressao> ::= <expressao> ("+"|"-") <termo> | <termo>
    def expressao(self):
        no = self.termo()
        while self.atual().tipo in OPS_ADITIVOS:
            op = self.casa(*OPS_ADITIVOS)
            dire = self.termo()
            no = NoBinaria(op.lexema, no, dire, op.linha)
        return no

    # <termo> ::= <termo> ("*"|"/") <fator> | <fator>
    def termo(self):
        no = self.fator()
        while self.atual().tipo in OPS_MULTIPLICATIVOS:
            op = self.casa(*OPS_MULTIPLICATIVOS)
            dire = self.fator()
            no = NoBinaria(op.lexema, no, dire, op.linha)
        return no

    # <fator> ::= <rolagem> | <numero> | <chamada> | <id> | "(" <expressao> ")"
    def fator(self):
        t = self.atual()
        if t.tipo == "ROLAGEM":
            self.casa("ROLAGEM")
            qtd, faces = t.lexema.split("d")
            return NoRolagem(int(qtd), int(faces), t.linha)
        if t.tipo == "NUMERO":
            self.casa("NUMERO")
            return NoNumero(int(t.lexema), t.linha)
        if t.tipo == "ID":
            if self.olhar(1).tipo == "ABRE_PAR":
                return self.chamada()
            self.casa("ID")
            return NoId(t.lexema, t.linha)
        if t.tipo == "ABRE_PAR":
            self.casa("ABRE_PAR")
            no = self.expressao()
            self.casa("FECHA_PAR")
            return no
        raise ErroSintatico(t.linha, t.coluna,
            "fator esperado (número, rolagem, id, chamada "
            f"ou '('), encontrado {_descrever(t)}")


def parsear(fonte: str):
    """Roda o lexico e depois o sintatico.
    Retorna (ast, erros_lexicos, erro_sintatico) -- os dois ultimos
    sao None/[] quando nao houve erro correspondente."""
    tokens, erros_lex = analisar(fonte)
    if erros_lex:
        return None, erros_lex, None
    try:
        ast = Parser(tokens).programa()
        return ast, [], None
    except ErroSintatico as e:
        return None, [], e


# -- 4. Impressao indentada da AST ----------------------------------
def imprimir_ast(no, prefixo="", raiz=True):
    linhas = []
    nome = type(no).__name__
    if isinstance(no, NoPrograma):
        linhas.append(f"{nome}  ({len(no.declaracoes)} declaração(ões))")
        for i, d in enumerate(no.declaracoes):
            ultimo = i == len(no.declaracoes) - 1
            linhas += _ramo(d, "", ultimo)
    else:
        linhas.append(nome)
        linhas += _ramo(no, "", True)
    return "\n".join(linhas)


def _rotulo(no):
    """Uma linha resumindo o no (sem os filhos)."""
    if isinstance(no, NoFuncao):
        return f"NoFuncao  func {no.nome}({', '.join(no.parametros)})  [linha {no.linha}]"
    if isinstance(no, NoAtribuicao):
        return f"NoAtribuicao  {no.alvo} =  [linha {no.linha}]"
    if isinstance(no, NoImpressao):
        return f"NoImpressao  print(...)  [linha {no.linha}]"
    if isinstance(no, NoSelecao):
        tem_else = " + else" if no.bloco_senao is not None else ""
        return f"NoSelecao  if (...){tem_else}  [linha {no.linha}]"
    if isinstance(no, NoRepeticao):
        return f"NoRepeticao  while (...)  [linha {no.linha}]"
    if isinstance(no, NoRetorno):
        return f"NoRetorno  return  [linha {no.linha}]"
    if isinstance(no, NoChamada):
        return f"NoChamada  {no.nome}(...)  [linha {no.linha}]"
    if isinstance(no, NoBinaria):
        return f"NoBinaria  '{no.op}'  [linha {no.linha}]"
    if isinstance(no, NoRolagem):
        return f"NoRolagem  {no.qtd}d{no.faces}  [linha {no.linha}]"
    if isinstance(no, NoNumero):
        return f"NoNumero  {no.valor}  [linha {no.linha}]"
    if isinstance(no, NoId):
        return f"NoId  {no.nome}  [linha {no.linha}]"
    return repr(no)


def _filhos(no):
    """Lista de (rotulo_da_aresta, no_filho) para cada no."""
    if isinstance(no, NoFuncao):
        return [(f"corpo[{i}]", c) for i, c in enumerate(no.corpo)]
    if isinstance(no, NoAtribuicao):
        return [("expr", no.expr)]
    if isinstance(no, NoImpressao):
        return [("expr", no.expr)]
    if isinstance(no, NoSelecao):
        filhos = [("cond", no.cond)]
        filhos += [(f"se[{i}]", c) for i, c in enumerate(no.bloco_se)]
        if no.bloco_senao is not None:
            filhos += [(f"senao[{i}]", c) for i, c in enumerate(no.bloco_senao)]
        return filhos
    if isinstance(no, NoRepeticao):
        return [("cond", no.cond)] + [(f"corpo[{i}]", c) for i, c in enumerate(no.bloco)]
    if isinstance(no, NoRetorno):
        return [("expr", no.expr)]
    if isinstance(no, NoChamada):
        return [(f"arg[{i}]", a) for i, a in enumerate(no.argumentos)]
    if isinstance(no, NoBinaria):
        return [("esq", no.esq), ("dir", no.dire)]
    return []  # NoRolagem, NoNumero, NoId: folhas


def _ramo(no, prefixo, ultimo):
    conector = "└── " if ultimo else "├── "
    linhas = [f"{prefixo}{conector}{_rotulo(no)}"]
    novo_prefixo = prefixo + ("    " if ultimo else "│   ")
    filhos = _filhos(no)
    for i, (rotulo_aresta, filho) in enumerate(filhos):
        e_ultimo = i == len(filhos) - 1
        conector_f = "└── " if e_ultimo else "├── "
        linhas.append(f"{novo_prefixo}{conector_f}[{rotulo_aresta}] {_rotulo(filho)}")
        sub_prefixo = novo_prefixo + ("    " if e_ultimo else "│   ")
        for j, (sub_rotulo, sub_filho) in enumerate(_filhos(filho)):
            sub_ultimo = j == len(_filhos(filho)) - 1
            linhas += _ramo_rec(sub_filho, sub_prefixo, sub_ultimo, sub_rotulo)
    return linhas


def _ramo_rec(no, prefixo, ultimo, rotulo_aresta):
    conector = "└── " if ultimo else "├── "
    linhas = [f"{prefixo}{conector}[{rotulo_aresta}] {_rotulo(no)}"]
    novo_prefixo = prefixo + ("    " if ultimo else "│   ")
    filhos = _filhos(no)
    for i, (r, f) in enumerate(filhos):
        e_ultimo = i == len(filhos) - 1
        linhas += _ramo_rec(f, novo_prefixo, e_ultimo, r)
    return linhas


# -- 5. Programa principal ------------------------------------------
def main():
    if len(sys.argv) > 2:
        print("uso: python parser.py [arquivo.dice]", file=sys.stderr)
        return 2
    if len(sys.argv) == 2:
        with open(sys.argv[1], encoding="utf-8") as arquivo:
            fonte = arquivo.read()
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

    print(imprimir_ast(ast))
    print(f"\nPrograma sintaticamente válido: {len(ast.declaracoes)} "
          f"declaração(ões) de nível superior.")
    return 0


if __name__ == "__main__":
    sys.exit(main())