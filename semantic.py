#!/usr/bin/env python3
"""
Analisador Semântico para DiceLang.
Verifica escopos de variáveis, declarações de funções e regras de validação.
"""
import sys
from typing import Dict, Optional, Set, List
from Parser import (
    No, NoPrograma, NoFuncao, NoAtribuicao, NoImpressao,
    NoSelecao, NoRepeticao, NoRetorno, NoChamada, NoBinaria,
    NoRolagem, NoNumero, NoId
)


class ErroSemantico(Exception):
    def __init__(self, linha: int, msg: str):
        super().__init__(f"Erro semântico (linha {linha}): {msg}")
        self.linha = linha
        self.msg = msg


class AnalisadorSemantico:
    def __init__(self):
        self.escopo_global: Set[str] = set()
        self.escopos_locais: List[Set[str]] = []

        self.funcoes: Dict[str, int] = {}

        self.em_funcao = False

        self.condicionais: Set[str] = set()

        self.atribuidos_func: Set[str] = set()

    def analisar(self, no_programa: NoPrograma):
        """Ponto de entrada: realiza duas etapas na AST."""
        # 1ª Passagem: Registrar todas as funções declaradas
        for decl in no_programa.declaracoes:
            if isinstance(decl, NoFuncao):
                if decl.nome in self.funcoes:
                    raise ErroSemantico(decl.linha, f"Função '{decl.nome}' já foi declarada.")
                self.funcoes[decl.nome] = len(decl.parametros)

        # 2ª Passagem: Validar comandos, escopos e expressões
        self.visitar(no_programa)

    def visitar(self, no: No):
        metodo_nome = f"visitar_{type(no).__name__}"
        metodo = getattr(self, metodo_nome, self.generico)
        return metodo(no)

    def generico(self, no: No):
        raise NotImplementedError(f"Método visitar_{type(no).__name__} não implementado.")

    def _escopo_atual(self) -> Set[str]:
        return self.escopos_locais[-1] if self.escopos_locais else self.escopo_global

    def _variavel_declarada(self, nome: str) -> bool:
        for escopo in reversed(self.escopos_locais):
            if nome in escopo:
                return True
        return nome in self.escopo_global

    def _declarar_variavel(self, nome: str):
        self._escopo_atual().add(nome)

    def _visitar_bloco(self, comandos: list) -> Set[str]:
        escopo = self._escopo_atual()
        antes = set(escopo)
        for cmd in comandos:
            self.visitar(cmd)
        novas = escopo - antes
        escopo -= novas
        return novas

    def _valor_constante(self, no: No) -> Optional[int]:
        if isinstance(no, NoNumero):
            return no.valor
        if isinstance(no, NoBinaria) and no.op in ("+", "-", "*", "/"):
            esq = self._valor_constante(no.esq)
            dire = self._valor_constante(no.dire)
            if esq is None or dire is None:
                return None
            if no.op == "+":
                return esq + dire
            if no.op == "-":
                return esq - dire
            if no.op == "*":
                return esq * dire
            return esq // dire if dire != 0 else None
        return None

    def _atribuidos(self, comandos: list) -> Set[str]:
        nomes = set()
        for cmd in comandos:
            if isinstance(cmd, NoAtribuicao):
                nomes.add(cmd.alvo)
            elif isinstance(cmd, NoSelecao):
                nomes |= self._atribuidos(cmd.bloco_se)
                nomes |= self._atribuidos(cmd.bloco_senao or [])
            elif isinstance(cmd, NoRepeticao):
                nomes |= self._atribuidos(cmd.bloco)
        return nomes


    def visitar_NoPrograma(self, no: NoPrograma):
        for decl in no.declaracoes:
            self.visitar(decl)

    def visitar_NoFuncao(self, no: NoFuncao):
        escopo_local = set(no.parametros)
        if len(no.parametros) != len(escopo_local):
            raise ErroSemantico(no.linha, f"Parâmetros duplicados na função '{no.nome}'.")

        for p in no.parametros:
            if p in self.funcoes:
                raise ErroSemantico(no.linha, f"Parâmetro '{p}' tem o mesmo nome de uma função.")

        self.em_funcao = True
        self.atribuidos_func = self._atribuidos(no.corpo)
        self.escopos_locais.append(escopo_local)
        condicionais_externos = self.condicionais
        self.condicionais = set()

        for cmd in no.corpo:
            self.visitar(cmd)

        self.condicionais = condicionais_externos
        self.escopos_locais.pop()
        self.em_funcao = False

    def visitar_NoAtribuicao(self, no: NoAtribuicao):
        self.visitar(no.expr)
        if no.alvo in self.funcoes:
            raise ErroSemantico(no.linha, f"'{no.alvo}' já é nome de uma função e não pode ser variável.")
        self._declarar_variavel(no.alvo)

    def visitar_NoImpressao(self, no: NoImpressao):
        self.visitar(no.expr)

    def visitar_NoSelecao(self, no: NoSelecao):
        self.visitar(no.cond)
        novas_se = self._visitar_bloco(no.bloco_se)
        novas_senao = self._visitar_bloco(no.bloco_senao) if no.bloco_senao else set()

        garantidas = novas_se & novas_senao
        self._escopo_atual().update(garantidas)
        self.condicionais |= (novas_se | novas_senao) - garantidas

    def visitar_NoRepeticao(self, no: NoRepeticao):
        self.visitar(no.cond)
        novas = self._visitar_bloco(no.bloco)
        self.condicionais |= novas

    def visitar_NoRetorno(self, no: NoRetorno):
        if not self.em_funcao:
            raise ErroSemantico(no.linha, "'return' utilizado fora do corpo de uma função.")
        self.visitar(no.expr)

    def visitar_NoChamada(self, no: NoChamada):
        if no.nome not in self.funcoes:
            raise ErroSemantico(no.linha, f"Função '{no.nome}' não declarada.")

        aridade_esperada = self.funcoes[no.nome]
        aridade_fornecida = len(no.argumentos)

        if aridade_esperada != aridade_fornecida:
            raise ErroSemantico(
                no.linha,
                f"Função '{no.nome}' esperava {aridade_esperada} argumento(s), "
                f"mas recebeu {aridade_fornecida}."
            )

        for arg in no.argumentos:
            self.visitar(arg)


    def visitar_NoBinaria(self, no: NoBinaria):
        self.visitar(no.esq)
        self.visitar(no.dire)

        if no.op == "/" and self._valor_constante(no.dire) == 0:
            raise ErroSemantico(no.linha, "Divisão por zero constante identificada.")

    def visitar_NoRolagem(self, no: NoRolagem):
        if no.qtd <= 0:
            raise ErroSemantico(no.linha, f"Quantidade de dados inválida ({no.qtd}). Deve ser > 0.")
        if no.faces <= 0:
            raise ErroSemantico(no.linha, f"Número de faces inválido ({no.faces}). Deve ser > 0.")

    def visitar_NoId(self, no: NoId):
        if (self.em_funcao and no.nome in self.atribuidos_func
                and no.nome not in self._escopo_atual()):
            raise ErroSemantico(
                no.linha,
                f"Variável '{no.nome}' é atribuída nesta função e é usada antes de ter valor local."
            )
        if not self._variavel_declarada(no.nome):
            if no.nome in self.condicionais:
                raise ErroSemantico(
                    no.linha,
                    f"Variável '{no.nome}' pode não estar definida: "
                    "ela só é atribuída dentro de um if/while."
                )
            raise ErroSemantico(no.linha, f"Variável '{no.nome}' usada antes da atribuição/declaração.")

    def visitar_NoNumero(self, no: NoNumero):
        pass



def analisar_semantica(ast: NoPrograma):
    analisador = AnalisadorSemantico()
    analisador.analisar(ast)


def main():
    from Parser import parsear

    if len(sys.argv) > 2:
        print("uso: python semantic.py [arquivo.dice]", file=sys.stderr)
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

    try:
        analisar_semantica(ast)
        print("Programa semanticamente válido.")
        return 0
    except ErroSemantico as e:
        print(str(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())