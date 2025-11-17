from __future__ import annotations
from pathlib import Path
import logging

def setup_logging(log_path: str) -> logging.Logger:
    # 로그 파일 폴더가 없으면 생성
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        filename=log_path,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    logger = logging.getLogger("kitbot-crawler")
    # 콘솔 출력도 추가
    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        logger.addHandler(logging.StreamHandler())
    return logger
