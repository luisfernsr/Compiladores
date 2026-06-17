from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
# Importar o analisador lexico para obter os tokens
from analisador_lexico import Token, analisar_arquivo

# Conjunto de tipos para o parser e verificações semânticas
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

class ErroCompilacao(Exception):
    # Classe base para todos os erros do compilador
    def __init__(self, mensagem: str, linha: int, coluna: int) -> None:
        self.mensagem = mensagem
        self.linha = linha
        self.coluna = coluna

class ErroLexico(ErroCompilacao):
    def __str__(self) -> str:
        return f"Erro léxico na linha {self.linha}, coluna {self.coluna}: {self.mensagem}"

class ErroSintatico(ErroCompilacao):
    def __str__(self) -> str:
        return f"Erro sintático na linha {self.linha}, coluna {self.coluna}: {self.mensagem}"

class ErroSemantico(ErroCompilacao):
    def __str__(self) -> str:
        return f"Erro semântico na linha {self.linha}, coluna {self.coluna}: {self.mensagem}"


@dataclass
class ResultadoAnalise:
    arvore: "NoArvore"
    erros: list[ErroCompilacao]
    tabela_global: "TabelaSimbolos"

# Arvore sintática
@dataclass
class NoArvore:
    nome: str
    filhos: list["NoArvore"] = field(default_factory=list)  # Cada nó começa sem filhos
    tipo_semantico: str | None = None 

    def adicionar(self, *novos_filhos: "NoArvore | None") -> "NoArvore":
        for filho in novos_filhos:
            if child is not None if (child := filho) else False:
                self.filhos.append(child)
        return self

    # Converte a árvore para texto
    def para_texto(self, nivel: int = 0) -> str:
        tipo_str = f" [{self.tipo_semantico}]" if self.tipo_semantico else ""
        linhas = [f"{'  ' * nivel}{self.nome}{tipo_str}"]
        for filho in self.filhos:
            linhas.append(filho.para_texto(nivel + 1))
        return "\n".join(linhas)

# Transforma token em nó
def no_token(token: Token) -> NoArvore:
    return NoArvore(f"{token.tipo}({token.lexema})")

# Tabela de símbolos
class TabelaSimbolos:
    def __init__(self, pai: TabelaSimbolos | None = None, nome_escopo: str = "global") -> None:
        self.tabela: dict[str, dict] = {}
        self.pai = pai
        self.nome_escopo = nome_escopo
        self.filhos_escopos: list[TabelaSimbolos] = []

    def inserir_variavel(self, nome: str, tipo: str, linha: int, coluna: int) -> None:
        if nome in self.tabela:
            raise ErroSemantico(f"Redeclaração da variável {nome!r} no mesmo escopo.", linha, coluna)
        self.tabela[nome] = {"categoria": "variavel", "tipo": tipo}

    def inserir_funcao(self, nome: str, tipo_retorno: str, params: list[str], linha: int, coluna: int) -> None:
        if nome in self.tabela:
            raise ErroSemantico(f"Redeclaração do identificador {nome!r}.", linha, coluna)
        self.tabela[nome] = {"categoria": "funcao", "tipo": tipo_retorno, "params": params}

    def buscar(self, nome: str) -> dict | None:
        if nome in self.tabela:
            return self.tabela[nome]
        if self.pai is not None:
            return self.pai.buscar(nome)
        return None

    def _coletar_simbolos(self, acumulador: list[tuple[str, dict, str]]) -> None:
        for nome, info in self.tabela.items():
            acumulador.append((nome, info, self.nome_escopo))
        for filho in self.filhos_escopos:
            filho._coletar_simbolos(acumulador)

    def imprimir_tabela(self) -> None:
        simbolos = []
        self._coletar_simbolos(simbolos)

        print(f"\n{'='*95}")
        print(f" {'TABELA DE SÍMBOLOS UNIFICADA':^93}")
        print(f"{'='*95}")
        print(f"{'Identificador':<20} | {'Categoria':<12} | {'Tipo/Retorno':<13} | {'Parâmetros':<15} | {'Escopo Original':<20}")
        print(f"{'-'*21}+{'-'*14}+{'-'*15}+{'-'*17}+{'-'*22}")
        
        if not simbolos:
            print(f"{'(nenhum símbolo)':<20} | {'':<12} | {'':<13} | {'':<15} | {'':<20}")
        else:
            for nome, info, escopo in simbolos:
                categoria = info["categoria"]
                tipo = info["tipo"]
                params = str(info["params"]) if "params" in info else "-"
                print(f"{nome:<20} | {categoria:<12} | {tipo:<13} | {params:<15} | {escopo:<20}")

