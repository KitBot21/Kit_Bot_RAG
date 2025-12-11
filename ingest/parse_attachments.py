import sys
import os
import json
import hashlib
import subprocess
import pdfplumber
import mimetypes
import easyocr  # EasyOCR 사용
from pathlib import Path
from datetime import datetime

# 프로젝트 루트 경로 추가
sys.path.append(str(Path(__file__).parent.parent))
from crawler.storage.minio_storage import create_minio_storage

# ---------------------------------------------------------
# 설정
# ---------------------------------------------------------
RAW_DIR = Path("data/raw")
UNIFIED_DIR = Path("data/unified")
TEMP_DIR = Path("temp_downloads")

minio = create_minio_storage()

# ---------------------------------------------------------
# EasyOCR 초기화 (GPU 우선 사용)
# ---------------------------------------------------------
print("⏳ EasyOCR 모델 로딩 중...")
try:
    # 1차 시도: GPU 사용
    ocr_reader = easyocr.Reader(['ko', 'en'], gpu=True)
    OCR_AVAILABLE = True
    print("✅ EasyOCR 로드 완료 (GPU 가속 활성화 🚀)")
except Exception as e:
    print(f"⚠️ GPU 로드 실패 ({e}). CPU 모드로 전환합니다.")
    try:
        # 2차 시도: CPU 사용 (Fallback)
        ocr_reader = easyocr.Reader(['ko', 'en'], gpu=False)
        OCR_AVAILABLE = True
        print("✅ EasyOCR 로드 완료 (CPU 모드)")
    except Exception as e2:
        print(f"❌ EasyOCR 초기화 완전 실패: {e2}")
        OCR_AVAILABLE = False

# ---------------------------------------------------------
# 처리 함수들 (로그 강화)
# ---------------------------------------------------------
def process_hwp(file_path):
    try:
        # print(f"      [Info] HWP 변환 중...") 
        res = subprocess.run(["hwp5txt", str(file_path)], capture_output=True, text=True, encoding="utf-8")
        return res.stdout if res.returncode == 0 else ""
    except: return ""

