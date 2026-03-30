from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path


RESERVED_WORDS = {
    "if",
    "else",
    "while",
    "for",
    "return",
    "int",
    "float",
    "char",
    "void",
    "string",
    "bool",
    "true",
    "false",
    "break",
    "continue",
    "class",
    "public",
    "private",
    "static",
    "def",
    "and",
    "or",
    "not",
}

DOUBLE_OPERATORS = {
    "==",
    "!=",
    "<=",
    ">=",
    "&&",
    "||",
    "++",
    "--",
    "+=",
    "-=",
    "*=",
    "/=",
    "%=",
    "->",
}

SINGLE_OPERATORS = {
    "+",
    "-",
    "*",
    "/",
    "%",
    "=",
    "<",
    ">",
    "!",
    "&",
    "|",
    "^",
}

DELIMITERS = {
    "(",
    ")",
    "{",
    "}",
    "[",
    "]",
    ";",
    ",",
    ".",
    ":",
}


@dataclass
class Token:
    tipo: str
    lexema: str
    linha: int
    coluna: int
    valido: bool = True
    mensagem: str = ""

    def formatar(self) -> str:
        status = "VALIDO" if self.valido else "INVALIDO"
        base = (
            f"{status} | tipo={self.tipo} | lexema={self.lexema!r} "
            f"| linha={self.linha} | coluna={self.coluna}"
        )
        if self.mensagem:
            return f"{base} | detalhe={self.mensagem}"
        return base


