# Analisador Léxico em Python

Este projeto implementa um analisador léxico em Python. O programa lê um arquivo de entrada `.txt`, identifica os tokens da linguagem, informa a linha e a coluna em que cada token começa e também sinaliza erros léxicos quando encontra símbolos ou construções inválidas.

## Tokens reconhecidos

O analisador reconhece os seguintes grupos de tokens:

- palavras reservadas, como `if`, `else`, `while`, `int`, `float`, `return`;
- identificadores, como `x`, `nome`, `soma_total`;
- números inteiros, como `10`, `25`, `300`;
- números reais, como `10.5`, `3.14`;
- strings entre aspas duplas, como `"Ana"`;
- literais de caractere entre aspas simples, como `'A'` e `'\n'`;
- operadores simples, como `+`, `-`, `*`, `/`, `=`, `<`, `>`;
- operadores duplos, como `==`, `!=`, `<=`, `>=`, `+=`;
- delimitadores, como `(`, `)`, `{`, `}`, `;`, `,`.

## Erros léxicos tratados

O analisador informa token inválido nos seguintes casos:

- símbolo não reconhecido pela linguagem;
- string não fechada;
- literal de caractere não fechado;
- literal de caractere com mais de um caractere;
- comentário de bloco não fechado.


## Exemplo de entrada

```txt
int main() {
  float x = 10.5;
  string nome = "Ana";
  char letra = 'A';
  // comentario de linha
  x += 1;
  @
}
```
