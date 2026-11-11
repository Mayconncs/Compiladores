#!/usr/bin/env python3
"""
Analisador Semântico para DiceLang.
Verifica escopos de variáveis, declarações de funções e regras de validação.
"""
import sys
from typing import Dict, Set, List
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
        # Escopo global e pilha para escopos locais (funções)
        self.escopo_global: Set[str] = set()
        self.escopos_locais: List[Set[str]] = []
        
        # Mapeamento de funções: nome -> quantidade de parâmetros (aridade)
        self.funcoes: Dict[str, int] = {}
        
        # Flag para controlar se o analisador está dentro de uma função
        self.em_funcao = False

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

    def _variavel_declarada(self, nome: str) -> bool:
        """Verifica se a variável existe em qualquer escopo local (da pilha) ou no global."""
        for escopo in reversed(self.escopos_locais):
            if nome in escopo:
                return True
        return nome in self.escopo_global

    def _declarar_variavel(self, nome: str):
        """Registra a variável no escopo local atual (topo da pilha) ou no global."""
        if self.escopos_locais:
            self.escopos_locais[-1].add(nome)
        else:
            self.escopo_global.add(nome)

    # --- Visitantes de Estrutura Principais ---

    def visitar_NoPrograma(self, no: NoPrograma):
        for decl in no.declaracoes:
            self.visitar(decl)

    def visitar_NoFuncao(self, no: NoFuncao):
        self.em_funcao = True
        
        # Cria um novo escopo local contendo os parâmetros
        escopo_local = set(no.parametros)
        if len(no.parametros) != len(escopo_local):
            raise ErroSemantico(no.linha, f"Parâmetros duplicados na função '{no.nome}'.")

        self.escopos_locais.append(escopo_local)

        # Processa cada comando do corpo da função
        for cmd in no.corpo:
            self.visitar(cmd)

        # Destrói o escopo local ao sair da função
        self.escopos_locais.pop()
        self.em_funcao = False

    def visitar_NoAtribuicao(self, no: NoAtribuicao):
        # Analisa a expressão antes de declarar a variável alvo (evita usar x em x = x + 1 se x não existia)
        self.visitar(no.expr)
        self._declarar_variavel(no.alvo)

    def visitar_NoImpressao(self, no: NoImpressao):
        self.visitar(no.expr)

    def visitar_NoSelecao(self, no: NoSelecao):
        self.visitar(no.cond)
        for cmd in no.bloco_se:
            self.visitar(cmd)
        if no.bloco_senao:
            for cmd in no.bloco_senao:
                self.visitar(cmd)

    def visitar_NoRepeticao(self, no: NoRepeticao):
        self.visitar(no.cond)
        for cmd in no.bloco:
            self.visitar(cmd)

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

    # --- Visitantes de Expressões e Valores ---

    def visitar_NoBinaria(self, no: NoBinaria):
        self.visitar(no.esq)
        self.visitar(no.dire)

        # Prevenção de divisão por zero literal
        if no.op == "/" and isinstance(no.dire, NoNumero) and no.dire.valor == 0:
            raise ErroSemantico(no.linha, "Divisão por zero constante identificada.")

    def visitar_NoRolagem(self, no: NoRolagem):
        if no.qtd <= 0:
            raise ErroSemantico(no.linha, f"Quantidade de dados inválida ({no.qtd}). Deve ser > 0.")
        if no.faces <= 0:
            raise ErroSemantico(no.linha, f"Número de faces inválido ({no.faces}). Deve ser > 0.")

    def visitar_NoId(self, no: NoId):
        if not self._variavel_declarada(no.nome):
            raise ErroSemantico(no.linha, f"Variável '{no.nome}' usada antes da atribuição/declaração.")

    def visitar_NoNumero(self, no: NoNumero):
        pass


# --- Função Auxiliar de Integração ---

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