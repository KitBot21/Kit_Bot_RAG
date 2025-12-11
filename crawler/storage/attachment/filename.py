import os, re, unicodedata
from urllib.parse import unquote

def fix_filename(raw: str, fallback_ext: str = ".bin") -> str:
    """깨진 한글 파일명을 정상적으로 변환"""
    # URL 인코딩 해제
    raw = unquote(raw)

    # 1차 변환: latin1 → utf-8
    try:
        raw = raw.encode("latin1").decode("utf-8")
    except Exception:
        pass

    # 2차 변환: 또다시 'ë°' 같은게 남으면 다시 변환
    try:
        raw = raw.encode("latin1").decode("utf-8")
    except Exception:
        pass

    # 파일명 정리
    name = os.path.basename(raw).strip()
    name = unicodedata.normalize("NFC", name)
    name = re.sub(r'[\\/:\*\?"<>\|\x00-\x1F]', "_", name)
    name = re.sub(r"\s+", " ", name).strip()

    # 확장자 없으면 fallback 붙이기
    if not os.path.splitext(name)[1]:
        name += fallback_ext

    return name or "download" + fallback_ext
