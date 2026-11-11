#!/usr/bin/env python3
"""
Interpretador para DiceLang.
Avalia a Árvore Sintática Abstrata (AST) e executa o código-fonte.
"""
import random
import sys
from typing import Dict, List, Any
from Parser import (
    No, NoPrograma, NoFuncao, NoAtribuicao, NoImpressao,
    NoSelecao, NoRepeticao, NoRetorno, NoChamada, NoBinaria,
    NoRolagem, NoNumero, NoId
)


class RetornoExcecao(Exception):
    """Exceção de controle de fluxo usada para interromper a execução de uma função e retornar um valor."""
    def __init__(self, valor: Any):
        self.valor = valor


class Interpretador:
    def __init__(self):
        # Mapeamento de funções declaradas: nome -> NoFuncao
        self.funcoes: Dict[str, NoFuncao] = {}
        
        # Escopo global de variáveis
        self.escopo_global: Dict[str, Any] = {}
        
        # Pilha de escopos locais (para chamadas de funções)
        self.escopos_locais: List[Dict[str, Any]] = []

    def executar(self, no_programa: NoPrograma):
        """Ponto de entrada: registra funções e executa as declarações de nível superior."""
        # Passagem 1: Mapear todas as funções declaradas
        for decl in no_programa.declaracoes:
            if isinstance(decl, NoFuncao):
                self.funcoes[decl.nome] = decl

        # Passagem 2: Executar declarações e comandos
        self.visitar(no_programa)

    def visitar(self, no: No) -> Any:
        metodo_nome = f"visitar_{type(no).__name__}"
        metodo = getattr(self, metodo_nome, self.generico)
        return metodo(no)

    def generico(self, no: No):
        raise NotImplementedError(f"Método visitar_{type(no).__name__} não implementado no interpretador.")

    def _obter_variavel(self, nome: str) -> Any:
        """Obtém o valor de uma variável buscando no escopo local atual e depois no global."""
        if self.escopos_locais and nome in self.escopos_locais[-1]:
            return self.escopos_locais[-1][nome]
        if nome in self.escopo_global:
            return self.escopo_global[nome]
        raise RuntimeError(f"Variável não definida em tempo de execução: '{nome}'")

    def _definir_variavel(self, nome: str, valor: Any):
        """Define o valor de uma variável no escopo atual."""
        if self.escopos_locais:
            self.escopos_locais[-1][nome] = valor
        else:
            self.escopo_global[nome] = valor

    # --- Visitantes de Estrutura ---

    def visitar_NoPrograma(self, no: NoPrograma):
        for decl in no.declaracoes:
            # Executa apenas comandos no nível global (funções já foram mapeadas)
            if not isinstance(decl, NoFuncao):
                self.visitar(decl)

    def visitar_NoFuncao(self, no: NoFuncao):
        # Declarações de função são ignoradas durante o fluxo normal
        pass

    def visitar_NoAtribuicao(self, no: NoAtribuicao):
        valor = self.visitar(no.expr)
        self._definir_variavel(no.alvo, valor)

    def visitar_NoImpressao(self, no: NoImpressao):
        valor = self.visitar(no.expr)
        print(valor)

    def visitar_NoSelecao(self, no: NoSelecao):
        condicao = self.visitar(no.cond)
        if condicao:
            for cmd in no.bloco_se:
                self.visitar(cmd)
        elif no.bloco_senao:
            for cmd in no.bloco_senao:
                self.visitar(cmd)

    def visitar_NoRepeticao(self, no: NoRepeticao):
        while self.visitar(no.cond):
            for cmd in no.bloco:
                self.visitar(cmd)

    def visitar_NoRetorno(self, no: NoRetorno):
        valor = self.visitar(no.expr)
        raise RetornoExcecao(valor)

    def visitar_NoChamada(self, no: NoChamada) -> Any:
        no_func = self.funcoes[no.nome]
        
        # Avaliar os argumentos passados
        valores_args = [self.visitar(arg) for arg in no.argumentos]

        # Criar novo escopo local mapeando parâmetros aos valores
        escopo_local = dict(zip(no_func.parametros, valores_args))
        self.escopos_locais.append(escopo_local)

        valor_retorno = 0  # Retorno padrão caso a função não tenha return
        try:
            for cmd in no_func.corpo:
                self.visitar(cmd)
        except RetornoExcecao as ret:
            valor_retorno = ret.valor
        finally:
            self.escopos_locais.pop()

        return valor_retorno

    # --- Visitantes de Expressões e Valores ---

    def visitar_NoBinaria(self, no: NoBinaria) -> Any:
        esq = self.visitar(no.esq)
        dire = self.visitar(no.dire)

        if no.op == "+":
            return esq + dire
        if no.op == "-":
            return esq - dire
        if no.op == "*":
            return esq * dire
        if no.op == "/":
            return esq // dire  # Divisão inteira
        if no.op == "==":
            return 1 if esq == dire else 0
        if no.op == "!=":
            return 1 if esq != dire else 0
        if no.op == "<":
            return 1 if esq < dire else 0
        if no.op == ">":
            return 1 if esq > dire else 0
        if no.op == "<=":
            return 1 if esq <= dire else 0
        if no.op == ">=":
            return 1 if esq >= dire else 0
        if no.op == "&&":
            return 1 if (esq and dire) else 0
        if no.op == "||":
            return 1 if (esq or dire) else 0

        raise RuntimeError(f"Operador desconhecido: {no.op}")

    def visitar_NoRolagem(self, no: NoRolagem) -> int:
        """Sorteia `qtd` dados de `faces` lados cada e retorna a soma."""
        return sum(random.randint(1, no.faces) for _ in range(no.qtd))

    def visitar_NoId(self, no: NoId) -> Any:
        return self._obter_variavel(no.nome)

    def visitar_NoNumero(self, no: NoNumero) -> int:
        return no.valor


def executar_programa(ast: NoPrograma):
    interpretador = Interpretador()
    interpretador.executar(ast)


def main():
    from Parser import parsear
    from semantic import analisar_semantica, ErroSemantico

    if len(sys.argv) > 2:
        print("uso: python interpreter.py [arquivo.dice]", file=sys.stderr)
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
    except ErroSemantico as e:
        print(str(e), file=sys.stderr)
        return 1

    # Executa a AST caso todas as etapas anteriores passem
    executar_programa(ast)
    return 0


if __name__ == "__main__":
    sys.exit(main())