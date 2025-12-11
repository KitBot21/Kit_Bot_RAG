#!/usr/bin/env python3
"""
새로 추가된 JSON 파일 통합
1. attachments를 metadata로 이동 (양식 통일)
2. ZIP 파일에서 첨부파일 추출 → MinIO 업로드 (출처 연결)
3. 인덱스 재생성
"""
import sys
sys.path.insert(0, 'crawler')

import json
import zipfile
from pathlib import Path
from datetime import datetime
from storage.minio_storage import MinIOStorage

def normalize_new_files(pages_dir: Path):
    """새로 추가된 JSON 파일 양식 통일"""
    print("=" * 80)
    print("📋 Step 1: JSON 양식 통일")
    print("=" * 80)
    
    json_files = list(pages_dir.glob("*.json"))
    
    stats = {
        "total": len(json_files),
        "normalized": 0,
        "already_ok": 0
    }
    
    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # attachments가 최상위에 있으면 metadata로 이동
            if 'attachments' in data:
                if 'metadata' not in data:
                    data['metadata'] = {}
                
                data['metadata']['attachments'] = data.pop('attachments')
                data['metadata']['attachments_count'] = len(data['metadata']['attachments'])
                
                # source, domain 추가
                if 'source' not in data['metadata']:
                    data['metadata']['source'] = 'new_batch'
                
                if 'domain' not in data['metadata']:
                    from urllib.parse import urlparse
                    if data.get('url'):
                        parsed = urlparse(data['url'])
                        data['metadata']['domain'] = parsed.netloc
                
                # 저장
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
                stats["normalized"] += 1
            else:
                stats["already_ok"] += 1
        
        except Exception as e:
            print(f"  ⚠️  {json_file.name}: {e}")
    
    print(f"\n✅ 양식 통일 완료:")
    print(f"   총 파일: {stats['total']}개")
    print(f"   정규화됨: {stats['normalized']}개")
    print(f"   이미 정상: {stats['already_ok']}개")
    
    return stats

def upload_zip_attachments_to_minio(zip_path: str, crawled_data_dir: Path, minio_storage):
    """ZIP 파일들에서 첨부파일 추출 → MinIO 업로드"""
    
    print("\n" + "=" * 80)
    print("📦 Step 2: ZIP 첨부파일 → MinIO 업로드")
    print("=" * 80)
    
    # zip_path가 디렉토리인 경우 모든 ZIP 파일 찾기
    zip_files = []
    zip_path_obj = Path(zip_path)
    
    if zip_path_obj.is_dir():
        zip_files = list(zip_path_obj.glob("*.zip")) + list(zip_path_obj.glob("*.ZIP")) + list(zip_path_obj.glob("*.Zip"))
        print(f"\nZIP 디렉토리: {zip_path}")
        print(f"찾은 ZIP 파일: {len(zip_files)}개")
    elif zip_path_obj.is_file():
        zip_files = [zip_path_obj]
        print(f"\nZIP 파일: {zip_path}")
    else:
        print(f"\n❌ ZIP 경로를 찾을 수 없습니다: {zip_path}")
        return
    
    # JSON 파일들에서 첨부파일 정보 수집
    file_mapping = {}  # {파일명: {page_url, download_url, original_name, size}}
    
    pages_dir = crawled_data_dir / "pages"
    for json_file in pages_dir.glob("*.json"):
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        page_url = data.get('url', '')
        attachments = data.get('metadata', {}).get('attachments', [])
        
        for att in attachments:
            saved_path = att.get('saved_path', '')
            if saved_path:
                # Windows 경로 → Unix 경로
                filename = saved_path.replace('\\', '/').split('/')[-1]
                
                file_mapping[filename] = {
                    'page_url': page_url,
                    'download_url': att.get('url', ''),
                    'original_name': att.get('name', ''),
                    'size': att.get('size', 0)
                }
    
    print(f"\nJSON에서 찾은 첨부파일 정보: {len(file_mapping)}개")
    
    # 각 ZIP 파일 처리
    total_uploaded = 0
    total_skipped = 0
    
    for zip_file in zip_files:
        try:
            print(f"\n📦 처리 중: {zip_file.name}")
            
            with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                file_list = zip_ref.namelist()
                print(f"   ZIP 내 파일: {len(file_list)}개")
                
                uploaded = 0
                skipped = 0
                
                for file_name in file_list:
                    # 디렉토리 엔트리 스킵
                    if file_name.endswith('/'):
                        continue
                    
                    # 한글 파일명 디코딩 (EUC-KR → UTF-8)
                    try:
                        # CP437로 인코딩된 것을 다시 바이트로 변환 후 EUC-KR로 디코딩
                        decoded_name = file_name.encode('cp437').decode('euc-kr')
                    except:
                        # 디코딩 실패 시 원본 사용
                        decoded_name = file_name
                    
                    # 파일명만 추출 (경로 제거)
                    base_name = decoded_name.replace('\\', '/').split('/')[-1]
                    
                    # 매핑 정보 확인
                    if base_name not in file_mapping:
                        skipped += 1
                        continue
                    
                    info = file_mapping[base_name]
                    
                    # ZIP에서 파일 읽기 (원본 file_name 사용)
                    file_data = zip_ref.read(file_name)
                    
                    # MinIO에 업로드
                    object_name = f"attachments/{base_name}"
                    minio_storage.upload_file(
                        file_data=file_data,
                        object_name=object_name,
                        content_type='application/octet-stream',
                        metadata={
                            'page-url': info['page_url'],
                            'download-url': info['download_url'],
                            'original-filename': info['original_name'],
                            'file-size': str(info['size'])
                        },
                        original_filename=info['original_name']
                    )
                    
                    uploaded += 1
                
                total_uploaded += uploaded
                total_skipped += skipped
                
                print(f"   ✅ 업로드: {uploaded}개, 스킵: {skipped}개")
        
        except Exception as e:
            print(f"\n   ❌ ZIP 파일 처리 실패 ({zip_file.name}): {e}")
            continue
    
    print(f"\n✅ 전체 MinIO 업로드 완료:")
    print(f"   총 업로드됨: {total_uploaded}개")
    print(f"   총 스킵됨: {total_skipped}개 (매핑 정보 없음)")


