#!/usr/bin/env python3
"""
ZIP 파일 처리 및 MinIO 업로드
ZIP 파일을 압축 해제하고 개별 파일을 MinIO에 업로드
"""
import sys
sys.path.insert(0, 'crawler')

import zipfile
from pathlib import Path
from storage.minio_storage import MinIOStorage

def process_zip_to_minio(zip_path: Path, minio_folder: str = "attachments"):
    """
    ZIP 파일을 압축 해제하고 MinIO에 업로드
    
    Args:
        zip_path: ZIP 파일 경로
        minio_folder: MinIO 내 저장 폴더
    """
    print("=" * 80)
    print("📦 ZIP 파일 처리 및 MinIO 업로드")
    print("=" * 80)
    
    if not zip_path.exists():
        print(f"❌ ZIP 파일이 없습니다: {zip_path}")
        return
    
    # MinIO 연결
    minio = MinIOStorage(
        endpoint="localhost:9000",
        access_key="admin",
        secret_key="kitbot2025!",
        bucket_name="kit-attachments"
    )
    
    print(f"\n📂 ZIP 파일: {zip_path}")
    print(f"📦 MinIO 폴더: {minio_folder}/")
    
    # ZIP 압축 해제
    stats = {
        "total": 0,
        "uploaded": 0,
        "skipped": 0,
        "errors": 0
    }
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            file_list = zf.namelist()
            stats["total"] = len(file_list)
            
            print(f"\n📋 ZIP 내 파일: {len(file_list)}개")
            print(f"\n⏳ 업로드 중...\n")
            
            for filename in file_list:
                # 폴더는 건너뛰기
                if filename.endswith('/'):
                    stats["skipped"] += 1
                    continue
                
                # 숨김 파일 건너뛰기
                if filename.startswith('.') or '/__MACOSX/' in filename:
                    stats["skipped"] += 1
                    continue
                
                try:
                    # 파일 읽기
                    file_data = zf.read(filename)
                    
                    # 파일명 정리 (경로 제거, 한글 파일명 유지)
                    clean_filename = Path(filename).name
                    
                    # MinIO 객체명
                    object_name = f"{minio_folder}/{clean_filename}"
                    
                    # Content-Type 추정
                    ext = Path(filename).suffix.lower()
                    content_type_map = {
                        '.pdf': 'application/pdf',
                        '.hwp': 'application/x-hwp',
                        '.doc': 'application/msword',
                        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                        '.xls': 'application/vnd.ms-excel',
                        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                        '.ppt': 'application/vnd.ms-powerpoint',
                        '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
                        '.zip': 'application/zip',
                        '.jpg': 'image/jpeg',
                        '.jpeg': 'image/jpeg',
                        '.png': 'image/png',
                        '.gif': 'image/gif',
                    }
                    content_type = content_type_map.get(ext, 'application/octet-stream')
                    
                    # MinIO 업로드
                    success, result = minio.upload_file(
                        file_data=file_data,
                        object_name=object_name,
                        content_type=content_type,
                        original_filename=clean_filename,
                        metadata={
                            "source": "zip_extraction",
                            "zip_file": zip_path.name,
                            "original_path": filename
                        }
                    )
                    
                    if success:
                        stats["uploaded"] += 1
                        print(f"✅ {clean_filename} ({len(file_data):,} bytes)")
                    else:
                        stats["errors"] += 1
                        print(f"❌ {clean_filename}: {result}")
                
                except Exception as e:
                    stats["errors"] += 1
                    print(f"❌ {filename}: {e}")
    
    except Exception as e:
        print(f"\n❌ ZIP 파일 처리 실패: {e}")
        return
    
    # 결과
    print("\n" + "=" * 80)
    print("📊 결과")
    print("=" * 80)
    print(f"총 파일: {stats['total']}개")
    print(f"  ✅ 업로드 성공: {stats['uploaded']}개")
    print(f"  ⏭️  건너뜀: {stats['skipped']}개")
    print(f"  ❌ 에러: {stats['errors']}개")
    print("=" * 80)

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='ZIP 파일 압축 해제 및 MinIO 업로드')
    parser.add_argument('zip_file', help='ZIP 파일 경로')
    parser.add_argument('--folder', default='attachments', help='MinIO 저장 폴더 (기본: attachments)')
    
    args = parser.parse_args()
    
    zip_path = Path(args.zip_file)
    process_zip_to_minio(zip_path, args.folder)

if __name__ == "__main__":
    main()
