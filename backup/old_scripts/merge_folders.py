#!/usr/bin/env python3
"""
크롤링 데이터 폴더 통합
test_crawled + another_crawled → crawled_data (통합)
"""
import json
import shutil
from pathlib import Path
from datetime import datetime

def merge_folders(
    source_dirs: list,
    target_dir: Path,
    dry_run: bool = False
) -> dict:
    """
    여러 크롤링 폴더를 하나로 통합
    
    Args:
        source_dirs: 원본 디렉토리 리스트
        target_dir: 통합 대상 디렉토리
        dry_run: True면 미리보기만
    
    Returns:
        통계 정보
    """
    stats = {
        "total_files": 0,
        "copied": 0,
        "duplicates": 0,
        "errors": 0
    }
    
    # URL 중복 체크용
    seen_urls = set()
    all_pages = []
    
    print("=" * 80)
    print("📦 크롤링 데이터 폴더 통합")
    print("=" * 80)
    print(f"통합 대상: {target_dir}")
    print(f"모드: {'미리보기' if dry_run else '실제 통합'}")
    print()
    
    # 대상 폴더 생성
    if not dry_run:
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "pages").mkdir(exist_ok=True)
    
    # 각 원본 폴더 처리
    for source_dir in source_dirs:
        source_path = Path(source_dir)
        pages_dir = source_path / "pages"
        
        if not pages_dir.exists():
            print(f"⚠️  pages 폴더 없음: {pages_dir}")
            continue
        
        print(f"📂 처리 중: {source_path.name}")
        
        json_files = list(pages_dir.glob("*.json"))
        stats["total_files"] += len(json_files)
        
        for json_file in json_files:
            try:
                # JSON 로드
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                url = data.get("url", "")
                
                # 중복 체크
                if url in seen_urls:
                    stats["duplicates"] += 1
                    print(f"   ⏭️  중복: {json_file.name}")
                    continue
                
                seen_urls.add(url)
                
                # 파일 복사
                if not dry_run:
                    target_file = target_dir / "pages" / json_file.name
                    shutil.copy2(json_file, target_file)
                
                # 페이지 정보 수집
                page_info = {
                    "url": url,
                    "file": str(target_dir / "pages" / json_file.name),
                    "title": data.get("title", ""),
                    "text_length": len(data.get("text", "")),
                    "source": data.get("metadata", {}).get("source", "unknown")
                }
                
                metadata = data.get("metadata", {})
                if "attachments_count" in metadata:
                    page_info["attachments_count"] = metadata["attachments_count"]
                if "domain" in metadata:
                    page_info["domain"] = metadata["domain"]
                
                all_pages.append(page_info)
                stats["copied"] += 1
                
            except Exception as e:
                print(f"   ❌ 에러: {json_file.name} - {e}")
                stats["errors"] += 1
        
        print(f"   ✅ 완료: {len(json_files)}개 파일 처리")
        print()
    
    # 통합 인덱스 생성
    if not dry_run:
        index = {
            "crawl_date": datetime.now().isoformat(),
            "total_pages": len(all_pages),
            "sources": list(set(p["source"] for p in all_pages)),
            "meta": {
                "format_version": "1.0",
                "description": "Merged crawled data from multiple sources",
                "merged_at": datetime.now().isoformat()
            },
            "pages": all_pages
        }
        
        index_file = target_dir / "crawl_index.json"
        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 통합 인덱스 생성: {index_file}")
    else:
        print(f"📝 통합 인덱스 예정: {len(all_pages)}개 페이지")
    
    # 결과 출력
    print()
    print("=" * 80)
    print("📊 통합 결과")
    print("=" * 80)
    print(f"총 파일: {stats['total_files']}개")
    print(f"  ✅ 복사됨: {stats['copied']}개")
    print(f"  ⏭️  중복 제외: {stats['duplicates']}개")
    print(f"  ❌ 에러: {stats['errors']}개")
    print(f"\n최종 데이터: {len(all_pages)}개 페이지")
    
    if not dry_run:
        print(f"\n💾 저장 위치: {target_dir}")
    else:
        print("\n⚠️  미리보기 모드: 실제 파일은 생성되지 않았습니다.")
        print("   실제 통합하려면 --execute 옵션을 사용하세요.")
    
    print("=" * 80)
    
    return stats


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='크롤링 데이터 폴더 통합')
    parser.add_argument('--sources', nargs='+', 
                        default=['data/test_crawled', 'data/another_crawled'],
                        help='원본 디렉토리들')
    parser.add_argument('--target', type=str, default='data/crawled_data',
                        help='통합 대상 디렉토리')
    parser.add_argument('--execute', action='store_true',
                        help='실제 통합 실행')
    
    args = parser.parse_args()
    
    source_dirs = args.sources
    target_dir = Path(args.target)
    
    # 원본 폴더 확인
    for source in source_dirs:
        if not Path(source).exists():
            print(f"❌ 원본 폴더 없음: {source}")
            return
    
    # 통합 실행
    merge_folders(
        source_dirs=source_dirs,
        target_dir=target_dir,
        dry_run=not args.execute
    )


if __name__ == "__main__":
    main()