def regenerate_index(pages_dir: Path, index_file: Path):
    """인덱스 재생성"""
    print("\n" + "=" * 80)
    print("📑 Step 3: 인덱스 재생성")
    print("=" * 80)
    
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
            
            metadata = data.get("metadata", {})
            if "attachments_count" in metadata:
                page_info["attachments_count"] = metadata["attachments_count"]
            if "domain" in metadata:
                page_info["domain"] = metadata["domain"]
            if "source" in metadata:
                page_info["source"] = metadata["source"]
            
            pages.append(page_info)
        
        except Exception as e:
            print(f"  ⚠️  {json_file.name}: {e}")
    
    # 인덱스 저장
    index = {
        "crawl_date": datetime.now().isoformat(),
        "total_pages": len(pages),
        "meta": {
            "format_version": "1.0",
            "description": "Merged and normalized crawled data"
        },
        "pages": pages
    }
    
    with open(index_file, 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 인덱스 재생성 완료:")
    print(f"   총 페이지: {len(pages)}개")
    print(f"   저장 위치: {index_file}")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='새 JSON 파일 통합 및 첨부파일 업로드')
    parser.add_argument('--zip', type=str, help='첨부파일 ZIP 경로')
    parser.add_argument('--skip-normalize', action='store_true', help='양식 통일 건너뛰기')
    parser.add_argument('--skip-upload', action='store_true', help='첨부파일 업로드 건너뛰기')
    
    args = parser.parse_args()
    
    pages_dir = Path("data/crawled_data/pages")
    index_file = Path("data/crawled_data/crawl_index.json")
    
    # Step 1: 양식 통일
    if not args.skip_normalize:
        normalize_new_files(pages_dir)
    
    # Step 2: 첨부파일 업로드
    if not args.skip_upload and args.zip:
        minio = MinIOStorage(
            endpoint="localhost:9000",
            access_key="admin",
            secret_key="kitbot2025!",
            bucket_name="kit-attachments"
        )
        upload_zip_attachments_to_minio(args.zip, pages_dir.parent, minio)
    
    # Step 3: 인덱스 재생성
    regenerate_index(pages_dir, index_file)
    
    print("\n" + "=" * 80)
    print("🎉 모든 작업 완료!")
    print("=" * 80)

if __name__ == "__main__":
    main()
