from storage.minio_storage import MinIOStorage

def delete_duplicate_objects(prefix="attachments"):
    minio = MinIOStorage.from_env()
    objects = [obj.object_name for obj in minio.client.list_objects(minio.bucket_name, prefix=prefix, recursive=True)]
    filename_map = {}
    duplicates = []

    for obj in objects:
        try:
            stat = minio.client.stat_object(minio.bucket_name, obj)
            # X-Amz-Meta-Original_filename은 소문자로 변환되어 저장됨
            original_filename = stat.metadata.get("x-amz-meta-original_filename")
        except Exception as e:
            print(f"오류: {obj} - {e}")
            continue
        if original_filename in filename_map:
            duplicates.append(obj)
        else:
            filename_map[original_filename] = obj

    for dup in duplicates:
        minio.client.remove_object(minio.bucket_name, dup)
        print(f"삭제됨: {dup}")

delete_duplicate_objects("attachments")
delete_duplicate_objects("images")