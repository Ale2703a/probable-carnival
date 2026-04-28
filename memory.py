# memory.py
import json
import os
from datetime import datetime
from config import obter   # ← novo import

def _garantir_pasta():
    """Cria a pasta de memória se não existir."""
    os.makedirs(obter("pasta_memoria"), exist_ok=True)   # ← dinâmico

def nova_sessao() -> str:
    """Gera nome de arquivo único baseado na data/hora."""
    _garantir_pasta()
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return os.path.join(obter("pasta_memoria"), f"{timestamp}.json")

def salvar_historico(caminho: str, historico: list[dict]) -> None:
    """Salva o histórico completo em JSON."""
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(historico, f, ensure_ascii=False, indent=2)

def carregar_historico(caminho: str) -> list[dict]:
    """Carrega histórico de um arquivo JSON."""
    if not os.path.exists(caminho):
        return []
    with open(caminho, "r", encoding="utf-8") as f:
        return json.load(f)

def listar_sessoes() -> list[str]:
    """Lista sessões salvas, da mais recente à mais antiga."""
    _garantir_pasta()
    pasta = obter("pasta_memoria")
    arquivos = [
        os.path.join(pasta, f)
        for f in os.listdir(pasta)
        if f.endswith(".json")
    ]
    return sorted(arquivos, reverse=True)

def salvar_resumo(caminho_sessao: str, texto_resumo: str) -> str:
    """Salva o resumo da sessão em arquivo .resumo.txt separado."""
    caminho_resumo = caminho_sessao.replace(".json", ".resumo.txt")
    with open(caminho_resumo, "w", encoding="utf-8") as f:
        f.write(f"Resumo gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
        f.write("=" * 50 + "\n")
        f.write(texto_resumo)
    return caminho_resumo
