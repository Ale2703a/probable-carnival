# semantic_memory.py
# Responsabilidade: memória de longo prazo usando ChromaDB.
# Salva mensagens importantes como vetores e busca memórias
# relevantes para enriquecer o contexto de cada conversa.

import chromadb
from chromadb.utils import embedding_functions
import hashlib
from datetime import datetime


# ─── CONFIGURAÇÃO ─────────────────────────────────────────────────────────────

PASTA_VETORIAL  = "./memoria_vetorial"
COLECAO_NOME    = "memorias_ia"

# Tamanho mínimo de mensagem para ser salva como memória
# Mensagens curtas ("ok", "sim", "obrigado") não vale a pena guardar
MIN_CHARS_MEMORIA = 60

# Quantas memórias buscar para enriquecer o contexto
NUM_MEMORIAS_CONTEXTO = 4


# ─── CLIENTE CHROMADB ─────────────────────────────────────────────────────────

# Embedding local — usa o modelo all-MiniLM-L6-v2 (baixado automaticamente
# na primeira execução, ~80MB, roda offline depois)
_embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)

_cliente = chromadb.PersistentClient(path=PASTA_VETORIAL)

_colecao = _cliente.get_or_create_collection(
    name=COLECAO_NOME,
    embedding_function=_embedding_fn,
    metadata={"hnsw:space": "cosine"}   # similaridade por cosseno
)


# ─── FUNÇÕES PÚBLICAS ─────────────────────────────────────────────────────────

def salvar_memoria(texto: str, role: str, sessao_id: str) -> bool:
    """
    Salva uma mensagem como memória vetorial se for relevante.

    Args:
        texto:     conteúdo da mensagem
        role:      "user" ou "assistant"
        sessao_id: identificador da sessão atual (nome do arquivo .json)

    Returns:
        True se salvou, False se ignorou (mensagem muito curta).
    """
    # Ignora mensagens curtas ou de sistema
    if len(texto.strip()) < MIN_CHARS_MEMORIA:
        return False

    # Ignora mensagens que são resultados de tools (contexto interno)
    if texto.startswith("["):
        return False

    # ID único baseado no conteúdo — evita duplicatas
    id_memoria = hashlib.md5(texto.encode()).hexdigest()

    # Metadados para filtros futuros
    metadata = {
        "role":      role,
        "sessao":    sessao_id,
        "timestamp": datetime.now().isoformat(),
        "preview":   texto[:80]   # prévia para debug
    }

    try:
        # upsert = insere ou atualiza se já existir
        _colecao.upsert(
            ids=[id_memoria],
            documents=[texto],
            metadatas=[metadata]
        )
        return True
    except Exception:
        return False


def buscar_memorias(
    pergunta: str,
    n: int = NUM_MEMORIAS_CONTEXTO,
    apenas_usuario: bool = False
) -> list[dict]:
    """
    Busca as memórias mais semanticamente relevantes para uma pergunta.

    Args:
        pergunta:       texto da pergunta atual do usuário
        n:              número de memórias a retornar
        apenas_usuario: se True, busca só mensagens do usuário

    Returns:
        Lista de dicts com campos: texto, role, sessao, timestamp, score
    """
    total = _colecao.count()
    if total == 0:
        return []

    # Não pede mais do que o que existe
    n_busca = min(n, total)

    where = {"role": "user"} if apenas_usuario else None

    try:
        resultado = _colecao.query(
            query_texts=[pergunta],
            n_results=n_busca,
            where=where,
            include=["documents", "metadatas", "distances"]
        )
    except Exception:
        return []

    memorias = []
    docs      = resultado["documents"][0]
    metas     = resultado["metadatas"][0]
    distancias = resultado["distances"][0]

    for doc, meta, dist in zip(docs, metas, distancias):
        # Distância cosseno: 0 = idêntico, 2 = oposto
        # Convertemos para score 0-1 (maior = mais relevante)
        score = round(1 - (dist / 2), 3)

        # Filtra memórias pouco relevantes (score abaixo de 0.3)
        if score < 0.3:
            continue

        memorias.append({
            "texto":     doc,
            "role":      meta.get("role", "?"),
            "sessao":    meta.get("sessao", "?"),
            "timestamp": meta.get("timestamp", "?"),
            "score":     score
        })

    return memorias


def montar_contexto_memorias(pergunta: str) -> str:
    """
    Busca memórias relevantes e formata como bloco de contexto
    para injetar no system prompt.

    Args:
        pergunta: mensagem atual do usuário

    Returns:
        String formatada com memórias relevantes,
        ou string vazia se não houver nada relevante.
    """
    memorias = buscar_memorias(pergunta)
    if not memorias:
        return ""

    linhas = ["[Memórias relevantes de conversas anteriores]"]
    for m in memorias:
        data = m["timestamp"][:10] if m["timestamp"] != "?" else "?"
        papel = "Você disse" if m["role"] == "user" else "Eu disse"
        linhas.append(f"• ({data}) {papel}: {m['texto'][:200]}")

    return "\n".join(linhas)


def contar_memorias() -> int:
    """Retorna o total de memórias salvas."""
    return _colecao.count()


def listar_memorias_recentes(n: int = 10) -> list[dict]:
    """
    Lista as N memórias mais recentes para debug/inspeção.

    Args:
        n: número de memórias a retornar

    Returns:
        Lista de dicts com preview, role e timestamp.
    """
    total = _colecao.count()
    if total == 0:
        return []

    resultado = _colecao.get(
        limit=min(n, total),
        include=["metadatas"]
    )

    memorias = []
    for meta in resultado["metadatas"]:
        memorias.append({
            "preview":   meta.get("preview", ""),
            "role":      meta.get("role", "?"),
            "timestamp": meta.get("timestamp", "?")[:16],
            "sessao":    meta.get("sessao", "?")
        })

    # Ordena por timestamp decrescente
    return sorted(memorias, key=lambda x: x["timestamp"], reverse=True)
