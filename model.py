# model.py
# Responsabilidade: comunicação com o modelo Llama 3 via Ollama.
# Nenhum outro módulo deve importar 'ollama' diretamente.

import ollama
from typing import Generator
from config import obter


def gerar_resposta(mensagens: list[dict]) -> str:
    """
    Envia uma lista de mensagens ao modelo e retorna a resposta.

    Args:
        mensagens: lista no formato [{"role": "user", "content": "..."}]
                   Pode incluir histórico completo da conversa.

    Returns:
        String com a resposta gerada pelo modelo.
    
    Raises:
        Exception: se o Ollama não estiver rodando ou o modelo não existir.
    """
    MODELO = obter("modelo")
    
    try:
        resposta = ollama.chat(
            model=MODELO,
            messages=mensagens
        )
        # A resposta vem aninhada — extraímos só o texto
        return resposta["message"]["content"]
    
    except Exception as e:
        # Mensagem clara para facilitar debug
        raise Exception(f"Erro ao comunicar com o modelo '{MODELO}': {e}")
    
def gerar_resposta_stream(mensagens: list[dict]) -> Generator[str, None, str]:
    """
    Envia mensagens ao modelo e retorna um gerador de tokens (streaming).
    Cada 'yield' entrega um pedaço do texto conforme é gerado.

    Args:
        mensagens: lista no formato [{"role": "user", "content": "..."}]

    Yields:
        Fragmentos (tokens) da resposta em tempo real.

    Returns:
        Resposta completa acumulada ao final (via StopIteration.value).
    
    Uso:
        for token in gerar_resposta_stream(msgs):
            print(token, end="", flush=True)
    """
    MODELO = obter("modelo")
    
    try:
        stream = ollama.chat(
            model=MODELO,
            messages=mensagens,
            stream=True       # <-- ativa o modo streaming
        )

        resposta_completa = ""

        for chunk in stream:
            # Cada chunk tem a mesma estrutura, mas com fragmento do texto
            token = chunk["message"]["content"]
            resposta_completa += token
            yield token          # entrega o fragmento para quem chamou

        return resposta_completa # valor final acessível via StopIteration

    except Exception as e:
        raise Exception(f"Erro no streaming do modelo '{MODELO}': {e}")
