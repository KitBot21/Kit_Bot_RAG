#!/usr/bin/env python3
"""
MinIO Storage Helper
첨부파일을 MinIO Object Storage에 업로드
"""
import os
import hashlib
import logging
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime
from minio import Minio
from minio.error import S3Error

logger = logging.getLogger(__name__)


class MinIOStorage:
    """MinIO Object Storage 관리 클래스"""
    
    def __init__(
        self,
        endpoint: str = "localhost:9000",
        access_key: str = "minioadmin",
        secret_key: str = "minioadmin",
        bucket_name: str = "kit-attachments",
        secure: bool = False
    ):
        """
        Args:
            endpoint: MinIO 서버 주소 (예: localhost:9000)
            access_key: Access Key
            secret_key: Secret Key
            bucket_name: 버킷 이름
            secure: HTTPS 사용 여부
        """
        self.endpoint = endpoint
        self.access_key = access_key
        self.secret_key = secret_key
        self.bucket_name = bucket_name
        self.secure = secure
        
        # MinIO 클라이언트 초기화
        self.client = Minio(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure
        )
        
        # 버킷 생성 (없으면)
        self._ensure_bucket()
    
    def _ensure_bucket(self):
        """버킷이 없으면 생성"""
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                logger.info(f"✅ MinIO 버킷 생성: {self.bucket_name}")
            else:
                logger.info(f"✅ MinIO 버킷 연결: {self.bucket_name}")
        except S3Error as e:
            logger.error(f"❌ MinIO 버킷 생성/확인 실패: {e}")
            raise
    
    def upload_file(
        self,
        file_data: bytes,
        object_name: str,
        content_type: str = "application/octet-stream",
        metadata: Optional[dict] = None,
        original_filename: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        파일을 MinIO에 업로드
        
        Args:
            file_data: 파일 바이너리 데이터
            object_name: MinIO에 저장할 객체 이름 (한글 파일명 가능)
            content_type: MIME 타입
            metadata: 메타데이터 (선택)
            original_filename: 원본 파일명 (메타데이터에 저장)
            
        Returns:
            (성공 여부, 객체 URL 또는 에러 메시지)
        """
        try:
            from io import BytesIO
            import urllib.parse
            
            # 메타데이터 기본값
            if metadata is None:
                metadata = {}
            
            # 업로드 날짜 추가
            metadata['uploaded_at'] = datetime.now().isoformat()
            metadata['sha256'] = hashlib.sha256(file_data).hexdigest()
            
            # 원본 파일명 저장
            if original_filename:
                metadata['original_filename'] = original_filename
            
            # 한글 메타데이터를 ASCII-safe하게 URL 인코딩
            safe_metadata = {}
            for key, value in metadata.items():
                if isinstance(value, str):
                    # ASCII가 아닌 문자를 URL 인코딩
                    try:
                        value.encode('ascii')
                        safe_metadata[key] = value
                    except UnicodeEncodeError:
                        safe_metadata[key] = urllib.parse.quote(value, safe='')
                else:
                    safe_metadata[key] = str(value)
            
            metadata = safe_metadata
            
            # BytesIO로 변환
            file_stream = BytesIO(file_data)
            file_size = len(file_data)
            
            # 업로드 (object_name은 한글 그대로 사용)
            self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                data=file_stream,
                length=file_size,
                content_type=content_type,
                metadata=metadata
            )
            
            # 객체 URL 생성
            object_url = f"minio://{self.bucket_name}/{object_name}"
            
            logger.info(f"✅ MinIO 업로드 성공: {object_name} ({file_size:,} bytes)")
            return True, object_url
            
        except S3Error as e:
            error_msg = f"MinIO 업로드 실패: {e}"
            logger.error(f"❌ {error_msg}")
            return False, error_msg
        except Exception as e:
            error_msg = f"업로드 중 에러: {e}"
            logger.error(f"❌ {error_msg}")
            return False, error_msg
    
    def file_exists(self, object_name: str) -> bool:
        """파일이 MinIO에 존재하는지 확인"""
        try:
            self.client.stat_object(self.bucket_name, object_name)
            return True
        except S3Error:
            return False
    
    def get_file_url(self, object_name: str, expires_hours: int = 24) -> Optional[str]:
        """
        Presigned URL 생성 (임시 다운로드 링크)
        
        Args:
            object_name: 객체 이름
            expires_hours: URL 유효 시간 (시간)
            
        Returns:
            Presigned URL 또는 None
        """
        try:
            from datetime import timedelta
            
            url = self.client.presigned_get_object(
                self.bucket_name,
                object_name,
                expires=timedelta(hours=expires_hours)
            )
            return url
        except S3Error as e:
            logger.error(f"❌ Presigned URL 생성 실패: {e}")
            return None
    
    def list_files(self, prefix: str = "") -> list:
        """버킷의 파일 목록 조회"""
        try:
            objects = self.client.list_objects(
                self.bucket_name,
                prefix=prefix,
                recursive=True
            )
            return [obj.object_name for obj in objects]
        except S3Error as e:
            logger.error(f"❌ 파일 목록 조회 실패: {e}")
            return []
    
    def delete_file(self, object_name: str) -> bool:
        """파일 삭제"""
        try:
            self.client.remove_object(self.bucket_name, object_name)
            logger.info(f"✅ MinIO 파일 삭제: {object_name}")
            return True
        except S3Error as e:
            logger.error(f"❌ MinIO 파일 삭제 실패: {e}")
            return False
    
    @staticmethod
    def from_env() -> 'MinIOStorage':
        """
        환경 변수에서 설정을 읽어서 MinIOStorage 생성
        
        환경 변수:
            MINIO_ENDPOINT: MinIO 서버 주소 (기본: localhost:9000)
            MINIO_ACCESS_KEY: Access Key (기본: minioadmin)
            MINIO_SECRET_KEY: Secret Key (기본: minioadmin)
            MINIO_BUCKET: 버킷 이름 (기본: kit-attachments)
            MINIO_SECURE: HTTPS 사용 여부 (기본: false)
        """
        endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000")
        access_key = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
        secret_key = os.getenv("MINIO_SECRET_KEY", "minioadmin")
        bucket_name = os.getenv("MINIO_BUCKET", "kit-attachments")
        secure = os.getenv("MINIO_SECURE", "false").lower() == "true"
        
        return MinIOStorage(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            bucket_name=bucket_name,
            secure=secure
        )


# 편의 함수
def create_minio_storage(
    endpoint: Optional[str] = None,
    access_key: Optional[str] = None,
    secret_key: Optional[str] = None,
    bucket_name: Optional[str] = None
) -> MinIOStorage:
    """
    MinIOStorage 인스턴스 생성 (환경 변수 우선)
    
    Args:
        endpoint: MinIO 서버 주소 (None이면 환경 변수 사용)
        access_key: Access Key (None이면 환경 변수 사용)
        secret_key: Secret Key (None이면 환경 변수 사용)
        bucket_name: 버킷 이름 (None이면 환경 변수 사용)
    """
    if all(v is None for v in [endpoint, access_key, secret_key, bucket_name]):
        # 모두 None이면 환경 변수에서 읽기
        return MinIOStorage.from_env()
    
    # 일부만 지정되면 나머지는 환경 변수에서 읽기
    return MinIOStorage(
        endpoint=endpoint or os.getenv("MINIO_ENDPOINT", "localhost:9000"),
        access_key=access_key or os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
        secret_key=secret_key or os.getenv("MINIO_SECRET_KEY", "minioadmin"),
        bucket_name=bucket_name or os.getenv("MINIO_BUCKET", "kit-attachments"),
        secure=os.getenv("MINIO_SECURE", "false").lower() == "true"
    )
