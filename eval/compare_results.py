#!/usr/bin/env python3
"""
실험 결과 비교 스크립트 (독립 실행)
"""

import pandas as pd
import json
from pathlib import Path
from datetime import datetime

def compare_results():
    """결과 비교 및 출력"""
    print("\n" + "="*80)
    print("📊 최종 결과 비교")
    print("="*80 + "\n")
    
    results = {}
    timing_results = {}
    
    # 각 결과 파일 로드
    files = {
        "베이스라인 (Boost)": "eval/evaluation_result.csv",
        "하이브리드 (BM25+Semantic)": "eval/evaluation_result_hybrid.csv",
        "리랭커 (BGE-reranker)": "eval/evaluation_result_reranker.csv",
        "Full (Hybrid+Reranker)": "eval/evaluation_result_full.csv",
    }
    
    timing_files = {
        "베이스라인 (Boost)": "eval/timing_result.json",
        "하이브리드 (BM25+Semantic)": "eval/timing_result_hybrid.json",
        "리랭커 (BGE-reranker)": "eval/timing_result_reranker.json",
        "Full (Hybrid+Reranker)": "eval/timing_result_full.json",
    }
    
    for name, filepath in files.items():
        path = Path(filepath)
        if path.exists():
            try:
                df = pd.read_csv(path)
                results[name] = {
                    'context_precision': df['context_precision'].mean(),
                    'context_recall': df['context_recall'].mean(),
                    'faithfulness': df['faithfulness'].mean(),
                    'answer_relevancy': df['answer_relevancy'].mean(),
                }
                print(f"✅ {name}: 로드 완료")
            except Exception as e:
                print(f"⚠️ {name} 결과 로드 실패: {e}")
        else:
            print(f"❌ {name}: 파일 없음 ({filepath})")
    
    # 응답 시간 데이터 로드
    for name, filepath in timing_files.items():
        path = Path(filepath)
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    timing_data = json.load(f)
                    timing_results[name] = timing_data
            except Exception as e:
                print(f"⚠️ {name} 응답 시간 로드 실패: {e}")
    
    if not results:
        print("❌ 비교할 결과가 없습니다.")
        return
    
    print()
    
    # 결과 테이블 생성
    comparison_df = pd.DataFrame(results).T
    comparison_df = comparison_df.round(4)
    
    print(comparison_df.to_string())
    print("\n")
    
    # 응답 시간 테이블 생성
    if timing_results:
        print("\n" + "="*80)
        print("⏱️ 응답 시간 비교")
        print("="*80 + "\n")
        
        timing_df_data = {}
        for name, timing in timing_results.items():
            timing_df_data[name] = {
                '평균 (sec)': timing.get('avg_response_time', 0),
                '중앙값 (sec)': timing.get('median_response_time', 0),
                '최소 (sec)': timing.get('min_response_time', 0),
                '최대 (sec)': timing.get('max_response_time', 0),
            }
        
        timing_df = pd.DataFrame(timing_df_data).T
        timing_df = timing_df.round(4)
        print(timing_df.to_string())
        print("\n")
    
    # 개선율 계산 (베이스라인 대비)
    if "베이스라인 (Boost)" in results:
        baseline = results["베이스라인 (Boost)"]
        print("📈 베이스라인 대비 개선율:\n")
        
        for name, scores in results.items():
            if name == "베이스라인 (Boost)":
                continue
            
            print(f"[{name}]")
            for metric in ['context_precision', 'context_recall', 'faithfulness', 'answer_relevancy']:
                baseline_score = baseline[metric]
                current_score = scores[metric]
                if baseline_score > 0:
                    improvement = ((current_score - baseline_score) / baseline_score) * 100
                    symbol = "📈" if improvement > 0 else "📉" if improvement < 0 else "➡️"
                    print(f"  {symbol} {metric}: {improvement:+.2f}%")
            print()
    
    # 결과 저장
    save_path = Path("eval/comparison_result.csv")
    comparison_df.to_csv(save_path, encoding="utf-8-sig")
    print(f"✅ 비교 결과 저장: {save_path}")
    
    # 응답 시간 저장
    if timing_results:
        timing_save_path = Path("eval/comparison_timing.csv")
        timing_df.to_csv(timing_save_path, encoding="utf-8-sig")
        print(f"✅ 응답 시간 저장: {timing_save_path}")
    
    # 마크다운 리포트 생성
    report_path = Path("eval/comparison_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"# RAG 검색 방법 비교 실험 결과\n\n")
        f.write(f"**실험 일시**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("## 📊 성능 비교\n\n")
        f.write(comparison_df.to_markdown())
        f.write("\n\n")
        
        # 응답 시간 테이블 추가
        if timing_results:
            f.write("## ⏱️ 응답 시간 비교\n\n")
            f.write(timing_df.to_markdown())
            f.write("\n\n")
        
        f.write("## 📈 베이스라인 대비 개선율\n\n")
        
        if "베이스라인 (Boost)" in results:
            baseline = results["베이스라인 (Boost)"]
            for name, scores in results.items():
                if name == "베이스라인 (Boost)":
                    continue
                
                f.write(f"### {name}\n\n")
                for metric in ['context_precision', 'context_recall', 'faithfulness', 'answer_relevancy']:
                    baseline_score = baseline[metric]
                    current_score = scores[metric]
                    if baseline_score > 0:
                        improvement = ((current_score - baseline_score) / baseline_score) * 100
                        symbol = "📈" if improvement > 0 else "📉" if improvement < 0 else "➡️"
                        f.write(f"- {symbol} **{metric}**: {improvement:+.2f}%\n")
                f.write("\n")
    
    print(f"✅ 마크다운 리포트 저장: {report_path}\n")
    
    # 최고 성능 버전 찾기
    print("🏆 최고 성능 버전:")
    for metric in ['context_precision', 'context_recall', 'faithfulness', 'answer_relevancy']:
        best_name = max(results.items(), key=lambda x: x[1][metric])[0]
        best_score = results[best_name][metric]
        print(f"   {metric}: {best_name} ({best_score:.4f})")


if __name__ == "__main__":
    compare_results()
