# config.py
# Responsabilidade: ler, validar e fornecer as configurações do projeto.
# É o único arquivo que lê o config.json — os outros módulos importam daqui.

import json
import os

# Caminho do arquivo de configuração
CAMINHO_CONFIG = "config.json"

# Valores padrão — usados se um campo estiver ausente no config.json
# Isso evita que o projeto quebre se o usuário apagar uma linha do JSON
DEFAULTS = {
    "modelo": "llama3",
    "streaming": True,
    "limite_mensagens": 20,
    "pasta_memoria": "memoria",
    "persona": (
        "Você é um assistente pessoal inteligente, direto e amigável. "
        "Responda sempre em português do Brasil. "
        "Seja conciso, mas completo. "
        "Se não souber algo, diga claramente."
    ),
    "nome_assistente": "IA"
}

def carregar_config() -> dict:
    """
    Lê o config.json e retorna as configurações com fallback para defaults.
    Se o arquivo não existir, cria um automaticamente com os valores padrão.

    Returns:
        Dicionário com todas as configurações do projeto.
    """
    if not os.path.exists(CAMINHO_CONFIG):
        # Primeira execução — cria o config.json automaticamente
        print(f"⚙️  '{CAMINHO_CONFIG}' não encontrado. Criando com valores padrão...")
        salvar_config(DEFAULTS.copy())
        return DEFAULTS.copy()

    with open(CAMINHO_CONFIG, "r", encoding="utf-8") as f:
        try:
            dados = json.load(f)
        except json.JSONDecodeError as e:
            # JSON inválido — avisa e usa defaults para não travar o projeto
            print(f"⚠️  Erro ao ler '{CAMINHO_CONFIG}': {e}")
            print("    Usando configurações padrão.")
            return DEFAULTS.copy()

    # Mescla com defaults — campos ausentes recebem o valor padrão
    config_final = {**DEFAULTS, **dados}
    return config_final


def salvar_config(config: dict) -> None:
    """
    Salva o dicionário de configurações no config.json.

    Args:
        config: dicionário com as configurações a salvar.
    """
    with open(CAMINHO_CONFIG, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def obter(chave: str):
    """
    Atalho para buscar um valor específico da configuração.

    Args:
        chave: nome do campo desejado (ex: "modelo", "streaming")

    Returns:
        Valor do campo, ou None se não existir.

    Exemplo:
        from config import obter
        modelo = obter("modelo")  # "llama3"
    """
    return carregar_config().get(chave)
