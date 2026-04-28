# chat.py — versão final com memória semântica

from model import gerar_resposta, gerar_resposta_stream
from memory import nova_sessao, salvar_historico, carregar_historico, listar_sessoes
from summarizer import resumir_historico, deve_resumir
from config import obter, carregar_config
from tools import executar_tool
from trigger import detectar_e_executar
from semantic_memory import (salvar_memoria, montar_contexto_memorias,
                              contar_memorias, listar_memorias_recentes)


def montar_system_prompt() -> dict:
    return {"role": "system", "content": obter("persona")}


def escolher_sessao() -> tuple[str, list[dict]]:
    sessoes = listar_sessoes()
    if sessoes:
        print("\n📂 Sessões anteriores encontradas:")
        for i, s in enumerate(sessoes[:5], 1):
            print(f"  [{i}] {s}")
        print("  [0] Iniciar nova sessão")
        escolha = input("\nEscolha uma opção: ").strip()
        if escolha.isdigit() and 1 <= int(escolha) <= len(sessoes[:5]):
            caminho = sessoes[int(escolha) - 1]
            historico = carregar_historico(caminho)
            print(f"✅ Sessão carregada: {caminho} ({len(historico)} mensagens)")
            return caminho, historico

    caminho = nova_sessao()
    print(f"🆕 Nova sessão iniciada: {caminho}")
    return caminho, []


def _responder_stream(historico: list[dict], nome: str) -> str:
    """Helper de streaming."""
    print(f"{nome}: ", end="", flush=True)
    resposta = ""
    gerador = gerar_resposta_stream(historico)
    try:
        while True:
            token = next(gerador)
            print(token, end="", flush=True)
            resposta += token
    except StopIteration as fim:
        resposta = resposta or fim.value
    print("\n")
    return resposta


def chat():
    config = carregar_config()
    nome = config["nome_assistente"]

    print("=" * 50)
    print(f"🤖 {nome} — Llama 3 via Ollama")
    print(f"   modelo: {config['modelo']}  |  stream: {config['streaming']}")
    print(f"   🧠 memórias salvas: {contar_memorias()}")
    print("   'sair'       → encerra e salva")
    print("   'limpar'     → nova sessão")
    print("   '/resumir'   → comprime o histórico")
    print("   '/config'    → mostra configurações")
    print("   '/tools'     → lista tools disponíveis")
    print("   '/memoria'   → inspeciona memórias salvas")
    print("=" * 50)

    arquivo_sessao, historico = escolher_sessao()

    if not historico:
        historico.append(montar_system_prompt())

    print("\n💬 Pode começar a conversa!\n")

    while True:
        try:
            entrada = input("Você: ").strip()

            if not entrada:
                continue

            # ── Comandos de controle ──────────────────────────────────────
            if entrada.lower() == "sair":
                print(f"👋 Até logo! Conversa salva em: {arquivo_sessao}")
                break

            if entrada.lower() == "limpar":
                arquivo_sessao = nova_sessao()
                historico = [montar_system_prompt()]
                print(f"🆕 Nova sessão: {arquivo_sessao}\n")
                continue

            if entrada.lower() == "/resumir":
                historico = resumir_historico(historico, arquivo_sessao)
                salvar_historico(arquivo_sessao, historico)
                continue

            if entrada.lower() == "/config":
                print("\n⚙️  Configuração atual:")
                for chave, valor in carregar_config().items():
                    if chave != "persona":
                        print(f"   {chave}: {valor}")
                print()
                continue

            if entrada.lower() == "/memoria":
                total = contar_memorias()
                print(f"\n🧠 Total de memórias salvas: {total}")
                if total > 0:
                    print("\nMais recentes:")
                    for m in listar_memorias_recentes(5):
                        papel = "Você" if m["role"] == "user" else nome
                        print(f"  [{m['timestamp']}] {papel}: {m['preview']}")
                print()
                continue

            # ── Tools manuais ─────────────────────────────────────────────
            eh_tool, resultado = executar_tool(entrada)
            if eh_tool:
                print(f"\n{resultado}\n")
                historico.append({
                    "role": "user",
                    "content": f"[Resultado do comando '{entrada}']\n{resultado}"
                })
                resposta = _responder_stream(historico, nome)
                historico.append({"role": "assistant", "content": resposta})
                salvar_historico(arquivo_sessao, historico)
                continue

            # ── Mensagem normal ───────────────────────────────────────────
            historico.append({"role": "user", "content": entrada})

            if deve_resumir(historico):
                print("⚠️  Histórico longo — resumindo automaticamente...")
                historico = resumir_historico(historico, arquivo_sessao)

            # ── Memória semântica ─────────────────────────────────────────
            contexto_memoria = montar_contexto_memorias(entrada)
            if contexto_memoria:
                print("🧠 [memória] ", end="", flush=True)
                historico.append({
                    "role": "user",
                    "content": (
                        f"{contexto_memoria}\n\n"
                        f"Com base nisso e na conversa atual, responda: {entrada}"
                    )
                })

            # ── Trigger automático de tools ───────────────────────────────
            encontrou, tool_usada, resultado_tool = detectar_e_executar(entrada)
            if encontrou:
                print(f"🔍 [{tool_usada}] ", end="", flush=True)
                historico.append({
                    "role": "user",
                    "content": (
                        f"[Dado obtido via {tool_usada}]\n"
                        f"{resultado_tool}\n\n"
                        f"Use esses dados para responder: {entrada}"
                    )
                })

            # ── Resposta ──────────────────────────────────────────────────
            resposta = _responder_stream(historico, nome)

            # ── Salva como memória ────────────────────────────────────────
            salvar_memoria(entrada, "user", arquivo_sessao)
            salvar_memoria(resposta, "assistant", arquivo_sessao)

            historico.append({"role": "assistant", "content": resposta})
            salvar_historico(arquivo_sessao, historico)

        except KeyboardInterrupt:
            print(f"\n\n👋 Interrompido. Conversa salva em: {arquivo_sessao}")
            break

        except Exception as e:
            print(f"\n❌ Erro: {e}\n")


if __name__ == "__main__":
    chat()
