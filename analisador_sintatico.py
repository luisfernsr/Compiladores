from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

from analisador_lexico import Token, analisar_arquivo


TIPOS_PRIMITIVOS = {"int", "float", "char", "string", "bool", "void"}
OPERADORES_ATRIBUICAO = {"=", "+=", "-=", "*=", "/=", "%="}
OPERADORES_OU = {"||", "or"}
OPERADORES_E = {"&&", "and"}
OPERADORES_IGUALDADE = {"==", "!="}
OPERADORES_COMPARACAO = {"<", ">", "<=", ">="}
OPERADORES_TERMO = {"+", "-"}
OPERADORES_FATOR = {"*", "/", "%"}
OPERADORES_UNARIOS = {"!", "-", "+", "not", "++", "--"}
LITERAIS_BOOLEANOS = {"true", "false"}


@dataclass
class ErroSintatico(Exception):
    mensagem: str
    linha: int
    coluna: int

    def __str__(self) -> str:
        return f"Erro sintatico na linha {self.linha}, coluna {self.coluna}: {self.mensagem}"


@dataclass
class NoArvore:
    nome: str
    filhos: list["NoArvore"] = field(default_factory=list)

    def adicionar(self, *novos_filhos: "NoArvore | None") -> "NoArvore":
        for filho in novos_filhos:
            if filho is not None:
                self.filhos.append(filho)
        return self

    def para_texto(self, nivel: int = 0) -> str:
        linhas = [f"{'  ' * nivel}{self.nome}"]
        for filho in self.filhos:
            linhas.append(filho.para_texto(nivel + 1))
        return "\n".join(linhas)


def no_token(token: Token) -> NoArvore:
    return NoArvore(f"{token.tipo}({token.lexema})")


class Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.indice = 0

    def token_atual(self) -> Token | None:
        if self.indice >= len(self.tokens):
            return None
        return self.tokens[self.indice]

    def ver_proximo(self, deslocamento: int = 1) -> Token | None:
        posicao = self.indice + deslocamento
        if posicao >= len(self.tokens):
            return None
        return self.tokens[posicao]

    def avancar(self) -> Token | None:
        token = self.token_atual()
        if token is not None:
            self.indice += 1
        return token

    def token_eh(self, *, tipo: str | None = None, lexema: str | None = None) -> bool:
        token = self.token_atual()
        if token is None:
            return False
        if tipo is not None and token.tipo != tipo:
            return False
        if lexema is not None and token.lexema != lexema:
            return False
        return True

    def consumir(self, *, tipo: str | None = None, lexema: str | None = None, esperado: str) -> Token:
        token = self.token_atual()
        if token is None:
            raise ErroSintatico(
                f"era esperado {esperado}, mas o arquivo terminou",
                self.linha_final(),
                self.coluna_final(),
            )
        if tipo is not None and token.tipo != tipo:
            raise ErroSintatico(
                f"era esperado {esperado}, mas foi encontrado {token.lexema!r}",
                token.linha,
                token.coluna,
            )
        if lexema is not None and token.lexema != lexema:
            raise ErroSintatico(
                f"era esperado {esperado}, mas foi encontrado {token.lexema!r}",
                token.linha,
                token.coluna,
            )
        self.indice += 1
        return token

    def consumir_no(self, *, tipo: str | None = None, lexema: str | None = None, esperado: str) -> NoArvore:
        return no_token(self.consumir(tipo=tipo, lexema=lexema, esperado=esperado))

    def linha_final(self) -> int:
        if not self.tokens:
            return 1
        return self.tokens[-1].linha

    def coluna_final(self) -> int:
        if not self.tokens:
            return 1
        ultimo = self.tokens[-1]
        return ultimo.coluna + len(ultimo.lexema)

    def analisar(self) -> NoArvore:
        self.validar_tokens_lexicos()
        arvore = self.programa()
        if self.token_atual() is not None:
            token = self.token_atual()
            raise ErroSintatico(
                f"token inesperado apos o fim da analise: {token.lexema!r}",
                token.linha,
                token.coluna,
            )
        return arvore

    def validar_tokens_lexicos(self) -> None:
        for token in self.tokens:
            if not token.valido:
                raise ErroSintatico(
                    f"token invalido recebido do analisador lexico: {token.mensagem}",
                    token.linha,
                    token.coluna,
                )

    def programa(self) -> NoArvore:
        raiz = NoArvore("programa")
        while self.token_atual() is not None:
            raiz.adicionar(self.declaracao_ou_comando())
        return raiz

    def declaracao_ou_comando(self) -> NoArvore:
        if self.inicio_declaracao_variavel_ou_funcao():
            return self.declaracao_variavel_ou_funcao()
        return self.comando()

    def inicio_declaracao_variavel_ou_funcao(self) -> bool:
        token = self.token_atual()
        proximo = self.ver_proximo()
        return (
            token is not None
            and token.tipo == "PALAVRA_RESERVADA"
            and token.lexema in TIPOS_PRIMITIVOS
            and proximo is not None
            and proximo.tipo == "IDENTIFICADOR"
        )

    def declaracao_variavel_ou_funcao(self) -> NoArvore:
        if self.eh_declaracao_funcao():
            return self.declaracao_funcao()
        return self.declaracao_variavel()

    def eh_declaracao_funcao(self) -> bool:
        terceiro = self.ver_proximo(2)
        return terceiro is not None and terceiro.lexema == "("

    def declaracao_funcao(self) -> NoArvore:
        return NoArvore("declaracao_funcao").adicionar(
            self.tipo(),
            self.consumir_no(tipo="IDENTIFICADOR", esperado="um identificador de funcao"),
            self.consumir_no(lexema="(", esperado="'('"),
            self.lista_parametros() if not self.token_eh(lexema=")") else NoArvore("lista_parametros_vazia"),
            self.consumir_no(lexema=")", esperado="')'"),
            self.bloco(),
        )

    def lista_parametros(self) -> NoArvore:
        no = NoArvore("lista_parametros")
        if (
            self.token_eh(tipo="PALAVRA_RESERVADA", lexema="void")
            and self.ver_proximo() is not None
            and self.ver_proximo().lexema == ")"
        ):
            no.adicionar(no_token(self.avancar()))
            return no

        no.adicionar(self.parametro())
        while self.token_eh(lexema=","):
            no.adicionar(
                self.consumir_no(lexema=",", esperado="','"),
                self.parametro(),
            )
        return no

    def parametro(self) -> NoArvore:
        return NoArvore("parametro").adicionar(
            self.tipo(),
            self.consumir_no(tipo="IDENTIFICADOR", esperado="um identificador de parametro"),
        )

    def declaracao_variavel(self) -> NoArvore:
        no = NoArvore("declaracao_variavel").adicionar(
            self.tipo(),
            self.consumir_no(tipo="IDENTIFICADOR", esperado="um identificador"),
        )
        if self.token_eh(lexema="="):
            no.adicionar(
                self.consumir_no(lexema="=", esperado="'='"),
                self.expressao(),
            )
        no.adicionar(self.consumir_no(lexema=";", esperado="';'"))
        return no

    def tipo(self) -> NoArvore:
        token = self.token_atual()
        if token is None or token.tipo != "PALAVRA_RESERVADA" or token.lexema not in TIPOS_PRIMITIVOS:
            if token is None:
                raise ErroSintatico("era esperado um tipo, mas o arquivo terminou", self.linha_final(), self.coluna_final())
            raise ErroSintatico("era esperado um tipo valido", token.linha, token.coluna)
        return no_token(self.avancar())

    def bloco(self) -> NoArvore:
        no = NoArvore("bloco").adicionar(self.consumir_no(lexema="{", esperado="'{'"))
        while self.token_atual() is not None and not self.token_eh(lexema="}"):
            no.adicionar(self.declaracao_ou_comando())
        no.adicionar(self.consumir_no(lexema="}", esperado="'}'"))
        return no

    def comando(self) -> NoArvore:
        token = self.token_atual()
        if token is None:
            raise ErroSintatico("era esperado um comando, mas o arquivo terminou", self.linha_final(), self.coluna_final())

        if token.lexema == "{":
            return self.bloco()
        if token.lexema == "if":
            return self.comando_if()
        if token.lexema == "while":
            return self.comando_while()
        if token.lexema == "return":
            return self.comando_return()
        if token.lexema == ";":
            return NoArvore("comando_vazio").adicionar(self.consumir_no(lexema=";", esperado="';'"))

        return self.comando_expressao()

    def comando_if(self) -> NoArvore:
        no = NoArvore("comando_if").adicionar(
            self.consumir_no(lexema="if", esperado="'if'"),
            self.consumir_no(lexema="(", esperado="'('"),
            self.expressao(),
            self.consumir_no(lexema=")", esperado="')'"),
            self.comando(),
        )
        if self.token_eh(lexema="else"):
            no.adicionar(
                self.consumir_no(lexema="else", esperado="'else'"),
                self.comando(),
            )
        return no

    def comando_while(self) -> NoArvore:
        return NoArvore("comando_while").adicionar(
            self.consumir_no(lexema="while", esperado="'while'"),
            self.consumir_no(lexema="(", esperado="'('"),
            self.expressao(),
            self.consumir_no(lexema=")", esperado="')'"),
            self.comando(),
        )

    def comando_return(self) -> NoArvore:
        no = NoArvore("comando_return").adicionar(
            self.consumir_no(lexema="return", esperado="'return'"),
        )
        if not self.token_eh(lexema=";"):
            no.adicionar(self.expressao())
        no.adicionar(self.consumir_no(lexema=";", esperado="';'"))
        return no

    def comando_expressao(self) -> NoArvore:
        return NoArvore("comando_expressao").adicionar(
            self.expressao(),
            self.consumir_no(lexema=";", esperado="';'"),
        )

    def expressao(self) -> NoArvore:
        return NoArvore("expressao").adicionar(self.atribuicao())

    def atribuicao(self) -> NoArvore:
        esquerda = self.ou_logico()
        if self.token_atual() is not None and self.token_atual().lexema in OPERADORES_ATRIBUICAO:
            operador = self.avancar()
            return NoArvore("atribuicao").adicionar(
                esquerda,
                no_token(operador),
                self.atribuicao(),
            )
        return esquerda

    def ou_logico(self) -> NoArvore:
        no = self.e_logico()
        while self.token_atual() is not None and self.token_atual().lexema in OPERADORES_OU:
            operador = self.avancar()
            no = NoArvore("ou_logico").adicionar(no, no_token(operador), self.e_logico())
        return no

    def e_logico(self) -> NoArvore:
        no = self.igualdade()
        while self.token_atual() is not None and self.token_atual().lexema in OPERADORES_E:
            operador = self.avancar()
            no = NoArvore("e_logico").adicionar(no, no_token(operador), self.igualdade())
        return no

    def igualdade(self) -> NoArvore:
        no = self.comparacao()
        while self.token_atual() is not None and self.token_atual().lexema in OPERADORES_IGUALDADE:
            operador = self.avancar()
            no = NoArvore("igualdade").adicionar(no, no_token(operador), self.comparacao())
        return no

    def comparacao(self) -> NoArvore:
        no = self.termo()
        while self.token_atual() is not None and self.token_atual().lexema in OPERADORES_COMPARACAO:
            operador = self.avancar()
            no = NoArvore("comparacao").adicionar(no, no_token(operador), self.termo())
        return no

    def termo(self) -> NoArvore:
        no = self.fator()
        while self.token_atual() is not None and self.token_atual().lexema in OPERADORES_TERMO:
            operador = self.avancar()
            no = NoArvore("termo").adicionar(no, no_token(operador), self.fator())
        return no

    def fator(self) -> NoArvore:
        no = self.unario()
        while self.token_atual() is not None and self.token_atual().lexema in OPERADORES_FATOR:
            operador = self.avancar()
            no = NoArvore("fator").adicionar(no, no_token(operador), self.unario())
        return no

    def unario(self) -> NoArvore:
        if self.token_atual() is not None and self.token_atual().lexema in OPERADORES_UNARIOS:
            operador = self.avancar()
            return NoArvore("unario").adicionar(no_token(operador), self.unario())
        return self.primario()

    def primario(self) -> NoArvore:
        token = self.token_atual()
        if token is None:
            raise ErroSintatico("era esperada uma expressao, mas o arquivo terminou", self.linha_final(), self.coluna_final())

        if token.lexema == "(":
            return NoArvore("agrupamento").adicionar(
                self.consumir_no(lexema="(", esperado="'('"),
                self.expressao(),
                self.consumir_no(lexema=")", esperado="')'"),
            )

        if token.tipo in {"NUMERO_INTEIRO", "NUMERO_REAL", "STRING", "CARACTERE"}:
            return NoArvore("literal").adicionar(no_token(self.avancar()))

        if token.tipo == "PALAVRA_RESERVADA" and token.lexema in LITERAIS_BOOLEANOS:
            return NoArvore("literal_booleano").adicionar(no_token(self.avancar()))

        if token.tipo == "IDENTIFICADOR":
            identificador = no_token(self.avancar())
            if self.token_eh(lexema="("):
                no = NoArvore("chamada_funcao").adicionar(
                    identificador,
                    self.consumir_no(lexema="(", esperado="'('"),
                )
                if not self.token_eh(lexema=")"):
                    no.adicionar(self.lista_argumentos())
                no.adicionar(self.consumir_no(lexema=")", esperado="')'"))
                return no
            return NoArvore("identificador").adicionar(identificador)

        raise ErroSintatico(
            f"token inesperado em expressao: {token.lexema!r}",
            token.linha,
            token.coluna,
        )

    def lista_argumentos(self) -> NoArvore:
        no = NoArvore("lista_argumentos").adicionar(self.expressao())
        while self.token_eh(lexema=","):
            no.adicionar(
                self.consumir_no(lexema=",", esperado="','"),
                self.expressao(),
            )
        return no


def salvar_arvore(arvore: NoArvore, caminho_saida: Path) -> None:
    caminho_saida.write_text(arvore.para_texto() + "\n", encoding="utf-8")


def analisar_sintaxe(caminho_arquivo: Path) -> NoArvore:
    tokens = analisar_arquivo(caminho_arquivo)
    parser = Parser(tokens)
    return parser.analisar()


def main() -> int:
    caminho_entrada = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("entrada.txt")
    caminho_saida = Path(sys.argv[2]) if len(sys.argv) > 2 else caminho_entrada.with_name("arvore_sintatica.txt")

    if not caminho_entrada.exists():
        print(
            f"Arquivo de entrada nao encontrado: {caminho_entrada}\n"
            "Uso: python analisador_sintatico.py caminho_do_arquivo.txt caminho_da_arvore.txt"
        )
        return 1

    try:
        arvore = analisar_sintaxe(caminho_entrada)
        salvar_arvore(arvore, caminho_saida)
    except ErroSintatico as erro:
        print(str(erro))
        return 1

    print("Analise sintatica concluida com sucesso.")
    print(f"Arvore sintatica salva em: {caminho_saida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
