# trigger.py
# Responsabilidade: detectar intenção na mensagem do usuário
# e executar a tool correspondente automaticamente.
# Simples, rápido, sem segunda chamada ao modelo.

from tools import executar_tool

# Mapa de palavras-chave → comando de tool
# Ordem importa — mais específico primeiro
TRIGGERS: list[tuple[list[str], str]] = [

    # /hora
    (["que horas", "horas são", "horário", "que dia",
      "hoje é", "dia da semana", "data de hoje"], "/hora"),

    # /clima
    (["clima", "tempo em", "temperatura", "previsão do tempo",
      "vai chover", "está chovendo", "faz calor", "faz frio",
      "está quente", "está frio"], "/clima"),

    # /calc
    (["quanto é", "quanto e", "calcule", "calcular",
      "resultado de", "raiz de", "raiz quadrada", "sqrt",
      "elevado", "dividido por", "multiplicado por"], "/calc"),
]


def _extrair_args_clima(mensagem: str) -> str:
    """
    Tenta extrair o nome da cidade da mensagem.

    Exemplos:
        'como está o clima em Salvador?'  → 'Salvador'
        'temperatura em São Paulo'        → 'São Paulo'
        'vai chover em Feira de Santana'  → 'Feira de Santana'
    """
    gatilhos = ["em ", "para ", "de ", "no ", "na "]
    msg = mensagem.lower()

    for gatilho in gatilhos:
        if gatilho in msg:
            idx = msg.index(gatilho) + len(gatilho)
            cidade = mensagem[idx:].strip().rstrip("?!.")
            if cidade:
                return cidade

    return ""  # cidade não identificada — não executa


def _extrair_args_calc(mensagem: str) -> str:
    """
    Tenta extrair a expressão matemática da mensagem.

    Exemplos:
        'quanto é 2 + 2?'       → '2 + 2'
        'calcule sqrt(144)'      → 'sqrt(144)'
        'raiz quadrada de 256'   → 'sqrt(256)'
    """
    # Substitui linguagem natural por sintaxe Python/math
    substituicoes = {
        "raiz quadrada de": "sqrt(",
        "raiz de":          "sqrt(",
        "elevado a":        "**",
        "elevado":          "**",
        "dividido por":     "/",
        "multiplicado por": "*",
        "quanto é":         "",
        "quanto e":         "",
        "calcule":          "",
        "calcular":         "",
        "resultado de":     "",
        "qual é":           "",
        "qual e":           "",
        "me diz":           "",
    }

    expr = mensagem.lower()
    for termo, substituto in substituicoes.items():
        expr = expr.replace(termo, substituto)

    expr = expr.strip().rstrip("?!.")

    # Fecha parêntese aberto pelo sqrt se necessário
    if "sqrt(" in expr and ")" not in expr:
        expr += ")"

    return expr


def detectar_e_executar(mensagem: str) -> tuple[bool, str, str]:
    """
    Analisa a mensagem e executa a tool correspondente se detectar intenção.

    Args:
        mensagem: texto digitado pelo usuário

    Returns:
        Tupla (encontrou, tool_usada, resultado):
            - (True, "/hora", "📅 Data: ...") se detectou e executou
            - (False, "", "")  se não detectou nenhuma intenção
    """
    msg_lower = mensagem.lower()

    for palavras_chave, tool in TRIGGERS:
        if any(p in msg_lower for p in palavras_chave):

            if tool == "/clima":
                args = _extrair_args_clima(mensagem)
                if not args:
                    # Cidade não identificada — deixa a IA responder normalmente
                    continue
                comando = f"/clima {args}"

            elif tool == "/calc":
                args = _extrair_args_calc(mensagem)
                if not args:
                    continue
                comando = f"/calc {args}"

            else:
                # /hora não precisa de args
                comando = tool

            eh_tool, resultado = executar_tool(comando)
            if eh_tool:
                return True, tool, resultado

    return False, "", ""
