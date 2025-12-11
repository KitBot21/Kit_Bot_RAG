"""
날짜 기반 필터링
2021년 이후 데이터만 크롤링
"""
from datetime import datetime, timedelta
from typing import Optional

class DateFilter:
    def __init__(self, cutoff_date: Optional[str] = None, cutoff_days_ago: Optional[int] = None):
        """
        Args:
            cutoff_date: "YYYY-MM-DD" 형식 (예: "2021-01-01")
            cutoff_days_ago: 현재부터 며칠 전까지 (예: 1460 = 4년)
        """
        if cutoff_date:
            self.cutoff = datetime.strptime(cutoff_date, "%Y-%m-%d")
        elif cutoff_days_ago:
            self.cutoff = datetime.now() - timedelta(days=cutoff_days_ago)
        else:
            # 기본값: 2021-01-01
            self.cutoff = datetime(2021, 1, 1)
    
    def is_recent(self, lastmod: Optional[str]) -> bool:
        """
        lastmod이 cutoff보다 최근인지 확인
        
        Args:
            lastmod: "YYYY-MM-DD" 또는 "YYYY-MM-DDTHH:MM:SS" 형식
        
        Returns:
            True if recent (허용), False if old (스킵)
        """
        if not lastmod:
            # lastmod 정보 없으면 허용 (최신으로 간주)
            return True
        
        try:
            # 날짜 파싱 (여러 형식 지원)
            if 'T' in lastmod:
                # ISO 8601 형식
                date = datetime.fromisoformat(lastmod.replace('Z', '+00:00'))
            else:
                # YYYY-MM-DD 형식
                date = datetime.strptime(lastmod[:10], "%Y-%m-%d")
            
            return date >= self.cutoff
            
        except Exception:
            # 파싱 실패 시 허용 (안전하게)
            return True
    
    def get_cutoff_str(self) -> str:
        """필터 날짜를 문자열로 반환"""
        return self.cutoff.strftime("%Y-%m-%d")