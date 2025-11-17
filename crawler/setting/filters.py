from __future__ import annotations
from urllib.parse import urlparse
from .robots import Robots
import re

class UrlFilter:
    def __init__(self, domain: str, allowed_prefixes: list[str], robots: Robots, deny_patterns: list[str]):
        self.domain = domain
        self.allowed_prefixes = allowed_prefixes
        self.robots = robots
        self._deny_regexes = [re.compile(p, re.IGNORECASE) for p in deny_patterns]

    def is_allowed(self, url: str) -> bool:
        u = urlparse(url)
        if u.netloc != self.domain:
            return False
        if self.allowed_prefixes and not any(u.path.startswith(p) for p in self.allowed_prefixes):
            return False
        for rx in self._deny_regexes:
            if rx.search(url):
                return False
        if not self.robots.allowed(url):
            return False
        return True
