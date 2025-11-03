from __future__ import annotations
import os
from typing import List, Callable, Tuple

# ===== 기본 모델명 (환경변수로 덮어쓰기 가능) =====
DEFAULTS = {
    "e5":      os.getenv("E5_MODEL", "intfloat/multilingual-e5-base"),   # ~768d
    "bge":     os.getenv("BGE_MODEL", "BAAI/bge-m3"),                    # ~1024d
    "openai":  os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-large"),
    "upstage": os.getenv("UPSTAGE_EMBED_MODEL", "solar-embedding-1-large"),
}

# ===== BGE / E5 (Sentence-Transformers) =====
def _encode_sbert(texts: List[str], model_name: str, batch_size: int = None) -> Tuple[List[List[float]], int]:
    from sentence_transformers import SentenceTransformer
    m = SentenceTransformer(model_name)
    bs = batch_size or int(os.getenv("SBERT_BATCH", "32"))
    vecs = m.encode(texts, batch_size=bs, show_progress_bar=True, normalize_embeddings=True).tolist()
    return vecs, m.get_sentence_embedding_dimension()

def _encode_bge(texts: List[str], model_name: str) -> Tuple[List[List[float]], int]:
    return _encode_sbert(texts, model_name)

def _encode_e5(texts: List[str], model_name: str) -> Tuple[List[List[float]], int]:
    return _encode_sbert(texts, model_name)

# ===== OpenAI =====
def _encode_openai(texts: List[str], model_name: str) -> Tuple[List[List[float]], int]:
    from openai import OpenAI
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY가 설정되어 있지 않습니다.")
    client = OpenAI(api_key=api_key)

    out: List[List[float]] = []
    B = int(os.getenv("OPENAI_BATCH", "256"))
    for i in range(0, len(texts), B):
        batch = texts[i:i+B]
        resp = client.embeddings.create(model=model_name, input=batch)
        out.extend([d.embedding for d in resp.data])

    dim = len(out[0]) if out else 0
    return out, dim

# ===== Upstage (REST; OpenAI 유사 포맷 가정) =====
def _encode_upstage(texts: List[str], model_name: str) -> Tuple[List[List[float]], int]:
    import requests
    api_key = os.getenv("UPSTAGE_API_KEY")
    if not api_key:
        raise RuntimeError("UPSTAGE_API_KEY가 설정되어 있지 않습니다.")
    endpoint = os.getenv("UPSTAGE_EMBED_ENDPOINT", "https://api.upstage.ai/v1/embeddings")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    out: List[List[float]] = []
    B = int(os.getenv("UPSTAGE_BATCH", "64"))
    timeout = int(os.getenv("UPSTAGE_TIMEOUT", "60"))

    for i in range(0, len(texts), B):
        batch = texts[i:i+B]
        r = requests.post(endpoint, json={"model": model_name, "input": batch}, headers=headers, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        # 응답이 {"data":[{"embedding":[...]}...]} 형태라고 가정
        out.extend([item["embedding"] for item in data["data"]])

    dim = len(out[0]) if out else 0
    return out, dim

# ===== Public API 1: ingest_multi.py 호환 (권장) =====
def get_encoder(provider: str) -> Callable[[List[str], str], Tuple[List[List[float]], int]]:
    """
    사용법:
        encoder = get_encoder("bge")
        vectors, dim = encoder(texts, model_name)
    """
    p = provider.lower()
    if p == "bge":     return _encode_bge
    if p == "e5":      return _encode_e5
    if p == "openai":  return _encode_openai
    if p == "upstage": return _encode_upstage
    raise ValueError(f"Unknown provider: {provider}")

# ===== Public API 2: (선택) 임베딩함수/차원함수 분리 버전 =====
def _dim_by_single_call(encode_fn: Callable[[List[str], str], Tuple[List[List[float]], int]], model_name: str) -> int:
    vecs, dim = encode_fn(["__dim_probe__"], model_name)
    return dim if dim else len(vecs[0])

def get_embedder(provider: str):
    """
    사용법:
        embed, dim_fn, default_model = get_embedder("bge")
        vecs = embed(list_of_texts, default_model)
        d = dim_fn(default_model)
    """
    enc = get_encoder(provider)
    default_model = DEFAULTS[provider.lower()]

    def embed(texts: List[str], model_name: str = None) -> List[List[float]]:
        m = model_name or default_model
        vecs, _ = enc(texts, m)
        return vecs

    def dim_fn(model_name: str = None) -> int:
        m = model_name or default_model
        return _dim_by_single_call(enc, m)

    return embed, dim_fn, default_model