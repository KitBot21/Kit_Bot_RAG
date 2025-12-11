from __future__ import annotations
import json, hashlib, sys
from datetime import datetime
from pathlib import Path
from infra.config import DATA_DIR, FIXTURES_DIR
from core.utils import normalize_url, html_cache_path
from setting.loader import Loader  # 당신 프로젝트의 로더 경로에 맞추세요

# 프로젝트 유틸/경로 가져오기
try:
    # 선택: 설정에서 base 구성 (start_url 우선, 없으면 domain)
    try:
        s = Loader().load()
        BASE = s.start_url or (f"https://{s.domain}/" if getattr(s, "domain", "") else "")
    except Exception:
        BASE = ""
except Exception as e:
    print("[ERROR] 프로젝트 경로 임포트 실패:", e)
    sys.exit(1)

STATE_DIR = (DATA_DIR / "state")
STATE_PATH = STATE_DIR / "crawl_state.json"

DROP_IF_SNAPSHOT_EXISTS = True  # 스냅샷(HTML) 이미 있으면 큐에서 제거

def _key(u: str) -> str:
    return hashlib.sha1(u.encode("utf-8")).hexdigest()[:16]

def is_absolute(u: str) -> bool:
    return u.startswith("http://") or u.startswith("https://")

def main():
    if not STATE_PATH.exists():
        print(f"[INFO] state 파일이 없습니다: {STATE_PATH}")
        return

    # 백업
    backup = STATE_PATH.with_suffix(".json.bak-" + datetime.utcnow().strftime("%Y%m%d%H%M%S"))
    backup.write_text(STATE_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"[OK] 백업 생성: {backup}")

    j = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    queue = j.get("queue", [])
    inflight = j.get("inflight")
    used = int(j.get("requests_used", 0))
    enqueued_keys = set(j.get("enqueued_keys", []))

    if not queue:
        print("[INFO] queue 비어 있음. 변경 없음.")
        return

    base = BASE
    if not base:
        # base를 못 구했어도 절대 URL은 정규화 가능
        print("[WARN] base URL을 찾지 못했습니다. 절대 URL만 정규화/정리합니다.")

    new_q = []
    seen_keys = set()
    removed_dup = removed_snap = removed_rel = 0

    for u in queue:
        # 상대경로 처리
        if not is_absolute(u):
            if base:
                nu = normalize_url(u, base)
            else:
                # base가 없는데 상대경로면 보수적으로 스킵(원하면 new_q에 그대로 넣도록 바꾸세요)
                removed_rel += 1
                continue
        else:
            nu = normalize_url(u, base or u)

        k = _key(nu)

        # 스냅샷 존재 시 제거
        if DROP_IF_SNAPSHOT_EXISTS and html_cache_path(FIXTURES_DIR, nu).exists():
            removed_snap += 1
            continue

        # 큐 중복 제거: enqueued_keys(과거 등록) + 지금 회차 중복(seen_keys)
        if (k in enqueued_keys) or (k in seen_keys):
            removed_dup += 1
            continue

        new_q.append(nu)
        seen_keys.add(k)

    # enqueued_keys 갱신(지금 큐의 전체를 등록 이력으로)
    enqueued_keys |= seen_keys

    j["queue"] = new_q
    j["inflight"] = None              # 안전하게 비움(원하면 유지 가능)
    j["enqueued_keys"] = list(enqueued_keys)
    # used(요청 카운트)는 유지. 실행마다 0으로 쓰려면 아래 주석 해제
    # j["requests_used"] = 0

    STATE_PATH.write_text(json.dumps(j, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[DONE] 큐 정리 완료")
    print(f" - 기존: {len(queue)} → 현재: {len(new_q)}")
    print(f" - 중복 제거: {removed_dup}")
    print(f" - 스냅샷 존재로 제거: {removed_snap}")
    if not base:
        print(f" - 상대경로로 제거( base 미설정 ): {removed_rel}")

if __name__ == "__main__":
    main()