# Parser Sintático e Semântico
class ParserSemantico:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.indice = 0
        self.erros: list[ErroCompilacao] = []
        self.tabela_global = TabelaSimbolos(nome_escopo="global")
        self.escopo_atual = self.tabela_global
        self.funcao_atual_retorno: str | None = None
        self.contador_blocos = 0

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

    def verificar_token_invalido(self) -> None:
        # Erro léxico 
        token = self.token_atual()
        if token is not None and not token.valido:
            raise ErroLexico(f"Token inválido detectado: {token.mensagem}", token.linha, token.coluna)

    def consumir(self, *, tipo: str | None = None, lexema: str | None = None, esperado: str) -> Token:
        self.verificar_token_invalido()
        token = self.token_atual()
        if token is None:
            raise ErroSintatico(f"era esperado {esperado}, mas o arquivo terminou", self.linha_final(), self.coluna_final())
        if tipo is not None and token.tipo != tipo:
            raise ErroSintatico(f"era esperado {esperado}, mas foi encontrado {token.lexema!r}", token.linha, token.coluna)
        if lexema is not None and token.lexema != lexema:
            raise ErroSintatico(f"era esperado {esperado}, mas foi encontrado {token.lexema!r}", token.linha, token.coluna)
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

    def registrar_erro(self, erro: ErroCompilacao) -> None:
        self.erros.append(erro)

    def sincronizar(self) -> None:
        tokens_sincronizacao = {";", "}", "if", "while", "return", "{", "int", "float", "char", "string", "bool", "void"}
        if self.token_atual() is not None:
            self.avancar()
        while self.token_atual() is not None:
            token = self.token_atual()
            if token.lexema == ";":
                self.avancar()
                return
            if token.lexema in tokens_sincronizacao:
                return
            self.avancar()

    def analisar(self) -> ResultadoAnalise:
        for token in self.tokens:
            if not token.valido:
                self.registrar_erro(ErroLexico(token.mensagem, token.linha, token.coluna))
        
        arvore = self.programa()
        if self.token_atual() is not None:
            token = self.token_atual()
            self.registrar_erro(ErroSintatico(f"token inesperado apos o fim da analise: {token.lexema!r}", token.linha, token.coluna))
            
        return ResultadoAnalise(arvore=arvore, erros=self.erros, tabela_global=self.tabela_global)

    def programa(self) -> NoArvore:
        raiz = NoArvore("programa")
        while self.token_atual() is not None:
            try:
                raiz.adicionar(self.declaracao_ou_comando())
            except ErroCompilacao as erro:
                self.registrar_erro(erro)
                raiz.adicionar(
                    NoArvore("erro").adicionar(
                        NoArvore(f"mensagem({erro.mensagem})"),
                        NoArvore(f"posicao(linha={erro.linha}, coluna={erro.coluna})"),
                    )
                )
                self.sincronizar()
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
        no_tipo = self.tipo()
        tipo_retorno = no_tipo.nome.split('(')[0] if '(' in no_tipo.nome else no_tipo.nome
        
        token_id = self.consumir(tipo="IDENTIFICADOR", esperado="um identificador de funcao")
        nome_funcao = token_id.lexema
        no_id = no_token(token_id)

        self.consumir(lexema="(", esperado="'('")
        
        novo_escopo = TabelaSimbolos(pai=self.escopo_atual, nome_escopo=f"funcao {nome_funcao}")
        self.escopo_atual.filhos_escopos.append(novo_escopo)
        self.escopo_atual = novo_escopo
        
        self.funcao_atual_retorno = tipo_retorno
        
        lista_params = []
        if not self.token_eh(lexema=")"):
            no_params = self.lista_parametros(lista_params)
        else:
            no_params = NoArvore("lista_parametros_vazia")
            
        self.consumir(lexema=")", esperado="')'")

        self.escopo_atual.pai.inserir_funcao(nome_funcao, tipo_retorno, lista_params, token_id.linha, token_id.coluna)

        no_bloco = self.bloco(criar_escopo=False)
        
        self.escopo_atual = self.escopo_atual.pai
        self.funcao_atual_retorno = None

        return NoArvore("declaracao_funcao").adicionar(
            no_tipo, no_id, NoArvore("("), no_params, NoArvore(")"), no_bloco
        )

    def lista_parametros(self, lista_params: list[str]) -> NoArvore:
        no = NoArvore("lista_parametros")
        if self.token_eh(tipo="PALAVRA_RESERVADA", lexema="void") and self.ver_proximo() and self.ver_proximo().lexema == ")":
            no.adicionar(no_token(self.avancar()))
            return no

        no.adicionar(self.parametro(lista_params))
        while self.token_eh(lexema=","):
            self.consumir(lexema=",", esperado="','")
            no.adicionar(self.parametro(lista_params))
        return no

    def parametro(self, lista_params: list[str]) -> NoArvore:
        no_tipo = self.tipo()
        tipo_str = no_tipo.nome
        token_id = self.consumir(tipo="IDENTIFICADOR", esperado="um identificador de parametro")
        
        self.escopo_atual.inserir_variavel(token_id.lexema, tipo_str, token_id.linha, token_id.coluna)
        lista_params.append(tipo_str)
        
        return NoArvore("parametro").adicionar(no_tipo, no_token(token_id))

    def declaracao_variavel(self) -> NoArvore:
        no_tipo = self.tipo()
        tipo_str = no_tipo.nome
        
        token_id = self.consumir(tipo="IDENTIFICADOR", esperado="um identificador")
        nome_var = token_id.lexema
        
        self.escopo_atual.inserir_variavel(nome_var, tipo_str, token_id.linha, token_id.coluna)
        
        no = NoArvore("declaracao_variavel").adicionar(no_tipo, no_token(token_id))
        
        if self.token_eh(lexema="="):
            self.consumir(lexema="=", esperado="'='")
            no_exp = self.expressao()
            
            if no_exp.tipo_semantico and no_exp.tipo_semantico != tipo_str:
                if not (tipo_str == "float" and no_exp.tipo_semantico == "int"):
                    self.registrar_erro(ErroSemantico(f"Tipo incompatível: não é possível atribuir {no_exp.tipo_semantico} a {tipo_str}.", token_id.linha, token_id.coluna))
            
            no.adicionar(NoArvore("="), no_exp)
            
        self.consumir(lexema=";", esperado="';'")
        return no

    def tipo(self) -> NoArvore:
        self.verificar_token_invalido()
        token = self.token_atual()
        if token is None or token.tipo != "PALAVRA_RESERVADA" or token.lexema not in TIPOS_PRIMITIVOS:
            if token is None:
                raise ErroSintatico("era esperado um tipo, mas o arquivo terminou", self.linha_final(), self.coluna_final())
            raise ErroSintatico("era esperado um tipo valido", token.linha, token.coluna)
        return NoArvore(self.avancar().lexema)

    def bloco(self, criar_escopo: bool = True) -> NoArvore:
        self.consumir(lexema="{", esperado="'{'")
        if criar_escopo:
            self.contador_blocos += 1
            novo_escopo = TabelaSimbolos(pai=self.escopo_atual, nome_escopo=f"bloco_local_{self.contador_blocos}")
            self.escopo_atual.filhos_escopos.append(novo_escopo)
            self.escopo_atual = novo_escopo
            
        no = NoArvore("bloco")
        while self.token_atual() is not None and not self.token_eh(lexema="}"):
            no.adicionar(self.declaracao_ou_comando())
            
        self.consumir(lexema="}", esperado="'}'")
        if criar_escopo:
            self.escopo_atual = self.escopo_atual.pai
            
        return no

    def comando(self) -> NoArvore:
        self.verificar_token_invalido()
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
            self.consumir(lexema=";", esperado="';'")
            return NoArvore("comando_vazio")

        return self.comando_expressao()

    def comando_if(self) -> NoArvore:
        self.consumir(lexema="if", esperado="'if'")
        self.consumir(lexema="(", esperado="'('")
        no_cond = self.expressao()
        
        if no_cond.tipo_semantico and no_cond.tipo_semantico != "bool":
            self.registrar_erro(ErroSemantico("A condição do 'if' deve ser uma expressão booleana.", self.linha_final(), self.coluna_final()))
            
        self.consumir(lexema=")", esperado="')'")
        no_cmd = self.comando()
        no = NoArvore("comando_if").adicionar(no_cond, no_cmd)
        
        if self.token_eh(lexema="else"):
            self.consumir(lexema="else", esperado="'else'")
            no.adicionar(self.comando())
        return no

    def comando_while(self) -> NoArvore:
        self.consumir(lexema="while", esperado="'while'")
        self.consumir(lexema="(", esperado="'('")
        no_cond = self.expressao()
        
        if no_cond.tipo_semantico and no_cond.tipo_semantico != "bool":
            self.registrar_erro(ErroSemantico("A condição do 'while' deve ser uma expressão booleana.", self.linha_final(), self.coluna_final()))
            
        self.consumir(lexema=")", esperado="')'")
        no_cmd = self.comando()
        return NoArvore("comando_while").adicionar(no_cond, no_cmd)

    def comando_return(self) -> NoArvore:
        token_ret = self.consumir(lexema="return", esperado="'return'")
        no = NoArvore("comando_return")
        
        tipo_exp = "void"
        if not self.token_eh(lexema=";"):
            no_exp = self.expressao()
            tipo_exp = no_exp.tipo_semantico or "void"
            no.adicionar(no_exp)
            
        if self.funcao_atual_retorno and self.funcao_atual_retorno != tipo_exp:
            self.registrar_erro(ErroSemantico(f"Retorno inválido. A função exige retorno do tipo {self.funcao_atual_retorno}, mas foi retornado {tipo_exp}.", token_ret.linha, token_ret.coluna))
            
        self.consumir(lexema=";", esperado="';'")
        return no

    def comando_expressao(self) -> NoArvore:
        no_exp = self.expressao()
        self.consumir(lexema=";", esperado="';'")
        return NoArvore("comando_expressao").adicionar(no_exp)

    def expressao(self) -> NoArvore:
        no = self.atribuicao()
        return NoArvore("expressao", tipo_semantico=no.tipo_semantico).adicionar(no)

    def atribuicao(self) -> NoArvore:
        esquerda = self.ou_logico()
        if self.token_atual() is not None and self.token_atual().lexema in OPERADORES_ATRIBUICAO:
            token_op = self.avancar()
            direita = self.atribuicao()
            
            if esquerda.tipo_semantico and direita.tipo_semantico:
                if esquerda.tipo_semantico != direita.tipo_semantico:
                    if not (esquerda.tipo_semantico == "float" and direita.tipo_semantico == "int"):
                        self.registrar_erro(ErroSemantico(f"Atribuição incompatível de {direita.tipo_semantico} para variável {esquerda.tipo_semantico}.", token_op.linha, token_op.coluna))
            
            return NoArvore("atribuicao", tipo_semantico=esquerda.tipo_semantico).adicionar(esquerda, no_token(token_op), direita)
        return esquerda

    def ou_logico(self) -> NoArvore:
        no = self.e_logico()
        while self.token_atual() is not None and self.token_atual().lexema in OPERADORES_OU:
            token_op = self.avancar()
            proximo = self.e_logico()
            no = NoArvore("ou_logico", tipo_semantico="bool").adicionar(no, no_token(token_op), proximo)
        return no

    def e_logico(self) -> NoArvore:
        no = self.igualdade()
        while self.token_atual() is not None and self.token_atual().lexema in OPERADORES_E:
            token_op = self.avancar()
            proximo = self.igualdade()
            no = NoArvore("e_logico", tipo_semantico="bool").adicionar(no, no_token(token_op), proximo)
        return no

    def igualdade(self) -> NoArvore:
        no = self.comparacao()
        while self.token_atual() is not None and self.token_atual().lexema in OPERADORES_IGUALDADE:
            token_op = self.avancar()
            proximo = self.comparacao()
            no = NoArvore("igualdade", tipo_semantico="bool").adicionar(no, no_token(token_op), proximo)
        return no

    def comparacao(self) -> NoArvore:
        no = self.termo()
        while self.token_atual() is not None and self.token_atual().lexema in OPERADORES_COMPARACAO:
            token_op = self.avancar()
            proximo = self.termo()
            no = NoArvore("comparacao", tipo_semantico="bool").adicionar(no, no_token(token_op), proximo)
        return no

    def termo(self) -> NoArvore:
        no = self.fator()
        while self.token_atual() is not None and self.token_atual().lexema in OPERADORES_TERMO:
            token_op = self.avancar()
            proximo = self.fator()
            
            # Promoção de tipos
            tipo_res = "int"
            if no.tipo_semantico == "float" or proximo.tipo_semantico == "float":
                tipo_res = "float"
                
            no = NoArvore("termo", tipo_semantico=tipo_res).adicionar(no, no_token(token_op), proximo)
        return no

    def fator(self) -> NoArvore:
        no = self.unario()
        while self.token_atual() is not None and self.token_atual().lexema in OPERADORES_FATOR:
            token_op = self.avancar()
            proximo = self.unario()
            
            tipo_res = "int"
            if no.tipo_semantico == "float" or proximo.tipo_semantico == "float":
                tipo_res = "float"
                
            no = NoArvore("fator", tipo_semantico=tipo_res).adicionar(no, no_token(token_op), proximo)
        return no

    def unario(self) -> NoArvore:
        if self.token_atual() is not None and self.token_atual().lexema in OPERADORES_UNARIOS:
            token_op = self.avancar()
            filho = self.unario()
            tipo_res = "bool" if token_op.lexema in {"!", "not"} else filho.tipo_semantico
            return NoArvore("unario", tipo_semantico=tipo_res).adicionar(no_token(token_op), filho)
        return self.primario()

    def primario(self) -> NoArvore:
        self.verificar_token_invalido()
        token = self.token_atual()
        if token is None:
            raise ErroSintatico("era esperada uma expressao, mas o arquivo terminou", self.linha_final(), self.coluna_final())

        if token.lexema == "(":
            self.consumir(lexema="(", esperado="'('")
            no_exp = self.expressao()
            self.consumir(lexema=")", esperado="')'")
            return NoArvore("agrupamento", tipo_semantico=no_exp.tipo_semantico).adicionar(no_exp)

        if token.tipo == "NUMERO_INTEIRO":
            return NoArvore("literal", tipo_semantico="int").adicionar(no_token(self.avancar()))
        if token.tipo == "NUMERO_REAL":
            return NoArvore("literal", tipo_semantico="float").adicionar(no_token(self.avancar()))
        if token.tipo == "STRING":
            return NoArvore("literal", tipo_semantico="string").adicionar(no_token(self.avancar()))
        if token.tipo == "CARACTERE":
            return NoArvore("literal", tipo_semantico="char").adicionar(no_token(self.avancar()))

        if token.tipo == "PALAVRA_RESERVADA" and token.lexema in LITERAIS_BOOLEANOS:
            return NoArvore("literal_booleano", tipo_semantico="bool").adicionar(no_token(self.avancar()))

        if token.tipo == "IDENTIFICADOR":
            nome_id = token.lexema
            token_id = self.avancar()
            no_id = no_token(token_id)
            
            if self.token_eh(lexema="("):
                self.consumir(lexema="(", esperado="'('")
                
                info_funcao = self.escopo_atual.buscar(nome_id)
                if not info_funcao or info_funcao["categoria"] != "funcao":
                    self.registrar_erro(ErroSemantico(f"Função {nome_id!r} não foi declarada.", token_id.linha, token_id.coluna))
                    info_funcao = {"tipo": "void", "params": []}
                
                lista_args_tipos = []
                if not self.token_eh(lexema=")"):
                    no_args = self.lista_argumentos(lista_args_tipos)
                else:
                    no_args = NoArvore("lista_argumentos_vazia")
                    
                self.consumir(lexema=")", esperado="')'")
                
                if len(lista_args_tipos) != len(info_funcao["params"]):
                    self.registrar_erro(ErroSemantico(f"A função {nome_id!r} esperava {len(info_funcao['params'])} argumentos, mas recebeu {len(lista_args_tipos)}.", token_id.linha, token_id.coluna))
                else:
                    for i, tipo_arg in enumerate(lista_args_tipos):
                        tipo_esperado = info_funcao["params"][i]
                        if tipo_arg != tipo_esperado:
                            self.registrar_erro(ErroSemantico(f"Argumento {i+1} da função {nome_id!r} inválido. Esperado {tipo_esperado}, recebido {tipo_arg}.", token_id.linha, token_id.coluna))

                return NoArvore("chamada_funcao", tipo_semantico=info_funcao["tipo"]).adicionar(no_id, no_args)
            
            else:
                info_var = self.escopo_atual.buscar(nome_id)
                if not info_var:
                    self.registrar_erro(ErroSemantico(f"Variável {nome_id!r} não foi declarada neste escopo.", token_id.linha, token_id.coluna))
                    tipo_var = "int"  # Recuperação simples
                else:
                    tipo_var = info_var["tipo"]
                    
                return NoArvore("identificador", tipo_semantico=tipo_var).adicionar(no_id)

        raise ErroSintatico(f"token inesperado em expressao: {token.lexema!r}", token.linha, token.coluna)

    def lista_argumentos(self, lista_args_tipos: list[str]) -> NoArvore:
        no_exp = self.expressao()
        if no_exp.tipo_semantico:
            lista_args_tipos.append(no_exp.tipo_semantico)
            
        no = NoArvore("lista_argumentos").adicionar(no_exp)
        while self.token_eh(lexema=","):
            self.consumir(lexema=",", esperado="','")
            prox_exp = self.expressao()
            if prox_exp.tipo_semantico:
                lista_args_tipos.append(prox_exp.tipo_semantico)
            no.adicionar(prox_exp)
        return no

