# 🕷️ 크롤러 업데이트 가이드 - 최근 5년 데이터 수집

## 📋 현재 크롤러 분석

✅ **잘 구성되어 있습니다!**
- Sitemap 기반 크롤링
- 섹션별 필터링 (`ko`, `bus`, `dorm`)
- 로그인 페이지 차단
- 첨부파일 정책 관리
- 중단/재개 기능

## 🎯 최근 5년 데이터만 수집하도록 개선

### 방법 1: Sitemap lastmod 필터링 (권장) ⭐

`crawler/core/sitemap.py` 수정:

```python
from datetime import datetime, timedelta

# 5년 전 날짜 계산
CUTOFF_DATE = (datetime.now() - timedelta(days=5*365)).strftime("%Y-%m-%d")

def seed_from_sitemaps(sitemap_index, headers, timeout, allow_sections=None):
    """Sitemap에서 최근 5년 URL만 수집"""
    lastmod_map = {}
    
    for url, lastmod in _extract_urls_from_sitemap(sitemap_index, headers, timeout):
        # lastmod 필터링
        if lastmod and lastmod < CUTOFF_DATE:
            continue  # 5년 이전 페이지는 건너뛰기
        
        # 섹션 필터링
        if allow_sections:
            section = _extract_section(url)
            if section not in allow_sections:
                continue
        
        lastmod_map[url] = lastmod
    
    return lastmod_map
```

### 방법 2: 설정 파일에 날짜 필터 추가

`crawler/config.yml`:

```yaml
start_url: "https://www.kumoh.ac.kr/ko/index.do?sso=ok"
domain: "www.kumoh.ac.kr"
sitemap_index: "https://www.kumoh.ac.kr/sitemap_index.xml"

allow_sections: ["ko","bus","dorm"]
allowed_path_prefixes: ["/ko/", "/bus/notice.do","/dorm/"]

# === 새로 추가 ===
# 최근 5년 데이터만 크롤링
date_filter:
  enabled: true
  cutoff_date: "2020-01-01"  # YYYY-MM-DD 형식
  # 또는 상대 날짜
  # cutoff_days_ago: 1825  # 5년 = 365 * 5

block_login_pages: true
attachment_policy: "blocklist"
attachment_allow_prefixes: []
attachment_block_prefixes: ["/cms/fileDownload.do"]

max_pages: 300000
request_timeout_sec: 10
request_sleep_sec: 0.7
user_agent: "KITBot (CSEcapstone, contact: cdh5113@naver.com)"

storage: "filesystem"
log_path: "../data/errors.log"

pii_policy:
  redact_email: true

deny_patterns:
  - "/login"
  - "/restaurant_menu_reg"
  - "/restaurant_reg"
```

### 방법 3: 빠른 스크립트 (기존 크롤러 수정 없이)

`crawler/crawl_recent.sh`:

```bash
#!/bin/bash
# 최근 5년 데이터만 크롤링하는 래퍼 스크립트

cd "$(dirname "$0")"

echo "🕷️  최근 5년 데이터 크롤링 시작..."
echo ""

# 1. 전체 크롤링 실행
python3 main.py config.yml

# 2. 5년 이전 파일 제거
echo ""
echo "📅 5년 이전 데이터 제거 중..."

CUTOFF_DATE="2020-01-01"
FIXTURES_DIR="../data/fixtures"

# 5년 이전 파일 찾기
OLD_FILES=$(find "$FIXTURES_DIR" -type f -not -newermt "$CUTOFF_DATE")
OLD_COUNT=$(echo "$OLD_FILES" | grep -c .)

if [ "$OLD_COUNT" -gt 0 ]; then
    echo "   발견된 오래된 파일: $OLD_COUNT 개"
    echo "   제거 중..."
    find "$FIXTURES_DIR" -type f -not -newermt "$CUTOFF_DATE" -delete
    echo "   ✅ 제거 완료"
else
    echo "   ℹ️  제거할 파일 없음"
fi

echo ""
echo "✅ 크롤링 완료!"
echo ""
echo "📊 통계:"
find "$FIXTURES_DIR" -type f | wc -l | xargs echo "   파일 수:"
du -sh "$FIXTURES_DIR" | awk '{print "   총 크기: " $1}'
```

---

## 🚀 사용 방법

### 옵션 A: 기존 fixtures 정리 후 재크롤링

```bash
cd ~/Kit_Bot_RAG/crawler

# 1. 기존 데이터 백업
mv ../data/fixtures ../data/fixtures_backup

# 2. 새 디렉토리 생성
mkdir -p ../data/fixtures

# 3. 크롤러 실행
python3 main.py config.yml

# 4. 결과 확인
ls -lh ../data/fixtures/ | head -20
find ../data/fixtures/ -type f | wc -l
```

### 옵션 B: 스마트 재크롤링 (수정된 페이지만)

```bash
cd ~/Kit_Bot_RAG/crawler

# 크롤러는 sitemap의 lastmod를 확인하고
# 변경된 페이지만 다시 다운로드
python3 main.py config.yml
```

### 옵션 C: 특정 섹션만 재크롤링

```bash
# config.yml 임시 수정
# allow_sections: ["dorm"]  # 기숙사만

python3 main.py config.yml

# 완료 후 원래대로
# allow_sections: ["ko","bus","dorm"]
```

---

## 📝 크롤러 개선 코드

