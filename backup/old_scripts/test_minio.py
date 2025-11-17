#!/usr/bin/env python3
from minio import Minio
from dotenv import load_dotenv
import os

load_dotenv()

endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000")
access_key = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
secret_key = os.getenv("MINIO_SECRET_KEY", "minioadmin")

print(f"Endpoint: {endpoint}")
print(f"Access Key: {access_key}")
print(f"Secret Key: {secret_key[:3]}{'*' * (len(secret_key)-3)}")

try:
    client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=False)
    buckets = client.list_buckets()
    print(f"\n✅ MinIO 연결 성공!")
    print(f"버킷 목록: {[b.name for b in buckets]}")
except Exception as e:
    print(f"\n❌ MinIO 연결 실패: {e}")
