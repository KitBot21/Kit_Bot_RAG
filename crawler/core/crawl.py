from __future__ import annotations
from collections import deque
from urllib.parse import urlparse
import signal, hashlib, json

from datetime import datetime
from infra.config import DATA_DIR, FIXTURES_DIR, ATTACH_DIR
from setting.loader import Loader
from infra.logging_setup import setup_logging
from setting.robots import Robots
from .utils import normalize_url, html_cache_path, is_already_crawled
from .fetch import fetch_html, fetch_binary
from setting.filters import UrlFilter
from .sitemap import seed_from_sitemaps
from storage.parser import extract_title_and_text, is_download_intent
from reporting.report import make_report_html
from storage.save import SaveStorage
from storage.snapshot.snapshot import extract_title_and_main_html, build_minimal_snapshot_html
from pathlib import Path
from storage.attachment.filename import fix_filename
from core.login_detect import is_login_like_url, is_login_page_html
from infra.state import CrawlState
from storage.pii import redact_email_html  # ← 추가

try:
    from pymongo import MongoClient  # type: ignore
    _HAS_MONGO = True
except Exception:
    _HAS_MONGO = False

class Crawler:
    def __init__(self, settings: Loader):
        self.s = settings
        self.logger = setup_logging(self.s.log_path)
        self.headers = {"User-Agent": self.s.user_agent}
        self.robots = Robots(self.s.domain, self.s.user_agent)
        self.filter = UrlFilter(self.s.domain, self.s.allowed_path_prefixes, self.robots, self.s.deny_patterns, )
        
        # 상태
        self.state = CrawlState(DATA_DIR)
        self.stop_flag = False
        self.request_limit = getattr(self.s, "request_limit_per_run", 300000)
        self.ops_per_snapshot = 50

        signal.signal(signal.SIGINT, self._on_sigint)
        
        # storage
        if self.s.storage == "mongodb":
            if not _HAS_MONGO:
                raise SystemExit("pymongo가 설치되어 있지 않습니다. STORAGE=filesystem으로 변경하거나 pymongo를 설치하세요.")
            client = MongoClient(self.s.mongodb_uri or "mongodb://localhost:27017")
            from ..storage.mongodb import MongoStorage
            self.storage = MongoStorage(client, self.s.mongodb_db)
        else:
            self.storage = SaveStorage(DATA_DIR)
            
    def _on_sigint(self, sig, frame):
        self.stop_flag = True
        self.logger.info("SIGINT 수신: 그레이스풀 종료 시도…")

    def _seed_queue(self) -> deque[str]:
        lastmod_map = {}
        if self.s.sitemap_index:
            lastmod_map = seed_from_sitemaps(
                self.s.sitemap_index, self.headers, self.s.request_timeout_sec, self.s.allow_sections
            )
        self.logger.info(f"사이트맵 시드: {len(lastmod_map)}개")

        q: deque[str] = deque()
        for u, _lm in sorted(lastmod_map.items(), key=lambda kv: kv[1] or "", reverse=True):
            if self.filter.is_allowed(u):
                q.append(u)
        if self.s.start_url and self.filter.is_allowed(self.s.start_url):
            q.append(self.s.start_url)
        return q
    
    def run(self):
        # === NEW: 실행 시작 시간 기록 ===
        start_dt = datetime.now()
        self.logger.info(f"크롤링 시작: {start_dt.isoformat(timespec='seconds')}")

        # === NEW: state 준비 (파일 기반 큐/진행상태) ===
        state = CrawlState(DATA_DIR)
        requests_used = 0
        requests_used_run = 0
        inflight = None
        OPS_PER_SNAPSHOT = 50      # 몇 개마다 state 저장할지
        ops_since_save = 0
        REQUEST_LIMIT = getattr(self.s, "request_limit_per_run", 300000)

        # === NEW: 큐 중복 차단용 키셋
        enqueued_keys: set[str] = set()

        def _key(u: str) -> str:
            return hashlib.sha1(u.encode("utf-8")).hexdigest()[:16]

        # === NEW: Ctrl+C 그레이스풀 종료 플래그 ===
        stop_flag = {"v": False}
        def _on_sigint(sig, frame):
            stop_flag["v"] = True
            self.logger.info("SIGINT 수신: 안전 종료를 준비합니다…")
        signal.signal(signal.SIGINT, _on_sigint)

        self.logger.info("사이트맵에서 시드 수집 중…")
        lastmod_map = {}
        if self.s.sitemap_index:
            lastmod_map = seed_from_sitemaps(self.s.sitemap_index, self.headers, self.s.request_timeout_sec, self.s.allow_sections)
        self.logger.info(f"사이트맵 시드: {len(lastmod_map)}개")

        queue: deque[str] = deque()
        seen: set[str] = set()

        # 최신순으로 큐 적재
        for u, _lm in sorted(lastmod_map.items(), key=lambda kv: kv[1] or "", reverse=True):
            if self.filter.is_allowed(u):
                queue.append(u)

        # 시작 URL 추가(옵션)
        if self.s.start_url and self.filter.is_allowed(self.s.start_url):
            queue.append(self.s.start_url)

        # === NEW: 저장된 상태가 있으면 복구하여 덮어쓰기 ===
        q_loaded, inflight_loaded, used_loaded, enq_loaded = state.load()
        if q_loaded or inflight_loaded:
            self.logger.info(f"[STATE] 저장된 큐 불러옴: {len(q_loaded)}개, inflight={bool(inflight_loaded)}, used={used_loaded}")
            queue = q_loaded
            if inflight_loaded:
                queue.appendleft(inflight_loaded)  # 처리 중이던 URL 맨 앞으로 복구
            inflight = None
            requests_used = requests_used  # ← 실행당 리셋 유지(원하면 used_loaded로)
            enqueued_keys = enq_loaded     # ← 키셋 복구
            state.save(queue, inflight, requests_used, enqueued_keys) # 깨끗한 상태로 정리 저장
        else:
            self.logger.info("[STATE] 저장된 상태 없음. 시드 큐로 시작.")
            # 시드로 채운 queue를 키셋에 등록
            base = self.s.start_url or f"https://{self.s.domain}/"
            for u in list(queue):
                enqueued_keys.add(_key(normalize_url(u, base)))
            state.save(queue, None, requests_used, enqueued_keys)

        pages_count = 0
        base = self.s.start_url or f"https://{self.s.domain}/"

        while queue and pages_count < self.s.max_pages:
            # === NEW: 안전 종료 플래그 확인 ===
            if stop_flag["v"]:
                self.logger.info("[STATE] 중단 신호 수신에 따라 종료 준비…")
                state.save(queue, None, requests_used, enqueued_keys)
                break

            raw = queue.popleft()
            url = normalize_url(raw, base)
            if url in seen:
                continue
            seen.add(url)

            # === NEW: inflight 기록 (크래시 대비), 주기적 스냅샷 ===
            inflight = url
            state.save(queue, inflight, requests_used, enqueued_keys)

            # === NEW: 이미 스냅샷 존재 시(멱등성) → 스킵 ===
            if is_already_crawled(FIXTURES_DIR, url):
                inflight = None
                ops_since_save += 1
                if ops_since_save >= OPS_PER_SNAPSHOT:
                    state.save(queue, inflight, requests_used, enqueued_keys)
                    ops_since_save = 0
                continue

            # 0) URL 단계에서 1차 차단
            if self.s.block_login_pages and is_login_like_url(url):
                self.logger.info(f"[LOGIN-URL] 차단: {url}")
                inflight = None
                ops_since_save += 1
                if ops_since_save >= OPS_PER_SNAPSHOT:
                    state.save(queue, inflight, requests_used, enqueued_keys)
                    ops_since_save = 0
                continue

            if not self.filter.is_allowed(url):
                inflight = None
                ops_since_save += 1
                if ops_since_save >= OPS_PER_SNAPSHOT:
                    state.save(queue, inflight, requests_used, enqueued_keys)
                    ops_since_save = 0
                continue

            html = fetch_html(url, self.headers, self.s.request_timeout_sec, self.s.request_sleep_sec, FIXTURES_DIR, self.robots.delay())
            
            # === NEW: 요청 카운트 증가 & 한도 체크 ===
            requests_used += 1
            requests_used_run +=1
            if requests_used_run >= REQUEST_LIMIT:
                self.logger.info(f"[STATE] 요청 한도 {REQUEST_LIMIT} 도달: 안전 종료")
                # 현재 inflight 처리는 이미 반영되었으므로 inflight 해제 후 저장
                inflight = None
                state.save(queue, inflight, requests_used, enqueued_keys)
                break

            if not html:
                # (기존 로직대로) 실패 시 재시도하고 싶으면 큐 뒤로 다시 넣기
                # queue.append(url)  # ← 필요시 주석 해제
                inflight = None
                ops_since_save += 1
                if ops_since_save >= OPS_PER_SNAPSHOT:
                    state.save(queue, inflight, requests_used, enqueued_keys)
                    ops_since_save = 0
                continue

            # 1) HTML 단계에서 2차 차단
            if self.s.block_login_pages and is_login_page_html(html):
                self.logger.info(f"[LOGIN-HTML] 로그인 페이지 감지, 스냅샷/첨부 건너뜀: {url}")
                inflight = None
                ops_since_save += 1
                if ops_since_save >= OPS_PER_SNAPSHOT:
                    state.save(queue, inflight, requests_used, enqueued_keys)
                    ops_since_save = 0
                continue

            # 1) <title> + 본문 컨테이너만 추출
            title, article_html, text_len = extract_title_and_main_html(html)

            # ✅ 이메일 레드액트 추가 (저장/임베딩 전에 가장 안전한 지점)
            if self.s.redact_email:
                article_html = redact_email_html(article_html, "[이메일 문의: 원문 참조]", page_url=url)

            # 2) 저장 경로(캐시 경로) 계산
            snap_path = html_cache_path(FIXTURES_DIR, url)   # Path 반환
            snap_path = Path(snap_path) if not isinstance(snap_path, Path) else snap_path

            # 3) 미니멀 스냅샷 HTML 생성 & 덮어쓰기 저장
            minimal_html = build_minimal_snapshot_html(
                base_url=url,
                title=title,
                article_html=article_html,
                fetched_at=datetime.now().isoformat(timespec="seconds"),
            )
            snap_path.parent.mkdir(parents=True, exist_ok=True)
            snap_path.write_text(minimal_html, encoding="utf-8")

            # 4) 링크/첨부는 정확도를 위해 '원본 html'에서 추출 유지
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")

            attachments, followables = [], []
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                if href.lower().startswith("mailto:"):   # ✅ 선택: mailto 큐 제외
                    continue
                abs_url = normalize_url(href, url)
                link_text = (a.get_text() or "").strip()
                cls = " ".join(a.get("class", []))
                
                if is_download_intent(href, abs_url, link_text, cls):
                    row = {
                        "page_url": str(snap_path),
                        "file_text": link_text,
                        "href_abs": abs_url,
                        "detected_at": datetime.now().isoformat(timespec="seconds"),
                    }
                    
                    if self._allow_download(abs_url):
                        try:
                            # referer 붙이면 403 방지에 도움
                            headers = {**self.headers, "Referer": url}
                            fname, content, ctype = fetch_binary(
                                abs_url, headers, self.s.request_timeout_sec,
                                self.s.request_sleep_sec, self.robots.delay()
                            )
                            # 파일명 충돌 방지: URL 해시 접두어
                            h = hashlib.sha1(abs_url.encode("utf-8")).hexdigest()[:10]
                            safe_name = fix_filename(fname)
                            out_path = ATTACH_DIR / f"{h}_{safe_name}"
                            out_path.write_bytes(content)

                            row["saved_path"] = str(out_path)
                            row["size_bytes"] = len(content)
                            row["sha1"] = hashlib.sha1(content).hexdigest()
                            row["content_type"] = ctype
                        except Exception:
                            # 실패해도 메타데이터는 남김
                            row["saved_path"] = ""
                    attachments.append(row)
                    continue
                if self.filter.is_allowed(abs_url):
                    followables.append(abs_url)

            # 5) 저장(리포트/CSV는 선택 스냅샷 경로를 가리키게)
            self.storage.save_attachments(attachments, policy=self.s.attachment_policy)

            section = ""
            try:
                p = urlparse(url).path.strip("/").split("/")
                section = "/".join(p[:2]) if len(p) >= 2 else (p[0] if p else "")
            except Exception:
                pass

            self.storage.save_page(
                url=url,
                saved_path=str(snap_path),   # ← 전체 HTML 대신 '선택 스냅샷' 파일 경로
                title=title,
                lastmod=lastmod_map.get(url),
                fetched_at=datetime.now().isoformat(timespec="seconds"),
                section=section,
                out_links=len(followables),
                text_length=text_len,
                html=html,   # Mongo의 해시/비교용. 원하면 minimal_html로 바꿔도 됨
            )
            pages_count += 1

            # === NEW: 큐 확장 (중복 차단 + 정규화 + 스냅샷 존재 검사)
            for nxt in followables:
                nn = normalize_url(nxt, url)  # base로 url 사용 (문맥상 현재 페이지 기준)
                if not self.filter.is_allowed(nn):
                    continue
                # 이미 방문했거나(seen), 이미 큐에 올린 적 있거나(enqueued_keys), 이미 스냅샷이 있으면 패스
                k = _key(nn)
                if (nn in seen) or (k in enqueued_keys) or is_already_crawled(FIXTURES_DIR, nn):
                    continue
                queue.append(nn)
                enqueued_keys.add(k)

            # === NEW: inflight 해제 & 주기적 상태 저장 ===
            inflight = None
            ops_since_save += 1
            if ops_since_save >= OPS_PER_SNAPSHOT:
                state.save(queue, inflight, requests_used, enqueued_keys)
                ops_since_save = 0

        make_report_html(DATA_DIR)
        self.logger.info(f"[완료] 수집 {pages_count}개 | report: data/report.html | HTML 캐시: fixtures/")

        # === NEW: 종료 직전 상태 저장 (안전)
        state.save(queue, None, requests_used, enqueued_keys)

        # === NEW: 실행 종료 시간/소요 시간 기록 & 저장 ===
        end_dt = datetime.now()
        elapsed_sec = (end_dt - start_dt).total_seconds()
        ...

         # === NEW: 실행 종료 시간/소요 시간 기록 & 저장 ===
        end_dt = datetime.now()
        elapsed_sec = (end_dt - start_dt).total_seconds()

        self.logger.info(
            f"크롤링 종료: {end_dt.isoformat(timespec='seconds')} "
            f"(총 {elapsed_sec:.1f}s)"
        )

        # data/run_meta.json 으로도 저장
        meta = {
            "started_at": start_dt.isoformat(timespec="seconds"),
            "ended_at": end_dt.isoformat(timespec="seconds"),
            "elapsed_seconds": elapsed_sec,
            "pages_count": pages_count,
        }
        meta_path = Path(DATA_DIR) / "run_meta.json"
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    # 클래스 내부 메서드로 다운로드 허용 규칙 정의
    def _allow_download(self, abs_url: str) -> bool:
        from urllib.parse import urlparse
        p = urlparse(abs_url).path

        if self.s.attachment_policy == "allowlist":
            # 허용 리스트 모드
            if any(p.startswith(bp) for bp in self.s.attachment_block_prefixes):
                return False
            return any(p.startswith(ap) for ap in self.s.attachment_allow_prefixes)

        elif self.s.attachment_policy == "blocklist":
            # 블락 리스트 모드
            if any(p.startswith(bp) for bp in self.s.attachment_block_prefixes):
                return False
            return True  # 그 외에는 모두 다운로드

        else:
            # metadata_only 모드
            return False