from __future__ import annotations
import os
from typing import List, Callable, Tuple
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(dotenv_path=Path.cwd()/".env")  # 실행 디렉터리 기준

# ===== 기본 모델명 (환경변수로 덮어쓰기 가능) =====
DEFAULTS = {
    "e5":      os.getenv("E5_MODEL", "intfloat/multilingual-e5-base"),
    "bge":     os.getenv("BGE_MODEL", "BAAI/bge-m3"),
    "openai":  os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-large"),
    "upstage": os.getenv("UPSTAGE_EMBED_MODEL", "solar-embedding-1-large-passage"),
    "kosimcse": os.getenv("KOSIMCSE_MODEL", "BM-K/KoSimCSE-roberta"),
    "krsbert": os.getenv("KRSBERT_MODEL", "jhgan/ko-sbert-nli"),
}

# ===== BGE / E5 (Sentence-Transformers) =====
def _encode_sbert(texts: List[str], model_name: str, batch_size: int = None) -> Tuple[List[List[float]], int]:
    from sentence_transformers import SentenceTransformer

    # device 결정: SBERT_DEVICE가 있으면 우선, 없으면 CUDA 자동 감지
    device = os.getenv("SBERT_DEVICE")
    if not device:
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            device = "cpu"

    m = SentenceTransformer(model_name, device=device)

    bs = batch_size or int(os.getenv("SBERT_BATCH", "32"))
    vecs = m.encode(
        texts,
        batch_size=bs,
        show_progress_bar=True,
        normalize_embeddings=True
    ).tolist()

    return vecs, m.get_sentence_embedding_dimension()

def _encode_bge(texts: List[str], model_name: str) -> Tuple[List[List[float]], int]:
    return _encode_sbert(texts, model_name)

def _encode_e5(texts: List[str], model_name: str) -> Tuple[List[List[float]], int]:
    return _encode_sbert(texts, model_name)

# ===== KoSimCSE / KR-SBERT (한글 특화 모델) =====
def _encode_kosimcse(texts: List[str], model_name: str) -> Tuple[List[List[float]], int]:
    return _encode_sbert(texts, model_name)

def _encode_krsbert(texts: List[str], model_name: str) -> Tuple[List[List[float]], int]:
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

    # ★ 추가: 정규화
    out = _l2_normalize(out)
    dim = len(out[0]) if out else 0
    return out, dim

# ===== Upstage (REST; OpenAI 유사 포맷 가정) =====
def _encode_upstage(texts: List[str], model_name: str) -> Tuple[List[List[float]], int]:
    import requests
    api_key = os.getenv("UPSTAGE_API_KEY")
    if not api_key:
        raise RuntimeError("UPSTAGE_API_KEY가 설정되어 있지 않습니다.")
    endpoint = os.getenv("UPSTAGE_EMBED_ENDPOINT", "https://api.upstage.ai/v1/solar/embeddings")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    out: List[List[float]] = []
    B = int(os.getenv("UPSTAGE_BATCH", "64"))
    timeout = int(os.getenv("UPSTAGE_TIMEOUT", "60"))

    for i in range(0, len(texts), B):
        batch = texts[i:i+B]
        r = requests.post(endpoint, json={"model": model_name, "input": batch}, headers=headers, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        out.extend([item["embedding"] for item in data["data"]])

    # ★ 추가: 정규화
    out = _l2_normalize(out)
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
    if p == "kosimcse": return _encode_kosimcse
    if p == "krsbert": return _encode_krsbert
    else:
        raise ValueError(f"Unknown provider: {provider}")

    # ★ 문서 인덱싱 전처리 래핑
    def wrapped(texts: List[str], model_name: str) -> Tuple[List[List[float]], int]:
        prepped = _prep_docs(texts, provider)
        return base(prepped, model_name)

    return wrapped

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

# ===== Public API 3: 문서 전처리 함수 =====
def _prep_docs(texts: List[str], provider: str) -> List[str]:
    p = provider.lower()
    if p == "e5":
        # e5는 문서에 "passage: " 권장
        return ["passage: " + t for t in texts]
    # bge 문서는 접두어 없음 (쿼리에서만 프롬프트)
    # openai/upstage는 그대로
    return texts

def _l2_normalize(vecs: List[List[float]]) -> List[List[float]]:
    # numpy 없이도 가능하지만, 성능 때문에 numpy 권장
    try:
        import numpy as np
        arr = np.asarray(vecs, dtype="float32")
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return (arr / norms).tolist()
    except Exception:
        out = []
        for v in vecs:
            s = sum(x*x for x in v) ** 0.5 or 1.0
            out.append([x/s for x in v])
        return out