class Lexer:
    def __init__(self, fonte: str) -> None:
        self.fonte = fonte
        self.tamanho = len(fonte)
        self.indice = 0
        self.linha = 1
        self.coluna = 1

    def caractere_atual(self) -> str | None:
        if self.indice >= self.tamanho:
            return None
        return self.fonte[self.indice]

    def espiar(self, deslocamento: int = 1) -> str | None:
        posicao = self.indice + deslocamento
        if posicao >= self.tamanho:
            return None
        return self.fonte[posicao]

    def avancar(self) -> str | None:
        caractere = self.caractere_atual()
        if caractere is None:
            return None

        self.indice += 1
        if caractere == "\n":
            self.linha += 1
            self.coluna = 1
        else:
            self.coluna += 1
        return caractere

    def ignorar_espacos_e_comentarios(self, tokens: list[Token]) -> None:
        while True:
            caractere = self.caractere_atual()

            if caractere is None:
                return

            if caractere in {" ", "\t", "\r", "\n"}:
                self.avancar()
                continue

            if caractere == "/" and self.espiar() == "/":
                while self.caractere_atual() not in {None, "\n"}:
                    self.avancar()
                continue

            if caractere == "/" and self.espiar() == "*":
                linha_inicial = self.linha
                coluna_inicial = self.coluna
                self.avancar()
                self.avancar()

                while True:
                    atual = self.caractere_atual()
                    if atual is None:
                        tokens.append(
                            Token(
                                tipo="COMENTARIO_BLOCO_NAO_FECHADO",
                                lexema="/*",
                                linha=linha_inicial,
                                coluna=coluna_inicial,
                                valido=False,
                                mensagem="comentario de bloco nao foi fechado",
                            )
                        )
                        return
                    if atual == "*" and self.espiar() == "/":
                        self.avancar()
                        self.avancar()
                        break
                    self.avancar()
                continue

            return

    def coletar_identificador_ou_palavra_reservada(self) -> Token:
        linha_inicial = self.linha
        coluna_inicial = self.coluna
        lexema = []

        while True:
            caractere = self.caractere_atual()
            if caractere is None or not (caractere.isalnum() or caractere == "_"):
                break
            lexema.append(self.avancar())

        texto = "".join(lexema)
        tipo = "PALAVRA_RESERVADA" if texto in RESERVED_WORDS else "IDENTIFICADOR"
        return Token(tipo=tipo, lexema=texto, linha=linha_inicial, coluna=coluna_inicial)

    def coletar_numero(self) -> Token:
        linha_inicial = self.linha
        coluna_inicial = self.coluna
        lexema = []
        tem_ponto = False

        while True:
            caractere = self.caractere_atual()
            if caractere is None:
                break

            if caractere.isdigit():
                lexema.append(self.avancar())
                continue

            if caractere == "." and not tem_ponto and (self.espiar() or "").isdigit():
                tem_ponto = True
                lexema.append(self.avancar())
                continue

            break

        texto = "".join(lexema)
        tipo = "NUMERO_REAL" if tem_ponto else "NUMERO_INTEIRO"
        return Token(tipo=tipo, lexema=texto, linha=linha_inicial, coluna=coluna_inicial)

    def coletar_string(self) -> Token:
        linha_inicial = self.linha
        coluna_inicial = self.coluna
        lexema = [self.avancar()]
        escapado = False

        while True:
            caractere = self.caractere_atual()
            if caractere is None or caractere == "\n":
                return Token(
                    tipo="STRING_MAL_FORMADA",
                    lexema="".join(lexema),
                    linha=linha_inicial,
                    coluna=coluna_inicial,
                    valido=False,
                    mensagem="cadeia de caracteres nao foi fechada",
                )

            lexema.append(self.avancar())

            if escapado:
                escapado = False
                continue

            if caractere == "\\":
                escapado = True
                continue

            if caractere == '"':
                return Token(
                    tipo="STRING",
                    lexema="".join(lexema),
                    linha=linha_inicial,
                    coluna=coluna_inicial,
                )

    def coletar_literal_caractere(self) -> Token:
        linha_inicial = self.linha
        coluna_inicial = self.coluna
        lexema = [self.avancar()]
        escapado = False

        while True:
            caractere = self.caractere_atual()
            if caractere is None or caractere == "\n":
                return Token(
                    tipo="CARACTERE_MAL_FORMADO",
                    lexema="".join(lexema),
                    linha=linha_inicial,
                    coluna=coluna_inicial,
                    valido=False,
                    mensagem="literal de caractere nao foi fechado",
                )

            lexema.append(self.avancar())

            if escapado:
                escapado = False
                continue

            if caractere == "\\":
                escapado = True
                continue

            if caractere == "'":
                texto = "".join(lexema)
                conteudo = texto[1:-1]
                if len(conteudo) == 1 or (conteudo.startswith("\\") and len(conteudo) == 2):
                    return Token(
                        tipo="CARACTERE",
                        lexema=texto,
                        linha=linha_inicial,
                        coluna=coluna_inicial,
                    )
                return Token(
                    tipo="CARACTERE_MAL_FORMADO",
                    lexema=texto,
                    linha=linha_inicial,
                    coluna=coluna_inicial,
                    valido=False,
                    mensagem="literal de caractere deve conter um unico caractere",
                )

    def proximo_token(self) -> Token | None:
        caractere = self.caractere_atual()
        if caractere is None:
            return None

        if caractere.isalpha() or caractere == "_":
            return self.coletar_identificador_ou_palavra_reservada()

        if caractere.isdigit():
            return self.coletar_numero()

        if caractere == '"':
            return self.coletar_string()

        if caractere == "'":
            return self.coletar_literal_caractere()

        linha_inicial = self.linha
        coluna_inicial = self.coluna

        par = (caractere or "") + (self.espiar() or "")
        if par in DOUBLE_OPERATORS:
            self.avancar()
            self.avancar()
            return Token(
                tipo="OPERADOR",
                lexema=par,
                linha=linha_inicial,
                coluna=coluna_inicial,
            )

        if caractere in SINGLE_OPERATORS:
            self.avancar()
            return Token(
                tipo="OPERADOR",
                lexema=caractere,
                linha=linha_inicial,
                coluna=coluna_inicial,
            )

        if caractere in DELIMITERS:
            self.avancar()
            return Token(
                tipo="DELIMITADOR",
                lexema=caractere,
                linha=linha_inicial,
                coluna=coluna_inicial,
            )

        self.avancar()
        return Token(
            tipo="TOKEN_DESCONHECIDO",
            lexema=caractere,
            linha=linha_inicial,
            coluna=coluna_inicial,
            valido=False,
            mensagem="simbolo nao reconhecido pela linguagem",
        )

    def tokenizar(self) -> list[Token]:
        tokens: list[Token] = []

        while self.caractere_atual() is not None:
            self.ignorar_espacos_e_comentarios(tokens)
            if self.caractere_atual() is None:
                break

            token = self.proximo_token()
            if token is not None:
                tokens.append(token)

        return tokens


def analisar_arquivo(caminho_arquivo: Path) -> list[Token]:
    fonte = caminho_arquivo.read_text(encoding="utf-8")
    lexer = Lexer(fonte)
    return lexer.tokenizar()


def imprimir_tokens(tokens: list[Token]) -> None:
    for token in tokens:
        print(token.formatar())


def main() -> int:
    caminho_entrada = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("entrada.txt")

    if not caminho_entrada.exists():
        print(
            f"Arquivo de entrada nao encontrado: {caminho_entrada}\n"
            "Uso: python analisador_lexico.py caminho_do_arquivo.txt"
        )
        return 1

    tokens = analisar_arquivo(caminho_entrada)
    imprimir_tokens(tokens)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
