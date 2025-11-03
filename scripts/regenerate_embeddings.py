import numpy as np
import pandas as pd
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).parent))
from embed_providers import get_encoder, DEFAULTS

def main():
    # corpus_with_sources.csv 로드
    df = pd.read_csv('../data/corpus_with_sources.csv')
    texts = df['text'].tolist()
    
    print(f"총 {len(texts)}개의 텍스트 임베딩 생성 중...")
    
    # 각 모델별로 임베딩 생성
    # API 키가 필요 없는 오픈소스 모델만 사용
    models = ['bge', 'e5', 'kosimcse', 'krsbert']
    
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
        output_path = Path(f"../embeddings/{model}.npy")
        output_path.parent.mkdir(exist_ok=True)
        np.save(output_path, embeds)
        print(f"✅ 저장 완료: {output_path}")

if __name__ == "__main__":
    main()
