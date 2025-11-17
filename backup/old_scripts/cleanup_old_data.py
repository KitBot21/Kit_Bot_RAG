#!/usr/bin/env python3
"""
크롤링 데이터 정리 스크립트
통합된 crawled_data만 남기고 원본 폴더 삭제
"""
import shutil
from pathlib import Path

def cleanup_crawled_data(dry_run=True):
    """
    원본 크롤링 폴더 정리
    
    Args:
        dry_run: True면 미리보기만, False면 실제 삭제
    """
    print("=" * 80)
    print("🗑️  크롤링 데이터 정리")
    print("=" * 80)
    print(f"모드: {'미리보기' if dry_run else '실제 삭제'}")
    print()
    
    # 삭제 대상 폴더
    folders_to_delete = [
        Path("data/test_crawled"),
        Path("data/another_crawled")
    ]
    
    # 유지할 폴더
    keep_folder = Path("data/crawled_data")
    
    if not keep_folder.exists():
        print("❌ 통합 데이터 폴더가 없습니다: data/crawled_data/")
        print("   먼저 데이터를 통합하세요!")
        return
    
    total_size = 0
    
    print("📂 삭제 대상:")
    for folder in folders_to_delete:
        if folder.exists():
            # 폴더 크기 계산
            size = sum(f.stat().st_size for f in folder.rglob('*') if f.is_file())
            total_size += size
            
            file_count = len(list(folder.rglob('*.json')))
            
            print(f"\n  {folder}/")
            print(f"    - JSON 파일: {file_count}개")
            print(f"    - 총 크기: {size / (1024**2):.1f} MB")
            
            if not dry_run:
                shutil.rmtree(folder)
                print(f"    ✅ 삭제 완료")
        else:
            print(f"\n  {folder}/ (없음)")
    
    # 통합 데이터 확인
    print(f"\n✅ 유지:")
    crawled_files = len(list(keep_folder.glob('pages/*.json')))
    print(f"  {keep_folder}/")
    print(f"    - JSON 파일: {crawled_files}개")
    
    print("\n" + "=" * 80)
    print("📊 요약:")
    print(f"  삭제할 크기: {total_size / (1024**2):.1f} MB")
    print(f"  유지할 데이터: {keep_folder}/ ({crawled_files}개 파일)")
    
    if dry_run:
        print("\n⚠️  미리보기 모드: 실제 삭제되지 않았습니다.")
        print("   실제 삭제하려면 --execute 옵션을 사용하세요.")
    else:
        print("\n✅ 정리 완료!")
    
    print("=" * 80)

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='크롤링 데이터 정리')
    parser.add_argument('--execute', action='store_true',
                        help='실제 삭제 실행 (기본값: 미리보기)')
    
    args = parser.parse_args()
    
    cleanup_crawled_data(dry_run=not args.execute)

if __name__ == "__main__":
    main()