def salvar_arvore(arvore: NoArvore, caminho_saida: Path) -> None:
    caminho_saida.write_text(arvore.para_texto() + "\n", encoding="utf-8")

def analisar_semantica(caminho_arquivo: Path) -> ResultadoAnalise:
    tokens = analisar_arquivo(caminho_arquivo)
    parser = ParserSemantico(tokens)
    return parser.analisar()

def main() -> int:
    caminho_entrada = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("entrada.txt")
    caminho_saida = Path(sys.argv[2]) if len(sys.argv) > 2 else caminho_entrada.with_name("arvore_semantica.txt")

    if not caminho_entrada.exists():
        print(
            f"Arquivo de entrada nao encontrado: {caminho_entrada}\n"
            "Uso: python analisador_semantico.py caminho_do_arquivo.txt caminho_da_arvore.txt"
        )
        return 1

    try:
        resultado = analisar_semantica(caminho_entrada)
        salvar_arvore(resultado.arvore, caminho_saida)
    except ErroCompilacao as erro:
        print(str(erro))
        return 1

    #Imprime a tabela de símbolos
    resultado.tabela_global.imprimir_tabela()
    print("\n" + "="*95)

    if resultado.erros:
        print("\nAnálise concluída com erros detectados:")
        for erro in resultado.erros:
            print(f"  - {erro}")
        print(f"\nÁrvore semântica parcial salva em: {caminho_saida}")
        return 1

    print("\nAnálise semântica e sintática concluídas com sucesso. Nenhum erro detectado.")
    print(f"Árvore anotada salva em: {caminho_saida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())