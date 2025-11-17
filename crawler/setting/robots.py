from __future__ import annotations
import urllib.robotparser as robotparser

class Robots:
    def __init__(self, domain: str, user_agent: str):
        self.user_agent = user_agent
        self.url = f"https://{domain}/robots.txt"
        self.rp = robotparser.RobotFileParser()
        try:
            self.rp.set_url(self.url)
            self.rp.read()
        except Exception:
            pass

    def allowed(self, url: str) -> bool:
        try:
            if self.rp.default_entry is None:
                return True
            return self.rp.can_fetch(self.user_agent, url)
        except Exception:
            return True

    def delay(self) -> float:
        try:
            return self.rp.crawl_delay(self.user_agent) or self.rp.crawl_delay("*") or 0.0
        except Exception:
            return 0.0