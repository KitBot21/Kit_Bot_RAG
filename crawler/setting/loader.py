from __future__ import annotations
from dataclasses import dataclass, field
from infra.config import load_config

@dataclass
class Loader:
    user_agent: str = "KITCrawler/1.0"
    request_timeout_sec: int = 10
    request_sleep_sec: float = 0.7
    max_pages: int = 300000
    start_url: str | None = None
    domain: str = "www.kumoh.ac.kr"
    sitemap_index: str | None = None
    allow_sections: list[str] | None = None
    allowed_path_prefixes: list[str] = field(default_factory=lambda: ["/"])
    block_login_pages: bool = True
    attachment_policy: str = "blocklist"  # metadata_only | allowlist | blocklist
    attachment_allow_prefixes: list[str] = field(default_factory=list)
    attachment_block_prefixes: list[str] = field(default_factory=list)
    storage: str = "filesystem"  # filesystem | mongodb
    mongodb_uri: str | None = None
    mongodb_db: str = "kitbot"
    log_path: str = "../data/errors.log"
    redact_email: bool = True
    deny_patterns: list[str] = field(default_factory=list)

    @classmethod
    def from_yaml(cls, cfg_path: str | None = None) -> "Loader":
        cfg = load_config(cfg_path) if cfg_path else load_config()
        pii_cfg = cfg.get("pii_policy") or {}
        return cls(
            user_agent=cfg.get("user_agent", cls.user_agent),
            request_timeout_sec=int(cfg.get("request_timeout_sec", cls.request_timeout_sec)),
            request_sleep_sec=float(cfg.get("request_sleep_sec", cls.request_sleep_sec)),
            max_pages=int(cfg.get("max_pages", cls.max_pages)),
            start_url=cfg.get("start_url"),
            domain=cfg.get("domain", cls.domain),
            sitemap_index=cfg.get("sitemap_index"),
            allow_sections=cfg.get("allow_sections"),
            allowed_path_prefixes=cfg.get("allowed_path_prefixes", ["/"]),
            block_login_pages=cfg.get("block_login_pages", cls.block_login_pages),
            attachment_policy=cfg.get("attachment_policy", cls.attachment_policy),
            attachment_allow_prefixes=cfg.get("attachment_allow_prefixes", []),
            attachment_block_prefixes=cfg.get("attachment_block_prefixes", []),
            storage=cfg.get("storage", cls.storage),
            mongodb_uri=cfg.get("mongodb_uri"),
            mongodb_db=cfg.get("mongodb_db", cls.mongodb_db),
            log_path=cfg.get("log_path", cls.log_path),
            redact_email=bool(pii_cfg.get("redact_email", cls.redact_email)),
            deny_patterns=cfg.get("deny_patterns", []),
        )
