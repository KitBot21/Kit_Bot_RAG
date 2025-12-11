from __future__ import annotations
from pathlib import Path
import yaml

# .../crawler/infra/config.py  기준
_INFRA_DIR   = Path(__file__).resolve().parent          # .../crawler/infra
_CRAWLER_DIR = _INFRA_DIR.parent                        # .../crawler
_PROJECT_DIR = _CRAWLER_DIR.parent                      # .../

# config.yml은 기존처럼 crawler/ 아래에 둠
CONFIG_PATH  = _CRAWLER_DIR / "config.yml"

# data/는 프로젝트 루트와 동등 위치에 생성 (crawler의 형제)
DATA_DIR     = _PROJECT_DIR / "data"
FIXTURES_DIR = DATA_DIR / "fixtures"
ATTACH_DIR   = DATA_DIR / "files"

DATA_DIR.mkdir(exist_ok=True)
FIXTURES_DIR.mkdir(exist_ok=True)
ATTACH_DIR.mkdir(exist_ok=True)

# infra/config.py
import yaml
from pathlib import Path

DEFAULT_CONFIG_PATH = Path(__file__).parent / "config.yml"

def load_config(cfg_path: str | Path | None = None):
    """YAML 설정 파일을 로드합니다."""
    path = Path(cfg_path) if cfg_path else DEFAULT_CONFIG_PATH
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
