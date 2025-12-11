import json
from pathlib import Path
from langchain_text_splitters import RecursiveCharacterTextSplitter

# --------------------------------------------------------------------------
# 1. 의미 단위 청킹 설정
# --------------------------------------------------------------------------
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    separators=["\n\n", "\n", " ", ""]
)

def build_header(doc):
    lines = [
        f"문서 제목: {doc.get('display_title') or doc.get('title')}",
        f"게시판: {doc.get('board_name')}",
        f"작성일: {doc.get('created_at') or '알 수 없음'}",
        f"출처 URL: {doc.get('url')}",
    ]
    return "\n".join(lines) + "\n\n"

def chunk_document(doc):
    header = build_header(doc)
    main_text = doc.get("main_text", "")
    
    if len(main_text) < 10:
        return []

    raw_chunks = text_splitter.split_text(main_text)

    chunk_docs = []
    for idx, chunk_text in enumerate(raw_chunks):
        final_text = header + chunk_text
        
        chunk_docs.append({
            "chunk_id": f"{doc['doc_id']}__{idx}",
            "doc_id": doc["doc_id"],
            "chunk_index": idx,
            "text": final_text,
            "metadata": {
                "site": doc.get("site"),
                "board_name": doc.get("board_name"),
                "title": doc.get("title"),
                "url": doc.get("url"),
                "created_at": doc.get("created_at"),
                "tags": doc.get("tags", []), 
                "source_type": doc.get("source_type", "page")
            }
        })

    return chunk_docs

def chunk_directory(unified_dir: str, chunk_output: str):
    input_path = Path(unified_dir)
    output_path = Path(chunk_output)
    output_path.mkdir(parents=True, exist_ok=True)

    count_docs = 0
    total_chunks = 0
    skipped_docs = 0  # 변수 초기화

    print(f"📂 청킹 시작: {input_path} -> {output_path}")

    files = list(input_path.glob("*.unified.json"))
    print(f"ℹ️  처리할 파일 수: {len(files)}개")
    
    for path in files:
        try:
            with path.open(encoding="utf-8") as f:
                doc = json.load(f)

            # [증분 처리] 첫 번째 청크 파일 존재 여부 확인
            first_chunk_name = f"{doc['doc_id']}__0.json"
            first_chunk_path = output_path / first_chunk_name

            # 파일이 이미 있고, 원본(path)이 청크(first_chunk_path)보다 오래된 경우(변경 없음) -> 스킵
            if first_chunk_path.exists():
                if path.stat().st_mtime <= first_chunk_path.stat().st_mtime:
                    skipped_docs += 1
                    continue
                # else: 원본이 더 최신이면(새로 갱신됨) -> 진행 (덮어쓰기)

            chunks = chunk_document(doc)

            for c in chunks:
                out_name = f"{c['chunk_id']}.json"
                if len(out_name) > 250:
                    out_name = c['chunk_id'][:240] + ".json"
                
                out_file = output_path / out_name
                with out_file.open("w", encoding="utf-8") as f:
                    json.dump(c, f, ensure_ascii=False, indent=2)

            count_docs += 1
            total_chunks += len(chunks)
            
            if count_docs % 1000 == 0:
                print(f"   ... {count_docs}개 문서 신규 처리 완료")

        except Exception as e:
            print(f"❌ Error processing {path.name}: {e}")

    print("=" * 60)
    print(f"✅ 청킹 완료!")
    print(f"📄 신규 처리 문서: {count_docs}개")
    print(f"⏭️ 건너뛴 문서: {skipped_docs}개")
    print(f"🧩 생성된 청크: {total_chunks}개")
    print("=" * 60)

if __name__ == "__main__":
    chunk_directory("data/unified", "data/chunks")