import numpy as np
import pandas as pd
from pathlib import Path
from embed_providers import get_encoder, DEFAULTS
from dotenv import load_dotenv

load_dotenv()  # .env 파일 로드

def main():
    # CSV 파일 읽기
    df = pd.read_csv("data/corpus_with_sources.csv")
    texts = df['text'].tolist()
    
    # embeddings 디렉토리 생성
    Path("embeddings").mkdir(exist_ok=True)
    
    # 지원하는 모든 모델로 임베딩 생성
    providers = ["bge", "e5", "openai", "upstage"]
    
    for provider in providers:
        print(f"\n=== {provider} 임베딩 시작 ===")
        
        # 임베더 가져오기
        encoder = get_encoder(provider)
        model_name = DEFAULTS[provider]
        
        # 임베딩 생성
        vectors, dim = encoder(texts, model_name)
        
        # 결과 저장
        output_path = f"embeddings/{provider}.npy"
        np.save(output_path, np.array(vectors))
        print(f"✅ 저장 완료: {output_path} (dimension={dim})")

if __name__ == "__main__":
    main()