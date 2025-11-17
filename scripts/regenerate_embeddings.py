import numpy as np
import pandas as pd
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).parent))
from embed_providers import get_encoder, DEFAULTS

def main():
    # corpus_all.csv 로드
    corpus_path = Path(__file__).parent.parent / 'data' / 'corpus_all.csv'
    df = pd.read_csv(corpus_path)
    
    # NaN 제거 및 문자열 변환
    df = df[df['text'].notna()]
    texts = df['text'].astype(str).tolist()
    texts = [t for t in texts if t and t.strip()]
    
    print(f"총 {len(texts):,}개의 텍스트 임베딩 생성 중...")
    print(f"입력 파일: {corpus_path}")
    
    # 각 모델별로 임베딩 생성
    # API 키가 필요 없는 오픈소스 모델만 사용 (BGE만 사용)
    models = ['bge']  # BGE-M3만 사용
    
    for model in models:
        print(f"\n📦 {model} 모델 임베딩 생성 중...")
        encoder = get_encoder(model)
        embedder_name = DEFAULTS[model]
        
        # 임베딩 생성
        embeds, dim = encoder(texts, embedder_name)
        
        # 리스트인 경우 numpy 배열로 변환
        if isinstance(embeds, list):
            embeds = np.array(embeds)
        
        print(f"임베딩 shape: {embeds.shape}, dimension: {dim}")
        
        # 임베딩 저장
        output_path = Path(__file__).parent.parent / "embeddings" / f"{model}_all.npy"
        output_path.parent.mkdir(exist_ok=True)
        np.save(output_path, embeds)
        print(f"✅ 저장 완료: {output_path}")

if __name__ == "__main__":
    main()