새 파일 생성: `crawler/filters/date_filter.py`

```python
"""날짜 기반 URL 필터링"""
from datetime import datetime, timedelta
from typing import Optional

class DateFilter:
    def __init__(self, cutoff_date: Optional[str] = None, cutoff_days_ago: Optional[int] = None):
        """
        Args:
            cutoff_date: "YYYY-MM-DD" 형식 (예: "2020-01-01")
            cutoff_days_ago: 현재부터 며칠 전까지 (예: 1825 = 5년)
        """
        if cutoff_date:
            self.cutoff = datetime.strptime(cutoff_date, "%Y-%m-%d")
        elif cutoff_days_ago:
            self.cutoff = datetime.now() - timedelta(days=cutoff_days_ago)
        else:
            # 기본값: 5년
            self.cutoff = datetime.now() - timedelta(days=5*365)
    
    def is_recent(self, lastmod: Optional[str]) -> bool:
        """
        lastmod이 cutoff보다 최근인지 확인
        
        Args:
            lastmod: "YYYY-MM-DD" 또는 "YYYY-MM-DDTHH:MM:SS" 형식
        
        Returns:
            True if recent, False if old
        """
        if not lastmod:
            # lastmod 정보 없으면 허용 (최신으로 간주)
            return True
        
        try:
            # 날짜 파싱 (여러 형식 지원)
            if 'T' in lastmod:
                date = datetime.fromisoformat(lastmod.replace('Z', '+00:00'))
            else:
                date = datetime.strptime(lastmod[:10], "%Y-%m-%d")
            
            return date >= self.cutoff
        except Exception:
            # 파싱 실패 시 허용
            return True
```

`crawler/core/sitemap.py` 수정:

```python
# 파일 상단에 추가
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from filters.date_filter import DateFilter

def seed_from_sitemaps(sitemap_index, headers, timeout, allow_sections=None, date_filter=None):
    """
    Args:
        sitemap_index: sitemap index URL
        headers: HTTP headers
        timeout: request timeout
        allow_sections: 허용 섹션 리스트
        date_filter: DateFilter 인스턴스 (옵션)
    """
    lastmod_map = {}
    
    # Sitemap 파싱 (기존 로직)
    # ...
    
    for url, lastmod in all_urls:
        # 날짜 필터링
        if date_filter and not date_filter.is_recent(lastmod):
            continue
        
        # 섹션 필터링 (기존 로직)
        # ...
        
        lastmod_map[url] = lastmod
    
    return lastmod_map
```

`crawler/core/crawl.py` 수정:

```python
# __init__ 메서드에 추가
from filters.date_filter import DateFilter

class Crawler:
    def __init__(self, settings: Loader):
        # ... 기존 코드 ...
        
        # 날짜 필터 설정
        self.date_filter = None
        if hasattr(settings, 'date_filter') and settings.date_filter.get('enabled'):
            cutoff_date = settings.date_filter.get('cutoff_date')
            cutoff_days = settings.date_filter.get('cutoff_days_ago')
            self.date_filter = DateFilter(cutoff_date, cutoff_days)
            self.logger.info(f"날짜 필터 활성화: {self.date_filter.cutoff.strftime('%Y-%m-%d')} 이후")
    
    def _seed_queue(self) -> deque[str]:
        lastmod_map = {}
        if self.s.sitemap_index:
            lastmod_map = seed_from_sitemaps(
                self.s.sitemap_index, 
                self.headers, 
                self.s.request_timeout_sec, 
                self.s.allow_sections,
                self.date_filter  # ← 추가
            )
        # ... 나머지 코드 ...
```

---

## ⚡ 빠른 시작

### 1. 가장 간단한 방법 (추천)

```bash
cd ~/Kit_Bot_RAG/crawler

# 기존 데이터 삭제
rm -rf ../data/fixtures/*

# 재크롤링
python3 main.py config.yml

# 완료 후 corpus 재생성
cd ..
python3 create_filtered_corpus.py
```

### 2. 코드 수정 후 실행

```bash
cd ~/Kit_Bot_RAG/crawler

# 1. 날짜 필터 추가
mkdir -p filters
# (위의 date_filter.py 코드를 filters/date_filter.py에 저장)

# 2. config.yml에 date_filter 설정 추가

# 3. 실행
python3 main.py config.yml
```

---

## 📊 예상 결과

### Before (전체 크롤링)
```
크롤링 완료: 2,847 페이지
용량: 185 MB
처리 시간: 2-3시간
```

### After (최근 5년)
```
크롤링 완료: 800-1,200 페이지
용량: 50-80 MB
처리 시간: 30-60분
```

---

## ✅ 체크리스트

- [ ] 기존 fixtures 백업 완료
- [ ] 크롤러 설정 확인 (config.yml)
- [ ] 날짜 필터 설정 (옵션)
- [ ] 크롤링 실행
- [ ] 결과 확인 (파일 수, 용량)
- [ ] corpus 재생성
- [ ] 임베딩 재생성
- [ ] RAG 테스트

---

**어떤 방법으로 진행하시겠습니까?**

1. **간단하게**: 기존 fixtures 삭제 후 재크롤링 (코드 수정 없음)
2. **스마트하게**: 날짜 필터 코드 추가 후 재크롤링
3. **단계적으로**: 일부 섹션만 먼저 테스트

추천: **1번 (간단하게)** - 가장 빠르고 확실합니다!
