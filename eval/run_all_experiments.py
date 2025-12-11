#!/usr/bin/env python3
"""
RAG 검색 방법 비교 실험 스크립트

4가지 버전을 순차적으로 실행하여 성능을 비교합니다:
1. 베이스라인 (기존 Boost 기반 검색)
2. 하이브리드 검색 (BM25 + Semantic)
3. 리랭커 (BGE-reranker-v2-m3)
4. Full (하이브리드 + 리랭커)
"""

import subprocess
import sys
import pandas as pd
from pathlib import Path
from datetime import datetime

def run_evaluation(script_name, version_name):
    """평가 스크립트 실행"""
    print("\n" + "="*80)
    print(f"🚀 [{version_name}] 평가 시작...")
    print("="*80)
    
    script_path = Path(__file__).parent / script_name
    
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(Path(__file__).parent.parent),
            capture_output=True,
            text=True,
            timeout=1800  # 30분 타임아웃
        )
        
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        if result.returncode == 0:
            print(f"✅ [{version_name}] 평가 완료!")
            return True
        else:
            print(f"❌ [{version_name}] 평가 실패 (exit code: {result.returncode})")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"⏰ [{version_name}] 타임아웃 (30분 초과)")
        return False
    except Exception as e:
        print(f"❌ [{version_name}] 에러 발생: {e}")
        return False


def compare_results():
    """결과 비교 및 출력"""
    print("\n" + "="*80)
    print("📊 최종 결과 비교")
    print("="*80 + "\n")
    
    results = {}
    
    # 각 결과 파일 로드
    files = {
        "베이스라인 (Boost)": "eval/evaluation_result.csv",
        "하이브리드 (BM25+Semantic)": "eval/evaluation_result_hybrid.csv",
        "리랭커 (BGE-reranker)": "eval/evaluation_result_reranker.csv",
        "Full (Hybrid+Reranker)": "eval/evaluation_result_full.csv",
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
            except Exception as e:
                print(f"⚠️ {name} 결과 로드 실패: {e}")
    
    if not results:
        print("❌ 비교할 결과가 없습니다.")
        return
    
    # 결과 테이블 생성
    comparison_df = pd.DataFrame(results).T
    comparison_df = comparison_df.round(4)
    
    print(comparison_df.to_string())
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
    
    # 마크다운 리포트 생성
    report_path = Path("eval/comparison_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"# RAG 검색 방법 비교 실험 결과\n\n")
        f.write(f"**실험 일시**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("## 📊 성능 비교\n\n")
        f.write(comparison_df.to_markdown())
        f.write("\n\n## 📈 베이스라인 대비 개선율\n\n")
        
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
    
    print(f"✅ 마크다운 리포트 저장: {report_path}")


def main():
    print("🎯 RAG 검색 방법 비교 실험 시작")
    print("=" * 80)
    print("실험 버전:")
    print("  1. 베이스라인 (Boost 기반)")
    print("  2. 하이브리드 (BM25 + Semantic)")
    print("  3. 리랭커 (BGE-reranker-v2-m3)")
    print("  4. Full (하이브리드 + 리랭커)")
    print("=" * 80)
    
    # 베이스라인은 이미 실행되었다고 가정 (evaluation_result.csv 존재)
    baseline_exists = Path("eval/evaluation_result.csv").exists()
    
    if not baseline_exists:
        print("\n⚠️ 베이스라인 결과가 없습니다. 먼저 실행합니다...")
        run_evaluation("evaluate_rag.py", "베이스라인 (Boost)")
    else:
        print("\n✅ 베이스라인 결과 존재 (건너뛰기)")
    
    # 나머지 3개 버전 실행
    experiments = [
        ("evaluate_rag_hybrid.py", "하이브리드 (BM25+Semantic)"),
        ("evaluate_rag_reranker.py", "리랭커 (BGE-reranker)"),
        ("evaluate_rag_full.py", "Full (Hybrid+Reranker)"),
    ]
    
    success_count = 0
    for script, name in experiments:
        if run_evaluation(script, name):
            success_count += 1
    
    print("\n" + "="*80)
    print(f"🎉 실험 완료! ({success_count}/{len(experiments)}개 성공)")
    print("="*80)
    
    # 결과 비교
    compare_results()
    
    print("\n✨ 모든 실험이 완료되었습니다!")


if __name__ == "__main__":
    main()