def process_pdf(file_path):
    text_content = []
    try:
        # print(f"      [Info] PDF 텍스트 추출 중...")
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                try:
                    tables = page.extract_tables()
                    for table in tables:
                        clean = [[str(c) if c else "" for c in r] for r in table]
                        if clean:
                            body = "\n".join([" | ".join(row) for row in clean])
                            text_content.append(f"\n[표 데이터]\n{body}\n")
                except: pass
                try:
                    text = page.extract_text()
                    if text: text_content.append(text)
                except: pass
        
        combined = "\n\n".join(text_content)
        
        # 텍스트가 너무 적으면 OCR 시도
        if len(combined.strip()) < 50 and OCR_AVAILABLE:
            print("      ⚠️ [OCR 전환] 스캔된 PDF 감지. EasyOCR 수행 중...")
            ocr_texts = []
            with pdfplumber.open(file_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    try:
                        # 이미지 변환
                        im = page.to_image(resolution=300)
                        temp = f"temp_ocr_{i}.jpg"
                        im.save(temp)
                        
                        # [EasyOCR] 실행 (GPU 활용)
                        result = ocr_reader.readtext(temp, detail=0)
                        
                        if result:
                            page_text = " ".join(result)
                            ocr_texts.append(f"\n[Page {i+1} OCR]\n{page_text}")
                        
                        if os.path.exists(temp): os.remove(temp)
                    except: pass
            
            combined = "\n".join(ocr_texts)
            if combined:
                print(f"      ✨ [OCR 결과] {len(combined)}자 추출")
            
        return combined
    except Exception as e:
        print(f"      ❌ PDF 처리 실패: {e}")
        return ""

def process_image(file_path):
    if not OCR_AVAILABLE: return ""
    try:
        # [EasyOCR] 실행
        result = ocr_reader.readtext(str(file_path), detail=0)
        full = " ".join(result)
        
        if full:
            return f"\n[이미지 내 텍스트]\n{full}\n"
        return ""
    except: return ""

# ---------------------------------------------------------
# 메인 로직
# ---------------------------------------------------------
def save_attachment_as_json(file_path, minio_obj_name, parent_data):
    filename = file_path.name
    ext = file_path.suffix.lower()
    
    if (ext == ".do" or not ext) and "." in minio_obj_name:
        ext = "." + minio_obj_name.split(".")[-1].lower()

    print(f"   ⚙️ [Processing] {filename} ({ext})...")
    
    content = ""
    if ext == ".pdf": content = process_pdf(file_path)
    elif ext == ".hwp": content = process_hwp(file_path)
    elif ext in [".jpg", ".jpeg", ".png", ".bmp", ".gif"]: content = process_image(file_path)
    else: return

    if not content or len(content.strip()) < 5: 
        print("      ⚠️ 내용 없음")
        return

    file_id = hashlib.md5(minio_obj_name.encode()).hexdigest()[:16]
    
    # 🔴 [Fix] 부모 데이터의 최상위 필드에서 직접 정보 추출
    parent_title = parent_data.get("title", "제목 없음")
    parent_url = parent_data.get("url", "")
    parent_board = parent_data.get("board_name", "첨부파일")
    parent_date = parent_data.get("created_at", datetime.now().isoformat())

    doc = {
        "doc_id": f"att_{file_id}",
        "source_type": "attachment",
        "site": "attachment",
        "board_name": parent_board,
        "title": f"[첨부파일] {filename}",
        "display_title": f"{filename} (출처: {parent_title})",
        "url": parent_url,
        "created_at": parent_date,
        "main_text": content,
        "doc_type": ext.replace(".", ""),
        "tags": ["첨부파일", ext.upper()],
        "metadata": {
            "original_filename": filename,
            "parent_title": parent_title
        }
    }

    out_path = UNIFIED_DIR / f"att_{file_id}.unified.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    print(f"      ✅ 성공! (URL 포함됨)")

def process_minio_attachments():
    print("="*60); print("📂 첨부파일 처리 (EasyOCR + GPU)"); print("="*60)
    UNIFIED_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    json_files = list(RAW_DIR.glob("**/*.json"))
    print(f"ℹ️  검사 대상: {len(json_files)}개 문서")

    success_count = 0
    for json_path in json_files:
        try:
            with json_path.open(encoding="utf-8") as f:
                data = json.load(f)
            
            attachments = data.get("attachments") or data.get("metadata", {}).get("attachments", [])
            if not attachments: continue

            for att in attachments:
                object_name = att.get("minio_object")
                filename = att.get("filename", "unknown")
                if not object_name: continue

                unique_filename = Path(object_name).name
                
                check_name = object_name if "." in object_name else filename
                ext = Path(check_name).suffix.lower()
                if ext not in [".pdf", ".hwp", ".jpg", ".jpeg", ".png", ".bmp", ".gif"]: continue

                file_id = hashlib.md5(object_name.encode()).hexdigest()[:16]
                if (UNIFIED_DIR / f"att_{file_id}.unified.json").exists(): continue
                
                local_path = TEMP_DIR / unique_filename
                downloaded = False
                try:
                    if not local_path.exists():
                        minio.client.fget_object(minio.bucket_name, object_name, str(local_path))
                    downloaded = True
                except:
                    try:
                        path_obj = Path(object_name)
                        stem = path_obj.stem
                        if "_" in stem:
                            clean_obj = f"{path_obj.parent}/{stem.rsplit('_', 1)[0]}{path_obj.suffix}"
                            minio.client.fget_object(minio.bucket_name, clean_obj, str(local_path))
                            downloaded = True
                    except: pass
                
                if not downloaded: continue

                save_attachment_as_json(local_path, object_name, parent_data=data)
                success_count += 1
                
                if local_path.exists(): os.remove(local_path)

        except Exception: continue

    try:
        if TEMP_DIR.exists():
            for f in TEMP_DIR.glob("*"): os.remove(f)
            os.rmdir(TEMP_DIR)
    except: pass

    print("="*60)
    print(f"🎉 완료! {success_count}개 처리됨.")

if __name__ == "__main__":
    process_minio_attachments()