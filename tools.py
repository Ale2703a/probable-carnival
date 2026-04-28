# tools.py
# Responsabilidade: funções utilitárias que a IA pode executar.
# Cada tool recebe argumentos como string e retorna string com o resultado.
# Nenhuma tool deve travar o programa — sempre retorna algo, mesmo em erro.

import os
import math
import datetime
import requests


# ─── REGISTRO DE TOOLS ────────────────────────────────────────────────────────
# Dicionário central: nome do comando → função correspondente
# Para adicionar uma nova tool, basta criar a função e registrar aqui.

TOOLS: dict = {}

def registrar(nome: str, descricao: str):
    """
    Decorator para registrar uma função como tool disponível.
    Uso:
        @registrar("/hora", "Mostra a data e hora atual")
        def tool_hora(args: str) -> str: ...
    """
    def decorator(func):
        TOOLS[nome] = {
            "funcao": func,
            "descricao": descricao
        }
        return func
    return decorator


# ─── TOOL: /hora ──────────────────────────────────────────────────────────────

@registrar("/hora", "Mostra a data e hora atual do sistema")
def tool_hora(args: str) -> str:
    """
    Retorna data e hora atual formatada.
    Não precisa de argumentos.
    """
    agora = datetime.datetime.now()
    return (
        f"📅 Data: {agora.strftime('%d/%m/%Y')}\n"
        f"🕐 Hora: {agora.strftime('%H:%M:%S')}\n"
        f"📆 Dia da semana: {_dia_semana(agora.weekday())}"
    )

