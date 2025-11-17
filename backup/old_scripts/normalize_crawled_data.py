#!/usr/bin/env python3
"""
크롤링 데이터 양식 통일 스크립트
모든 JSON 파일을 동일한 구조로 변환
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

def normalize_page_data(data: Dict[str, Any], source_dir: str) -> Dict[str, Any]:
    """
    페이지 데이터를 표준 형식으로 변환
    
    표준 형식:
    {
        "url": str,
        "title": str,
        "text": str,
        "html": str | null,
        "crawled_at": str (ISO format),
        "metadata": {
            "source": str,
            "domain": str,
            "attachments": [...] (선택),
            "attachments_count": int (선택),
            ...
        }
    }
    """
    # 기본 필드
    normalized = {
        "url": data.get("url", ""),
        "title": data.get("title", ""),
        "text": data.get("text", ""),
        "html": data.get("html"),
        "crawled_at": data.get("crawled_at", datetime.now().isoformat()),
    }
    
    # 메타데이터 초기화
    metadata = data.get("metadata", {}).copy()
    
    # 도메인 추출
    if normalized["url"]:
        from urllib.parse import urlparse
        parsed = urlparse(normalized["url"])
        metadata["domain"] = parsed.netloc
    
    # 소스 정보 추가
    if "test_crawled" in source_dir:
        metadata["source"] = "test_crawled"
    elif "another_crawled" in source_dir:
        metadata["source"] = "another_crawled"
    else:
        metadata["source"] = "unknown"
    
    # attachments 처리 (최상위에 있으면 metadata로 이동)
    if "attachments" in data and data["attachments"]:
        metadata["attachments"] = data["attachments"]
        metadata["attachments_count"] = len(data["attachments"])
    
    normalized["metadata"] = metadata
    
    return normalized


def normalize_directory(
    directory: Path,
    dry_run: bool = False,
    backup: bool = True
) -> Dict[str, int]:
    """
    디렉토리의 모든 JSON 파일을 정규화
    
    Args:
        directory: 대상 디렉토리 (pages 폴더 포함)
        dry_run: True면 실제 변경 없이 미리보기만
        backup: True면 원본 백업
    
    Returns:
        통계 정보 dict
    """
    pages_dir = directory / "pages"
    
    if not pages_dir.exists():
        print(f"❌ pages 폴더 없음: {pages_dir}")
        return {}
    
    stats = {
        "total": 0,
        "normalized": 0,
        "skipped": 0,
        "errors": 0
    }
    
    json_files = list(pages_dir.glob("*.json"))
    stats["total"] = len(json_files)
    
    print(f"\n📂 디렉토리: {directory}")
    print(f"📄 JSON 파일: {len(json_files)}개")
    
    if backup and not dry_run:
        backup_dir = directory / "pages_backup"
        backup_dir.mkdir(exist_ok=True)
        print(f"💾 백업 디렉토리: {backup_dir}")
    
    for json_file in json_files:
        try:
            # JSON 로드
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 정규화
            normalized = normalize_page_data(data, str(directory))
            
            # 변경 사항 체크
            if data == normalized:
                stats["skipped"] += 1
                continue
            
            if not dry_run:
                # 백업
                if backup:
                    import shutil
                    backup_file = backup_dir / json_file.name
                    shutil.copy2(json_file, backup_file)
                
                # 저장
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(normalized, f, ensure_ascii=False, indent=2)
            
            stats["normalized"] += 1
            
        except Exception as e:
            print(f"❌ 에러: {json_file.name} - {e}")
            stats["errors"] += 1
    
    return stats


def update_index(directory: Path, dry_run: bool = False):
    """크롤 인덱스 업데이트"""
    index_file = directory / "crawl_index.json"
    pages_dir = directory / "pages"
    
    if not pages_dir.exists():
        print(f"❌ pages 폴더 없음: {pages_dir}")
        return
    
    # 모든 페이지 로드
    pages = []
    for json_file in sorted(pages_dir.glob("*.json")):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            page_info = {
                "url": data.get("url", ""),
                "file": str(json_file),
                "title": data.get("title", ""),
                "text_length": len(data.get("text", "")),
            }
            
            # 메타데이터에서 추가 정보
            metadata = data.get("metadata", {})
            if "attachments_count" in metadata:
                page_info["attachments_count"] = metadata["attachments_count"]
            if "domain" in metadata:
                page_info["domain"] = metadata["domain"]
            
            pages.append(page_info)
            
        except Exception as e:
            print(f"❌ 인덱스 업데이트 실패: {json_file.name} - {e}")
    
    # 인덱스 생성
    index = {
        "crawl_date": datetime.now().isoformat(),
        "total_pages": len(pages),
        "normalized": True,
        "meta": {
            "format_version": "1.0",
            "description": "Normalized crawled data"
        },
        "pages": pages
    }
    
    if not dry_run:
        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
        print(f"✅ 인덱스 업데이트: {index_file}")
    else:
        print(f"📝 인덱스 업데이트 예정: {len(pages)}개 페이지")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='크롤링 데이터 양식 통일')
    parser.add_argument('directories', nargs='+', help='대상 디렉토리들')
    parser.add_argument('--execute', action='store_true', help='실제 변경 실행')
    parser.add_argument('--no-backup', action='store_true', help='백업 생략')
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("📋 크롤링 데이터 양식 통일")
    print("=" * 80)
    print(f"모드: {'실제 변경' if args.execute else '미리보기'}")
    print(f"백업: {'아니오' if args.no_backup else '예'}")
    print()
    
    total_stats = {
        "total": 0,
        "normalized": 0,
        "skipped": 0,
        "errors": 0
    }
    
    for dir_path in args.directories:
        directory = Path(dir_path)
        
        if not directory.exists():
            print(f"❌ 디렉토리 없음: {directory}")
            continue
        
        # 정규화
        stats = normalize_directory(
            directory=directory,
            dry_run=not args.execute,
            backup=not args.no_backup
        )
        
        # 통계 합계
        for key in total_stats:
            total_stats[key] += stats.get(key, 0)
        
        # 인덱스 업데이트
        update_index(directory, dry_run=not args.execute)
        
        print()
    
    # 전체 결과
    print("=" * 80)
    print("📊 전체 결과")
    print("=" * 80)
    print(f"총 파일: {total_stats['total']}개")
    print(f"  ✅ 정규화됨: {total_stats['normalized']}개")
    print(f"  ⏭️  변경 없음: {total_stats['skipped']}개")
    print(f"  ❌ 에러: {total_stats['errors']}개")
    
    if not args.execute:
        print("\n⚠️  미리보기 모드: 실제 파일은 변경되지 않았습니다.")
        print("   실제 변경하려면 --execute 옵션을 사용하세요.")
    
    print("=" * 80)


if __name__ == "__main__":
    main()
