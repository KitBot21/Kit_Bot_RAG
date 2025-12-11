#!/usr/bin/env python3
"""
MinIO Storage Helper
첨부파일을 MinIO Object Storage에 업로드 (중복 내용 방지 기능 추가)
"""
import os
import hashlib
import logging
from typing import Optional, Tuple, Union
from datetime import datetime
from minio import Minio
from minio.error import S3Error
from io import BytesIO
import urllib.parse

logger = logging.getLogger(__name__)

class MinIOStorage:
    def __init__(
        self,
        endpoint: str = "localhost:9100",
        access_key: str = "minioadmin",
        secret_key: str = "minioadmin",
        bucket_name: str = "kit-attachments",
        secure: bool = False
    ):
        self.endpoint = endpoint
        self.bucket_name = bucket_name
        self.client = Minio(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure
        )
        self._ensure_bucket()
    
    def _ensure_bucket(self):
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                logger.info(f"✅ MinIO 버킷 생성: {self.bucket_name}")
        except S3Error as e:
            logger.error(f"❌ MinIO 버킷 확인 실패: {e}")
    
    def upload_file(
        self,
        file_data: bytes,
        object_name: str,
        content_type: str = "application/octet-stream",
        metadata: Optional[Union[dict, str]] = None,
        original_filename: Optional[str] = None
    ) -> Tuple[bool, str]:
        try:
            # 1. 업로드할 파일의 해시(지문) 계산
            file_hash = hashlib.sha256(file_data).hexdigest()
            file_size = len(file_data)

            # 2. metadata 타입 안전 처리
            if isinstance(metadata, str):
                if original_filename is None: original_filename = metadata
                metadata = {}
            if metadata is None: metadata = {}

            metadata['uploaded_at'] = datetime.now().isoformat()
            metadata['sha256'] = file_hash
            if original_filename:
                metadata['original_filename'] = original_filename

            # 한글 메타데이터 인코딩
            safe_metadata = {}
            for k, v in metadata.items():
                try:
                    safe_metadata[k] = str(v).encode('ascii') and str(v)
                except:
                    safe_metadata[k] = urllib.parse.quote(str(v))
            
            # ---------------------------------------------------------
            # [Smart Check] 중복 파일 방지 로직
            # ---------------------------------------------------------
            if self.file_exists(object_name):
                # 이미 같은 이름의 파일이 존재함. 내용도 같은지 확인
                try:
                    stat = self.client.stat_object(self.bucket_name, object_name)
                    existing_hash = stat.metadata.get('x-amz-meta-sha256')
                    
                    # 기존 파일과 해시값이 일치하면 -> 업로드 스킵!
                    if existing_hash == file_hash:
                        logger.info(f"⏭️ 중복 파일 스킵 (내용 동일): {object_name}")
                        return True, f"minio://{self.bucket_name}/{object_name}"
                    
                    # 이름은 같은데 내용이 다르면 -> 이름 변경 (충돌 방지)
                    else:
                        if '.' in object_name:
                            name, ext = object_name.rsplit('.', 1)
                            object_name = f"{name}_{file_hash[:8]}.{ext}"
                        else:
                            object_name = f"{object_name}_{file_hash[:8]}"
                            
                except Exception:
                    pass # stat 실패 시 그냥 덮어쓰거나 진행

            # 3. 업로드 수행
            file_stream = BytesIO(file_data)
            self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                data=file_stream,
                length=file_size,
                content_type=content_type,
                metadata=safe_metadata
            )
            
            logger.info(f"✅ MinIO 업로드: {object_name}")
            return True, f"minio://{self.bucket_name}/{object_name}"
            
        except Exception as e:
            logger.error(f"❌ MinIO 업로드 실패: {e}")
            return False, str(e)

    def file_exists(self, object_name: str) -> bool:
        try:
            self.client.stat_object(self.bucket_name, object_name)
            return True
        except:
            return False

    # (나머지 메서드는 기존과 동일하거나 필요시 사용)
    @staticmethod
    def from_env():
        return create_minio_storage()

def create_minio_storage(**kwargs):
    return MinIOStorage(
        endpoint=os.getenv("MINIO_ENDPOINT", "localhost:9100"),
        access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
        secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
        bucket_name=os.getenv("MINIO_BUCKET", "kit-attachments"),
        secure=os.getenv("MINIO_SECURE", "false").lower() == "true"
    )