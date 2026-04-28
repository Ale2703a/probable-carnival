# summarizer.py
from model import gerar_resposta
from memory import salvar_resumo
from config import obter   # ← novo import

def deve_resumir(historico: list[dict]) -> bool:
    """Verifica se o histórico atingiu o limite configurado."""
    limite = obter("limite_mensagens")   # ← antes era constante fixa
    msgs_conversa = [m for m in historico if m["role"] != "system"]
    return len(msgs_conversa) >= limite

def resumir_historico(historico: list[dict], arquivo_sessao: str) -> list[dict]:
    """Gera resumo e retorna histórico comprimido."""
    print("\n📝 Comprimindo histórico longo... ", end="", flush=True)

    system = [m for m in historico if m["role"] == "system"]
    conversa = [m for m in historico if m["role"] != "system"]

    conversa_texto = ""
    for msg in conversa:
        papel = "Usuário" if msg["role"] == "user" else "IA"
        conversa_texto += f"{papel}: {msg['content']}\n\n"

    instrucao_resumo = [{
        "role": "user",
        "content": (
            "Resuma a conversa abaixo de forma clara e estruturada. "
            "Inclua: tópicos discutidos, decisões tomadas, informações "
            "importantes mencionadas pelo usuário, e contexto necessário "
            "para continuar a conversa. Seja objetivo.\n\n"
            f"CONVERSA:\n{conversa_texto}"
        )
    }]

    texto_resumo = gerar_resposta(instrucao_resumo)
    caminho_resumo = salvar_resumo(arquivo_sessao, texto_resumo)
    print(f"salvo em {caminho_resumo}")

    ultima_msg_usuario = next(
        (m for m in reversed(conversa) if m["role"] == "user"), None
    )

    novo_historico = system + [{
        "role": "assistant",
        "content": f"[Resumo da conversa anterior]\n{texto_resumo}"
    }]

    if ultima_msg_usuario:
        novo_historico.append(ultima_msg_usuario)

    print(f"✅ Histórico comprimido: {len(historico)} → {len(novo_historico)} mensagens\n")
    return novo_historico