def _dia_semana(numero: int) -> str:
    """Converte número do dia da semana para nome em português."""
    dias = ["Segunda-feira", "Terça-feira", "Quarta-feira",
            "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]
    return dias[numero]


# ─── TOOL: /clima ─────────────────────────────────────────────────────────────

@registrar("/clima", "Mostra o clima atual de uma cidade. Uso: /clima [cidade]")
def tool_clima(args: str) -> str:
    """
    Busca o clima atual via Open-Meteo (gratuita, sem API key).
    Primeiro geocodifica a cidade, depois busca os dados climáticos.

    Args:
        args: nome da cidade (ex: "São Paulo", "Lisboa")
    """
    cidade = args.strip()
    if not cidade:
        return "❌ Informe uma cidade. Exemplo: /clima São Paulo"

    try:
        # Passo 1: Geocodificação — cidade → coordenadas (lat/lon)
        geo_url = "https://geocoding-api.open-meteo.com/v1/search"
        geo_resp = requests.get(
            geo_url,
            params={"name": cidade, "count": 1, "language": "pt"},
            timeout=5
        )
        geo_resp.raise_for_status()
        geo_dados = geo_resp.json()

        if not geo_dados.get("results"):
            return f"❌ Cidade '{cidade}' não encontrada."

        local = geo_dados["results"][0]
        lat = local["latitude"]
        lon = local["longitude"]
        nome_local = local.get("name", cidade)
        pais = local.get("country", "")

        # Passo 2: Dados climáticos via Open-Meteo
        clima_url = "https://api.open-meteo.com/v1/forecast"
        clima_resp = requests.get(
            clima_url,
            params={
                "latitude": lat,
                "longitude": lon,
                "current_weather": True,
                "hourly": "relativehumidity_2m",
                "timezone": "auto"
            },
            timeout=5
        )
        clima_resp.raise_for_status()
        clima_dados = clima_resp.json()

        atual = clima_dados["current_weather"]
        temp = atual["temperature"]
        vento = atual["windspeed"]
        codigo = atual["weathercode"]

        # Pega a umidade da hora atual
        horas = clima_dados["hourly"]["time"]
        umidades = clima_dados["hourly"]["relativehumidity_2m"]
        hora_atual = datetime.datetime.now().strftime("%Y-%m-%dT%H:00")
        umidade = "N/A"
        if hora_atual in horas:
            idx = horas.index(hora_atual)
            umidade = f"{umidades[idx]}%"

        return (
            f"🌍 {nome_local}, {pais}\n"
            f"🌡️  Temperatura: {temp}°C\n"
            f"💨 Vento: {vento} km/h\n"
            f"💧 Umidade: {umidade}\n"
            f"☁️  Condição: {_descricao_clima(codigo)}"
        )

    except requests.exceptions.ConnectionError:
        return "❌ Sem conexão com a internet para buscar o clima."
    except requests.exceptions.Timeout:
        return "❌ Tempo de resposta esgotado. Tente novamente."
    except Exception as e:
        return f"❌ Erro ao buscar clima: {e}"


def _descricao_clima(codigo: int) -> str:
    """Traduz o weather code da Open-Meteo para descrição em português."""
    tabela = {
        0: "Céu limpo ☀️",
        1: "Principalmente limpo 🌤️",
        2: "Parcialmente nublado ⛅",
        3: "Nublado ☁️",
        45: "Neblina 🌫️",
        48: "Neblina com geada 🌫️",
        51: "Garoa leve 🌦️",
        53: "Garoa moderada 🌦️",
        55: "Garoa intensa 🌧️",
        61: "Chuva leve 🌧️",
        63: "Chuva moderada 🌧️",
        65: "Chuva intensa 🌧️",
        71: "Neve leve ❄️",
        73: "Neve moderada ❄️",
        75: "Neve intensa ❄️",
        80: "Pancadas de chuva 🌦️",
        81: "Pancadas moderadas 🌦️",
        82: "Pancadas intensas ⛈️",
        95: "Tempestade ⛈️",
        99: "Tempestade com granizo ⛈️🌨️",
    }
    return tabela.get(codigo, f"Código {codigo}")


# ─── TOOL: /calc ──────────────────────────────────────────────────────────────

@registrar("/calc", "Calcula expressões matemáticas. Uso: /calc [expressão]")
def tool_calc(args: str) -> str:
    """
    Avalia expressões matemáticas com segurança.
    Usa apenas funções do módulo math — sem eval irrestrito.

    Args:
        args: expressão matemática (ex: "2 ** 10", "sqrt(144)", "cos(0)")

    Exemplos válidos:
        /calc 2 + 2
        /calc sqrt(256)
        /calc 10 ** 3 + 50
        /calc pi * 5 ** 2
    """
    expressao = args.strip()
    if not expressao:
        return "❌ Informe uma expressão. Exemplo: /calc sqrt(144)"

    # Namespace seguro — apenas funções matemáticas permitidas
    # Isso evita execução de código arbitrário via eval
    namespace_seguro = {
        "__builtins__": {},   # bloqueia builtins do Python
        **{nome: getattr(math, nome) for nome in dir(math)
           if not nome.startswith("_")},
        "abs": abs,
        "round": round,
    }

    try:
        resultado = eval(expressao, namespace_seguro)   # noqa: S307
        return f"🧮 {expressao} = {resultado}"
    except ZeroDivisionError:
        return "❌ Divisão por zero."
    except Exception:
        return f"❌ Expressão inválida: '{expressao}'"


# ─── TOOL: /ler ───────────────────────────────────────────────────────────────

@registrar("/ler", "Lê um arquivo .txt e injeta no contexto. Uso: /ler [caminho]")
def tool_ler(args: str) -> str:
    """
    Lê um arquivo .txt e retorna seu conteúdo para o contexto da IA.
    Permite conversar sobre documentos locais.

    Args:
        args: caminho do arquivo (ex: "notas.txt", "docs/relatorio.txt")

    Após chamar /ler, você pode perguntar coisas como:
        "Faça um resumo desse documento"
        "Quais são os pontos principais?"
    """
    caminho = args.strip()
    if not caminho:
        return "❌ Informe o caminho do arquivo. Exemplo: /ler notas.txt"

    if not os.path.exists(caminho):
        return f"❌ Arquivo não encontrado: '{caminho}'"

    if not caminho.endswith(".txt"):
        return "❌ Por enquanto só arquivos .txt são suportados."

    tamanho = os.path.getsize(caminho)
    limite_bytes = 50_000   # ~50KB — evita injetar arquivos gigantes no contexto

    if tamanho > limite_bytes:
        return (
            f"❌ Arquivo muito grande ({tamanho // 1024}KB). "
            f"Limite: {limite_bytes // 1024}KB."
        )

    try:
        with open(caminho, "r", encoding="utf-8") as f:
            conteudo = f.read()

        linhas = conteudo.count("\n") + 1
        return (
            f"📄 Arquivo: {caminho} ({linhas} linhas)\n"
            f"{'─' * 40}\n"
            f"{conteudo}\n"
            f"{'─' * 40}\n"
            f"✅ Arquivo carregado. Agora você pode fazer perguntas sobre ele."
        )
    except UnicodeDecodeError:
        return "❌ Não foi possível ler o arquivo (encoding não suportado)."
    except Exception as e:
        return f"❌ Erro ao ler arquivo: {e}"


# ─── TOOL: /tools ─────────────────────────────────────────────────────────────

@registrar("/tools", "Lista todos os comandos disponíveis")
def tool_tools(args: str) -> str:
    """Lista todas as tools registradas com suas descrições."""
    linhas = ["🛠️  Comandos disponíveis:\n"]
    for nome, info in TOOLS.items():
        linhas.append(f"  {nome:<20} → {info['descricao']}")
    return "\n".join(linhas)


# ─── EXECUTOR CENTRAL ─────────────────────────────────────────────────────────

def executar_tool(entrada: str) -> tuple[bool, str]:
    """
    Verifica se a entrada é um comando de tool e executa se for.

    Args:
        entrada: texto digitado pelo usuário

    Returns:
        Tupla (é_tool, resultado):
            - (True, resultado) se era um comando de tool
            - (False, "") se não era um comando
    
    Uso em chat.py:
        eh_tool, resultado = executar_tool(entrada)
        if eh_tool:
            print(resultado)
            continue
    """
    partes = entrada.strip().split(" ", 1)
    comando = partes[0].lower()
    args = partes[1] if len(partes) > 1 else ""

    if comando in TOOLS:
        resultado = TOOLS[comando]["funcao"](args)
        return True, resultado

    return False, ""
