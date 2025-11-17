#!/usr/bin/env python3
"""
크롤링 데이터 통합 스크립트
test_crawled와 another_crawled를 하나로 통합
"""
import json
import shutil
from pathlib import Path
from datetime import datetime
import hashlib

def get_url_hash(url: str) -> str:
    """URL을 해시값으로 변환"""
    return hashlib.md5(url.encode()).hexdigest()[:16]

def merge_crawled_data(
    source_dir: Path,
    target_dir: Path,
    dry_run: bool = False
):
    """
    크롤링 데이터 통합
    
    Args:
        source_dir: 원본 디렉토리 (another_crawled)
        target_dir: 대상 디렉토리 (test_crawled)
        dry_run: True면 실제 작업 없이 미리보기만
    """
    print("=" * 80)
    print("📦 크롤링 데이터 통합")
    print("=" * 80)
    print(f"\n원본: {source_dir}")
    print(f"대상: {target_dir}")
    print(f"모드: {'미리보기' if dry_run else '실제 통합'}")
    print()
    
    # 1. 기존 인덱스 로드
    target_index_file = target_dir / "crawl_index.json"
    if target_index_file.exists():
        with open(target_index_file, 'r', encoding='utf-8') as f:
            target_index = json.load(f)
        existing_urls = {page['url'] for page in target_index.get('pages', [])}
        print(f"✅ 기존 데이터: {len(existing_urls)}개 URL")
    else:
        target_index = {
            "crawl_date": datetime.now().isoformat(),
            "total_pages": 0,
            "meta": {},
            "pages": []
        }
        existing_urls = set()
        print(f"📝 새 인덱스 생성")
    
    # 2. 원본 JSON 파일 로드
    source_pages = list((source_dir / "pages").glob("*.json"))
    print(f"📂 원본 페이지: {len(source_pages)}개")
    
    # 3. 통합 처리
    stats = {
        "total": len(source_pages),
        "copied": 0,
        "skipped": 0,
        "errors": 0
    }
    
    new_pages = []
    
    for source_file in sorted(source_pages):
        try:
            # JSON 로드
            with open(source_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            url = data.get('url', '')
            
            # 중복 체크
            if url in existing_urls:
                stats["skipped"] += 1
                continue
            
            # 파일명을 URL 해시로 변경
            url_hash = get_url_hash(url)
            target_filename = f"{url_hash}.json"
            target_file = target_dir / "pages" / target_filename
            
            # JSON 구조 정규화 (test_crawled 형식에 맞추기)
            normalized_data = {
                "url": url,
                "title": data.get('title', ''),
                "text": data.get('text', ''),
                "html": data.get('html'),
                "crawled_at": data.get('crawled_at', datetime.now().isoformat()),
                "metadata": data.get('metadata', {})
            }
            
            # attachments가 있으면 metadata에 추가
            if 'attachments' in data and data['attachments']:
                normalized_data['metadata']['attachments'] = data['attachments']
                normalized_data['metadata']['attachments_count'] = len(data['attachments'])
            
            if not dry_run:
                # 파일 저장
                with open(target_file, 'w', encoding='utf-8') as f:
                    json.dump(normalized_data, f, ensure_ascii=False, indent=2)
            
            # 인덱스에 추가
            page_info = {
                "url": url,
                "file": str(target_file),
                "title": normalized_data['title'],
                "text_length": len(normalized_data['text']),
            }
            
            # 메타데이터에서 추가 정보
            metadata = normalized_data.get('metadata', {})
            if 'attachments_count' in metadata:
                page_info['attachments_count'] = metadata['attachments_count']
            
            new_pages.append(page_info)
            existing_urls.add(url)
            stats["copied"] += 1
            
        except Exception as e:
            print(f"❌ 에러: {source_file.name} - {e}")
            stats["errors"] += 1
    
    # 4. 인덱스 업데이트
    if not dry_run and new_pages:
        target_index['pages'].extend(new_pages)
        target_index['total_pages'] = len(target_index['pages'])
        target_index['last_merged'] = datetime.now().isoformat()
        
        with open(target_index_file, 'w', encoding='utf-8') as f:
            json.dump(target_index, f, ensure_ascii=False, indent=2)
    
    # 5. 결과 출력
    print("\n" + "=" * 80)
    print("📊 통합 결과")
    print("=" * 80)
    print(f"총 처리: {stats['total']}개")
    print(f"  ✅ 복사됨: {stats['copied']}개")
    print(f"  ⏭️  중복 건너뜀: {stats['skipped']}개")
    print(f"  ❌ 에러: {stats['errors']}개")
    print(f"\n최종 데이터: {len(target_index['pages'])}개 페이지")
    
    if dry_run:
        print("\n⚠️  미리보기 모드: 실제 파일은 변경되지 않았습니다.")
        print("   실제 통합하려면 --execute 옵션을 사용하세요.")
    
    print("=" * 80)
    
    return stats

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='크롤링 데이터 통합')
    parser.add_argument('--source', type=str, default='data/another_crawled',
                        help='원본 디렉토리 (기본값: data/another_crawled)')
    parser.add_argument('--target', type=str, default='data/test_crawled',
                        help='대상 디렉토리 (기본값: data/test_crawled)')
    parser.add_argument('--execute', action='store_true',
                        help='실제 통합 실행 (기본값: 미리보기)')
    
    args = parser.parse_args()
    
    source_dir = Path(args.source)
    target_dir = Path(args.target)
    
    # 디렉토리 확인
    if not source_dir.exists():
        print(f"❌ 원본 디렉토리가 없습니다: {source_dir}")
        return
    
    if not target_dir.exists():
        print(f"❌ 대상 디렉토리가 없습니다: {target_dir}")
        return
    
    # pages 폴더 확인 및 생성
    (target_dir / "pages").mkdir(exist_ok=True)
    
    # 통합 실행
    merge_crawled_data(
        source_dir=source_dir,
        target_dir=target_dir,
        dry_run=not args.execute
    )

if __name__ == "__main__":
    main()
