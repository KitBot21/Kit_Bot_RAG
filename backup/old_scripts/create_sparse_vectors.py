#!/usr/bin/env python3
"""
BM25 기반 Sparse Vector 생성
Qdrant의 sparse vector 기능을 사용하여 키워드 검색 지원
"""
import numpy as np
import pandas as pd
from pathlib import Path
from collections import Counter, defaultdict
import math
import pickle
from konlpy.tag import Okt
import re

# 한국어 형태소 분석기
okt = Okt()

def tokenize_korean(text):
    """한국어 텍스트 토크나이징"""
    # 숫자, 영문, 한글만 남기고 나머지 제거
    text = re.sub(r'[^\w\s가-힣]', ' ', text)
    # 형태소 분석 (명사, 동사, 형용사만)
    tokens = okt.pos(text, norm=True, stem=True)
    words = [word for word, pos in tokens if pos in ['Noun', 'Verb', 'Adjective']]
    # 단일 문자 제거
    words = [w for w in words if len(w) > 1]
    return words

class BM25Vectorizer:
    def __init__(self, k1=1.5, b=0.75):
        self.k1 = k1
        self.b = b
        self.vocab = {}  # word -> index
        self.idf = {}    # word -> idf score
        self.avgdl = 0   # average document length
        
    def fit(self, documents):
        """BM25 파라미터 계산"""
        print(f"📊 BM25 학습 중... ({len(documents)}개 문서)")
        
        # 문서별 토큰화
        tokenized_docs = []
        doc_lengths = []
        
        for i, doc in enumerate(documents):
            if i % 100 == 0:
                print(f"  토큰화: {i}/{len(documents)}")
            tokens = tokenize_korean(doc)
            tokenized_docs.append(tokens)
            doc_lengths.append(len(tokens))
        
        self.avgdl = sum(doc_lengths) / len(doc_lengths) if doc_lengths else 0
        print(f"  평균 문서 길이: {self.avgdl:.1f} 토큰")
        
        # 어휘 구축 및 DF 계산
        word_df = Counter()  # document frequency
        all_words = set()
        
        for tokens in tokenized_docs:
            unique_tokens = set(tokens)
            all_words.update(unique_tokens)
            for word in unique_tokens:
                word_df[word] += 1
        
        # 어휘 인덱스 생성
        self.vocab = {word: idx for idx, word in enumerate(sorted(all_words))}
        print(f"  어휘 크기: {len(self.vocab):,}개 단어")
        
        # IDF 계산
        N = len(documents)
        for word, df in word_df.items():
            self.idf[word] = math.log((N - df + 0.5) / (df + 0.5) + 1.0)
        
        return tokenized_docs
    
    def transform(self, tokenized_docs):
        """BM25 sparse vector 생성"""
        print(f"\n🔢 Sparse Vector 생성 중...")
        sparse_vectors = []
        
        for i, tokens in enumerate(tokenized_docs):
            if i % 100 == 0:
                print(f"  벡터화: {i}/{len(tokenized_docs)}")
            
            doc_len = len(tokens)
            term_freq = Counter(tokens)
            
            # Sparse vector: {index: score}
            sparse_vec = {}
            for word, tf in term_freq.items():
                if word in self.vocab:
                    idx = self.vocab[word]
                    idf = self.idf.get(word, 0)
                    
                    # BM25 score
                    score = idf * (tf * (self.k1 + 1)) / (tf + self.k1 * (1 - self.b + self.b * doc_len / self.avgdl))
                    
                    if score > 0:
                        sparse_vec[idx] = score
            
            sparse_vectors.append(sparse_vec)
        
        return sparse_vectors
    
    def transform_query(self, query):
        """쿼리를 sparse vector로 변환"""
        tokens = tokenize_korean(query)
        term_freq = Counter(tokens)
        
        sparse_vec = {}
        for word, tf in term_freq.items():
            if word in self.vocab:
                idx = self.vocab[word]
                idf = self.idf.get(word, 0)
                # 쿼리는 간단히 tf * idf
                score = tf * idf
                if score > 0:
                    sparse_vec[idx] = score
        
        return sparse_vec

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--corpus', default='data/corpus_filtered.csv', help='Corpus CSV file path')
    parser.add_argument('--output', default='embeddings/bm25_filtered', help='Output prefix (without extension)')
    args = parser.parse_args()
    
    # Corpus 로드
    df = pd.read_csv(args.corpus)
    texts = df['text'].tolist()
    
    print(f"총 {len(texts)}개 문서 from {args.corpus}")
    
    # BM25 벡터화
    vectorizer = BM25Vectorizer()
    tokenized_docs = vectorizer.fit(texts)
    sparse_vectors = vectorizer.transform(tokenized_docs)
    
    # 출력 디렉토리 생성
    output_path = Path(args.output)
    output_path.parent.mkdir(exist_ok=True, parents=True)
    
    # 벡터화기 저장
    vectorizer_path = f"{args.output}_vectorizer.pkl"
    with open(vectorizer_path, 'wb') as f:
        pickle.dump(vectorizer, f)
    print(f"\n✅ BM25 벡터화기 저장: {vectorizer_path}")
    
    # Sparse vectors 저장
    vectors_path = f"{args.output}_vectors.pkl"
    with open(vectors_path, 'wb') as f:
        pickle.dump(sparse_vectors, f)
    print(f"✅ Sparse vectors 저장: {vectors_path}")
    
    # 통계 출력
    non_zero_counts = [len(vec) for vec in sparse_vectors]
    print(f"\n📊 Sparse Vector 통계")
    print(f"  평균 non-zero 요소: {np.mean(non_zero_counts):.1f}개")
    print(f"  최대 non-zero 요소: {max(non_zero_counts)}개")
    print(f"  최소 non-zero 요소: {min(non_zero_counts)}개")
    print(f"  어휘 크기: {len(vectorizer.vocab):,}개")

if __name__ == "__main__":
    main()
