#!/usr/bin/env python3
"""
ZIP 첨부파일 처리 스크립트
ZIP 파일들을 압축 해제하고 내부 문서에서 텍스트를 추출하여 corpus에 추가
"""

import json
import zipfile
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple
import subprocess
import sys

# 텍스트 추출 라이브러리
try:
    import olefile
    from pdfminer.high_level import extract_text as extract_pdf_text
    from docx import Document
except ImportError:
    print("❌ 필요한 라이브러리를 설치해주세요:")
    print("   pip install olefile pdfminer.six python-docx")
    sys.exit(1)


def extract_hwp_text(file_path: Path) -> str:
    """HWP 파일에서 텍스트 추출 (LibreOffice 사용)"""
    try:
        # LibreOffice를 사용한 HWP → TXT 변환
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / f"{file_path.stem}.txt"
            
            # libreoffice --headless --convert-to txt 사용
            result = subprocess.run(
                [
                    'libreoffice',
                    '--headless',
                    '--convert-to', 'txt:Text',
                    '--outdir', temp_dir,
                    str(file_path)
                ],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            # 변환된 파일 읽기
            if output_path.exists():
                with open(output_path, 'r', encoding='utf-8', errors='ignore') as f:
                    text = f.read().strip()
                    if text:
                        return text
            
            # LibreOffice 실패 시 olefile로 시도
            return extract_hwp_with_olefile(file_path)
    
    except FileNotFoundError:
        # LibreOffice가 없으면 olefile 사용
        return extract_hwp_with_olefile(file_path)
    except subprocess.TimeoutExpired:
        print(f"      ⚠️  HWP 변환 타임아웃")
        return extract_hwp_with_olefile(file_path)
    except Exception as e:
        print(f"      ⚠️  HWP 추출 실패: {e}")
        return extract_hwp_with_olefile(file_path)


def extract_hwp_with_olefile(file_path: Path) -> str:
    """olefile을 사용한 HWP 텍스트 추출 (제한적)"""
    try:
        if not olefile.isOleFile(str(file_path)):
            return ""
        
        ole = olefile.OleFileIO(str(file_path))
        
        # HWP 파일 구조에서 텍스트 스트림 찾기
        text_streams = []
        for stream in ole.listdir():
            stream_name = '/'.join(stream)
            if 'PrvText' in stream_name or 'BodyText' in stream_name:
                try:
                    data = ole.openstream(stream).read()
                    text = data.decode('utf-16-le', errors='ignore')
                    text_streams.append(text)
                except:
                    pass
        
        ole.close()
        return '\n'.join(text_streams).strip()
    except Exception as e:
        print(f"      ⚠️  olefile HWP 추출 실패: {e}")
        return ""


def extract_pdf_text_from_file(file_path: Path) -> str:
    """PDF 파일에서 텍스트 추출"""
    try:
        text = extract_pdf_text(str(file_path))
        return text.strip()
    except Exception as e:
        print(f"      ⚠️  PDF 추출 실패: {e}")
        return ""


def extract_docx_text(file_path: Path) -> str:
    """DOCX 파일에서 텍스트 추출"""
    try:
        doc = Document(str(file_path))
        text = '\n'.join([para.text for para in doc.paragraphs])
        return text.strip()
    except Exception as e:
        print(f"      ⚠️  DOCX 추출 실패: {e}")
        return ""


def extract_text_from_file(file_path: Path) -> str:
    """파일 확장자에 따라 텍스트 추출"""
    ext = file_path.suffix.lower()
    
    if ext in ['.hwp', '.hwpx']:
        return extract_hwp_text(file_path)
    elif ext == '.pdf':
        return extract_pdf_text_from_file(file_path)
    elif ext in ['.docx', '.doc']:
        return extract_docx_text(file_path)
    else:
        print(f"      ⚠️  지원하지 않는 파일 형식: {ext}")
        return ""


def process_zip_files(zip_dir: Path, pages_dir: Path, output_file: Path):
    """
    ZIP 파일들을 처리하여 텍스트를 추출하고 corpus 형식으로 저장
    
    Args:
        zip_dir: ZIP 파일들이 있는 디렉토리
        pages_dir: JSON 페이지 파일들이 있는 디렉토리
        output_file: 출력할 corpus 파일 (CSV)
    """
    
    print("=" * 80)
    print("📦 ZIP 첨부파일 텍스트 추출")
    print("=" * 80)
    
    # Step 1: JSON에서 ZIP 파일 매핑 정보 수집
    print("\n1️⃣ JSON 메타데이터 수집...")
    
    zip_mapping = {}  # {zip_filename: [{page_url, page_title, download_url, ...}]}
    
    for json_file in pages_dir.glob("*.json"):
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        page_url = data.get('url', '')
        page_title = data.get('title', '')
        attachments = data.get('metadata', {}).get('attachments', [])
        
        for att in attachments:
            saved_path = att.get('saved_path', '')
            if saved_path.endswith(('.zip', '.ZIP', '.Zip')):
                filename = saved_path.replace('\\', '/').split('/')[-1]
                
                if filename not in zip_mapping:
                    zip_mapping[filename] = []
                
                zip_mapping[filename].append({
                    'page_url': page_url,
                    'page_title': page_title,
                    'download_url': att.get('url', ''),
                    'attachment_name': att.get('name', '')
                })
    
    print(f"   찾은 ZIP 파일: {len(zip_mapping)}개")
    
    # Step 2: ZIP 파일들 처리
    print("\n2️⃣ ZIP 파일 텍스트 추출...")
    
    zip_files = list(zip_dir.glob("*.zip")) + list(zip_dir.glob("*.ZIP")) + list(zip_dir.glob("*.Zip"))
    
    extracted_documents = []  # [{text, metadata}]
    
    for zip_file in zip_files:
        filename = zip_file.name
        
        if filename not in zip_mapping:
            print(f"\n⏭️  스킵: {filename} (매핑 정보 없음)")
            continue
        
        print(f"\n📦 처리: {filename}")
        
        # ZIP 파일이 참조된 페이지들
        references = zip_mapping[filename]
        
        try:
            with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                file_list = [f for f in zip_ref.namelist() if not f.endswith('/')]
                print(f"   파일 {len(file_list)}개")
                
                # 임시 디렉토리에 압축 해제
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_path = Path(temp_dir)
                    
                    for file_name in file_list:
                        # 한글 파일명 디코딩
                        try:
                            decoded = file_name.encode('cp437').decode('euc-kr')
                        except:
                            decoded = file_name
                        
                        base_name = decoded.replace('\\', '/').split('/')[-1]
                        
                        # ZIP에서 파일 추출
                        try:
                            file_data = zip_ref.read(file_name)
                            temp_file = temp_path / base_name
                            temp_file.write_bytes(file_data)
                            
                            # 텍스트 추출
                            print(f"   📄 {base_name[:50]}")
                            text = extract_text_from_file(temp_file)
                            
                            if text:
                                # 각 참조 페이지마다 문서 추가
                                for ref in references:
                                    extracted_documents.append({
                                        'text': text,
                                        'title': f"{ref['page_title']} - {base_name}",
                                        'url': ref['page_url'],
                                        'source_type': 'zip_attachment',
                                        'zip_file': filename,
                                        'document_name': base_name,
                                        'download_url': ref['download_url']
                                    })
                                
                                print(f"      ✅ 텍스트 추출: {len(text):,}자")
                            else:
                                print(f"      ⚠️  텍스트 없음")
                        
                        except Exception as e:
                            print(f"      ❌ 에러: {e}")
                            continue
        
        except Exception as e:
            print(f"   ❌ ZIP 처리 실패: {e}")
            continue
    
    # Step 3: Corpus 형식으로 저장
    print(f"\n3️⃣ Corpus 저장...")
    print(f"   추출된 문서: {len(extracted_documents)}개")
    
    if extracted_documents:
        import csv
        
        with open(output_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'text', 'title', 'url', 'source_type', 
                'zip_file', 'document_name', 'download_url'
            ])
            writer.writeheader()
            writer.writerows(extracted_documents)
        
        print(f"   ✅ 저장 완료: {output_file}")
    else:
        print("   ⚠️  추출된 문서가 없습니다.")
    
    print("\n" + "=" * 80)
    print("🎉 완료!")
    print("=" * 80)


def main():
    zip_dir = Path("data/zip")
    pages_dir = Path("data/crawled_data/pages")
    output_file = Path("data/corpus_zip_attachments.csv")
    
    if not zip_dir.exists():
        print(f"❌ ZIP 디렉토리가 없습니다: {zip_dir}")
        return
    
    if not pages_dir.exists():
        print(f"❌ Pages 디렉토리가 없습니다: {pages_dir}")
        return
    
    process_zip_files(zip_dir, pages_dir, output_file)


if __name__ == "__main__":
    main()
