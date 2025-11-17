#!/usr/bin/env python3
"""
로컬 디렉토리의 파일들을 MinIO에 업로드하는 헬퍼 스크립트
"""
import os
import sys
import argparse
from pathlib import Path
from minio import Minio
from minio.error import S3Error
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

def upload_to_minio(source_dir: Path, minio_config: dict, prefix: str = ""):
    """
    로컬 디렉토리의 파일들을 MinIO에 업로드
    
    Args:
        source_dir: 업로드할 소스 디렉토리
        minio_config: MinIO 설정
        prefix: MinIO 내 경로 prefix (예: "2025/")
    """
    try:
        print("=" * 80)
        print("📤 MinIO 파일 업로드 시작")
        print("=" * 80)
        
        # MinIO 클라이언트 생성
        client = Minio(
            minio_config['endpoint'],
            access_key=minio_config['access_key'],
            secret_key=minio_config['secret_key'],
            secure=minio_config.get('secure', False)
        )
        
        bucket = minio_config['bucket']
        
        # 버킷 존재 확인
        if not client.bucket_exists(bucket):
            print(f"⚠️  버킷이 존재하지 않습니다: {bucket}")
            response = input(f"버킷 '{bucket}'를 생성하시겠습니까? (y/n): ")
            if response.lower() == 'y':
                client.make_bucket(bucket)
                print(f"✅ 버킷 생성 완료: {bucket}")
            else:
                print("❌ 업로드 취소")
                return
        
        print(f"\n📊 소스 디렉토리: {source_dir}")
        print(f"🗄️  대상 버킷: {bucket}")
        if prefix:
            print(f"📁 Prefix: {prefix}")
        
        # 지원하는 파일 형식
        supported_extensions = {'.pdf', '.docx', '.doc', '.xlsx', '.xls', 
                                '.pptx', '.ppt', '.txt', '.hwp'}
        
        # 파일 목록 수집
        files_to_upload = []
        total_size = 0
        
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                file_path = Path(root) / file
                ext = file_path.suffix.lower()
                
                if ext in supported_extensions:
                    files_to_upload.append(file_path)
                    total_size += file_path.stat().st_size
        
        if not files_to_upload:
            print("\n⚠️  업로드할 파일이 없습니다.")
            print(f"   지원 형식: {', '.join(supported_extensions)}")
            return
        
        # 확인
        print(f"\n📋 업로드 요약:")
        print(f"   파일 수: {len(files_to_upload)}개")
        print(f"   총 크기: {total_size / (1024**3):.2f} GB")
        
        response = input(f"\n업로드를 시작하시겠습니까? (y/n): ")
        if response.lower() != 'y':
            print("❌ 업로드 취소")
            return
        
        # 업로드 실행
        print("\n🚀 업로드 중...")
        uploaded = 0
        failed = 0
        
        for i, file_path in enumerate(files_to_upload, 1):
            try:
                # MinIO 내 객체 이름 생성
                relative_path = file_path.relative_to(source_dir)
                object_name = str(Path(prefix) / relative_path) if prefix else str(relative_path)
                
                # 파일 크기
                file_size = file_path.stat().st_size
                file_size_mb = file_size / (1024**2)
                
                # 업로드
                client.fput_object(
                    bucket,
                    object_name,
                    str(file_path),
                )
                
                uploaded += 1
                print(f"  [{i}/{len(files_to_upload)}] ✅ {file_path.name} ({file_size_mb:.2f} MB)")
                
            except S3Error as e:
                failed += 1
                print(f"  [{i}/{len(files_to_upload)}] ❌ {file_path.name}: {e}")
            except Exception as e:
                failed += 1
                print(f"  [{i}/{len(files_to_upload)}] ❌ {file_path.name}: {e}")
        
        # 최종 결과
        print("\n" + "=" * 80)
        print("📊 업로드 완료")
        print("=" * 80)
        print(f"  성공: {uploaded}개")
        print(f"  실패: {failed}개")
        print(f"  총 크기: {total_size / (1024**3):.2f} GB")
        
        if uploaded > 0:
            print(f"\n💡 다음 단계:")
            print(f"   python3 scripts/process_attachments.py --source minio")
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description='로컬 파일을 MinIO에 업로드')
    parser.add_argument('source_dir', type=Path, help='업로드할 소스 디렉토리')
    parser.add_argument('--prefix', default='', help='MinIO 내 경로 prefix (예: 2025/)')
    parser.add_argument('--endpoint', help='MinIO endpoint (기본값: .env 파일)')
    parser.add_argument('--access-key', help='Access key (기본값: .env 파일)')
    parser.add_argument('--secret-key', help='Secret key (기본값: .env 파일)')
    parser.add_argument('--bucket', help='버킷 이름 (기본값: .env 파일)')
    parser.add_argument('--secure', action='store_true', help='HTTPS 사용')
    
    args = parser.parse_args()
    
    # 소스 디렉토리 확인
    if not args.source_dir.exists():
        print(f"❌ 디렉토리가 존재하지 않습니다: {args.source_dir}")
        sys.exit(1)
    
    if not args.source_dir.is_dir():
        print(f"❌ 디렉토리가 아닙니다: {args.source_dir}")
        sys.exit(1)
    
    # MinIO 설정
    minio_config = {
        'endpoint': args.endpoint or os.getenv('MINIO_ENDPOINT'),
        'access_key': args.access_key or os.getenv('MINIO_ACCESS_KEY'),
        'secret_key': args.secret_key or os.getenv('MINIO_SECRET_KEY'),
        'bucket': args.bucket or os.getenv('MINIO_BUCKET', 'kit-attachments'),
        'secure': args.secure or os.getenv('MINIO_SECURE', 'false').lower() == 'true'
    }
    
    # 필수 설정 확인
    if not all([minio_config['endpoint'], minio_config['access_key'], 
                minio_config['secret_key']]):
        print("❌ MinIO 설정이 부족합니다.")
        print("\n.env 파일에 다음을 추가하거나 명령행 옵션을 사용하세요:")
        print("  MINIO_ENDPOINT=localhost:9000")
        print("  MINIO_ACCESS_KEY=your_access_key")
        print("  MINIO_SECRET_KEY=your_secret_key")
        print("  MINIO_BUCKET=kit-attachments")
        print("\n또는:")
        print(f"  python3 {sys.argv[0]} {args.source_dir} \\")
        print("    --endpoint localhost:9000 \\")
        print("    --access-key YOUR_KEY \\")
        print("    --secret-key YOUR_SECRET \\")
        print("    --bucket kit-attachments")
        sys.exit(1)
    
    # 업로드 실행
    upload_to_minio(args.source_dir, minio_config, args.prefix)

if __name__ == "__main__":
    main()
