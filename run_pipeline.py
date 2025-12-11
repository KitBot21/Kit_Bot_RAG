import subprocess
import time
import sys

def run_command(command, step_name):
    print(f"\n" + "="*50)
    print(f"🚀 [{step_name}] 시작...")
    print("="*50)
    
    start_time = time.time()
    
    # 명령어 실행
    result = subprocess.run(command, shell=True)
    
    end_time = time.time()
    duration = end_time - start_time
    
    if result.returncode != 0:
        print(f"\n❌ [{step_name}] 실패! (에러 코드: {result.returncode})")
        print("🚨 파이프라인을 중단합니다.")
        sys.exit(1)
    else:
        print(f"\n✅ [{step_name}] 완료! (소요 시간: {duration:.2f}초)")

def main():
    print("🏗️  금오공대 챗봇 데이터 파이프라인 가동")
    
    # 1. 크롤링 (새로운 글 수집)
    # (필요하다면 departmentCrawler.py도 여기에 추가 가능)
    run_command("python crawler/departmentCrawler.py --enable-minio", "1. 크롤링 (공지/학사일정/식당)")
    run_command("python crawler/repeatCrawler.py --enable-minio", "1. 크롤링 (공지/학사일정/식당)")
    
    # 2. 정규화 (JSON 표준화)
    run_command("python ingest/normalize.py", "2. 데이터 정규화")
    
    # 3. 첨부파일 처리 (HWP/PDF/이미지 -> 텍스트)
    run_command("python ingest/parse_attachments.py", "3. 첨부파일 텍스트 추출")
    
    # 4. 청킹 (의미 단위 분할)
    run_command("python ingest/chunk.py", "4. 청킹 (Chunking)")
    
    # 5. 임베딩 & 업로드 (Qdrant 적재)
    run_command("python ingest/embed_upload.py", "5. 임베딩 및 DB 업로드")
    
    print("\n" + "="*50)
    print("🎉 모든 작업이 성공적으로 끝났습니다! 챗봇이 똑똑해졌습니다.")
    print("="*50)

if __name__ == "__main__":
    main()